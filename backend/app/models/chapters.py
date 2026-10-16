"""The chapter level, between a subject and its topics.

GATE preparation is organised four deep, and the user's own framing is the
clearest statement of it:

    Operating Systems   subject
    Process Management  chapter
    Process Scheduling  topic
    FCFS, SJF, Round Robin, Convoy Effect   concepts

The data already held all four levels, one name out of step: `topics` rows
were chapter-sized ("CPU Scheduling"), `concepts` rows were topic-sized
("Shortest Job First Scheduling"), and `feed_cards` carried the actual
concepts. Nothing needs generating -- 1,289 of 1,294 cards are already
attached to a concept, covering 266 of 282.

So this adds the missing *container* rather than renaming anything.
`topics.chapter_id` groups existing topic rows under a chapter, and every
id stays exactly where it is. That matters: 1,953 questions, 1,294 cards,
282 concepts, 27 papers and 11 mistake rows point at `topics.id`, across
104 code sites. A rename would have had to move all of them, and a missed
one fails silently -- a question quietly detached from its topic still
renders, it just stops counting towards anything.

`chapter_id` is nullable on purpose. An unmapped topic shows up under
"Unassigned" instead of disappearing from the breakdown, so a gap in the
mapping is visible rather than silent.

Not reusing `syllabus.Chapter`: that one is wired to `SyllabusTopic`, part
of a parallel taxonomy that has zero rows in it. Pointing the live tables
at a dead hierarchy would tie the two together and leave the question of
which is authoritative permanently open.
"""

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class Chapter(Base):
    """A group of related topics within a subject."""

    __tablename__ = "syllabus_chapters"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(
        Integer, ForeignKey("subjects.id"), nullable=False, index=True
    )

    name = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False, index=True)
    summary = Column(Text, default="")

    #: Teaching order within the subject, taken from the curriculum rather
    #: than from id order -- chapters were not created in study order.
    sequence = Column(Integer, default=0, index=True)

    #: Share of the subject's exam marks, for weighting what to revise.
    exam_weight = Column(Float, default=1.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")
    topics = relationship(
        "Topic",
        primaryjoin="Chapter.id == foreign(Topic.chapter_id)",
        viewonly=True,
    )

    __table_args__ = (
        # One slug per subject, not globally: "miscellaneous" is a legitimate
        # chapter name in more than one subject.
        Index("ix_chapter_subject_slug", "subject_id", "slug", unique=True),
    )
