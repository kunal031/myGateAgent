"""Turn attempt history into things worth changing study behaviour over.

The old summary gave accuracy, marks and a mistake count. Those say how it
is going, not what to do about it. The data to answer the second question
was already being recorded and never read: time per question, how often an
item was revisited before answering, which question types fail, which
wrong option was chosen, whether a topic is improving or decaying.

Every function here is scoped to one student. An unscoped aggregate reads
as your own performance and is not, which is worse than showing nothing.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ...models.concepts import Concept, ConceptProgress, ConceptStatus
from ...models.exams import ExamItem, ExamSession
from ...models.models import Attempt, MistakeRegistry, Question, Subject, Topic
from ...models.rotation import CardView

logger = logging.getLogger(__name__)

#: Below this an average is noise rather than a signal.
MIN_ATTEMPTS_FOR_SIGNAL = 3

#: A GATE 1-mark question is roughly 1.5 minutes, a 2-mark one roughly 3.
#: Past these the question is costing more than it returns.
PACE_BUDGET_SECONDS = {1: 90, 2: 180}

#: How far back "recent" reaches when comparing against earlier work.
TREND_WINDOW_DAYS = 14


def _scoped(query, user_id: int):
    return query.filter(Attempt.user_id == user_id)


def accuracy_by_question_type(db: Session, user_id: int) -> list[dict]:
    """MCQ vs MSQ vs NAT.

    Worth separating because they fail for different reasons: MCQ rewards
    elimination, MSQ punishes a single wrong tick with the whole mark, and
    NAT has no options to work backwards from. A student strong on MCQ and
    weak on MSQ has a specific, fixable habit.
    """
    rows = (
        db.query(
            Question.question_type,
            func.count(Attempt.id),
            func.sum(case((Attempt.is_correct, 1), else_=0)),
            func.avg(Attempt.time_spent_seconds),
            func.sum(Attempt.marks_obtained),
        )
        .join(Question, Attempt.question_id == Question.id)
        .filter(Attempt.user_id == user_id)
        .group_by(Question.question_type)
        .all()
    )
    out = []
    for qtype, total, correct, avg_time, marks in rows:
        total = int(total or 0)
        correct = int(correct or 0)
        out.append({
            "question_type": qtype,
            "attempts": total,
            "correct": correct,
            "accuracy": round(correct / total * 100, 1) if total else 0.0,
            "avg_seconds": round(float(avg_time or 0), 1),
            "marks": round(float(marks or 0), 2),
        })
    return sorted(out, key=lambda r: -r["attempts"])


def pace(db: Session, user_id: int) -> dict:
    """Where time is going, against the budget the exam implies.

    GATE is three hours for 65 questions. Accuracy without pace is
    misleading: a student at 80% who takes four minutes a question will
    not finish the paper.
    """
    rows = (
        db.query(
            Question.marks,
            Attempt.time_spent_seconds,
            Attempt.is_correct,
        )
        .join(Question, Attempt.question_id == Question.id)
        .filter(Attempt.user_id == user_id, Attempt.time_spent_seconds > 0)
        .all()
    )
    if not rows:
        return {"samples": 0}

    over_budget = 0
    slow_and_wrong = 0
    fast_and_wrong = 0
    total_seconds = 0
    by_marks: dict[int, list[int]] = defaultdict(list)

    for marks, seconds, correct in rows:
        marks = int(marks or 1)
        seconds = int(seconds or 0)
        budget = PACE_BUDGET_SECONDS.get(marks, 90)
        total_seconds += seconds
        by_marks[marks].append(seconds)
        if seconds > budget:
            over_budget += 1
            if not correct:
                slow_and_wrong += 1
        elif not correct and seconds < budget * 0.3:
            # Answered fast and wrong: usually a misread, not a gap.
            fast_and_wrong += 1

    return {
        "samples": len(rows),
        "total_minutes": round(total_seconds / 60, 1),
        "over_budget": over_budget,
        "over_budget_pct": round(over_budget / len(rows) * 100, 1),
        # Time spent and nothing gained -- the most expensive failure.
        "slow_and_wrong": slow_and_wrong,
        # Likely rushed rather than unknown.
        "rushed_errors": fast_and_wrong,
        "avg_seconds_by_marks": {
            str(m): round(sum(v) / len(v), 1) for m, v in sorted(by_marks.items())
        },
    }


def trend(db: Session, user_id: int, *, days: int = TREND_WINDOW_DAYS) -> dict:
    """Recent accuracy against everything before it.

    Direction matters more than level. A student at 55% and climbing is in
    a better position than one at 65% and falling, and the headline number
    hides both.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    def window(newer: bool):
        q = db.query(
            func.count(Attempt.id),
            func.sum(case((Attempt.is_correct, 1), else_=0)),
        ).filter(Attempt.user_id == user_id)
        q = q.filter(Attempt.created_at >= cutoff) if newer else \
            q.filter(Attempt.created_at < cutoff)
        total, correct = q.first()
        total = int(total or 0)
        return total, int(correct or 0)

    recent_total, recent_correct = window(True)
    prior_total, prior_correct = window(False)

    recent_acc = round(recent_correct / recent_total * 100, 1) if recent_total else None
    prior_acc = round(prior_correct / prior_total * 100, 1) if prior_total else None

    change = None
    if recent_acc is not None and prior_acc is not None:
        change = round(recent_acc - prior_acc, 1)

    return {
        "window_days": days,
        "recent_attempts": recent_total,
        "recent_accuracy": recent_acc,
        "prior_attempts": prior_total,
        "prior_accuracy": prior_acc,
        "change": change,
        "direction": (
            "improving" if change and change > 2
            else "declining" if change and change < -2
            else "steady" if change is not None
            else "unknown"
        ),
    }


