"""Question papers: a batch of questions imported from one source.

A paper groups the questions that arrived together from one URL or one PDF,
so they can be listed, re-imported, corrected or removed as a unit. Without
it an import is irreversible -- 27 questions land in a bank of 718 with
nothing tying them together.

Deliberately not reusing `Source`. That table exists for the RAG corpus and
carries a content hash, page counts, extraction method and embedding status,
none of which a question paper has: a paper is parsed once into rows and
never chunked or embedded.
"""

from datetime import datetime

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class PaperSource:
    """Where a paper's questions came from."""

    URL = "url"
    PDF = "pdf"
    MANUAL = "manual"


class ImportStatus:
    """How far an import got.

    A paper is created when parsing starts, so a failure leaves a row saying
    what went wrong rather than vanishing. PREVIEW means parsed but not yet
    confirmed: nothing is written to `questions` until the student has seen
    what was found and supplied any missing answers.
    """

    PARSING = "parsing"       # fetching and structuring the questions
    PREVIEW = "preview"       # parsed, waiting for the student to confirm
    SAVING = "saving"         # confirmed; writing solutions and rows
    COMPLETE = "complete"
    FAILED = "failed"


class QuestionPaper(Base):
    __tablename__ = "question_papers"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String(250), nullable=False)

    # Where its questions are filed. Both required: a question cannot be
    # stored without them, so a paper that cannot name them is not importable.
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False, index=True)

    source_kind = Column(String(20), default=PaperSource.URL, nullable=False)
    origin_url = Column(String(1000), default="")
    file_name = Column(String(300), default="")

    #: The paper's own year, when it is a single sitting. A topic-wise page
    #: mixes years, so each question carries its own `exam_year` too.
    exam_year = Column(Integer, nullable=True, index=True)
    #: Free text as printed, e.g. "GATE CSE 2024 SET-2" or "ISRO CSE".
    source_label = Column(String(120), default="")

    question_count = Column(Integer, default=0, nullable=False)

    import_status = Column(
        String(20), default=ImportStatus.PARSING, nullable=False, index=True,
    )
    import_error = Column(Text, default="")

    #: How far a background import has got. Stored rather than held in
    #: memory so the page can be closed and reopened mid-import, and so a
    #: restart leaves evidence of what was running.
    progress_done = Column(Integer, default=0, nullable=False)
    progress_total = Column(Integer, default=0, nullable=False)
    #: What it is doing right now, in words the student can read.
    progress_note = Column(String(120), default="")

    #: The parsed questions before they are confirmed, as JSON. Held here so
    #: a preview survives a page reload and the parse is not paid for twice.
    preview_json = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow)

    subject = relationship("Subject")
    topic = relationship("Topic")
    questions = relationship("Question", back_populates="paper")

    __table_args__ = (
        Index("ix_paper_subject_topic", "subject_id", "topic_id"),
    )
