"""Concepts: the atomic, ordered unit of study beneath a Topic.

A topic such as "Process Synchronization (Semaphores, Peterson's, Mutex)" is
a dozen separate ideas that must be learned in order -- critical section
before Peterson's, Peterson's before semaphores. Cards therefore hang off a
Concept, not a Topic, so BASIC mode can walk a chapter in a sensible
sequence instead of showing whatever ranks highest.
"""

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base
from .models import Subject, Topic  # noqa: F401  (register FK targets)


class StudyMode:
    """Which pass through a chapter a card belongs to."""

    BASIC = "BASIC"          # definitions, prerequisites, "what is this"
    ADVANCED = "ADVANCED"    # what GATE actually tests: traps, edge cases
    REVISION = "REVISION"    # rapid recall of what was already seen


class ConceptStatus:
    NOT_STARTED = "not_started"
    LEARNING = "learning"
    LEARNED = "learned"
    REVISED = "revised"
    MASTERED = "mastered"


class Concept(Base):
    """One teachable idea, ordered within its topic."""

    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    slug = Column(String(200), index=True, nullable=False)
    summary = Column(Text, default="")

    # Teaching order within the topic. Lower comes first; BASIC mode walks
    # these in sequence rather than by rank.
    sequence = Column(Integer, default=0, index=True)

    # Comma-separated concept slugs that should be understood first. Used to
    # warn when a concept is opened out of order, not to hard-block it.
    prerequisite_slugs = Column(Text, default="")

    # Which mode this concept first belongs to. A concept can carry cards in
    # several modes; this is where it is introduced.
    introduced_in = Column(String(20), default=StudyMode.BASIC, index=True)

    # Rough share of the topic's exam weight, for marks-weighted progress.
    exam_weight = Column(Float, default=1.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("Topic")
    subject = relationship("Subject")

    __table_args__ = (
        Index("ix_concept_topic_sequence", "topic_id", "sequence"),
        Index("ix_concept_topic_slug", "topic_id", "slug", unique=True),
    )


class ConceptProgress(Base):
    """Per-concept study state, driving the tracker and mode gating."""

    __tablename__ = "concept_progress"

    id = Column(Integer, primary_key=True, index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    status = Column(String(20), default=ConceptStatus.NOT_STARTED, index=True)
    mode_completed = Column(String(20), default="")  # highest mode finished

    cards_seen = Column(Integer, default=0)
    revision_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)

    # Mirrors the escalation ladder: repeated mistakes push this up, which
    # lifts the concept's cards back to the front of the feed.
    escalation_level = Column(Integer, default=0, index=True)

    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_revised_at = Column(DateTime, nullable=True)

    concept = relationship("Concept")

    @property
    def accuracy(self) -> float:
        total = self.correct_count + self.wrong_count
        return (self.correct_count / total * 100) if total else 0.0
