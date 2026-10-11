"""Import a question paper from a URL or a PDF, and manage what it created."""

import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.models import Question, Subject, Topic
from ..models.papers import ImportStatus, PaperSource, QuestionPaper
from ..services.import_paper.explain import explain
from ..services.import_paper.fetch import FetchError, fetch_url
from ..services.import_paper.parse import parse_questions
from ..services.import_paper.store import resolve_target, store_questions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/papers", tags=["Papers"])

#: A paper larger than this is a book, and belongs in the ingestion inbox.
MAX_UPLOAD_BYTES = 40 * 1024 * 1024


class UrlImportRequest(BaseModel):
    url: str
    subject_slug: str
    topic_slug: str
    name: str | None = None


class ConfirmRequest(BaseModel):
    """The reviewed questions, with any answers the student filled in."""

    questions: list[dict]
    generate_explanations: bool = True


class QuestionEdit(BaseModel):
    correct_answer: str | None = None
    explanation: str | None = None
    question_type: str | None = None


def _paper_dict(paper: QuestionPaper) -> dict:
    return {
        "id": paper.id,
        "name": paper.name,
        "subject_id": paper.subject_id,
        "topic_id": paper.topic_id,
        "subject_name": paper.subject.name if paper.subject else "",
        "topic_name": paper.topic.name if paper.topic else "",
        "source_kind": paper.source_kind,
        "origin_url": paper.origin_url,
        "file_name": paper.file_name,
        "exam_year": paper.exam_year,
        "source_label": paper.source_label,
        "question_count": paper.question_count,
        "import_status": paper.import_status,
        "import_error": paper.import_error,
        "created_at": paper.created_at.isoformat() if paper.created_at else None,
    }


def _preview(paper: QuestionPaper, parsed: list[dict]) -> dict:
    """What the client reviews before anything is written."""
    return {
        "paper": _paper_dict(paper),
        "questions": parsed,
        "total": len(parsed),
        # The whole point of the preview: these need the student's input
        # before they can be stored.
        "missing_answers": sum(1 for q in parsed if q.get("needs_answer")),
    }


def _begin(db: Session, *, name: str, subject_slug: str, topic_slug: str,
           source_kind: str, origin_url: str = "", file_name: str = "") -> QuestionPaper:
    """Create the paper row before parsing, so a failure leaves a record."""
    try:
        subject, topic = resolve_target(db, subject_slug, topic_slug)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    paper = QuestionPaper(
        name=name[:250], subject_id=subject.id, topic_id=topic.id,
        source_kind=source_kind, origin_url=origin_url[:1000],
        file_name=file_name[:300], import_status=ImportStatus.PARSING,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


def _fail(db: Session, paper: QuestionPaper, message: str) -> None:
    paper.import_status = ImportStatus.FAILED
    paper.import_error = message[:1000]
    db.commit()


def _finish_parse(db: Session, paper: QuestionPaper, text: str) -> dict:
    """Parse, store the preview, and return it."""
    try:
        parsed = parse_questions(text)
    except Exception as exc:
        logger.exception("Parsing failed for paper %s", paper.id)
        _fail(db, paper, f"Could not read questions: {exc}")
        raise HTTPException(422, "Could not read any questions from that source")

    if not parsed:
        _fail(db, paper, "No questions found")
        raise HTTPException(
            422,
            "No questions found there. The page may need signing in, or "
            "render its questions with JavaScript.",
        )

    # Label the paper from what the questions actually said.
    years = [q["exam_year"] for q in parsed if q.get("exam_year")]
    if years:
        paper.exam_year = max(years)
    labels = [q["source_label"] for q in parsed if q.get("source_label")]
    if labels:
        paper.source_label = labels[0][:120]

    paper.preview_json = json.dumps(parsed)
    paper.question_count = len(parsed)
    paper.import_status = ImportStatus.PREVIEW
    db.commit()
    db.refresh(paper)

    return _preview(paper, parsed)


@router.get("")
def list_papers(
    subject_slug: str | None = None,
    topic_slug: str | None = None,
    db: Session = Depends(get_db),
):
    """Papers, newest first, for the quiz page's paper picker."""
    query = db.query(QuestionPaper)
    if subject_slug and subject_slug != "all":
        query = query.join(Subject, QuestionPaper.subject_id == Subject.id) \
                     .filter(Subject.slug == subject_slug)
    if topic_slug and topic_slug != "all":
        query = query.join(Topic, QuestionPaper.topic_id == Topic.id) \
                     .filter(Topic.slug == topic_slug)

    papers = query.order_by(QuestionPaper.id.desc()).limit(200).all()
    return {"items": [_paper_dict(p) for p in papers]}


@router.post("/import/url")
def import_from_url(payload: UrlImportRequest, db: Session = Depends(get_db)):
    """Fetch a page, parse its questions, and return them for review.

    Nothing reaches the question bank here. A parse that guessed an answer
    wrongly is costlier than one that asks: a wrong answer is practised as
    if it were right.
    """
    paper = _begin(
        db, name=payload.name or payload.url, subject_slug=payload.subject_slug,
        topic_slug=payload.topic_slug, source_kind=PaperSource.URL,
        origin_url=payload.url,
    )
    try:
        page = fetch_url(payload.url)
    except FetchError as exc:
        _fail(db, paper, str(exc))
        raise HTTPException(422, str(exc)) from exc

    if not payload.name and page.get("title"):
        paper.name = page["title"][:250]
        db.commit()

    return _finish_parse(db, paper, page["text"])


@router.post("/import/upload")
async def import_from_pdf(
    file: UploadFile = File(...),
    subject_slug: str = Form(...),
    topic_slug: str = Form(...),
    name: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Same as the URL import, from an uploaded PDF."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files can be imported")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            "That file is larger than 40 MB. A book belongs in the ingestion "
            "inbox rather than here.",
        )

    paper = _begin(
        db, name=name or file.filename, subject_slug=subject_slug,
        topic_slug=topic_slug, source_kind=PaperSource.PDF,
        file_name=file.filename or "upload.pdf",
    )

    # Written to disk because the extractor works on a path, and deleted
    # straight after: a question paper is parsed once, not kept as corpus.
    from ..services.ingestion.extract import extract_pdf_pages

    tmp = Path(tempfile.gettempdir()) / f"paper-{paper.id}.pdf"
    try:
        tmp.write_bytes(raw)
        pages = extract_pdf_pages(tmp, f"paper-{paper.id}")
        text = "\n\n".join(p["text"] for p in pages)
    except Exception as exc:
        logger.exception("PDF extraction failed for paper %s", paper.id)
        _fail(db, paper, f"Could not read that PDF: {exc}")
        raise HTTPException(422, "Could not read that PDF") from exc
    finally:
        tmp.unlink(missing_ok=True)

    if len(text.strip()) < 200:
        _fail(db, paper, "The PDF has no readable text")
        raise HTTPException(
            422, "That PDF has no readable text. It may be a scan.",
        )

    return _finish_parse(db, paper, text)


