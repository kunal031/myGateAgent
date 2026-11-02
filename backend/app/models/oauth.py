"""Pending OAuth sign-ins, stored in the database rather than in memory.

The PKCE verifier has to survive between two separate HTTP requests: the
one that redirects to Google, and the callback Google sends the browser
back to. In a single long-lived process a dict was enough.

On Lambda it is not. Every concurrent invocation gets its own process, so
a sign-in that starts on one instance and returns on another finds no
state and fails -- intermittently, which is the worst kind, because it
works perfectly whenever you test it by hand.

The row is deleted on use, so this is single-use by construction: a
replayed callback finds nothing and an intercepted authorisation code
cannot be redeemed twice.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, Integer, String

from ..core.database import Base


class PendingOAuth(Base):
    __tablename__ = "pending_oauth"

    id = Column(Integer, primary_key=True, index=True)

    #: The state parameter, which is also the lookup key. Unique so two
    #: sign-ins can never collide on one row.
    state = Column(String(64), nullable=False, unique=True, index=True)

    #: The PKCE secret. Never leaves the server: it is sent only to
    #: Google's token endpoint, never through the browser.
    verifier = Column(String(128), nullable=False)

    #: Where the user was headed before being asked to sign in. Already
    #: reduced to a same-origin path before it is stored.
    next_url = Column(String(512), default="")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False,
                        index=True)

    __table_args__ = (
        # Expiry sweeps scan by age.
        Index("ix_pending_oauth_created", "created_at"),
    )
