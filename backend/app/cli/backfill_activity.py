"""Reconstruct activity events from the history that predates the log.

The activity log starts empty, so without this the calendar shows nothing
before the day it was added -- including real study from 7-11 October.

Only two sources can be recovered honestly:

* `attempts` is append-only and carries `created_at`, so every past
  attempt reconstructs exactly.
* `exam_sessions` carries `started_at` and `submitted_at`.

Card reading **cannot** be recovered. `card_views` keeps one row per card
with a rolling `last_seen_at`, so a card read on three days left one
timestamp; inventing the other two would be fabrication. Those days will
show their attempts and nothing else, which is accurate rather than
flattering.

Idempotent: events are matched on (kind, object_id, created_at) before
insert, so re-running adds nothing. Safe to run after each import.

    python -m app.cli.backfill_activity --dry-run
    python -m app.cli.backfill_activity
"""

import argparse

from sqlalchemy import text

from ..core.database import SessionLocal
from ..models.activity import ActivityEvent, ActivityKind


def backfill(*, dry_run: bool = False) -> dict:
    db = SessionLocal()
    counts = {"attempts": 0, "exam_start": 0, "exam_submit": 0, "skipped": 0}

    existing = {
        (kind, oid, created)
        for kind, oid, created in db.execute(text(
            "SELECT kind, object_id, created_at FROM activity_events"
        ))
    }

    # --- attempts -------------------------------------------------------
    rows = db.execute(text("""
        SELECT a.id, a.user_id, a.question_id, a.is_correct,
               a.marks_obtained, a.time_spent_seconds, a.mode, a.created_at,
               q.content, q.concept_id, q.topic_id,
               t.chapter_id, q.subject_id
        FROM attempts a
        JOIN questions q ON q.id = a.question_id
        LEFT JOIN topics t ON t.id = q.topic_id
        WHERE a.user_id IS NOT NULL
        ORDER BY a.created_at
    """)).all()

    for (_aid, uid, qid, correct, marks, secs, mode, created,
         content, concept_id, topic_id, chapter_id, subject_id) in rows:
        if (ActivityKind.ATTEMPT, qid, created) in existing:
            counts["skipped"] += 1
            continue
        if not dry_run:
            db.add(ActivityEvent(
                user_id=uid, kind=ActivityKind.ATTEMPT,
                subject_id=subject_id, chapter_id=chapter_id,
                topic_id=topic_id, concept_id=concept_id,
                object_type="question", object_id=qid,
                label=(content or "")[:300],
                correct=1 if correct else 0,
                marks=float(marks or 0.0), seconds=int(secs or 0),
                detail=mode or "quiz", created_at=created,
            ))
        counts["attempts"] += 1

    # --- exam sessions --------------------------------------------------
    sessions = db.execute(text("""
        SELECT s.id, s.user_id, s.name, s.kind, s.subject_id, s.topic_id,
               s.started_at, s.submitted_at, s.score, s.time_spent_seconds,
               s.status, t.chapter_id
        FROM exam_sessions s
        LEFT JOIN topics t ON t.id = s.topic_id
        WHERE s.user_id IS NOT NULL
        ORDER BY s.started_at
    """)).all()

    for (sid, uid, name, kind, subject_id, topic_id,
         started, submitted, score, secs, _status, chapter_id) in sessions:
        if started and (ActivityKind.EXAM_START, sid, started) not in existing:
            if not dry_run:
                db.add(ActivityEvent(
                    user_id=uid, kind=ActivityKind.EXAM_START,
                    subject_id=subject_id, chapter_id=chapter_id,
                    topic_id=topic_id,
                    object_type="exam_session", object_id=sid,
                    label=name or f"{kind} session",
                    detail=kind or "", created_at=started,
                ))
            counts["exam_start"] += 1

        if submitted and (ActivityKind.EXAM_SUBMIT, sid, submitted) not in existing:
            if not dry_run:
                db.add(ActivityEvent(
                    user_id=uid, kind=ActivityKind.EXAM_SUBMIT,
                    subject_id=subject_id, chapter_id=chapter_id,
                    topic_id=topic_id,
                    object_type="exam_session", object_id=sid,
                    label=name or f"{kind} session",
                    marks=float(score) if score is not None else None,
                    seconds=int(secs or 0), detail=kind or "",
                    created_at=submitted,
                ))
            counts["exam_submit"] += 1

    if not dry_run:
        db.commit()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    counts = backfill(dry_run=args.dry_run)
    prefix = "would add" if args.dry_run else "added"
    print(f"{prefix}: {counts['attempts']} attempt, "
          f"{counts['exam_start']} exam-start, "
          f"{counts['exam_submit']} exam-submit event(s)")
    print(f"skipped (already present): {counts['skipped']}")
    print("\nCard reading before the log existed is not recoverable: "
          "card_views keeps only the latest view per card.")


if __name__ == "__main__":
    main()
