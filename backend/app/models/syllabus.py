"""The GATE CSE content hierarchy.

Five levels, matching how the books and the syllabus are actually laid out:

    Subject → Chapter → Topic → Subtopic → Concept

A standard text is organised chapter → topic → subtopic, and a concept is
the single idea a card teaches. Content hangs off a Concept, so new material
slots into an existing node rather than forcing a reorganisation.

The previous model had three levels, where `Topic` was really a chapter and
`Concept` a subtopic. Those tables stay until the migration moves their
rows across; see cli/migrate_hierarchy.py.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base
from .models import Subject  # noqa: F401  (register FK target)


class Level:
    """How deep into a topic a piece of content sits."""

    FOUNDATIONAL = "foundational"   # definitions, prerequisites
    CORE = "core"                   # what GATE tests every year
    ADVANCED = "advanced"           # traps, edge cases, rank-deciders


class Relevance:
    """Whether a node is worth studying for GATE.

    The books carry far more than the syllabus needs -- Cormen has chapters
    GATE never touches. Nodes are marked so generation can skip them rather
    than spending quota on content that cannot be examined.
    """

    IN_SYLLABUS = "in_syllabus"
    PERIPHERAL = "peripheral"       # context only, not directly examined
    OUT_OF_SCOPE = "out_of_scope"


class Chapter(Base):
    """A book chapter, e.g. 'Process Synchronization'."""

    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    slug = Column(String(200), index=True, nullable=False)
    summary = Column(Text, default="")

    sequence = Column(Integer, default=0, index=True)
    relevance = Column(String(20), default=Relevance.IN_SYLLABUS, index=True)
    exam_weight = Column(Float, default=1.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")
    topics = relationship(
        "SyllabusTopic", back_populates="chapter",
        cascade="all, delete-orphan", order_by="SyllabusTopic.sequence",
    )

    __table_args__ = (
        Index("ix_chapter_subject_slug", "subject_id", "slug", unique=True),
    )


class SyllabusTopic(Base):
    """A topic within a chapter, e.g. 'Semaphores'.

    Named SyllabusTopic because the legacy `topics` table still exists and
    holds the old three-level rows until migration completes.
    """

    __tablename__ = "syllabus_topics"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    slug = Column(String(200), index=True, nullable=False)
    summary = Column(Text, default="")

    sequence = Column(Integer, default=0, index=True)
    relevance = Column(String(20), default=Relevance.IN_SYLLABUS, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    chapter = relationship("Chapter", back_populates="topics")
    subtopics = relationship(
        "Subtopic", back_populates="topic",
        cascade="all, delete-orphan", order_by="Subtopic.sequence",
    )

    __table_args__ = (
        Index("ix_topic_chapter_slug", "chapter_id", "slug", unique=True),
    )


class Subtopic(Base):
    """A subtopic within a topic, e.g. 'Binary vs Counting Semaphores'."""

    __tablename__ = "subtopics"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id"),
                      nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    slug = Column(String(200), index=True, nullable=False)
    summary = Column(Text, default="")

    sequence = Column(Integer, default=0, index=True)
    relevance = Column(String(20), default=Relevance.IN_SYLLABUS, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    topic = relationship("SyllabusTopic", back_populates="subtopics")
    concepts = relationship(
        "SyllabusConcept", back_populates="subtopic",
        cascade="all, delete-orphan", order_by="SyllabusConcept.sequence",
    )

    __table_args__ = (
        Index("ix_subtopic_topic_slug", "topic_id", "slug", unique=True),
    )


class SyllabusConcept(Base):
    """The atomic idea a card teaches, e.g. 'wait() decrements then blocks'.

    Cards and questions hang off this node. Denormalised ancestry keeps the
    common query -- "everything under this subject at this level" -- a single
    indexed filter rather than a four-way join.
    """

    __tablename__ = "syllabus_concepts"

    id = Column(Integer, primary_key=True, index=True)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False, index=True)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id"),
                      nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)

    name = Column(String(250), nullable=False)
    slug = Column(String(250), index=True, nullable=False)
    summary = Column(Text, default="")

    sequence = Column(Integer, default=0, index=True)
    level = Column(String(20), default=Level.CORE, index=True)
    relevance = Column(String(20), default=Relevance.IN_SYLLABUS, index=True)

    # Comma-separated slugs that should be understood first. Advisory, used
    # to warn when a concept is opened out of order rather than to block it.
    prerequisite_slugs = Column(Text, default="")

    # How often GATE tests this: 0.5 rare, 3.0 nearly every year.
    exam_weight = Column(Float, default=1.0)

    # Set when generation could not find enough source material, so the UI
    # can show which nodes still need a book or a web pass.
    needs_source = Column(Boolean, default=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    subtopic = relationship("Subtopic", back_populates="concepts")

    __table_args__ = (
        Index("ix_concept_subtopic_slug", "subtopic_id", "slug", unique=True),
        Index("ix_concept_subject_level", "subject_id", "level"),
    )

    @property
    def path(self) -> str:
        """Readable ancestry, for citations and the tracker UI."""
        return " › ".join(filter(None, [
            self.subtopic.topic.chapter.name if self.subtopic else None,
            self.subtopic.topic.name if self.subtopic else None,
            self.subtopic.name if self.subtopic else None,
            self.name,
        ]))
