"""Concept tags: a cross-disciplinary graph laid over the syllabus tree.

The taxonomy (Subject → Chapter → Concept) answers "where does this card
live?" and has exactly one answer per card. It cannot answer "what else
touches this idea?", because the interesting connections cut across it: a
card on Prim's algorithm sits under Algorithms → Graphs, but it is also
about a priority queue (Data Structures), the cut property (a theorem), and
greedy choice (a paradigm). Filing it under one of those would lose the
other three.

So tags are many-to-many and typed. The type is what makes a hover useful:
"Graph (Data Structure)" and "Cut Property (Theorem)" are different kinds
of claim about the card, and grouping them by type turns a flat tag list
into a readable summary.

Two tables rather than a string column on the card, which is what this
replaces:

    concept_tags      the vocabulary -- one row per distinct idea, typed
    feed_card_tags    the edges, with per-edge context

Keeping tags as rows means renaming "Dijkstra's Algorithm" fixes every card
at once, a tag can be looked up to find related cards in both directions,
and the type vocabulary stays closed instead of drifting with each typo.
"""

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class TagType:
    """What kind of thing a tag names.

    A closed vocabulary: these are the categories a GATE concept actually
    falls into, and an open set would collapse into synonyms within a week
    of use. Unknown values are coerced to CONCEPT on write.
    """

    DATA_STRUCTURE = "data_structure"
    ALGORITHM = "algorithm"
    THEOREM = "theorem"
    PARADIGM = "paradigm"              # greedy, divide and conquer, DP
    SYSTEM_MECHANISM = "system_mechanism"  # paging, scheduling, locking
    FORMULA = "formula"
    PROBLEM_PATTERN = "problem_pattern"    # the shape a question takes
    CONCEPT = "concept"                # the catch-all

    ALL = (
        DATA_STRUCTURE, ALGORITHM, THEOREM, PARADIGM, SYSTEM_MECHANISM,
        FORMULA, PROBLEM_PATTERN, CONCEPT,
    )

    #: Display labels, so the UI does not have to own this mapping.
    LABELS = {
        DATA_STRUCTURE: "Data Structure",
        ALGORITHM: "Algorithm",
        THEOREM: "Theorem",
        PARADIGM: "Paradigm",
        SYSTEM_MECHANISM: "System Mechanism",
        FORMULA: "Formula",
        PROBLEM_PATTERN: "Problem Pattern",
        CONCEPT: "Concept",
    }

    @classmethod
    def coerce(cls, value: str | None) -> str:
        return value if value in cls.ALL else cls.CONCEPT


class TagRole:
    """How a card relates to a tag.

    The same tag means different things on different cards: Prim's uses a
    priority queue, whereas a card about heaps teaches one. Without this the
    hover cannot distinguish "this is what the card is about" from "this is
    machinery it happens to need", and every tag looks equally central.
    """

    PRIMARY = "primary"        # what the card is mainly about
    USES = "uses"              # machinery it depends on
    RELATED = "related"        # worth knowing alongside
    CONTRASTS = "contrasts"    # the thing it is commonly confused with

    ALL = (PRIMARY, USES, RELATED, CONTRASTS)

    #: Hover order: most central first, so a long list degrades gracefully.
    ORDER = {PRIMARY: 0, USES: 1, RELATED: 2, CONTRASTS: 3}

    @classmethod
    def coerce(cls, value: str | None) -> str:
        return value if value in cls.ALL else cls.RELATED


class ConceptTag(Base):
    """One idea, named once and reused across every card that touches it."""

    __tablename__ = "concept_tags"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(120), nullable=False)
    #: Lowercased, punctuation-stripped name. The uniqueness key, so
    #: "Prim's Algorithm" and "prims algorithm" cannot both exist.
    slug = Column(String(120), nullable=False, unique=True, index=True)
    tag_type = Column(String(30), default=TagType.CONCEPT, nullable=False, index=True)

    summary = Column(Text, default="")

    #: Home subject, where the idea is normally taught. Nullable because a
    #: tag like "Recurrence Relation" genuinely belongs to several, and
    #: forcing a choice would be a lie the hover then repeats.
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True, index=True)

    #: Denormalised count of linked cards, so the tag browser can rank
    #: without aggregating over the join table on every request.
    usage_count = Column(Integer, default=0, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")
    links = relationship(
        "FeedCardTag", back_populates="tag", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_concept_tag_type_usage", "tag_type", "usage_count"),
    )


class FeedCardTag(Base):
    """An edge from a card to a tag, carrying how they relate."""

    __tablename__ = "feed_card_tags"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(
        Integer, ForeignKey("feed_cards.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tag_id = Column(
        Integer, ForeignKey("concept_tags.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    role = Column(String(20), default=TagRole.RELATED, nullable=False)

    #: Why this tag is on this card, shown in the hover under the tag name.
    #: Per-edge rather than per-tag: the reason differs by card.
    note = Column(String(300), default="")

    #: "user" or "auto" -- a tag inferred by generation should be
    #: distinguishable from one the student put there deliberately.
    added_by = Column(String(20), default="user", nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    tag = relationship("ConceptTag", back_populates="links")
    card = relationship("FeedCard", back_populates="tag_links")

    __table_args__ = (
        # One edge per (card, tag). The role lives on the edge, so a second
        # row would be a contradiction rather than extra information.
        UniqueConstraint("card_id", "tag_id", name="uq_card_tag"),
        # The hover query is "all tags for this card", so card_id leads.
        Index("ix_card_tag_lookup", "card_id", "tag_id"),
    )
