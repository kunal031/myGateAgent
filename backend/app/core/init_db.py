from sqlalchemy.orm import Session
from .database import engine, SessionLocal, Base
from ..models.models import Subject, Topic, Question, FeedCard
from ..models.sources import Source, SourceChunk  # noqa: F401  (register tables)
from ..models.concepts import Concept, ConceptProgress  # noqa: F401
from ..data.syllabus import SYLLABUS_DATA
from ..data.seeds import SEED_FEED_CARDS, SEED_QUESTIONS

def init_database():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # Check if already seeded
        existing_subjects = db.query(Subject).count()
        if existing_subjects == 0:
            print("Seeding syllabus subjects and topics...")
            subject_map = {}
            topic_map = {}

            for s_data in SYLLABUS_DATA:
                subject = Subject(
                    name=s_data["name"],
                    slug=s_data["slug"],
                    icon=s_data.get("icon", "BookOpen"),
                    description=s_data.get("description", ""),
                    weightage_marks=s_data.get("weightage_marks", 8.0)
                )
                db.add(subject)
                db.flush()
                subject_map[subject.slug] = subject.id

                for t_data in s_data.get("topics", []):
                    topic = Topic(
                        subject_id=subject.id,
                        name=t_data["name"],
                        slug=t_data["slug"],
                        importance=t_data.get("importance", "High")
                    )
                    db.add(topic)
                    db.flush()
                    topic_map[f"{subject.slug}:{topic.slug}"] = topic.id

            db.commit()

            # Seed Feed Cards
            print("Seeding initial feed cards...")
            for fc in SEED_FEED_CARDS:
                sub_id = subject_map.get(fc["subject_slug"])
                top_id = topic_map.get(f"{fc['subject_slug']}:{fc['topic_slug']}")
                if sub_id and top_id:
                    card = FeedCard(
                        subject_id=sub_id,
                        topic_id=top_id,
                        card_type=fc["card_type"],
                        title=fc["title"],
                        content=fc["content"],
                        takeaway=fc["takeaway"],
                        difficulty=fc["difficulty"],
                        base_weight=fc.get("base_weight", 1)
                    )
                    db.add(card)

            # Seed Questions
            print("Seeding initial GATE questions...")
            for q in SEED_QUESTIONS:
                sub_id = subject_map.get(q["subject_slug"])
                top_id = topic_map.get(f"{q['subject_slug']}:{q['topic_slug']}")
                if sub_id and top_id:
                    question = Question(
                        subject_id=sub_id,
                        topic_id=top_id,
                        question_type=q["question_type"],
                        marks=q["marks"],
                        negative_marks=q["negative_marks"],
                        content=q["content"],
                        options=q["options"],
                        correct_answer=q["correct_answer"],
                        nat_min=q["nat_min"],
                        nat_max=q["nat_max"],
                        explanation=q["explanation"],
                        difficulty=q["difficulty"],
                        source=q.get("source", "GATE CSE"),
                        is_pyq=q.get("is_pyq", False)
                    )
                    db.add(question)

            db.commit()
            print("Database initialized & seeded successfully!")
        else:
            print(f"Database already contains {existing_subjects} subjects.")
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
