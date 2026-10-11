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
from .rate_limit import (
    DailyQuotaExceeded, generation_limiter, ingest_limiter,
    interactive_limiter, search_limiter,
)

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
        from google.genai import types

        # Without a timeout a stalled socket blocks forever. Two long runs
        # were found wedged at 0% CPU on reads that never returned -- one
        # for two days -- while the API itself was answering normally.
        # tenacity retries TimeoutError, so a request that dies this way is
        # now retried instead of hanging the whole run.
        _client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=settings.GEMINI_REQUEST_TIMEOUT_MS,
            ),
        )
        _apply_socket_timeout(_client)
    return _client


def _apply_socket_timeout(client: "genai.Client") -> None:
    """Force the timeout onto the transport the SDK actually reads from.

    Passing HttpOptions(timeout=...) is not enough: the SDK stores it but
    leaves its httpx client on Timeout(timeout=None). Verified by reading
    the live object -- _http_options.timeout was 180000 while the transport
    said None.

    The consequence is not a slow request but a permanent one. Google's
    endpoint occasionally leaves a half-open socket: the connection stays
    ESTABLISHED, no data ever arrives, and a blocking SSL read waits
    forever. Three long runs were lost to it, one for two days, each
    sitting at 0% CPU inside _ssl__SSLSocket_read while the API answered
    other callers normally.
    """
    import httpx

    seconds = settings.GEMINI_REQUEST_TIMEOUT_MS / 1000
    timeout = httpx.Timeout(seconds, connect=30.0)
    for attr in ("_httpx_client", "_async_httpx_client"):
        transport = getattr(getattr(client, "_api_client", None), attr, None)
        if transport is not None:
            try:
                transport.timeout = timeout
            except Exception:  # pragma: no cover - SDK internals may change
                logger.warning("Could not set a timeout on %s", attr)


# Retry transient faults only. A bad request or an exhausted daily quota is
# not worth retrying, so those propagate immediately.
# httpx raises its own timeout types, which are not TimeoutError, so a
# stalled request would otherwise exhaust no retries at all.
try:  # pragma: no cover - import shape depends on the installed httpx
    import httpx

    _TRANSIENT: tuple[type[BaseException], ...] = (
        TimeoutError, ConnectionError, httpx.TimeoutException,
        httpx.TransportError,
    )
except ImportError:
    _TRANSIENT = (TimeoutError, ConnectionError)

_retry = retry(
    retry=retry_if_exception_type(_TRANSIENT),
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
    interactive: bool = False,
) -> str:
    """Plain text or structured JSON generation.

    `interactive=True` draws on a separate budget, so a request someone is
    waiting on does not queue behind a batch run holding the shared bucket.
    """
    limiter = interactive_limiter if interactive else generation_limiter
    limiter.acquire()

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
    ingest_limiter.acquire()

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
    interactive: bool = False,
) -> dict:
    """Generate with Google Search grounding.

    Returns the text plus the cited sources, so web-derived content can
    always be traced back to a URL.
    """
    # Grounded calls have their own daily budget, but a request someone is
    # waiting on must not queue behind a batch of them either.
    (interactive_limiter if interactive else search_limiter).acquire()

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
