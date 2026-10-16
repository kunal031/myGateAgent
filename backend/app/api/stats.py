from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..core.auth import current_user
from ..core.database import get_db
from ..models.models import Attempt, MistakeRegistry, Subject, Topic, Question
from ..models.users import User

router = APIRouter(prefix="/api/stats", tags=["Stats"])

@router.get("/summary")
def get_stats_summary(db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    """One student's performance.

    Every count here is scoped: unscoped, the analytics would report the
    combined accuracy of everyone using the instance, which is worse than
    useless -- it reads as your own and is not.
    """
    mine = Attempt.user_id == user.id
    total_attempts = db.query(Attempt).filter(mine).count()
    correct_attempts = db.query(Attempt).filter(mine, Attempt.is_correct == True).count()
    accuracy = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0.0
    
    total_marks_earned = (
        db.query(func.sum(Attempt.marks_obtained)).filter(mine).scalar() or 0.0
    )
    active_mistakes_count = db.query(MistakeRegistry).filter(
        MistakeRegistry.user_id == user.id,
        MistakeRegistry.mastery_level < 3,
    ).count()
    
    # Subject breakdown
    subjects = db.query(Subject).all()
    subject_stats = []
    
    for s in subjects:
        sub_attempts = (
            db.query(Attempt).join(Question)
            .filter(Question.subject_id == s.id, mine).all()
        )
        sub_total = len(sub_attempts)
        sub_correct = sum(1 for a in sub_attempts if a.is_correct)
        sub_acc = (sub_correct / sub_total * 100) if sub_total > 0 else 0.0
        sub_marks = sum(a.marks_obtained for a in sub_attempts)
        
        # Count unresolved mistakes in this subject
        sub_mistakes = db.query(MistakeRegistry).filter(
            MistakeRegistry.subject_id == s.id,
            MistakeRegistry.user_id == user.id,
            MistakeRegistry.mastery_level < 3
        ).count()
        
        subject_stats.append({
            "subject_id": s.id,
            "subject_name": s.name,
            "subject_slug": s.slug,
            "weightage_marks": s.weightage_marks,
            "attempts": sub_total,
            "accuracy": round(sub_acc, 1),
            "marks_earned": round(sub_marks, 2),
            "unresolved_mistakes": sub_mistakes
        })
        
    return {
        "total_attempts": total_attempts,
        "correct_attempts": correct_attempts,
        "accuracy": round(accuracy, 1),
        "total_marks_earned": round(total_marks_earned, 2),
        "active_mistakes_count": active_mistakes_count,
        "subject_stats": subject_stats
    }


@router.get("/deep")
def deep_analytics(db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    """Everything the attempt history can say, in one call.

    One endpoint rather than eight: the analytics page shows all of it at
    once, and eight round trips on mobile data is the wrong trade. Each
    section is independently computed, so a section with no data returns
    its empty shape rather than failing the request.
    """
    from ..services.analytics import performance as perf

    return {
        "by_question_type": perf.accuracy_by_question_type(db, user.id),
        "pace": perf.pace(db, user.id),
        "trend": perf.trend(db, user.id),
        "daily_activity": perf.daily_activity(db, user.id),
        "weak_topics": perf.weak_topics(db, user.id),
        "distractors": perf.distractor_analysis(db, user.id),
        "readiness": perf.exam_readiness(db, user.id),
        "retention": perf.retention(db, user.id),
        "exam_behaviour": perf.exam_behaviour(db, user.id),
    }


@router.get("/insights")
def insights(db: Session = Depends(get_db),
             user: User = Depends(current_user)):
    """The handful of observations worth acting on today.

    Analytics that only describe are easy to ignore. These are phrased as
    findings with a next step, and only appear when the data supports
    them -- an insight drawn from three attempts is a guess.
    """
    from ..services.analytics import performance as perf

    found: list[dict] = []

    pace_data = perf.pace(db, user.id)
    if pace_data.get("samples", 0) >= 10:
        rushed = pace_data.get("rushed_errors", 0)
        if rushed >= pace_data["samples"] * 0.25:
            found.append({
                "kind": "pace",
                "severity": "high",
                "title": "Many wrong answers came quickly",
                "detail": (
                    f"{rushed} of {pace_data['samples']} attempts were wrong "
                    f"in under a third of the time budget. That pattern is "
                    f"usually misreading the question, not a gap in the topic."
                ),
                "action": "Re-read the question stem before answering.",
            })
        if pace_data.get("slow_and_wrong", 0) >= 3:
            found.append({
                "kind": "pace",
                "severity": "medium",
                "title": "Time spent without marks",
                "detail": (
                    f"{pace_data['slow_and_wrong']} questions ran over the "
                    f"time budget and were still wrong."
                ),
                "action": "Set a hard limit and move on; come back if time allows.",
            })

    types = perf.accuracy_by_question_type(db, user.id)
    for row in types:
        if row["attempts"] >= 5 and row["accuracy"] < 40:
            found.append({
                "kind": "question_type",
                "severity": "high",
                "title": f"{row['question_type']} questions are costing marks",
                "detail": (
                    f"{row['accuracy']}% across {row['attempts']} attempts."
                    + (" MSQ has no partial credit, so one wrong tick loses "
                       "the whole mark." if row["question_type"] == "MSQ" else "")
                ),
                "action": f"Drill {row['question_type']} specifically.",
            })

    weak = perf.weak_topics(db, user.id, limit=3)
    for row in weak:
        if row["marks_at_stake"] >= 2:
            found.append({
                "kind": "topic",
                "severity": "high" if row["marks_at_stake"] >= 4 else "medium",
                "title": f"{row['topic_name'][:48]} is worth revisiting",
                "detail": (
                    f"{row['accuracy']}% across {row['attempts']} attempts in "
                    f"{row['subject_name']}, which carries "
                    f"{row['marks_at_stake']} recoverable marks."
                ),
                "action": "Open this topic in the feed.",
            })

    readiness = perf.exam_readiness(db, user.id)
    if readiness["unassessed_weight"] >= 30:
        top = readiness["untested_subjects"][:2]
        names = ", ".join(s["subject_name"] for s in top)
        found.append({
            "kind": "coverage",
            "severity": "medium",
            "title": "Most of the syllabus is untested",
            "detail": (
                f"{readiness['unassessed_weight']} marks' worth of subjects "
                f"have too few attempts to judge, starting with {names}."
            ),
            "action": "Take a short quiz in each to get a baseline.",
        })

    behaviour = perf.exam_behaviour(db, user.id)
    if behaviour.get("sessions", 0) and behaviour.get("unattempted_pct", 0) > 15:
        found.append({
            "kind": "exam",
            "severity": "high",
            "title": "Questions are being left unanswered",
            "detail": (
                f"{behaviour['unattempted_pct']}% of questions across "
                f"{behaviour['sessions']} papers were never answered."
            ),
            "action": "MSQ and NAT carry no negative marking -- always attempt them.",
        })

    retention_data = perf.retention(db, user.id)
    if retention_data["due_now"] >= 10:
        found.append({
            "kind": "revision",
            "severity": "medium",
            "title": f"{retention_data['due_now']} cards are due",
            "detail": "Spaced repetition only works if the reviews happen.",
            "action": "Clear the due queue in the feed.",
        })

    order = {"high": 0, "medium": 1, "low": 2}
    found.sort(key=lambda i: order.get(i["severity"], 3))
    return {"insights": found, "count": len(found)}
