"""Fetch a question page and reduce it to readable text.

Question pages are mostly navigation, adverts and sign-up prompts. Feeding
the raw HTML to a model wastes most of the context window on furniture, so
the markup is stripped to text first and the parsing stage sees only the
part that could plausibly hold questions.
"""

import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

#: A page that answers slower than this is not worth waiting on.
TIMEOUT_SECONDS = 45

#: Enough for a long topic-wise page; beyond this the parse is split.
MAX_TEXT_CHARS = 180_000

#: Some sites serve a stub to unknown clients.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

#: Elements that never carry question content.
_STRIP_TAGS = (
    "script", "style", "noscript", "nav", "header", "footer", "svg",
    "iframe", "form", "button", "aside",
)

_BLANK_LINES = re.compile(r"\n{3,}")


class FetchError(RuntimeError):
    """The page could not be retrieved or held no usable text."""


def fetch_url(url: str) -> dict:
    """Return {"text", "title", "url"} for a question page.

    Redirects are followed: these pages are frequently served from a
    canonical path that differs from the one shared.
    """
    if not url.startswith(("http://", "https://")):
        raise FetchError("That does not look like a web address")

    try:
        with httpx.Client(
            timeout=TIMEOUT_SECONDS, follow_redirects=True, headers=HEADERS,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise FetchError(
            f"The page returned {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise FetchError(f"Could not reach that page: {exc}") from exc

    text, title = html_to_text(response.text)
    if len(text) < 200:
        raise FetchError(
            "That page has almost no text. It may require signing in, or "
            "render its questions with JavaScript."
        )
    return {"text": text, "title": title, "url": str(response.url)}


def html_to_text(html: str) -> tuple[str, str]:
    """Strip markup to text, keeping block structure.

    Line breaks are preserved between blocks because question boundaries
    depend on them: options sit on their own lines, and collapsing those
    into one paragraph makes a question and its choices indistinguishable.
    """
    soup = BeautifulSoup(html, "lxml")

    title = soup.title.get_text(strip=True) if soup.title else ""

    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    # Code blocks carry significant whitespace -- a C program in a question
    # stem is unreadable once its indentation is normalised away.
    for pre in soup.find_all(("pre", "code")):
        pre.string = "\n" + pre.get_text() + "\n"

    text = soup.get_text("\n")
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    text = _BLANK_LINES.sub("\n\n", text)

    return text[:MAX_TEXT_CHARS], title
