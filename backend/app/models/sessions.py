"""One row per refresh token, so rotation can detect a stolen one.

Rotation alone is bookkeeping: hand out a new refresh token on every
refresh and retire the old one. What makes it worth the table is what
happens when a *retired* token is presented. A well-behaved client never
does that -- it just replaced it -- so a replay means two parties hold
the same token, which means it leaked. The whole family is then revoked.

This does not prevent theft. An attacker who steals a token and uses it
before the real client does gets a working session; nothing in a bearer
scheme prevents that, because the token is the credential. What it
changes is the aftermath: theft stops being silent for the token's full
lifetime and becomes a detected event that ends every session on the
account, and a token is only useful until its owner next refreshes.

Only a hash is stored. A leaked database should not hand over working
refresh tokens, and the server never needs the original -- it only ever
asks "is the token I was just handed the one I issued".
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String,
)

from ..core.database import Base


class RefreshSession(Base):
    """A single device's login, and the token chain it has rotated through."""

    __tablename__ = "refresh_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )

    #: Shared by every token in one rotation chain, so detecting a reuse
    #: can revoke exactly this device rather than the whole account.
    family_id = Column(String(64), nullable=False, index=True)

    #: SHA-256 of the token. Unique so a replay cannot create a second row.
    token_hash = Column(String(64), nullable=False, unique=True, index=True)

    #: Set when this token is rotated away or revoked. A presented token
    #: whose row is already used is the signal that something went wrong.
    used_at = Column(DateTime, nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)

    #: Why it was revoked, for answering "was I actually compromised".
    revoked_reason = Column(String(40), nullable=True)

    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    #: Coarse, and deliberately so: enough to tell two devices apart in a
    #: session list, not enough to be a tracking log.
    user_agent = Column(String(200), nullable=True)

    __table_args__ = (
        # The two lookups this table exists for: find a presented token,
        # and revoke a family.
        Index("ix_refresh_family_live", "family_id", "revoked"),
        Index("ix_refresh_user_live", "user_id", "revoked"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<RefreshSession user={self.user_id} family={self.family_id[:8]} "
            f"used={self.used_at is not None} revoked={self.revoked}>"
        )
