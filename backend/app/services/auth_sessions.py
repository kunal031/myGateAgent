"""Issuing, rotating and revoking refresh tokens.

The flow, and why each step is there:

**issue** on sign-in starts a family and records the token's hash.

**rotate** is the only way to get a new access token. It retires the
presented token and issues a successor in the same family, so a token is
useful exactly once.

**reuse** -- a token presented after it was already rotated away -- is
the signal this exists for. A correct client never replays: it discarded
that token when it received the successor. Two parties holding the same
token means it leaked, so the whole family is revoked and that device has
to sign in again.

What this does not do is prevent theft. A bearer token is the credential;
whoever holds it is authenticated, and an attacker who uses a stolen
token before its owner next refreshes gets a working session. Rotation
bounds and reveals that rather than preventing it: the token dies at the
owner's next refresh, and the replay is detected. Preventing the theft
itself needs the token to be unreadable to scripts (an httpOnly cookie)
or bound to the device, neither of which a shared client can assume.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..core.security import (
    REFRESH_TOKEN_DAYS, create_access_token, create_refresh_token,
)
from ..models.sessions import RefreshSession
from ..models.users import User

logger = logging.getLogger(__name__)

#: How many rotations to keep after a token is retired. Enough to explain
#: a session list; not a permanent history.
PRUNE_KEEP_DAYS = 7


class ReuseDetected(RuntimeError):
    """A retired refresh token was presented: it leaked."""


def _hash(token: str) -> str:
    """SHA-256, not bcrypt.

    The token is 32 bytes of CSPRNG output carried in a signed JWT, so it
    has no guessable structure to attack -- there is nothing for a slow
    hash to protect against here, and refresh runs on a request path.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _truncate_agent(user_agent: str | None) -> str | None:
    return (user_agent or "")[:200] or None


def issue(
    db: Session, user: User, *, user_agent: str | None = None,
) -> dict:
    """Start a new session. Returns the token pair."""
    family_id = secrets.token_urlsafe(24)
    return _mint(db, user, family_id=family_id, user_agent=user_agent)


def _mint(
    db: Session, user: User, *, family_id: str, user_agent: str | None,
) -> dict:
    """Create one token in a family and record it."""
    # A nonce makes every refresh token distinct even when issued to the
    # same user in the same second. Without it two tokens could hash
    # identically and collide on the unique index.
    nonce = secrets.token_urlsafe(16)
    refresh_token = create_refresh_token(
        user.id, user.token_version, nonce=nonce,
    )
    db.add(RefreshSession(
        user_id=user.id,
        family_id=family_id,
        token_hash=_hash(refresh_token),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
        user_agent=_truncate_agent(user_agent),
    ))
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def revoke_family(db: Session, family_id: str, *, reason: str) -> int:
    """Kill every token in one chain. Returns how many rows changed."""
    changed = (
        db.query(RefreshSession)
        .filter(RefreshSession.family_id == family_id,
                RefreshSession.revoked.is_(False))
        .update({"revoked": True, "revoked_reason": reason},
                synchronize_session=False)
    )
    db.commit()
    return changed


def revoke_all(db: Session, user_id: int, *, reason: str) -> int:
    """Sign one account out of everything."""
    changed = (
        db.query(RefreshSession)
        .filter(RefreshSession.user_id == user_id,
                RefreshSession.revoked.is_(False))
        .update({"revoked": True, "revoked_reason": reason},
                synchronize_session=False)
    )
    db.commit()
    return changed


def rotate(
    db: Session, user: User, presented: str, *,
    user_agent: str | None = None,
) -> dict:
    """Retire the presented token and issue its successor.

    Raises ReuseDetected when the token was already rotated away or its
    family revoked. The caller turns that into a 401 -- and because the
    family is dead, every device in it must sign in again.
    """
    row = (
        db.query(RefreshSession)
        .filter(RefreshSession.token_hash == _hash(presented))
        .first()
    )

    if row is None:
        # No record. Either it predates this table (an existing session
        # from before rotation shipped) or it is forged. The signature
        # and token_version were already checked by the caller, so a
        # forged one cannot reach here; treat it as a legacy token and
        # adopt it into a new family rather than signing the user out on
        # deploy day.
        logger.info("refresh: adopting a pre-rotation token for user %s", user.id)
        return issue(db, user, user_agent=user_agent)

    # Order matters here, and getting it wrong is silent.
    #
    # Rotation marks a retired token BOTH used_at and revoked, so testing
    # `revoked` first would catch every replay in that branch and never
    # reach the reuse logic -- the family would survive and the thief
    # would keep a working chain. used_at is therefore checked first: it
    # is the specific signal, and `revoked` is the general one.
    if row.used_at is not None:
        # A correct client discarded this token the moment it received the
        # successor, so a replay means two parties hold it.
        logger.warning(
            "refresh: REUSE of a retired token (user=%s family=%s); "
            "revoking the whole family",
            row.user_id, row.family_id,
        )
        revoke_family(db, row.family_id, reason="reuse_detected")
        raise ReuseDetected("That session was signed out")

    if row.revoked:
        # Revoked without ever being used: an explicit sign-out.
        raise ReuseDetected("That session was signed out")

    row.used_at = datetime.utcnow()
    row.revoked = True
    row.revoked_reason = "rotated"
    db.commit()

    return _mint(db, user, family_id=row.family_id, user_agent=user_agent)


def prune(db: Session, *, keep_days: int = PRUNE_KEEP_DAYS) -> int:
    """Delete rows that can no longer explain anything.

    Expired or retired past the keep window. Without this the table grows
    by one row per refresh forever -- roughly one per 30 minutes of use
    per device.
    """
    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    removed = (
        db.query(RefreshSession)
        .filter(
            (RefreshSession.expires_at < datetime.utcnow())
            | ((RefreshSession.used_at.isnot(None))
               & (RefreshSession.used_at < cutoff))
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return removed


def active_sessions(db: Session, user_id: int) -> list[dict]:
    """The devices currently able to refresh, for an account screen."""
    rows = (
        db.query(RefreshSession)
        .filter(RefreshSession.user_id == user_id,
                RefreshSession.revoked.is_(False),
                RefreshSession.expires_at > datetime.utcnow())
        .order_by(RefreshSession.created_at.desc())
        .all()
    )
    return [
        {
            "family_id": r.family_id,
            "created_at": r.created_at.isoformat(),
            "expires_at": r.expires_at.isoformat(),
            "user_agent": r.user_agent,
        }
        for r in rows
    ]
