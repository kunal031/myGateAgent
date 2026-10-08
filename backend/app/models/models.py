from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from ..core.database import Base

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    icon = Column(String(50), default="BookOpen")
    description = Column(Text, default="")
    weightage_marks = Column(Float, default=8.0)  # average historical weightage

    topics = relationship("Topic", back_populates="subject", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="subject")
    feed_cards = relationship("FeedCard", back_populates="subject")

class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    name = Column(String(150), nullable=False)
    slug = Column(String(150), index=True, nullable=False)
    importance = Column(String(20), default="High")  # High, Medium, Core

    subject = relationship("Subject", back_populates="topics")
    questions = relationship("Question", back_populates="topic")
    feed_cards = relationship("FeedCard", back_populates="topic")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    
    # MCQ: Multiple Choice (1 option), MSQ: Multiple Select (1+ options), NAT: Numerical Answer Type
    question_type = Column(String(10), nullable=False, default="MCQ")
    marks = Column(Integer, default=1)  # 1 or 2
    negative_marks = Column(Float, default=0.33)  # 0.33 for 1M MCQ, 0.66 for 2M MCQ, 0.0 for MSQ/NAT
    
    content = Column(Text, nullable=False)
    options = Column(Text, nullable=True)  # JSON-encoded array of options [{"id": "A", "text": "..."}]
    correct_answer = Column(String(255), nullable=False)  # "A" or "A,C" or "14.5"
    nat_min = Column(Float, nullable=True)
    nat_max = Column(Float, nullable=True)
    
    explanation = Column(Text, nullable=False)
    difficulty = Column(String(20), default="Standard GATE")  # Foundational, Standard GATE, Rank Booster
    source = Column(String(100), default="GATE CSE")
    is_pyq = Column(Boolean, default=False)

    subject = relationship("Subject", back_populates="questions")
    topic = relationship("Topic", back_populates="questions")
    attempts = relationship("Attempt", back_populates="question")

class FeedCard(Base):
    __tablename__ = "feed_cards"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    
    # Ordered study unit this card teaches. Nullable so the hand-written
    # seed cards predating the concept model keep working.
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=True, index=True)

    # Which pass through the chapter this card belongs to: BASIC introduces,
    # ADVANCED goes deep, REVISION recalls.
    mode = Column(String(20), default="ADVANCED", index=True)

    # Position within the concept, so BASIC can be walked in order.
    sequence = Column(Integer, default=0)

    # Where this card came from. Generated cards must cite a source chunk;
    # see services/generation. Empty means hand-authored seed content.
    provenance = Column(Text, default="")
    source_chunk_ids = Column(String(200), default="")
    review_status = Column(String(20), default="approved", index=True)

    card_type = Column(String(20), default="CONCEPT")  # TRAP, FORMULA, CONCEPT, SHORTCUT
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    takeaway = Column(Text, nullable=False)
    difficulty = Column(String(20), default="Standard")
    base_weight = Column(Integer, default=1)

    subject = relationship("Subject", back_populates="feed_cards")
    topic = relationship("Topic", back_populates="feed_cards")

class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    user_answer = Column(String(255), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    marks_obtained = Column(Float, default=0.0)
    time_spent_seconds = Column(Integer, default=0)
    mode = Column(String(20), default="quiz")  # quiz, test, feed
    created_at = Column(DateTime, default=datetime.utcnow)

    question = relationship("Question", back_populates="attempts")

class MistakeRegistry(Base):
    __tablename__ = "mistake_registry"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    error_count = Column(Integer, default=1)
    last_user_answer = Column(String(255), default="")
    mastery_level = Column(Integer, default=0)  # 0 to 5
    last_attempted_at = Column(DateTime, default=datetime.utcnow)