@router.post("/{paper_id}/confirm")
def confirm_import(
    paper_id: int, payload: ConfirmRequest, db: Session = Depends(get_db),
):
    """Write the reviewed questions into the bank.

    Explanations are written here rather than during parsing, because until
    the answers are confirmed there is nothing trustworthy to explain.
    """
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if paper is None:
        raise HTTPException(404, "No such paper")
    if paper.import_status == ImportStatus.COMPLETE:
        raise HTTPException(409, "That paper has already been imported")

    questions = payload.questions or json.loads(paper.preview_json or "[]")
    if not questions:
        raise HTTPException(400, "There is nothing to import")

    if payload.generate_explanations:
        for item in questions:
            if item.get("explanation"):
                continue
            result = explain(
                db, item.get("content", ""), item.get("correct_answer", ""),
                subject_id=paper.subject_id,
            )
            item["explanation"] = result["explanation"]
            item["solution_source"] = result["solution_source"]

    provenance = paper.origin_url or f"{paper.file_name} (uploaded)"
    counts = store_questions(db, paper, questions, provenance=provenance)

    paper.preview_json = ""
    db.commit()

    return {"paper": _paper_dict(paper), **counts}


@router.get("/{paper_id}")
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    """A paper and the questions it created."""
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if paper is None:
        raise HTTPException(404, "No such paper")

    rows = db.query(Question).filter(Question.paper_id == paper_id).all()
    return {
        "paper": _paper_dict(paper),
        "questions": [
            {
                "id": q.id,
                "content": q.content,
                "options": json.loads(q.options) if q.options else [],
                "correct_answer": q.correct_answer,
                "question_type": q.question_type,
                "marks": q.marks,
                "negative_marks": q.negative_marks,
                "explanation": q.explanation or "",
                "solution_source": q.solution_source or "",
                "exam_year": q.exam_year,
                "source": q.source,
                "review_status": q.review_status,
            }
            for q in rows
        ],
    }


@router.patch("/questions/{question_id}")
def edit_question(
    question_id: int, payload: QuestionEdit, db: Session = Depends(get_db),
):
    """Correct an imported answer or rewrite its solution."""
    question = db.query(Question).filter(Question.id == question_id).first()
    if question is None:
        raise HTTPException(404, "No such question")

    if payload.correct_answer is not None:
        answer = payload.correct_answer.strip()
        if not answer:
            raise HTTPException(400, "An answer cannot be empty")
        question.correct_answer = answer

    if payload.question_type is not None:
        qtype = payload.question_type.upper()
        if qtype not in {"MCQ", "MSQ", "NAT"}:
            raise HTTPException(400, "Type must be MCQ, MSQ or NAT")
        question.question_type = qtype
        from ..services.import_paper.store import negative_for
        question.negative_marks = negative_for(qtype, question.marks or 1)

    if payload.explanation is not None:
        question.explanation = payload.explanation.strip()
        # A solution the student wrote outranks any generated one, and its
        # badge should say so.
        question.solution_source = "user"

    # Edited means looked at, which is what review_status records.
    question.review_status = "approved"
    db.commit()
    db.refresh(question)

    return {
        "id": question.id,
        "correct_answer": question.correct_answer,
        "question_type": question.question_type,
        "negative_marks": question.negative_marks,
        "explanation": question.explanation or "",
        "solution_source": question.solution_source or "",
        "review_status": question.review_status,
    }


@router.delete("/{paper_id}", status_code=204)
def delete_paper(
    paper_id: int,
    delete_questions: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Remove a paper, and optionally the questions it imported.

    Questions are kept by default: they may already have been attempted, and
    an attempt pointing at a deleted question loses that history.
    """
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if paper is None:
        raise HTTPException(404, "No such paper")

    if delete_questions:
        db.query(Question).filter(Question.paper_id == paper_id).delete()
    else:
        db.query(Question).filter(Question.paper_id == paper_id) \
            .update({Question.paper_id: None})

    db.delete(paper)
    db.commit()
