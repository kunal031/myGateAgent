"""Extract text from a source file.

PDFs with a usable text layer are read directly (free). Scanned pages go to
Gemini vision, cached per page so an interrupted run never re-transcribes
work it already paid for.
"""

import hashlib
import logging
import re
from pathlib import Path

import pymupdf

from ...ai import client as ai_client
from ...core.config import settings

logger = logging.getLogger(__name__)

TRANSCRIBE_PROMPT = """Transcribe this page of handwritten or printed GATE CSE
study notes into Markdown.

- Use LaTeX for all mathematics: $...$ inline, $$...$$ for display.
- Preserve tables, lists and the structure of worked examples.
- Transcribe only what is on the page. Do not explain or add anything.
- If the page is blank, decorative, or has no study content, reply with
  exactly: EMPTY_PAGE"""

EMPTY_MARKER = "EMPTY_PAGE"
RENDER_DPI = 150

# Below this average line length, a text layer is shattered rather than
# readable and the page is better transcribed from the image.
MIN_AVG_LINE_CHARS = 20

# Watermarks and boilerplate that appear on every page of some sources and
# would otherwise look like a usable text layer.
_NOISE = re.compile(r"Priyanshu|x\.com/|GATE \d{4} AIR", re.I)

# Bad OCR signature: <br> soup with little real prose.
_BR_SOUP = re.compile(r"<br\s*/?>", re.I)

# PDF text layers sometimes carry control characters. PostgreSQL rejects a
# NUL outright, and the rest are noise, so they are stripped at extraction
# rather than left for the database to reject mid-transaction.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitise(text: str) -> str:
    return _CONTROL.sub(" ", text)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def page_has_usable_text(page) -> bool:
    """True when the embedded text layer is worth using as-is.

    Some digital PDFs carry a text layer that extracts one word per line
    with words split mid-token ("INTR ODUCTION", "R UN-TIME ENVIR ONMENTS").
    It is technically text, but generating from it produces nonsense, so a
    page whose lines are too short goes to vision like a scan.
    """
    text = sanitise(_NOISE.sub("", page.get_text("text"))).strip()
    if len(text) < 200:
        return False
    if len(_BR_SOUP.findall(text)) >= len(text) / 120:
        return False

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    # Healthy prose averages well over 20 characters a line; a shattered
    # layer averages about 3.
    return sum(len(line) for line in lines) / len(lines) >= MIN_AVG_LINE_CHARS


def _cache_path(content_hash: str, page_number: int) -> Path:
    return settings.TRANSCRIPT_CACHE_DIR / content_hash / f"p{page_number:04d}.md"


def transcribe_page(page, content_hash: str, page_number: int) -> str:
    """Vision-transcribe one page, reading and writing the on-disk cache."""
    cached = _cache_path(content_hash, page_number)
    if cached.exists():
        return cached.read_text(encoding="utf-8")

    png = page.get_pixmap(dpi=RENDER_DPI).tobytes("png")
    text = ai_client.transcribe_image(png, TRANSCRIBE_PROMPT)

    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(text, encoding="utf-8")
    return text


def file_has_text_layer(doc, *, samples: int = 5) -> bool:
    """Whether the document's body carries a usable text layer.

    Sampled from the body, because front matter -- cover, contents, preface
    -- is often imaged even in a digital edition.
    """
    total = len(doc)
    if total == 0:
        return False
    step = max(1, total // (samples + 1))
    indexes = [min(total - 1, step * (i + 1)) for i in range(samples)]
    usable = sum(1 for i in indexes if page_has_usable_text(doc[i]))
    return usable >= max(1, len(indexes) // 2)


def extract_pdf_pages(
    path: Path, content_hash: str, *, max_pages: int | None = None
) -> list[dict]:
    """Return [{page_number, text, method}] for every page with content.

    A document with a good text layer never falls back to vision. Its
    occasional blank page is front matter or a full-page figure, and paying
    six seconds of quota to transcribe a cover page is waste -- Cormen's
    first forty pages alone would cost forty calls.
    """
    pages: list[dict] = []
    doc = pymupdf.open(path)
    try:
        has_text_layer = file_has_text_layer(doc)
        total = len(doc) if max_pages is None else min(len(doc), max_pages)
        for index in range(total):
            page = doc[index]
            number = index + 1

            if page_has_usable_text(page):
                text, method = page.get_text("text").strip(), "DIRECT"
            elif has_text_layer:
                continue  # front matter or a figure; not worth a vision call
            else:
                text, method = transcribe_page(page, content_hash, number), "VISION"

            text = sanitise(_NOISE.sub("", text)).strip()
            if text and EMPTY_MARKER not in text:
                pages.append({"page_number": number, "text": text, "method": method})
    finally:
        doc.close()
    return pages
