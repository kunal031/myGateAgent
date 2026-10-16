"""Assistant endpoints: ask, continue a thread, explain a card."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.assistant import AssistantMessage, AssistantThread, Language
from ..models.models import FeedCard, Subject
from ..services.assistant import answer, parse_intent
from ..services.assistant.intent import Intent

router = APIRouter(prefix="/api/assistant", tags=["Assistant"])

VALID_LANGUAGES = {Language.ENGLISH, Language.HINDI, Language.HINGLISH}


class AskRequest(BaseModel):
    query: str
    thread_id: int | None = None
    card_id: int | None = None
    language: str | None = None          # overrides the detected language


def _card_intent(card: FeedCard, query: str, language: str | None):
    """The intent for an Explain, taken from the card instead of the model.

    Mirrors what parse_intent would return for a question about this card:
    a chat scoped to the card's own subject.
    """
    return Intent(
        output="chat",
        subject_slug=card.subject.slug if card.subject else None,
        topic=None,
        level=None,
        card_type=None,
        clean_query=query,
        language=language if language in VALID_LANGUAGES else "en",
    )


@router.post("/ask")
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    """Answer a question, or resolve a request for cards into feed filters.

    One endpoint for the single search box: the intent decides whether the
    caller should refill the feed or render a conversation.
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(400, "Ask something")

    card = (
        db.query(FeedCard).filter(FeedCard.id == payload.card_id).first()
        if payload.card_id else None
    )
    if payload.card_id and card is None:
        raise HTTPException(404, "No such card")

    # Intent parsing is an LLM round trip, and with a card there is nothing
    # to decide: Explain is always a conversation about that card, never a
    # request to refile the feed. Skipping it removes ~1.4s from the path
    # the student actually waits on.
    if card is not None:
        intent = _card_intent(card, query, payload.language)
    else:
        intent = parse_intent(db, query)
    language = payload.language if payload.language in VALID_LANGUAGES else intent.language

    # A request for cards is answered with filters, not prose: the client
    # reloads the feed with them rather than rendering a chat turn.
    if intent.output == "feed" and card is None:
        return {
            "output": "feed",
            "filters": {
                "subject_slug": intent.subject_slug,
                "topic": intent.topic,
                "level": intent.level,
                "card_type": intent.card_type,
                "query": intent.clean_query,
            },
            "language": language,
        }

    thread = _thread_for(db, payload, card, language)
    history = list(thread.messages)

    db.add(AssistantMessage(thread_id=thread.id, role="user", content=query))
    db.commit()

    subject_id = None
    if intent.subject_slug:
        subject = db.query(Subject).filter(Subject.slug == intent.subject_slug).first()
        subject_id = subject.id if subject else None

    result = answer(db, query, language=language, subject_id=subject_id,
                    card=card, history=history)

    message = AssistantMessage(
        thread_id=thread.id, role="assistant", content=result.text,
        citations=json.dumps(result.citations),
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return {
        "output": "chat",
        "thread_id": thread.id,
        "message_id": message.id,
        "answer": result.text,
        "citations": result.citations,
        "source_type": result.source_type,
        "language": language,
    }


@router.get("/threads")
def list_threads(limit: int = Query(default=20, le=50),
                 db: Session = Depends(get_db)):
    threads = (
        db.query(AssistantThread)
        .order_by(AssistantThread.updated_at.desc())
        .limit(limit).all()
    )
    return [
        {
            "id": t.id,
            "title": t.title,
            "language": t.language,
            "card_id": t.card_id,
            "message_count": len(t.messages),
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in threads
    ]


@router.get("/threads/{thread_id}")
def get_thread(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(AssistantThread).filter(AssistantThread.id == thread_id).first()
    if thread is None:
        raise HTTPException(404, "No such thread")

    return {
        "id": thread.id,
        "title": thread.title,
        "language": thread.language,
        "card_id": thread.card_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": json.loads(m.citations) if m.citations else [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in thread.messages
        ],
    }


@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(AssistantThread).filter(AssistantThread.id == thread_id).first()
    if thread is None:
        raise HTTPException(404, "No such thread")
    db.delete(thread)
    db.commit()
    return {"deleted": thread_id}


def _thread_for(db: Session, payload: AskRequest, card: FeedCard | None,
                language: str) -> AssistantThread:
    """Continue the named thread, or open one titled after what prompted it."""
    if payload.thread_id:
        thread = (
            db.query(AssistantThread)
            .filter(AssistantThread.id == payload.thread_id).first()
        )
        if thread is None:
            raise HTTPException(404, "No such thread")
        return thread

    title = card.title[:200] if card else payload.query.strip()[:200]
    thread = AssistantThread(
        title=title, language=language,
        card_id=card.id if card else None,
        subject_id=card.subject_id if card else None,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread
