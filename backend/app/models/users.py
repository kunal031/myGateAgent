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

    #: bcrypt hash. The plaintext never leaves the request that set it.
    password_hash = Column(String(255), nullable=False)

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
