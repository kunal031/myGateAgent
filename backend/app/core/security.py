"""Password hashing and token issuing.

Two token types. An access token is short-lived and carries everything a
request needs, so authorising a request is signature verification and no
database round trip. A refresh token lives much longer, is checked against
the user's `token_version`, and is the only way to get a new access token.

That split is what makes "sign out everywhere" cheap: bumping
`token_version` invalidates every refresh token for an account without
maintaining a blacklist, and existing access tokens expire on their own
within the access window.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings

ALGORITHM = "HS256"

#: Short enough that a stolen access token is of limited use, long enough
#: that a phone on a train is not re-authenticating constantly.
ACCESS_TOKEN_MINUTES = 30

#: A mobile client should not ask for a password every week.
REFRESH_TOKEN_DAYS = 30

#: bcrypt silently truncates at 72 bytes, so a longer password would make
#: every suffix equivalent. Rejecting is honest; truncating is not.
MAX_PASSWORD_BYTES = 72

#: Short enough to type on a phone, long enough to be worth hashing.
MIN_PASSWORD_CHARS = 8


class AuthError(RuntimeError):
    """A token is missing, malformed, expired or no longer valid."""


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes"
        )
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against its hash.

    Returns False rather than raising on a malformed hash: a corrupted row
    should fail the login, not return a 500 that tells an attacker the
    account exists.
    """
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:MAX_PASSWORD_BYTES],
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def _encode(payload: dict, *, expires: timedelta, kind: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            **payload,
            "iat": now,
            "exp": now + expires,
            # Checked on decode, so a refresh token cannot be presented as
            # an access token to skip the token_version check.
            "typ": kind,
        },
        settings.JWT_SECRET,
        algorithm=ALGORITHM,
    )


def create_access_token(user_id: int, role: str) -> str:
    """Carries the role, so authorisation needs no database read."""
    return _encode(
        {"sub": str(user_id), "role": role},
        expires=timedelta(minutes=ACCESS_TOKEN_MINUTES),
        kind="access",
    )


def create_refresh_token(user_id: int, token_version: int) -> str:
    return _encode(
        {"sub": str(user_id), "ver": token_version},
        expires=timedelta(days=REFRESH_TOKEN_DAYS),
        kind="refresh",
    )


def decode_token(token: str, *, expect: str) -> dict:
    """Decode and verify, or raise AuthError.

    `expect` is enforced: a refresh token presented where an access token
    belongs is rejected, which stops the long-lived credential from being
    used to skip the revocation check.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("That session has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("That token is not valid") from exc

    if payload.get("typ") != expect:
        raise AuthError(f"Expected a {expect} token")
    if not payload.get("sub"):
        raise AuthError("That token names no user")
    return payload
