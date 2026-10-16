"""Decide what the feed shows next, and in what mix.

The feed used to sort by `base_weight` descending. With 654 of 659 cards at
weight 1 that collapsed to ordering by id -- the order the cards happened to
be generated in. Opening the feed twice looked the same, finishing a concept
led nowhere, and the prerequisite graph sitting in the database was never
consulted.

Two ideas here.

**Readiness.** A concept whose prerequisites are unlearned sinks rather than
being blocked. The graph is a clean DAG (164 concepts, 129 edges, no
cycles), so walking it is well defined; sinking rather than hiding means a
student who wants to jump ahead still can, which a hard gate would prevent.

**Mixing, not blocking.** The obvious design -- march through one concept at
a time -- is the one the evidence rejects. Blocked practice improves
performance *during* study and worsens it on a later test, while
interleaving does the reverse; Rohrer's arithmetic studies found it roughly
doubled test scores. So a page is deliberately not one concept: it is mostly
current work, partly due review, and partly a contrasting concept whose
juxtaposition is the point.
"""

import logging
import random
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from ...data.curriculum import subject_rank, topic_rank
from ...models.concepts import Concept, ConceptStatus
from ...models.models import FeedCard, Subject, Topic
from ...models.rotation import CardView
from . import progress as progress_service

logger = logging.getLogger(__name__)

#: Shares of a page. Current work dominates, but never fills it.
SHARE_CURRENT = 0.60
SHARE_REVIEW = 0.25
SHARE_CONTRAST = 0.15

#: A concept whose prerequisites are unmet drops by this much. Large enough
#: to sink it below ready work, small enough that it still appears once the
#: ready material runs out.
NOT_READY_PENALTY = 40.0

#: Mastered material is not worth a slot unless it is due for review.
MASTERED_PENALTY = 25.0

#: Each escalation step from repeated mistakes.
ESCALATION_BOOST = 12.0

#: A card past its review date.
DUE_BOOST = 18.0

#: Exam marks matter, but a 15-mark subject should not bury an 8-mark one.
WEIGHT_SCALE = 1.2

#: How much the study order outranks exam weight. The curriculum is a
#: dependency order -- Discrete Maths before Algorithms, Digital Logic
#: before COA -- so a subject that comes later is genuinely harder to learn
#: now, whatever it is worth in the exam. Sorting by marks alone put
#: General Aptitude, which depends on nothing, ahead of the maths that
#: Algorithms needs.
CURRICULUM_STEP = 6.0
TOPIC_STEP = 1.5


@dataclass
class ScoredCard:
    card: FeedCard
    subject: Subject
    concept: Concept | None
    score: float
    ready: bool
    due: bool
    #: Position in the study order, for grouping the page by what is
    #: currently being studied rather than by raw score.
    curriculum_rank: tuple[int, int] = (0, 0)


def _prerequisite_map(db: Session) -> dict[int, list[int]]:
    """concept id -> ids of the concepts it depends on."""
    by_slug: dict[str, int] = {}
    raw: list[tuple[int, str]] = []
    for concept in db.query(Concept).all():
        by_slug[concept.slug] = concept.id
        raw.append((concept.id, concept.prerequisite_slugs or ""))

    graph: dict[int, list[int]] = {}
    for concept_id, slugs in raw:
        graph[concept_id] = [
            by_slug[s.strip()]
            for s in slugs.split(",")
            if s.strip() and s.strip() in by_slug
        ]
    return graph


def score_cards(
    db: Session,
    rows: list[tuple[FeedCard, Subject, Topic, Concept | None, int]],
    *,
    user_id: int | None = None,
) -> list[ScoredCard]:
    """Score candidate cards by how worth showing they are right now.

    `rows` carries the card with its subject, topic, concept and
    recent-mistake count, so this does no further queries per card.
    """
    graph = _prerequisite_map(db)
    learned = progress_service.learned_concept_ids(db, user_id=user_id)
    states = progress_service.progress_by_concept(db, user_id=user_id)

    views = {
        v.card_id: v
        # Scoped: another student's review schedule must not decide what
        # this one sees as due.
        for v in db.query(CardView).filter(
            CardView.card_id.in_([r[0].id for r in rows]),
            CardView.user_id == user_id,
        ).all()
    } if rows else {}

    now = datetime.utcnow()
    scored: list[ScoredCard] = []

    for card, subject, topic, concept, mistakes in rows:
        # The study order dominates. A subject that comes later in the
        # curriculum is harder to learn now because its prerequisites are
        # unlearned, whatever it is worth in the exam.
        s_rank = subject_rank(subject.slug)
        t_rank = topic_rank(subject.slug, topic.slug) if topic else 0
        rank = (s_rank, t_rank)

        score = -s_rank * CURRICULUM_STEP - t_rank * TOPIC_STEP
        score += float(subject.weightage_marks or 1) * WEIGHT_SCALE
        score += float(card.base_weight or 1)
        score += mistakes * ESCALATION_BOOST

        view = views.get(card.id)
        due = bool(view and view.due_at and view.due_at <= now)
        if due:
            score += DUE_BOOST

        ready = True
        if concept is not None:
            needed = graph.get(concept.id, [])
            ready = all(p in learned for p in needed)
            if not ready:
                score -= NOT_READY_PENALTY

            state = states.get(concept.id)
            if state is not None:
                score += (state.escalation_level or 0) * ESCALATION_BOOST
                if state.status == ConceptStatus.MASTERED and not due:
                    score -= MASTERED_PENALTY
                # Teaching order inside a ready concept.
                score -= (concept.sequence or 0) * 0.1
                score -= (card.sequence or 0) * 0.05

        scored.append(
            ScoredCard(card, subject, concept, score, ready, due, rank),
        )

    scored.sort(key=lambda s: -s.score)
    return scored


