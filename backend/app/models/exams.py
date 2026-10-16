"""Mock test sessions, mirroring how the real GATE exam is conducted.

A session fixes its question set at creation, so the paper does not change
underneath the candidate. Per-question state matches the official interface:
every question is Not Visited, Not Answered, Answered, Marked for Review, or
Answered and Marked for Review, and that palette is what the candidate
navigates by.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base
from .models import Question, Subject, Topic  # noqa: F401  (register FK targets)


class SessionKind:
    """What a session is for.

    A quiz drills a topic to build concepts and shows feedback as you go; a
    test evaluates performance under exam conditions and reveals nothing
    until submission. Both are the same record, so both get dated history,
    a palette and per-question timing without a parallel implementation.
    """

    QUIZ = "quiz"
    TEST = "test"


class ExamStatus:
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    ABANDONED = "abandoned"


class QuestionState:
    """The five states of the official GATE question palette."""

    NOT_VISITED = "not_visited"
    NOT_ANSWERED = "not_answered"          # seen, left blank
    ANSWERED = "answered"
    MARKED = "marked"                      # flagged, no answer
    ANSWERED_MARKED = "answered_marked"    # flagged, answered


class ExamSession(Base):
    """One mock test attempt."""

    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String(200), default="Mock Test")
    kind = Column(String(10), default=SessionKind.TEST, index=True)
    pattern = Column(String(30), default="full")   # full, subject, custom, topic
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)

    total_questions = Column(Integer, default=65)
    total_marks = Column(Float, default=100.0)
    duration_minutes = Column(Integer, default=180)

    # Records any section the bank could not fill, so a short paper is
    # visible rather than silently scored against the full marks.
    shortfall_note = Column(Text, default="")

    status = Column(String(20), default=ExamStatus.IN_PROGRESS, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    # Seconds actually spent, which differs from wall-clock if the tab closed.
    time_spent_seconds = Column(Integer, default=0)

    # Filled on submission.
    score = Column(Float, default=0.0)
    max_score = Column(Float, default=0.0)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    unattempted_count = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)

    items = relationship(
        "ExamItem", back_populates="session",
        cascade="all, delete-orphan", order_by="ExamItem.position",
    )

    @property
    def is_open(self) -> bool:
        return self.status == ExamStatus.IN_PROGRESS


class ExamItem(Base):
    """One question within a session, with its palette state and answer."""

    __tablename__ = "exam_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"),
                        nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)

    position = Column(Integer, default=0)          # 1-based, as numbered in the paper
    state = Column(String(24), default=QuestionState.NOT_VISITED, index=True)

    user_answer = Column(Text, default="")
    time_spent_seconds = Column(Integer, default=0)
    visit_count = Column(Integer, default=0)

    # Scored on submission, not while answering.
    is_correct = Column(Boolean, nullable=True)
    marks_obtained = Column(Float, default=0.0)

    session = relationship("ExamSession", back_populates="items")
    question = relationship("Question")

    __table_args__ = (
        Index("ix_exam_item_session_position", "session_id", "position", unique=True),
    )

    @property
    def is_answered(self) -> bool:
        return self.state in {QuestionState.ANSWERED, QuestionState.ANSWERED_MARKED}

    @property
    def is_marked(self) -> bool:
        return self.state in {QuestionState.MARKED, QuestionState.ANSWERED_MARKED}
