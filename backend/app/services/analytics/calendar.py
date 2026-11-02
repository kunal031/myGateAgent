"""The activity calendar, and the report behind one day of it.

Two views of the same log. The calendar is a year of day-level totals, for
seeing consistency and streaks at a glance. The day report is everything
that happened on one day, grouped Subject -> Chapter -> Topic -> Concept,
for answering "what did I actually do, and what did it tell me".

The day report exists to make strengths and weaknesses visible rather than
implied. For each topic touched it reports what was answered right and
wrong, what was read, and which concepts moved -- so a day's work reads as
"you got semaphores wrong twice and have not read the deadlock cards"
rather than "you studied for 40 minutes".

Streaks count days with *study*, not days with any event. Starting a paper
and abandoning it is not studying, and a streak that rewards it is a
streak that lies.
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models.activity import ActivityEvent, ActivityKind
from ...models.chapters import Chapter
from ...models.concepts import Concept
from ...models.models import Subject, Topic

logger = logging.getLogger(__name__)

#: A year, so the heatmap matches the GitHub-style grid people expect.
DEFAULT_WINDOW_DAYS = 365

#: Intensity buckets for the heatmap. Chosen so a typical working-evening
#: session (a handful of cards plus a few questions) reads as a middle
#: shade rather than maxing the scale on day one.
INTENSITY_THRESHOLDS = (1, 5, 15, 30)


def _intensity(count: int) -> int:
    """0-4, for the heatmap's colour ramp."""
    if count <= 0:
        return 0
    for level, threshold in enumerate(INTENSITY_THRESHOLDS, start=1):
        if count <= threshold:
            return level
    return 4


def activity_calendar(db: Session, user_id: int, *,
                      days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """Day-level totals for a heatmap, plus streaks."""
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.query(
            func.date(ActivityEvent.created_at).label("day"),
            ActivityEvent.kind,
            func.count(ActivityEvent.id),
            func.sum(ActivityEvent.correct),
            func.sum(ActivityEvent.seconds),
        )
        .filter(
            ActivityEvent.user_id == user_id,
            ActivityEvent.created_at >= since,
        )
        .group_by(func.date(ActivityEvent.created_at), ActivityEvent.kind)
        .all()
    )

    by_day: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "study": 0, "attempts": 0, "correct": 0,
                 "cards": 0, "seconds": 0, "kinds": {}}
    )

    for day, kind, count, correct, seconds in rows:
        key = str(day)
        entry = by_day[key]
        entry["kinds"][kind] = int(count or 0)
        entry["total"] += int(count or 0)
        if kind in ActivityKind.COUNTS_AS_STUDY:
            entry["study"] += int(count or 0)
        if kind == ActivityKind.ATTEMPT:
            entry["attempts"] += int(count or 0)
            entry["correct"] += int(correct or 0)
        if kind in (ActivityKind.CARD_VIEW, ActivityKind.CARD_REVIEW):
            entry["cards"] += int(count or 0)
        entry["seconds"] += int(seconds or 0)

    days_list = [
        {
            "date": key,
            "intensity": _intensity(value["study"]),
            **value,
        }
        for key, value in sorted(by_day.items())
    ]

    studied = {d["date"] for d in days_list if d["study"] > 0}
    current, longest = _streaks(studied)

    return {
        "days": days_list,
        "window_days": days,
        "active_days": len(studied),
        "current_streak": current,
        "longest_streak": longest,
        "total_events": sum(d["total"] for d in days_list),
    }


def _streaks(studied: set[str]) -> tuple[int, int]:
    """Current and longest run of consecutive study days.

    The current streak counts back from today, and tolerates today being
    empty -- at 9am a streak that ended yesterday is still alive, and
    resetting it before the day is over would nag someone who is about to
    study anyway.
    """
    if not studied:
        return 0, 0

    as_dates = sorted(date.fromisoformat(d) for d in studied)

    longest = run = 1
    for previous, current_day in zip(as_dates, as_dates[1:]):
        run = run + 1 if (current_day - previous).days == 1 else 1
        longest = max(longest, run)

    today = datetime.utcnow().date()
    anchor = today if today in studied else None
    if anchor is None:
        yesterday = today - timedelta(days=1)
        anchor = yesterday if yesterday in set(as_dates) else None
    if anchor is None and today - as_dates[-1] <= timedelta(days=1):
        anchor = as_dates[-1]

    current = 0
    if anchor is not None:
        cursor = anchor
        present = set(as_dates)
        while cursor in present:
            current += 1
            cursor -= timedelta(days=1)

    return current, longest