def daily_activity(db: Session, user_id: int, *, days: int = 30) -> list[dict]:
    """Questions answered per day, for a streak and a consistency read.

    For someone studying around a job, consistency predicts the outcome
    better than any single session does.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            func.date(Attempt.created_at),
            func.count(Attempt.id),
            func.sum(case((Attempt.is_correct, 1), else_=0)),
        )
        .filter(Attempt.user_id == user_id, Attempt.created_at >= cutoff)
        .group_by(func.date(Attempt.created_at))
        .order_by(func.date(Attempt.created_at))
        .all()
    )
    return [
        {
            "date": str(day),
            "attempts": int(total or 0),
            "correct": int(correct or 0),
        }
        for day, total, correct in rows
    ]


def weak_topics(db: Session, user_id: int, *, limit: int = 10) -> list[dict]:
    """Topics ranked by what fixing them is worth.

    Not simply lowest accuracy: a topic worth 8 marks that you fail is a
    bigger problem than one worth 1. The score weights the gap by the
    subject's exam weight, so the list is ordered by marks recoverable
    rather than by embarrassment.
    """
    rows = (
        db.query(
            Topic.id, Topic.name, Topic.slug,
            Subject.name, Subject.slug, Subject.weightage_marks,
            func.count(Attempt.id),
            func.sum(case((Attempt.is_correct, 1), else_=0)),
        )
        .join(Question, Attempt.question_id == Question.id)
        .join(Topic, Question.topic_id == Topic.id)
        .join(Subject, Question.subject_id == Subject.id)
        .filter(Attempt.user_id == user_id)
        .group_by(Topic.id, Topic.name, Topic.slug,
                  Subject.name, Subject.slug, Subject.weightage_marks)
        .having(func.count(Attempt.id) >= MIN_ATTEMPTS_FOR_SIGNAL)
        .all()
    )

    scored = []
    for (tid, tname, tslug, sname, sslug, weight,
         total, correct) in rows:
        total = int(total or 0)
        correct = int(correct or 0)
        accuracy = correct / total if total else 0.0
        # Marks at stake: how much of this subject's weight is being lost.
        recoverable = (1 - accuracy) * float(weight or 1)
        scored.append({
            "topic_id": tid,
            "topic_name": tname,
            "topic_slug": tslug,
            "subject_name": sname,
            "subject_slug": sslug,
            "attempts": total,
            "accuracy": round(accuracy * 100, 1),
            "marks_at_stake": round(recoverable, 2),
        })

    return sorted(scored, key=lambda r: -r["marks_at_stake"])[:limit]


def distractor_analysis(db: Session, user_id: int, *, limit: int = 8) -> list[dict]:
    """Which wrong option gets picked, and how often.

    A consistently chosen wrong answer is a specific misconception, not
    bad luck -- the trap the examiner built. Naming it is more useful than
    telling someone they got the question wrong.
    """
    rows = (
        db.query(
            Question.id, Question.content, Question.options,
            Question.correct_answer, Topic.name,
            MistakeRegistry.last_user_answer, MistakeRegistry.error_count,
        )
        .join(MistakeRegistry, MistakeRegistry.question_id == Question.id)
        .join(Topic, Question.topic_id == Topic.id)
        .filter(
            MistakeRegistry.user_id == user_id,
            MistakeRegistry.error_count >= 2,
        )
        .order_by(MistakeRegistry.error_count.desc())
        .limit(limit)
        .all()
    )

    out = []
    for qid, content, options_json, correct, topic, chosen, errors in rows:
        chosen_text = ""
        if options_json and chosen:
            try:
                for option in json.loads(options_json):
                    if option.get("id") == chosen:
                        chosen_text = option.get("text", "")[:120]
                        break
            except (json.JSONDecodeError, TypeError):
                pass
        out.append({
            "question_id": qid,
            "topic_name": topic,
            "question": (content or "")[:160],
            "your_answer": chosen or "",
            "your_answer_text": chosen_text,
            "correct_answer": correct,
            "times_wrong": int(errors or 0),
        })
    return out


def exam_readiness(db: Session, user_id: int) -> dict:
    """A projected score, and what it rests on.

    Projects from per-subject accuracy against the real mark distribution
    rather than averaging raw accuracy, because a subject worth 15 marks
    and one worth 4 do not contribute equally. Subjects never attempted
    are reported separately instead of being scored as zero -- unknown is
    not the same as bad.
    """
    rows = (
        db.query(
            Subject.name, Subject.slug, Subject.weightage_marks,
            func.count(Attempt.id),
            func.sum(case((Attempt.is_correct, 1), else_=0)),
        )
        .join(Question, Question.subject_id == Subject.id)
        .outerjoin(
            Attempt,
            (Attempt.question_id == Question.id) & (Attempt.user_id == user_id),
        )
        .group_by(Subject.name, Subject.slug, Subject.weightage_marks)
        .all()
    )

    projected = 0.0
    assessed_weight = 0.0
    untested = []

    for name, slug, weight, total, correct in rows:
        weight = float(weight or 0)
        total = int(total or 0)
        if total < MIN_ATTEMPTS_FOR_SIGNAL:
            untested.append({"subject_name": name, "subject_slug": slug,
                             "weightage_marks": weight, "attempts": total})
            continue
        accuracy = int(correct or 0) / total
        projected += accuracy * weight
        assessed_weight += weight

    return {
        "projected_marks": round(projected, 1),
        "assessed_weight": round(assessed_weight, 1),
        "unassessed_weight": round(sum(u["weightage_marks"] for u in untested), 1),
        # Honest about its own basis: a projection from a third of the
        # syllabus is not a score prediction.
        "confidence": (
            "low" if assessed_weight < 30
            else "moderate" if assessed_weight < 70
            else "good"
        ),
        "untested_subjects": sorted(untested, key=lambda u: -u["weightage_marks"]),
    }


def retention(db: Session, user_id: int) -> dict:
    """How much of what was learned is staying learned.

    Lapses are the signal: a card recalled then forgotten means the first
    recall was recognition rather than memory.
    """
    row = (
        db.query(
            func.count(CardView.id),
            func.sum(case((CardView.mastered, 1), else_=0)),
            func.sum(CardView.lapse_count),
            func.sum(case((CardView.recall_count > 0, 1), else_=0)),
        )
        .filter(CardView.user_id == user_id)
        .first()
    )
    seen, mastered, lapses, recalled = (int(v or 0) for v in row)

    due_now = (
        db.query(func.count(CardView.id))
        .filter(CardView.user_id == user_id,
                CardView.due_at.isnot(None),
                CardView.due_at <= datetime.utcnow())
        .scalar() or 0
    )

    concepts = (
        db.query(ConceptProgress.status, func.count(ConceptProgress.id))
        .filter(ConceptProgress.user_id == user_id)
        .group_by(ConceptProgress.status)
        .all()
    )
    by_status = {status: int(count) for status, count in concepts}

    return {
        "cards_seen": seen,
        "cards_recalled": recalled,
        "cards_mastered": mastered,
        "total_lapses": lapses,
        "lapse_rate": round(lapses / recalled * 100, 1) if recalled else 0.0,
        "due_now": int(due_now),
        "concepts_by_status": {
            s: by_status.get(s, 0)
            for s in (ConceptStatus.LEARNING, ConceptStatus.LEARNED,
                      ConceptStatus.REVISED, ConceptStatus.MASTERED)
        },
    }


def exam_behaviour(db: Session, user_id: int) -> dict:
    """What happens inside a timed paper, as distinct from a drill.

    Exam items record the palette state and how many times a question was
    revisited, which drills do not. Questions left unanswered and questions
    marked and never resolved are both marks given away without being
    wrong, and neither shows up in an accuracy figure.
    """
    sessions = (
        db.query(ExamSession)
        .filter(ExamSession.user_id == user_id,
                ExamSession.status == "submitted")
        .all()
    )
    if not sessions:
        return {"sessions": 0}

    session_ids = [s.id for s in sessions]
    rows = (
        db.query(
            ExamItem.state,
            func.count(ExamItem.id),
            func.avg(ExamItem.visit_count),
        )
        .filter(ExamItem.session_id.in_(session_ids))
        .group_by(ExamItem.state)
        .all()
    )
    by_state = {state: int(count) for state, count, _ in rows}
    total_items = sum(by_state.values()) or 1

    revisited = (
        db.query(func.count(ExamItem.id))
        .filter(ExamItem.session_id.in_(session_ids), ExamItem.visit_count > 2)
        .scalar() or 0
    )

    # Marks left on the table by not answering at all.
    unattempted = by_state.get("not_answered", 0) + by_state.get("not_visited", 0)

    return {
        "sessions": len(sessions),
        "items": total_items,
        "by_state": by_state,
        "unattempted": unattempted,
        "unattempted_pct": round(unattempted / total_items * 100, 1),
        # Revisited three or more times: indecision, which costs time.
        "heavily_revisited": int(revisited),
        "avg_accuracy": round(
            sum(s.accuracy or 0 for s in sessions) / len(sessions), 1
        ),
        "best_score": round(max((s.score or 0) for s in sessions), 2),
        "latest_score": round(sessions[-1].score or 0, 2),
    }
