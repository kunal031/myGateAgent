"""Performance down the four levels of the syllabus.

    Subject -> Chapter -> Topic -> Concept

The drill-down answers a different question at each level. A subject tells
you where you stand against the exam; a chapter tells you which part of a
subject is the problem; a topic tells you what to practise; a concept
tells you what to actually read. Stopping at subject level -- which is
what the old breakdown did -- says "you are weak at Operating Systems",
which is true of everyone and actionable by no one.

Two decisions worth stating:

**Aggregates are computed per level in SQL, not summed from the level
below.** Summing upward looks equivalent and is not: a question attached
to a topic whose chapter is null would vanish from its subject's total,
and the totals would quietly stop matching the subject page. Each level
aggregates over the same join, so a row missing a parent is still counted
where it does belong.

**Concept mastery comes from review state, not attempts.** A concept can
be thoroughly learned without a question existing for it, and most have
none -- only 28 of 57 topics carry any questions at all. Reading mastery
from attempts would report almost every concept as unknown.
"""

import logging

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ...models.chapters import Chapter
from ...models.concepts import Concept, ConceptProgress, ConceptStatus
from ...models.models import (
    Attempt, FeedCard, Question, Subject, Topic,
)
from ...models.rotation import CardView

logger = logging.getLogger(__name__)

#: Below this, an accuracy figure is noise. Reported as None rather than a
#: number, so the UI can say "not enough data" instead of implying 0%.
MIN_FOR_ACCURACY = 3


def _accuracy(correct: int, total: int) -> float | None:
    if total < MIN_FOR_ACCURACY:
        return None
    return round(correct / total * 100, 1)


def _node(*, level: str, node_id: int | None, name: str, slug: str,
          total: int, correct: int, available: int,
          distinct: int | None = None, sequence: int = 0,
          children: int = 0, weight: float = 0.0,
          cards: int = 0, cards_seen: int = 0, cards_mastered: int = 0,
          status: str = "", expandable: bool = True) -> dict:
    """One node of the tree. Every level returns exactly this shape.

    Uniform on purpose: with four different shapes the client needed four
    types, four fetch functions and four renderers, and adding a level or
    a metric meant touching all of them. One shape means one renderer and
    one cache, and `level` plus `id` is all a caller needs to ask for the
    children of anything.

    The fields that do not apply to a level are present and zero rather
    than absent, so a consumer never has to test for their existence --
    a missing key and a zero look identical in JavaScript right up until
    one of them throws.

    `attempted` counts attempts and `covered` counts distinct questions
    seen, because they differ whenever a question is retried: one topic
    held a single question attempted twice, which as a bare "2 / 1" reads
    like a broken query. Coverage is the honest denominator; the repeats
    are worth seeing separately, since re-attempting a question you got
    wrong is the behaviour spaced repetition is meant to produce.
    """
    covered = total if distinct is None else distinct
    covered = min(covered, available) if available else covered

    # Questions at the top three levels, cards at the concept level. Both
    # answer "how much of this have I touched", which is what the bar
    # renders -- the unit differs, the meaning does not.
    if level == "concept":
        progress_done, progress_total = cards_seen, cards
    else:
        progress_done, progress_total = covered, available

    return {
        "level": level,
        "id": node_id,
        "name": name,
        "slug": slug,
        "sequence": sequence,
        # Whether asking for this node's children is meaningful. False for
        # a concept (nothing below it) and for the Unassigned bucket,
        # which is a placeholder rather than a real chapter.
        "expandable": expandable,
        "children": children,

        "attempted": total,
        "correct": correct,
        "accuracy": _accuracy(correct, total),
        "available": available,
        "covered": covered,
        "repeats": max(total - covered, 0),
        # What is left untouched. The single most useful number on the
        # page for someone 14 months out: coverage, not accuracy.
        "unattempted": max(available - covered, 0),

        "cards": cards,
        "cards_seen": cards_seen,
        "cards_mastered": cards_mastered,

        "coverage": (
            round(progress_done / progress_total * 100)
            if progress_total else 0
        ),
        "weight": weight,
        "status": status,
    }