def day_report(db: Session, user_id: int, on: date) -> dict:
    """Everything done on one day, grouped down the hierarchy."""
    start = datetime.combine(on, datetime.min.time())
    end = start + timedelta(days=1)

    events = (
        db.query(ActivityEvent)
        .filter(
            ActivityEvent.user_id == user_id,
            ActivityEvent.created_at >= start,
            ActivityEvent.created_at < end,
        )
        .order_by(ActivityEvent.created_at)
        .all()
    )

    if not events:
        return {
            "date": on.isoformat(), "empty": True, "subjects": [],
            "totals": {"events": 0, "attempts": 0, "correct": 0,
                       "cards_read": 0, "minutes": 0, "concepts_touched": 0},
            "verdict": "Nothing recorded on this day.",
        }

    # Names are resolved in three bulk queries rather than per event: a
    # busy day holds hundreds of rows, and one query each keeps the report
    # a fixed cost instead of one that grows with how hard you worked.
    names = _name_lookup(db, events)

    tree: dict = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: {
            "events": [], "attempts": 0, "correct": 0, "cards": 0,
            "seconds": 0, "concepts": {},
        }))
    )

    totals = {"events": 0, "attempts": 0, "correct": 0, "cards_read": 0,
              "seconds": 0}
    concepts_touched: set[int] = set()

    for event in events:
        bucket = tree[event.subject_id][event.chapter_id][event.topic_id]
        bucket["events"].append({
            "kind": event.kind,
            "label": event.label or "",
            "correct": event.correct,
            "marks": event.marks,
            "seconds": event.seconds,
            "detail": event.detail or "",
            "at": event.created_at.isoformat(),
            "concept_id": event.concept_id,
            "concept_name": names["concepts"].get(event.concept_id, ""),
        })

        totals["events"] += 1
        bucket["seconds"] += int(event.seconds or 0)
        totals["seconds"] += int(event.seconds or 0)

        if event.kind == ActivityKind.ATTEMPT:
            bucket["attempts"] += 1
            totals["attempts"] += 1
            if event.correct:
                bucket["correct"] += 1
                totals["correct"] += 1
        if event.kind in (ActivityKind.CARD_VIEW, ActivityKind.CARD_REVIEW):
            bucket["cards"] += 1
            totals["cards_read"] += 1

        if event.concept_id:
            concepts_touched.add(event.concept_id)
            concept = bucket["concepts"].setdefault(event.concept_id, {
                "concept_id": event.concept_id,
                "concept_name": names["concepts"].get(event.concept_id, ""),
                "attempts": 0, "correct": 0, "cards": 0, "status": "",
            })
            if event.kind == ActivityKind.ATTEMPT:
                concept["attempts"] += 1
                concept["correct"] += int(bool(event.correct))
            if event.kind in (ActivityKind.CARD_VIEW, ActivityKind.CARD_REVIEW):
                concept["cards"] += 1
            if event.kind == ActivityKind.CONCEPT_PROGRESS:
                concept["status"] = event.detail or ""

    subjects = []
    for subject_id, chapters in tree.items():
        chapter_rows = []
        for chapter_id, topics in chapters.items():
            topic_rows = []
            for topic_id, bucket in topics.items():
                # Session-level events (a paper spanning many topics) carry
                # no topic. They are counted in the day's totals but would
                # otherwise render as an empty "Unspecified" row beside the
                # real ones, and make a topic look duplicated.
                if (topic_id is None and not bucket["attempts"]
                        and not bucket["cards"]):
                    continue
                topic_rows.append({
                    "topic_id": topic_id,
                    "topic_name": names["topics"].get(topic_id, "Unspecified"),
                    "attempts": bucket["attempts"],
                    "correct": bucket["correct"],
                    "accuracy": (
                        round(bucket["correct"] / bucket["attempts"] * 100, 1)
                        if bucket["attempts"] else None
                    ),
                    "cards_read": bucket["cards"],
                    "minutes": round(bucket["seconds"] / 60, 1),
                    "concepts": list(bucket["concepts"].values()),
                    "events": bucket["events"],
                })
            if not topic_rows:
                continue
            chapter_rows.append({
                "chapter_id": chapter_id,
                "chapter_name": names["chapters"].get(chapter_id, "Unassigned"),
                "attempts": sum(t["attempts"] for t in topic_rows),
                "correct": sum(t["correct"] for t in topic_rows),
                "cards_read": sum(t["cards_read"] for t in topic_rows),
                "topics": topic_rows,
            })
        if not chapter_rows:
            continue
        subjects.append({
            "subject_id": subject_id,
            "subject_name": names["subjects"].get(subject_id, "Unspecified"),
            "attempts": sum(c["attempts"] for c in chapter_rows),
            "correct": sum(c["correct"] for c in chapter_rows),
            "cards_read": sum(c["cards_read"] for c in chapter_rows),
            "chapters": chapter_rows,
        })

    subjects.sort(key=lambda s: -(s["attempts"] + s["cards_read"]))

    return {
        "date": on.isoformat(),
        "empty": False,
        "subjects": subjects,
        "totals": {
            "events": totals["events"],
            "attempts": totals["attempts"],
            "correct": totals["correct"],
            "accuracy": (
                round(totals["correct"] / totals["attempts"] * 100, 1)
                if totals["attempts"] else None
            ),
            "cards_read": totals["cards_read"],
            "minutes": round(totals["seconds"] / 60, 1),
            "concepts_touched": len(concepts_touched),
        },
        "strengths": _strengths(subjects),
        "weaknesses": _weaknesses(subjects),
    }


