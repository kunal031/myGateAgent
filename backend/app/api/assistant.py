"""Assistant endpoints: ask, continue a thread, explain a card."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import current_user
from ..core.background import dispatch, register
from ..core.database import get_db
from ..models.assistant import AssistantMessage, AssistantThread, Language
from ..models.models import FeedCard, Subject
from ..models.users import User
from ..services.assistant import answer, parse_intent
from ..services.assistant.intent import Intent

logger = logging.getLogger(__name__)

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
def ask(payload: AskRequest, db: Session = Depends(get_db),
        user: User = Depends(current_user)):
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

    thread = _thread_for(db, payload, card, language, user.id)
    history = list(thread.messages)

    db.add(AssistantMessage(thread_id=thread.id, role="user", content=query))
    db.commit()

    subject_id = None
    if intent.subject_slug:
        subject = db.query(Subject).filter(Subject.slug == intent.subject_slug).first()
        subject_id = subject.id if subject else None

    # A placeholder, so the conversation renders in order and the client
    # has an id to poll. Written before generation starts rather than
    # after, because on Lambda generation happens in another process.
    message = AssistantMessage(
        thread_id=thread.id, role="assistant", content="",
        citations="[]", status="pending",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    dispatch(
        "answer_question",
        message_id=message.id, query=query, language=language,
        subject_id=subject_id, card_id=card.id if card else None,
    )

    return {
        "output": "chat",
        "thread_id": thread.id,
        "message_id": message.id,
        # No answer yet. The client polls the thread, which is what keeps
        # a 60-second Gemini call from hitting API Gateway's 29s ceiling.
        "status": "pending",
        "answer": "",
        "citations": [],
        "language": language,
    }


def _student_facing_error(exc: BaseException) -> str:
    """Turn a provider failure into something worth reading.

    "Fallback provider is rate limited" is accurate and useless to
    someone mid-study: it names our plumbing and implies a bug. The
    free tier's token-per-minute budget fits about two questions a
    minute, so the honest answer is to say so and name the wait.
    """
    from ..ai.fallback import FallbackRateLimited

    if isinstance(exc, FallbackRateLimited):
        return (
            "The free AI tier only allows a couple of questions a minute, "
            "and this one went over. Wait about a minute and ask again — "
            "your place in the conversation is kept."
        )
    return str(exc)[:500]


@register("answer_question")
def answer_question(db: Session, *, message_id: int, query: str,
                    language: str, subject_id: int | None = None,
                    card_id: int | None = None) -> None:
    """Generate an answer and fill in its placeholder message.

    Runs in the worker, which has fifteen minutes rather than the API's
    twenty-nine seconds. Retrieval, grading and generation are unchanged;
    only where they run has moved.
    """
    message = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.id == message_id)
        .first()
    )
    if message is None:
        return

    try:
        card = (
            db.query(FeedCard).filter(FeedCard.id == card_id).first()
            if card_id else None
        )
        history = [
            m for m in message.thread.messages
            if m.id != message_id and m.status == "ready"
        ]
        result = answer(db, query, language=language, subject_id=subject_id,
                        card=card, history=history)
        message.content = result.text
        message.citations = json.dumps(result.citations)
        message.status = "ready"
    except Exception as exc:
        logger.exception("Answer generation failed for message %s", message_id)
        # Recorded on the row rather than raised into nothing: the request
        # that asked has long since returned, so this is the only place
        # the student can be told.
        message.status = "failed"
        message.error = _student_facing_error(exc)
    finally:
        db.commit()


@router.get("/threads")
def list_threads(limit: int = Query(default=20, le=50),
                 db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    threads = (
        db.query(AssistantThread)
        .filter(AssistantThread.user_id == user.id)
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
def get_thread(thread_id: int, db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    # 404 rather than 403 on someone else's thread: a 403 confirms it exists.
    thread = db.query(AssistantThread).filter(
        AssistantThread.id == thread_id,
        AssistantThread.user_id == user.id,
    ).first()
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
                # The client polls this thread while any message is
                # pending; without the status it cannot tell a generating
                # answer from an empty one.
                "status": m.status or "ready",
                "error": m.error or "",
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in thread.messages
        ],
        # Saves the client inspecting every message to decide whether to
        # keep polling.
        "pending": any(m.status == "pending" for m in thread.messages),
    }


@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    thread = db.query(AssistantThread).filter(
        AssistantThread.id == thread_id,
        AssistantThread.user_id == user.id,
    ).first()
    if thread is None:
        raise HTTPException(404, "No such thread")
    db.delete(thread)
    db.commit()
    return {"deleted": thread_id}


def _thread_for(db: Session, payload: AskRequest, card: FeedCard | None,
                language: str, user_id: int) -> AssistantThread:
    """Continue the named thread, or open one titled after what prompted it."""
    if payload.thread_id:
        thread = (
            db.query(AssistantThread)
            .filter(AssistantThread.id == payload.thread_id,
                    AssistantThread.user_id == user_id)
            .first()
        )
        if thread is None:
            raise HTTPException(404, "No such thread")
        return thread

    title = card.title[:200] if card else payload.query.strip()[:200]
    thread = AssistantThread(
        user_id=user_id,
        title=title, language=language,
        card_id=card.id if card else None,
        subject_id=card.subject_id if card else None,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread
