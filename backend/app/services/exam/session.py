"""Create, drive and score a mock test session."""

import random
from datetime import datetime

from sqlalchemy.orm import Session

from ...models import *  # noqa: F401,F403  (register all tables)
from ...models.exams import ExamItem, ExamSession, ExamStatus, QuestionState
from ...models.models import Attempt, MistakeRegistry, Question, Subject
from .patterns import ExamPattern
from .scoring import score_item


class NotEnoughQuestions(RuntimeError):
    """Raised when the bank cannot fill the requested pattern."""


def _pick(db: Session, slugs: tuple[str, ...], marks: int, count: int,
          exclude: set[int]) -> tuple[list[Question], int]:
    """Pick `count` questions of a given mark value.

    Returns what was found and how many were short. A section the bank
    cannot fill yields fewer questions rather than failing the paper, and
    the shortfall is reported so the candidate knows the mock is not a full
    100 marks -- silently handing back a 85-mark paper labelled 100 would
    make every score misleading.
    """
    if count <= 0:
        return [], 0

    query = (
        db.query(Question)
        .join(Subject, Question.subject_id == Subject.id)
        .filter(Question.marks == marks)
    )
    if slugs:
        query = query.filter(Subject.slug.in_(slugs))
    pool = [q for q in query.all() if q.id not in exclude]

    if len(pool) < count:
        # Fall back to the other mark value rather than failing the paper:
        # a slightly off mark split beats no test at all.
        spare = (
            db.query(Question)
            .join(Subject, Question.subject_id == Subject.id)
            .filter(Question.marks != marks)
        )
        if slugs:
            spare = spare.filter(Subject.slug.in_(slugs))
        pool += [q for q in spare.all() if q.id not in exclude]

    random.shuffle(pool)
    picked = pool[:count]
    return picked, count - len(picked)


def create_session(db: Session, pattern: ExamPattern, *,
                   name: str | None = None,
                   subject_id: int | None = None) -> ExamSession:
    """Assemble a paper and open a session for it.

    The question set is fixed now and never re-drawn, so refreshing or
    reconnecting does not change the paper mid-attempt.
    """
    chosen: list[Question] = []
    used: set[int] = set()
    shortfalls: list[str] = []

    for section in pattern.sections:
        for marks, count in ((1, section.one_mark), (2, section.two_mark)):
            picked, short = _pick(db, section.subject_slugs, marks, count, used)
            used.update(q.id for q in picked)
            chosen.extend(picked)
            if short:
                where = ", ".join(section.subject_slugs) or "any subject"
                shortfalls.append(f"{short} x {marks}M from {where}")

    if not chosen:
        raise NotEnoughQuestions("Could not assemble any questions")

    session = ExamSession(
        name=name or pattern.name,
        shortfall_note="; ".join(shortfalls),
        pattern=pattern.key,
        subject_id=subject_id,
        total_questions=len(chosen),
        total_marks=float(sum(q.marks for q in chosen)),
        duration_minutes=pattern.duration_minutes,
        max_score=float(sum(q.marks for q in chosen)),
    )
    db.add(session)
    db.flush()

    for position, question in enumerate(chosen, start=1):
        db.add(ExamItem(session_id=session.id, question_id=question.id,
                        position=position))

    db.commit()
    db.refresh(session)
    return session


def visit_item(db: Session, session_id: int, position: int) -> ExamItem | None:
    """Mark a question as seen. A visited-but-blank question is Not Answered."""
    item = (
        db.query(ExamItem)
        .filter(ExamItem.session_id == session_id, ExamItem.position == position)
        .first()
    )
    if item is None:
        return None

    item.visit_count += 1
    if item.state == QuestionState.NOT_VISITED:
        item.state = QuestionState.NOT_ANSWERED
    db.commit()
    return item


def save_answer(db: Session, session_id: int, position: int, *,
                answer: str | None = None, marked: bool | None = None,
                time_spent_seconds: int | None = None) -> ExamItem | None:
    """Record an answer and/or the review flag, then recompute the state.

    Clearing an answer returns the question to Not Answered, which is what
    the official interface's "Clear Response" does.
    """
    item = (
        db.query(ExamItem)
        .filter(ExamItem.session_id == session_id, ExamItem.position == position)
        .first()
    )
    if item is None:
        return None

    if answer is not None:
        item.user_answer = answer.strip()
    if time_spent_seconds is not None:
        item.time_spent_seconds = max(item.time_spent_seconds, time_spent_seconds)

    is_marked = item.is_marked if marked is None else marked
    has_answer = bool(item.user_answer)

    if has_answer and is_marked:
        item.state = QuestionState.ANSWERED_MARKED
    elif has_answer:
        item.state = QuestionState.ANSWERED
    elif is_marked:
        item.state = QuestionState.MARKED
    else:
        item.state = QuestionState.NOT_ANSWERED

    db.commit()
    return item


def submit_session(db: Session, session_id: int) -> ExamSession | None:
    """Score every item, record attempts, and close the session.

    Scoring happens only here. Each answered item also writes an Attempt and
    updates the mistake registry, so a mock feeds the same analytics and
    remedial feed as a quiz drill.
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if session is None or not session.is_open:
        return session

    correct = wrong = unattempted = 0
    total = 0.0

    for item in session.items:
        question = item.question
        if not item.user_answer:
            unattempted += 1
            item.is_correct = None
            item.marks_obtained = 0.0
            continue

        is_correct, marks = score_item(question, item.user_answer)
        item.is_correct = is_correct
        item.marks_obtained = marks
        total += marks
        correct += int(is_correct)
        wrong += int(not is_correct)

        db.add(Attempt(
            question_id=question.id, user_answer=item.user_answer,
            is_correct=is_correct, marks_obtained=marks,
            time_spent_seconds=item.time_spent_seconds, mode="test",
        ))

        if not is_correct:
            mistake = (
                db.query(MistakeRegistry)
                .filter(MistakeRegistry.question_id == question.id).first()
            )
            if mistake:
                mistake.error_count += 1
                mistake.last_user_answer = item.user_answer
                mistake.last_attempted_at = datetime.utcnow()
                mistake.mastery_level = max(0, mistake.mastery_level - 1)
            else:
                db.add(MistakeRegistry(
                    question_id=question.id, topic_id=question.topic_id,
                    subject_id=question.subject_id, error_count=1,
                    last_user_answer=item.user_answer,
                ))

    attempted = correct + wrong
    session.score = round(total, 2)
    session.correct_count = correct
    session.wrong_count = wrong
    session.unattempted_count = unattempted
    session.accuracy = round(correct / attempted * 100, 1) if attempted else 0.0
    session.status = ExamStatus.SUBMITTED
    session.submitted_at = datetime.utcnow()

    db.commit()
    db.refresh(session)
    return session
