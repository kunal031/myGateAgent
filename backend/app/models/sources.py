"""Ingested source files and their extracted page-level chunks.

Every generated feed card and question must cite a SourceChunk, so these
tables are the anti-hallucination backbone: if content cannot be traced to
a page here, it does not belong in the database.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class SourceKind:
    """What a file is, which decides how its content is used."""

    HANDWRITTEN_NOTES = "HANDWRITTEN_NOTES"   # topper notes: traps, shortcuts
    TEXTBOOK = "TEXTBOOK"                     # foundational concepts
    PYQ_PAPER = "PYQ_PAPER"                   # actual exam paper
    PYQ_ANSWER_KEY = "PYQ_ANSWER_KEY"         # official answer key
    PYQ_TOPICWISE = "PYQ_TOPICWISE"           # topic-grouped PYQ compilation
    SYLLABUS = "SYLLABUS"                     # official syllabus
    CONCEPT_IMAGE = "CONCEPT_IMAGE"           # single-image comparison table
    STRATEGY = "STRATEGY"                     # preparation strategy notes
    EXCLUDED = "EXCLUDED"                     # present but deliberately unindexed


class ExtractionMethod:
    DIRECT = "DIRECT"    # PDF text layer was clean
    VISION = "VISION"    # Gemini transcription of a rendered page
    PENDING = "PENDING"


class Source(Base):
    """One ingested file, identified by content hash so re-drops are no-ops."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)

    content_hash = Column(String(64), unique=True, index=True, nullable=False)
    file_name = Column(String(300), nullable=False)
    relative_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, default=0)
    file_type = Column(String(20), default="pdf")

    kind = Column(String(40), default=SourceKind.TEXTBOOK, index=True)
    # Optional: notes and books are often per-subject.
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)

    # Provenance of the file itself, for citations the user can act on.
    origin = Column(String(300), default="")      # e.g. GitHub URL, Drive folder
    author_credit = Column(String(200), default="")  # e.g. "Priyanshu, AIR 379"
    exam_year = Column(Integer, nullable=True)       # for PYQ papers

    total_pages = Column(Integer, default=0)
    pages_extracted = Column(Integer, default=0)
    extraction_method = Column(String(20), default=ExtractionMethod.PENDING)
    is_indexed = Column(Boolean, default=False)

    # Versioning: a newer edition supersedes rather than overwrites, so old
    # citations keep pointing at the page they were generated from.
    version = Column(Integer, default=1)
    superseded_by_id = Column(Integer, ForeignKey("sources.id"), nullable=True)

    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = relationship(
        "SourceChunk", back_populates="source", cascade="all, delete-orphan"
    )

    @property
    def citation(self) -> str:
        """Human-readable attribution shown on any derived card."""
        parts = [self.file_name]
        if self.author_credit:
            parts.append(self.author_credit)
        return " - ".join(parts)


class SourceChunk(Base):
    """A retrievable passage, anchored to the page it came from."""

    __tablename__ = "source_chunks"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, index=True)

    page_number = Column(Integer, default=1)
    chunk_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    char_count = Column(Integer, default=0)

    # Set once the chunk is classified; lets generation target a concept.
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True, index=True)

    extraction_method = Column(String(20), default=ExtractionMethod.DIRECT)
    is_embedded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Source", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunk_source_page", "source_id", "page_number"),
        Index("ix_chunk_dedupe", "source_id", "page_number", "chunk_index",
              unique=True),
    )

    @property
    def citation(self) -> str:
        return f"{self.source.citation} (p. {self.page_number})"
