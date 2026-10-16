"""Split extracted page text into retrievable chunks.

Chunks are page-scoped so every one keeps an exact citation. Splitting
prefers paragraph breaks, because cutting mid-derivation produces chunks
that retrieve well but read as nonsense in a generated card.
"""

CHUNK_CHARS = 1400
OVERLAP_CHARS = 200
MIN_CHUNK_CHARS = 120


def chunk_page(text: str) -> list[str]:
    text = text.strip()
    if len(text) <= CHUNK_CHARS:
        return [text] if len(text) >= MIN_CHUNK_CHARS else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))

        if end < len(text):
            window = text[start:end]
            # Prefer a paragraph break, then a sentence end, in the last
            # third of the window.
            for sep in ("\n\n", ". ", "\n"):
                cut = window.rfind(sep)
                if cut > CHUNK_CHARS * 0.6:
                    end = start + cut + len(sep)
                    break

        body = text[start:end].strip()
        if len(body) >= MIN_CHUNK_CHARS:
            chunks.append(body)

        if end >= len(text):
            break
        start = max(end - OVERLAP_CHARS, start + 1)

    return chunks
