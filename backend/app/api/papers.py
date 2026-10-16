"""Import a question paper from a URL or a PDF, and manage what it created.

Importing is slow -- fetching, then a model pass to structure the questions,
then up to three model calls per question to write a solution. Minutes, for
a paper of any size. So the endpoints that start that work return as soon as
the paper row exists, and the work continues in a background thread.

Progress lives on the paper row itself (`import_status`, `import_error`,
`progress_done`/`progress_total`) rather than in memory, so a client can
close the page, reload, and still see where its import got to.
"""

import json
import logging
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import admin_user, current_user
from ..core.database import get_db
from ..models.models import Question, Subject, Topic
from ..models.papers import ImportStatus, PaperSource, QuestionPaper
from ..models.users import User
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


#: Explanations run concurrently. Each is up to three sequential model
#: calls -- retrieve, grade, write -- so a paper of 25 done one at a time
#: takes many minutes while the student waits on a request.
EXPLAIN_CONCURRENCY = 6


def _explain_all(
    db: Session, paper: QuestionPaper, questions: list[dict], *, subject_id: int,
) -> None:
    """Fill in missing explanations in parallel, in place.

    Each worker opens its own session: a SQLAlchemy Session is not safe to
    share across threads, and the corpus lookup inside explain() queries.
    Progress is written to the paper as each one lands, so the client sees
    movement rather than a spinner for several minutes.
    """
    from concurrent.futures import ThreadPoolExecutor

    from ..core.database import SessionLocal

    pending = [q for q in questions if not q.get("explanation")]
    if not pending:
        return

    done = 0
    lock = threading.Lock()

    def run(item: dict) -> None:
        nonlocal done
        worker = SessionLocal()
        try:
            result = explain(
                worker, item.get("content", ""), item.get("correct_answer", ""),
                subject_id=subject_id,
            )
            item["explanation"] = result["explanation"]
            item["solution_source"] = result["solution_source"]
        except Exception:
            logger.exception("Could not explain a question")
        finally:
            worker.close()
        with lock:
            done += 1
            paper.progress_done = done
            db.commit()

    with ThreadPoolExecutor(max_workers=EXPLAIN_CONCURRENCY) as pool:
        list(pool.map(run, pending))


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
        "progress_done": paper.progress_done,
        "progress_total": paper.progress_total,
        "progress_note": paper.progress_note or "",
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
           source_kind: str, user_id: int, origin_url: str = "",
           file_name: str = "") -> QuestionPaper:
    """Create the paper row before parsing, so a failure leaves a record."""
    try:
        subject, topic = resolve_target(db, subject_slug, topic_slug)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    paper = QuestionPaper(
        name=name[:250], subject_id=subject.id, topic_id=topic.id,
        user_id=user_id, source_kind=source_kind, origin_url=origin_url[:1000],
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


def _run_in_background(fn, *args) -> None:
    """Run `fn` on its own thread with its own database session.

    A daemon thread rather than a task queue: this is a single-user study
    app with no broker to run, and the work is already recoverable from the
    paper row if the process dies mid-import.
    """
    import threading

    from ..core.database import SessionLocal

    def runner() -> None:
        worker = SessionLocal()
        try:
            fn(worker, *args)
        except Exception:
            logger.exception("Background import failed")
        finally:
            worker.close()

    threading.Thread(target=runner, daemon=True).start()


def _note(db: Session, paper: QuestionPaper, note: str,
          *, done: int | None = None, total: int | None = None) -> None:
    """Record what the import is doing, for the client's progress display."""
    paper.progress_note = note[:120]
    if done is not None:
        paper.progress_done = done
    if total is not None:
        paper.progress_total = total
    db.commit()


def _parse_in_background(db: Session, paper_id: int, text: str) -> None:
    """Structure the fetched text into questions, then wait for review."""
    # Not scoped by user_id, deliberately: these routes are admin-only,
    # and an admin reviewing an import needs to see every paper.
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if paper is None:
        return

    _note(db, paper, "Reading the questions")
    try:
        parsed = parse_questions(text)
    except Exception as exc:
        logger.exception("Parsing failed for paper %s", paper_id)
        _fail(db, paper, f"Could not read questions: {exc}")
        return

    if not parsed:
        _fail(
            db, paper,
            "No questions found there. The page may need signing in, or "
            "render its questions with JavaScript.",
        )
        return

    _finish_parse(db, paper, parsed)


def _finish_parse(db: Session, paper: QuestionPaper, parsed: list[dict]) -> dict:
    """Store the parsed preview against the paper."""

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
    paper.progress_note = ""
    paper.progress_done = paper.progress_total = 0
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
def import_from_url(payload: UrlImportRequest, db: Session = Depends(get_db),
                    user: User = Depends(admin_user)):
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
    def work(worker: Session, paper_id: int) -> None:
        row = worker.query(QuestionPaper).filter(
            QuestionPaper.id == paper_id).first()
        if row is None:
            return
        _note(worker, row, "Fetching the page")
        try:
            page = fetch_url(payload.url)
        except FetchError as exc:
            _fail(worker, row, str(exc))
            return
        if not payload.name and page.get("title"):
            row.name = page["title"][:250]
            worker.commit()
        _parse_in_background(worker, paper_id, page["text"])

    _run_in_background(work, paper.id)
    return {"paper": _paper_dict(paper), "queued": True}


@router.post("/import/upload")
async def import_from_pdf(
    file: UploadFile = File(...),
    subject_slug: str = Form(...),
    topic_slug: str = Form(...),
    name: str | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(admin_user),
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

    def work(worker: Session, paper_id: int) -> None:
        # Written to disk because the extractor works on a path, and
        # deleted straight after: a question paper is parsed once into
        # rows, not kept as corpus.
        from ..services.ingestion.extract import extract_pdf_pages

        row = worker.query(QuestionPaper).filter(
            QuestionPaper.id == paper_id).first()
        if row is None:
            return

        _note(worker, row, "Reading the PDF")
        tmp = Path(tempfile.gettempdir()) / f"paper-{paper_id}.pdf"
        try:
            tmp.write_bytes(raw)
            pages = extract_pdf_pages(tmp, f"paper-{paper_id}")
            text = "\n\n".join(p["text"] for p in pages)
        except Exception as exc:
            logger.exception("PDF extraction failed for paper %s", paper_id)
            _fail(worker, row, f"Could not read that PDF: {exc}")
            return
        finally:
            tmp.unlink(missing_ok=True)

        if len(text.strip()) < 200:
            _fail(worker, row,
                  "That PDF has no readable text. It may be a scan.")
            return

        _parse_in_background(worker, paper_id, text)

    _run_in_background(work, paper.id)
    return {"paper": _paper_dict(paper), "queued": True}


@router.post("/{paper_id}/confirm")
def confirm_import(
    paper_id: int, payload: ConfirmRequest, db: Session = Depends(get_db),
    user: User = Depends(admin_user),
):
    """Write the reviewed questions into the bank.

    Explanations are written here rather than during parsing, because until
    the answers are confirmed there is nothing trustworthy to explain.
    """
    # Not scoped by user_id, deliberately: these routes are admin-only,
    # and an admin reviewing an import needs to see every paper.
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if paper is None:
        raise HTTPException(404, "No such paper")
    if paper.import_status == ImportStatus.COMPLETE:
        raise HTTPException(409, "That paper has already been imported")

    questions = payload.questions or json.loads(paper.preview_json or "[]")
    if not questions:
        raise HTTPException(400, "There is nothing to import")

    paper.import_status = ImportStatus.SAVING
    paper.progress_done = 0
    paper.progress_total = len(questions)
    paper.progress_note = (
        "Writing solutions" if payload.generate_explanations else "Saving"
    )
    db.commit()
    db.refresh(paper)

    def work(worker: Session, paper_id: int) -> None:
        row = worker.query(QuestionPaper).filter(
            QuestionPaper.id == paper_id).first()
        if row is None:
            return
        try:
            if payload.generate_explanations:
                _explain_all(
                    worker, row, questions, subject_id=row.subject_id,
                )
            _note(worker, row, "Saving questions")
            provenance = row.origin_url or f"{row.file_name} (uploaded)"
            store_questions(worker, row, questions, provenance=provenance)
            row.preview_json = ""
            row.progress_note = ""
            worker.commit()
        except Exception as exc:
            logger.exception("Confirm failed for paper %s", paper_id)
            _fail(worker, row, f"Could not save those questions: {exc}")

    _run_in_background(work, paper.id)
    return {"paper": _paper_dict(paper), "queued": True}


@router.get("/{paper_id}/status")
def paper_status(paper_id: int, db: Session = Depends(get_db)):
    """Just the progress fields, for polling while an import runs.

    Separate from GET /{id}, which returns every question: polling that once
    a second would send the whole paper back each time.
    """
    # Not scoped by user_id, deliberately: these routes are admin-only,
    # and an admin reviewing an import needs to see every paper.
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if paper is None:
        raise HTTPException(404, "No such paper")
    return {
        "id": paper.id,
        "import_status": paper.import_status,
        "import_error": paper.import_error,
        "progress_done": paper.progress_done,
        "progress_total": paper.progress_total,
        "progress_note": paper.progress_note or "",
        "question_count": paper.question_count,
    }


@router.get("/{paper_id}/preview")
def paper_preview(paper_id: int, db: Session = Depends(get_db)):
    """The parsed questions awaiting review.

    Held on the paper rather than in the response to the import call, so
    closing the page mid-parse does not lose the work it paid for.
    """
    # Not scoped by user_id, deliberately: these routes are admin-only,
    # and an admin reviewing an import needs to see every paper.
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if paper is None:
        raise HTTPException(404, "No such paper")
    parsed = json.loads(paper.preview_json or "[]")
    return _preview(paper, parsed)


@router.get("/{paper_id}")
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    """A paper and the questions it created."""
    # Not scoped by user_id, deliberately: these routes are admin-only,
    # and an admin reviewing an import needs to see every paper.
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
    user: User = Depends(admin_user),
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
    user: User = Depends(admin_user),
):
    """Remove a paper, and optionally the questions it imported.

    Questions are kept by default: they may already have been attempted, and
    an attempt pointing at a deleted question loses that history.
    """
    # Not scoped by user_id, deliberately: these routes are admin-only,
    # and an admin reviewing an import needs to see every paper.
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
