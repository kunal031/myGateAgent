from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from ..core.database import get_db
from ..models.models import FeedCard, Subject, Topic, MistakeRegistry

router = APIRouter(prefix="/api/feed", tags=["Feed"])

@router.get("")
def get_feed(
    subject_slug: Optional[str] = None,
    card_type: Optional[str] = None,
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db)
):
    # Explicit ON clauses: see the note in api/quiz.py. A bare chained join
    # here inflated 6 cards into 30 rows.
    query = (
        db.query(FeedCard)
        .join(Subject, FeedCard.subject_id == Subject.id)
        .join(Topic, FeedCard.topic_id == Topic.id)
    )
    
    if subject_slug and subject_slug != "all":
        query = query.filter(Subject.slug == subject_slug)
    if card_type and card_type != "all":
        query = query.filter(FeedCard.card_type == card_type)
        
    cards = query.all()
    
    # Calculate mistake boost for each card
    # Get all mistakes grouped by topic
    mistake_counts = {}
    mistakes = db.query(MistakeRegistry).all()
    for m in mistakes:
        mistake_counts[m.topic_id] = mistake_counts.get(m.topic_id, 0) + m.error_count
        
    enriched_cards = []
    for card in cards:
        topic_mistakes = mistake_counts.get(card.topic_id, 0)
        boost = topic_mistakes * 3
        effective_weight = card.base_weight + boost
        
        enriched_cards.append({
            "id": card.id,
            "subject_name": card.subject.name,
            "subject_slug": card.subject.slug,
            "topic_name": card.topic.name,
            "topic_slug": card.topic.slug,
            "card_type": card.card_type,
            "title": card.title,
            "content": card.content,
            "takeaway": card.takeaway,
            "difficulty": card.difficulty,
            "effective_weight": effective_weight,
            "is_remedial": topic_mistakes > 0,
            "recent_mistakes_in_topic": topic_mistakes
        })
        
    # Sort by effective weight descending
    enriched_cards.sort(key=lambda x: x["effective_weight"], reverse=True)
    return enriched_cards[:limit]