def _name_lookup(db: Session, events: list[ActivityEvent]) -> dict:
    """Resolve the ids on a day's events to names, in bulk."""
    def ids(attr: str) -> set[int]:
        return {getattr(e, attr) for e in events if getattr(e, attr)}

    subject_ids, chapter_ids = ids("subject_id"), ids("chapter_id")
    topic_ids, concept_ids = ids("topic_id"), ids("concept_id")

    return {
        "subjects": dict(
            db.query(Subject.id, Subject.name)
            .filter(Subject.id.in_(subject_ids)).all()
        ) if subject_ids else {},
        "chapters": dict(
            db.query(Chapter.id, Chapter.name)
            .filter(Chapter.id.in_(chapter_ids)).all()
        ) if chapter_ids else {},
        "topics": dict(
            db.query(Topic.id, Topic.name)
            .filter(Topic.id.in_(topic_ids)).all()
        ) if topic_ids else {},
        "concepts": dict(
            db.query(Concept.id, Concept.name)
            .filter(Concept.id.in_(concept_ids)).all()
        ) if concept_ids else {},
    }


#: Below this an accuracy figure on a single day is noise.
MIN_FOR_DAY_SIGNAL = 3


def _strengths(subjects: list[dict]) -> list[dict]:
    """Topics answered well enough on this day to call a strength."""
    out = []
    for subject in subjects:
        for chapter in subject["chapters"]:
            for topic in chapter["topics"]:
                if (topic["attempts"] >= MIN_FOR_DAY_SIGNAL
                        and (topic["accuracy"] or 0) >= 75):
                    out.append({
                        "topic_name": topic["topic_name"],
                        "subject_name": subject["subject_name"],
                        "accuracy": topic["accuracy"],
                        "attempts": topic["attempts"],
                    })
    return sorted(out, key=lambda r: -(r["accuracy"] or 0))[:5]


def _weaknesses(subjects: list[dict]) -> list[dict]:
    """Where this day went wrong, with the concepts to revisit.

    Reported from a single wrong answer upward, unlike strengths: one
    mistake is worth looking at, whereas one correct answer proves little.
    """
    out = []
    for subject in subjects:
        for chapter in subject["chapters"]:
            for topic in chapter["topics"]:
                wrong = topic["attempts"] - topic["correct"]
                if wrong <= 0:
                    continue
                out.append({
                    "topic_name": topic["topic_name"],
                    "subject_name": subject["subject_name"],
                    "chapter_name": chapter["chapter_name"],
                    "wrong": wrong,
                    "attempts": topic["attempts"],
                    "accuracy": topic["accuracy"],
                    "concepts": [
                        c["concept_name"] for c in topic["concepts"]
                        if c["concept_name"] and c["attempts"] > c["correct"]
                    ],
                })
    return sorted(out, key=lambda r: -r["wrong"])[:5]
