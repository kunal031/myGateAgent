"""Accounts, and the ownership that makes the app multi-user.

Every table holding study state -- attempts, card views, concept progress,
exam sessions, assistant threads -- gained a `user_id` alongside this
model. Before that the application had one implicit user, and two people
sharing it would have shared one study history: one person's wrong answer
would raise another's escalation level, and a quiz submitted by one would
appear in the other's analytics.

Content is deliberately *not* owned. Subjects, topics, concepts, source
chunks and generated cards are the syllabus and the corpus; they cost real
quota to produce and are identical for every student. Only the cards a
student writes by hand carry an owner, which is why `feed_cards.user_id` is
nullable: null means "everyone's", set means "mine".

An account can hold either a password, a Google identity, or both. The two
are linked by verified email: signing in with Google using the address of
an existing password account adopts that account rather than creating a
second one, because otherwise the same person would end up with two
separate study histories and no way to merge them.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class UserRole:
    """What an account may do.

    Two roles, because the distinction that matters here is between
    studying and changing the corpus. A student reads the syllabus and
    writes their own progress; an admin can ingest sources, generate
    content and import question papers, all of which spend API quota and
    affect every user.
    """

    STUDENT = "student"
    ADMIN = "admin"

    ALL = (STUDENT, ADMIN)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    #: Lowercased on write, so Kunal@x.com and kunal@x.com are one account.
    email = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(120), default="")

    #: bcrypt hash, or null for an account that only signs in with Google.
    #: Nullable rather than storing a dummy hash: an unusable placeholder
    #: is indistinguishable from a real hash at the database level, and the
    #: login path would then have to guess whether a password was ever set.
    #: Null says it plainly, and `has_password` is the only check needed.
    password_hash = Column(String(255), nullable=True)

    #: Google's subject identifier -- the stable account key.
    #:
    #: Not the email. Google's own documentation is explicit that a Google
    #: account's email can change while `sub` never does, so keying on
    #: email means a user who changes their address either loses their
    #: history or, if that address is later reassigned, inherits someone
    #: else's. Unique so two rows can never claim one Google account.
    google_sub = Column(String(255), nullable=True, unique=True, index=True)

    #: Profile picture URL from Google. Cosmetic, and refreshed on each
    #: sign-in because Google's URLs expire.
    avatar_url = Column(String(512), nullable=True)

    role = Column(String(20), default=UserRole.STUDENT, nullable=False, index=True)

    #: A disabled account keeps its data and stops being able to sign in,
    #: which is what you want for a shared key you are rotating away from.
    is_active = Column(Boolean, default=True, nullable=False)

    #: Refresh tokens are validated against this. Bumping it signs the
    #: account out everywhere without a token blacklist to maintain --
    #: cheap, and it survives a restart because it is in the database.
    token_version = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    attempts = relationship("Attempt", back_populates="user")

    __table_args__ = (
        Index("ix_user_active_role", "is_active", "role"),
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def has_password(self) -> bool:
        """Whether this account can sign in with a password at all.

        A Google-only account has none. The login endpoint needs this to
        refuse without implying the password was merely wrong, and the
        account screen needs it to offer "set a password" rather than
        "change password".
        """
        return bool(self.password_hash)