def subject_breakdown(db: Session, user_id: int) -> list[dict]:
    """Every subject, with attempts, accuracy and coverage."""
    attempted = dict(
        db.query(
            Question.subject_id,
            func.count(Attempt.id),
        )
        .join(Attempt, Attempt.question_id == Question.id)
        .filter(Attempt.user_id == user_id)
        .group_by(Question.subject_id)
        .all()
    )
    correct = dict(
        db.query(
            Question.subject_id,
            func.sum(case((Attempt.is_correct, 1), else_=0)),
        )
        .join(Attempt, Attempt.question_id == Question.id)
        .filter(Attempt.user_id == user_id)
        .group_by(Question.subject_id)
        .all()
    )
    available = dict(
        db.query(Question.subject_id, func.count(Question.id))
        .group_by(Question.subject_id)
        .all()
    )
    distinct = dict(
        db.query(
            Question.subject_id,
            func.count(func.distinct(Attempt.question_id)),
        )
        .join(Attempt, Attempt.question_id == Question.id)
        .filter(Attempt.user_id == user_id)
        .group_by(Question.subject_id)
        .all()
    )

    # Chapters per subject, so a row can say what opening it will show.
    chapter_counts = dict(
        db.query(Chapter.subject_id, func.count(Chapter.id))
        .group_by(Chapter.subject_id)
        .all()
    )

    out = []
    for subject in db.query(Subject).all():
        total = int(attempted.get(subject.id, 0))
        ok = int(correct.get(subject.id, 0) or 0)
        out.append(_node(
            level="subject", node_id=subject.id, name=subject.name,
            slug=subject.slug,
            total=total, correct=ok,
            available=int(available.get(subject.id, 0)),
            distinct=int(distinct.get(subject.id, 0)),
            weight=float(subject.weightage_marks or 0),
            children=int(chapter_counts.get(subject.id, 0)),
        ))

    # Heaviest subject first: 13 marks of Engineering Mathematics outranks
    # 3 marks of Compiler Design regardless of accuracy.
    return sorted(out, key=lambda r: -r["weight"])


def chapter_breakdown(db: Session, subject_id: int, user_id: int) -> list[dict]:
    """The chapters of one subject."""
    rows = (
        db.query(
            Chapter.id, Chapter.name, Chapter.slug, Chapter.sequence,
            func.count(Attempt.id),
            func.sum(case((Attempt.is_correct, 1), else_=0)),
        )
        .select_from(Chapter)
        .outerjoin(Topic, Topic.chapter_id == Chapter.id)
        .outerjoin(Question, Question.topic_id == Topic.id)
        .outerjoin(
            Attempt,
            (Attempt.question_id == Question.id)
            & (Attempt.user_id == user_id),
        )
        .filter(Chapter.subject_id == subject_id)
        .group_by(Chapter.id, Chapter.name, Chapter.slug, Chapter.sequence)
        .all()
    )

    # Counted separately: the outer join above multiplies question rows by
    # attempts, so counting questions in the same query inflates them once
    # per attempt. This is the bug that would make coverage read above
    # 100% and look like a display problem rather than a query one.
    available = dict(
        db.query(Chapter.id, func.count(Question.id))
        .select_from(Chapter)
        .outerjoin(Topic, Topic.chapter_id == Chapter.id)
        .outerjoin(Question, Question.topic_id == Topic.id)
        .filter(Chapter.subject_id == subject_id)
        .group_by(Chapter.id)
        .all()
    )

    distinct = dict(
        db.query(
            Topic.chapter_id,
            func.count(func.distinct(Attempt.question_id)),
        )
        .select_from(Topic)
        .join(Question, Question.topic_id == Topic.id)
        .join(Attempt, (Attempt.question_id == Question.id)
                       & (Attempt.user_id == user_id))
        .filter(Topic.subject_id == subject_id)
        .group_by(Topic.chapter_id)
        .all()
    )

    # How many topics each chapter holds, so a row can say what opening
    # it will show before the request is made.
    topic_counts = dict(
        db.query(Topic.chapter_id, func.count(Topic.id))
        .filter(Topic.subject_id == subject_id,
                Topic.chapter_id.isnot(None))
        .group_by(Topic.chapter_id)
        .all()
    )

    out = [
        _node(
            level="chapter", node_id=cid, name=name, slug=slug,
            sequence=seq or 0,
            total=int(total or 0), correct=int(ok or 0),
            available=int(available.get(cid, 0)),
            distinct=int(distinct.get(cid, 0)),
            children=int(topic_counts.get(cid, 0)),
        )
        for cid, name, slug, seq, total, ok in rows
    ]

    # Topics whose chapter is null would otherwise be invisible. Surfaced
    # as a pseudo-chapter so a mapping gap is obvious on the page.
    orphan = (
        db.query(
            func.count(Attempt.id),
            func.sum(case((Attempt.is_correct, 1), else_=0)),
        )
        .select_from(Topic)
        .outerjoin(Question, Question.topic_id == Topic.id)
        .outerjoin(
            Attempt,
            (Attempt.question_id == Question.id)
            & (Attempt.user_id == user_id),
        )
        .filter(Topic.subject_id == subject_id, Topic.chapter_id.is_(None))
        .first()
    )
    orphan_available = (
        db.query(func.count(Question.id))
        .select_from(Topic)
        .outerjoin(Question, Question.topic_id == Topic.id)
        .filter(Topic.subject_id == subject_id, Topic.chapter_id.is_(None))
        .scalar()
    )
    if orphan and (int(orphan[0] or 0) or int(orphan_available or 0)):
        out.append(_node(
            level="chapter", node_id=None, name="Unassigned",
            slug="unassigned", sequence=9_999,
            total=int(orphan[0] or 0), correct=int(orphan[1] or 0),
            available=int(orphan_available or 0),
            # No id, so there is nothing to ask for its children.
            expandable=False,
        ))

    return sorted(out, key=lambda r: r["sequence"])


def topic_breakdown(db: Session, chapter_id: int, user_id: int) -> list[dict]:
    """The topics of one chapter."""
    rows = (
        db.query(
            Topic.id, Topic.name, Topic.slug, Topic.sequence,
            func.count(Attempt.id),
            func.sum(case((Attempt.is_correct, 1), else_=0)),
        )
        .select_from(Topic)
        .outerjoin(Question, Question.topic_id == Topic.id)
        .outerjoin(
            Attempt,
            (Attempt.question_id == Question.id)
            & (Attempt.user_id == user_id),
        )
        .filter(Topic.chapter_id == chapter_id)
        .group_by(Topic.id, Topic.name, Topic.slug, Topic.sequence)
        .all()
    )

    available = dict(
        db.query(Topic.id, func.count(Question.id))
        .select_from(Topic)
        .outerjoin(Question, Question.topic_id == Topic.id)
        .filter(Topic.chapter_id == chapter_id)
        .group_by(Topic.id)
        .all()
    )
    concept_counts = dict(
        db.query(Topic.id, func.count(Concept.id))
        .select_from(Topic)
        .outerjoin(Concept, Concept.topic_id == Topic.id)
        .filter(Topic.chapter_id == chapter_id)
        .group_by(Topic.id)
        .all()
    )

    distinct = dict(
        db.query(
            Question.topic_id,
            func.count(func.distinct(Attempt.question_id)),
        )
        .join(Attempt, (Attempt.question_id == Question.id)
                       & (Attempt.user_id == user_id))
        .join(Topic, Topic.id == Question.topic_id)
        .filter(Topic.chapter_id == chapter_id)
        .group_by(Question.topic_id)
        .all()
    )

    return sorted(
        [
            _node(
                level="topic", node_id=tid, name=name, slug=slug,
                sequence=seq or 0,
                total=int(total or 0), correct=int(ok or 0),
                available=int(available.get(tid, 0)),
                distinct=int(distinct.get(tid, 0)),
                children=int(concept_counts.get(tid, 0)),
                expandable=int(concept_counts.get(tid, 0)) > 0,
            )
            for tid, name, slug, seq, total, ok in rows
        ],
        key=lambda r: r["sequence"],
    )


def concept_breakdown(db: Session, topic_id: int, user_id: int) -> list[dict]:
    """The concepts of one topic, with how well each is known.

    Progress is measured in cards, not questions: 1,289 of 1,294 cards
    carry a concept while **no question does** -- all 1,953 have a null
    concept_id. So a per-concept accuracy figure cannot be computed at
    all, and inventing one from the parent topic would attribute the
    topic's wrong answers to concepts that may have had nothing to do
    with them.

    What is real per concept: how many cards exist, how many have been
    read, how many are mastered, and the exam weight. That is enough to
    answer "what should I read next", which is the question this level
    exists for.
    """
    progress = {
        row.concept_id: row
        for row in db.query(ConceptProgress)
        .filter(ConceptProgress.user_id == user_id)
        .join(Concept, Concept.id == ConceptProgress.concept_id)
        .filter(Concept.topic_id == topic_id)
        .all()
    }

    # Card totals per concept, in three bulk queries rather than one per
    # row: a topic can hold a dozen concepts and this level is opened
    # often while exploring.
    available = dict(
        db.query(FeedCard.concept_id, func.count(FeedCard.id))
        .filter(FeedCard.topic_id == topic_id,
                FeedCard.concept_id.isnot(None))
        .group_by(FeedCard.concept_id)
        .all()
    )
    seen = dict(
        db.query(FeedCard.concept_id, func.count(CardView.id))
        .join(CardView, (CardView.card_id == FeedCard.id)
                        & (CardView.user_id == user_id))
        .filter(FeedCard.topic_id == topic_id,
                FeedCard.concept_id.isnot(None))
        .group_by(FeedCard.concept_id)
        .all()
    )
    mastered = dict(
        db.query(FeedCard.concept_id, func.count(CardView.id))
        .join(CardView, (CardView.card_id == FeedCard.id)
                        & (CardView.user_id == user_id))
        .filter(FeedCard.topic_id == topic_id,
                FeedCard.concept_id.isnot(None),
                CardView.mastered.is_(True))
        .group_by(FeedCard.concept_id)
        .all()
    )

    out = []
    for concept in (
        db.query(Concept)
        .filter(Concept.topic_id == topic_id)
        .order_by(Concept.sequence)
        .all()
    ):
        state = progress.get(concept.id)
        status = state.status if state else ConceptStatus.NOT_STARTED
        total_cards = int(available.get(concept.id, 0))
        cards_seen = int(seen.get(concept.id, 0))
        out.append(_node(
            level="concept", node_id=concept.id, name=concept.name,
            slug=concept.slug, sequence=concept.sequence or 0,
            # No question carries a concept_id, so there is no
            # per-concept accuracy to report. Zeroes here are honest;
            # deriving one from the parent topic would attribute its
            # wrong answers to concepts that had nothing to do with them.
            total=0, correct=0, available=0,
            cards=total_cards, cards_seen=cards_seen,
            cards_mastered=int(mastered.get(concept.id, 0)),
            weight=float(concept.exam_weight or 1.0),
            status=status,
            # Nothing below a concept.
            expandable=False,
        ))
    return out


def full_tree(db: Session, user_id: int, subject_id: int | None = None) -> list[dict]:
    """The whole hierarchy, for an export or a single-request render.

    Only used where the caller genuinely needs every level at once; the
    drill-down endpoints fetch one level at a time so opening a subject
    does not compute 282 concepts the user will not look at.
    """
    subjects = subject_breakdown(db, user_id)
    if subject_id is not None:
        subjects = [s for s in subjects if s["subject_id"] == subject_id]

    for subject in subjects:
        subject["chapters"] = chapter_breakdown(db, subject["subject_id"], user_id)
        for chapter in subject["chapters"]:
            if chapter["chapter_id"] is None:
                chapter["topics"] = []
                continue
            chapter["topics"] = topic_breakdown(
                db, chapter["chapter_id"], user_id
            )
            for topic in chapter["topics"]:
                topic["concept_rows"] = concept_breakdown(
                    db, topic["topic_id"], user_id
                )
    return subjects
