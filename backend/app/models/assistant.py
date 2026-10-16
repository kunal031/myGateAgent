"""Assistant conversations.

A thread persists so a conversation continues across page loads, and so an
explanation started from a card keeps that card as context.
"""

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base
from .models import FeedCard, Subject  # noqa: F401  (register FK targets)


class Language:
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"


LANGUAGE_NAMES = {
    Language.ENGLISH: "English",
    Language.HINDI: "Hindi (हिंदी), using Devanagari script",
    Language.HINGLISH: "Hinglish — Hindi phrasing in Latin script, the way "
                       "Indian students actually explain things to each other",
}


class AssistantThread(Base):
    __tablename__ = "assistant_threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String(200), default="New conversation")
    language = Column(String(12), default=Language.ENGLISH)

    # What the conversation is about, when it started from a card or a
    # scope rather than a free-form question.
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    card_id = Column(Integer, ForeignKey("feed_cards.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "AssistantMessage", back_populates="thread",
        cascade="all, delete-orphan", order_by="AssistantMessage.id",
    )


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("assistant_threads.id"),
                       nullable=False, index=True)

    role = Column(String(12), default="user")     # user | assistant
    content = Column(Text, nullable=False)

    # Citations for an assistant turn, so an answer stays auditable.
    citations = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow)

    thread = relationship("AssistantThread", back_populates="messages")

    __table_args__ = (Index("ix_message_thread_id", "thread_id", "id"),)
