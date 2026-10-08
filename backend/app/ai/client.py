"""Gemini client wrapper: rate limiting, retry, and a single call surface.

Every Gemini call in the app goes through here so quota accounting and
backoff live in one place.
"""

import logging
from typing import Any, Optional

from google import genai
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..core.config import settings
from . import models
from .rate_limit import DailyQuotaExceeded, generation_limiter, search_limiter

logger = logging.getLogger(__name__)

_client: Optional[genai.Client] = None


class GeminiNotConfigured(RuntimeError):
    """Raised when an AI feature is used without GEMINI_API_KEY set."""


def get_client() -> genai.Client:
    global _client
    if not settings.gemini_configured:
        raise GeminiNotConfigured(
            "GEMINI_API_KEY is not set. Copy backend/.env.example to "
            "backend/.env and add your key."
        )
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


# Retry transient faults only. A bad request or an exhausted daily quota is
# not worth retrying, so those propagate immediately.
_retry = retry(
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)


@_retry
def generate_text(
    prompt: str,
    *,
    model: str = models.PRIMARY,
    system_instruction: Optional[str] = None,
    response_mime_type: Optional[str] = None,
    response_schema: Any = None,
    temperature: float = 0.2,
) -> str:
    """Plain text or structured JSON generation."""
    generation_limiter.acquire()

    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction,
        response_mime_type=response_mime_type,
        response_schema=response_schema,
    )
    response = get_client().models.generate_content(
        model=model, contents=prompt, config=config
    )
    return (response.text or "").strip()


@_retry
def transcribe_image(
    image_bytes: bytes,
    prompt: str,
    *,
    model: str = models.PRIMARY,
    mime_type: str = "image/png",
    temperature: float = 0.0,
) -> str:
    """Transcribe a rendered page image. Temperature 0: copying, not creating."""
    generation_limiter.acquire()

    response = get_client().models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(temperature=temperature),
    )
    return (response.text or "").strip()


@_retry
def generate_grounded(
    prompt: str,
    *,
    model: str = models.PRIMARY,
    temperature: float = 0.2,
) -> dict:
    """Generate with Google Search grounding.

    Returns the text plus the cited sources, so web-derived content can
    always be traced back to a URL.
    """
    search_limiter.acquire()

    response = get_client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    citations = []
    try:
        metadata = response.candidates[0].grounding_metadata
        for chunk in (getattr(metadata, "grounding_chunks", None) or []):
            web = getattr(chunk, "web", None)
            if web is not None:
                citations.append({
                    "title": getattr(web, "title", "") or "",
                    "uri": getattr(web, "uri", "") or "",
                })
    except (AttributeError, IndexError, TypeError):
        logger.warning("No grounding metadata on a grounded response")

    return {"text": (response.text or "").strip(), "citations": citations}


__all__ = [
    "DailyQuotaExceeded",
    "GeminiNotConfigured",
    "generate_grounded",
    "generate_text",
    "get_client",
    "transcribe_image",
]