def build_page(scored: list[ScoredCard], limit: int) -> list[ScoredCard]:
    """Lay out one page as a mix rather than a ranked list.

    Taking the top N by score would group a concept together, which is the
    blocked practice the research warns about. The page is filled from three
    pools instead, then shuffled so the order is not predictable -- the
    unpredictability is itself a desirable difficulty.
    """
    if not scored or limit <= 0:
        return []

    want_review = int(limit * SHARE_REVIEW)
    want_contrast = int(limit * SHARE_CONTRAST)

    chosen: list[ScoredCard] = []
    used: set[int] = set()

    def take(pool: list[ScoredCard], count: int) -> None:
        for item in pool:
            if count <= 0:
                break
            if item.card.id in used:
                continue
            chosen.append(item)
            used.add(item.card.id)
            count -= 1

    # Due reviews first: spacing works only if it is not skipped.
    take([s for s in scored if s.due], want_review)

    # Then the current thread: ready cards, best first.
    lead_concept = next(
        (s.concept.id for s in scored
         if s.ready and s.concept is not None and s.card.id not in used),
        None,
    )
    take(
        [s for s in scored
         if s.ready and s.concept is not None and s.concept.id == lead_concept],
        limit - want_review - want_contrast,
    )

    # Then contrast: different concepts, and preferably different subjects.
    # Juxtaposition is where the interleaving benefit comes from, and two
    # concepts from the same subject contrast less than two from different
    # ones. One card per concept so the slice stays varied.
    lead_subject = next(
        (s.subject.id for s in scored if s.concept
         and s.concept.id == lead_concept), None,
    )
    seen_concepts: set[int] = set()
    contrast: list[ScoredCard] = []
    for item in scored:
        if len(contrast) >= want_contrast:
            break
        if not item.ready or item.concept is None:
            continue
        if item.concept.id == lead_concept or item.card.id in used:
            continue
        if item.concept.id in seen_concepts:
            continue
        # Prefer another subject; fall back to another concept.
        if item.subject.id == lead_subject and len(contrast) < want_contrast:
            continue
        seen_concepts.add(item.concept.id)
        contrast.append(item)
    for item in contrast:
        chosen.append(item)
        used.add(item.card.id)

    # Backfill by rotating through subjects rather than draining the top of
    # the list. Taking best-first here undid the mixing above: the highest
    # scoring subject simply filled the rest of the page.
    remaining = limit - len(chosen)
    if remaining > 0:
        by_subject: dict[int, list[ScoredCard]] = {}
        for item in scored:
            if item.card.id in used:
                continue
            by_subject.setdefault(item.subject.id, []).append(item)
        # Each subject's queue stays in curriculum order, so rotating
        # across subjects still hands out earlier topics before later ones.
        for queue in by_subject.values():
            queue.sort(key=lambda s: (s.curriculum_rank, -s.score))

        # A single-subject view has nothing to rotate between, and
        # alternating would only scramble the teaching order.
        if len(by_subject) == 1:
            queues = list(by_subject.values())
        else:
            queues = [
                by_subject[k] for k in sorted(
                    by_subject,
                    key=lambda k: by_subject[k][0].curriculum_rank,
                )
            ]

        while remaining > 0 and queues:
            for queue in list(queues):
                if remaining <= 0:
                    break
                if not queue:
                    queues.remove(queue)
                    continue
                item = queue.pop(0)
                chosen.append(item)
                used.add(item.card.id)
                remaining -= 1

    random.shuffle(chosen)
    return chosen
