"""SQLite FTS5 keyword search over source chunks.

Vector search alone is weak on exact technical tokens -- "BCNF", "Rice's
theorem", "SJF", "2^10" -- where the user means that literal term and a
semantic near-match is wrong. BM25 handles those precisely, so retrieval
combines both (see hybrid.py).

The FTS table is a shadow of source_chunks, rebuilt from it on demand
rather than kept in sync by triggers: ingestion is batch, so an explicit
reindex is simpler to reason about than trigger ordering.
"""

import logging
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    content,
    chunk_id UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
)
"""

# Keep only characters FTS5's unicode61 tokenizer treats as word content.
# Anything else (quotes, punctuation, operators) is replaced with a space so
# "theorem?" becomes "theorem" rather than a literal that matches nothing.
_NON_TOKEN = re.compile(r"[^0-9A-Za-z\u00c0-\u024f']+")

# Very common words that only add noise when every term is OR-ed.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for",
    "from", "how", "in", "is", "it", "its", "of", "on", "or", "that", "the",
    "to", "vs", "was", "what", "when", "which", "why", "with",
})


def ensure_table(db: Session) -> None:
    db.execute(text(_CREATE))
    db.commit()


def rebuild(db: Session) -> int:
    """Rebuild the whole FTS index from source_chunks."""
    ensure_table(db)
    db.execute(text("DELETE FROM chunk_fts"))
    db.execute(text(
        "INSERT INTO chunk_fts (content, chunk_id) "
        "SELECT content, id FROM source_chunks"
    ))
    db.commit()
    count = db.execute(text("SELECT count(*) FROM chunk_fts")).scalar() or 0
    logger.info("FTS index rebuilt: %d chunks", count)
    return count


def build_match_query(query: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression.

    Terms are OR-ed so a long question still matches partially; without
    this, FTS5's implicit AND makes most natural-language queries return
    nothing.
    """
    cleaned = _NON_TOKEN.sub(" ", query)
    terms = [
        t for t in cleaned.split()
        if len(t) > 1 and t.lower() not in _STOPWORDS
    ]
    if not terms:
        # Every word was a stopword; fall back to them so we return something.
        terms = [t for t in cleaned.split() if t]
    if not terms:
        return ""
    # Dedupe while preserving order.
    seen: set[str] = set()
    unique = [t for t in terms if not (t.lower() in seen or seen.add(t.lower()))]
    return " OR ".join(f'"{t}"' for t in unique)


def search(db: Session, query: str, top_k: int = 8) -> list[tuple[int, float]]:
    """Return (chunk_id, score) pairs, best first. Score is normalised to
    0..1 so it can be fused with cosine similarity."""
    match = build_match_query(query)
    if not match:
        return []

    ensure_table(db)
    rows = db.execute(
        text(
            "SELECT chunk_id, bm25(chunk_fts) AS score FROM chunk_fts "
            "WHERE chunk_fts MATCH :q ORDER BY score LIMIT :k"
        ),
        {"q": match, "k": top_k},
    ).fetchall()

    if not rows:
        return []

    # bm25() returns negative numbers, more negative being a better match.
    scores = [-float(r.score) for r in rows]
    best = max(scores) or 1.0
    return [(int(r.chunk_id), s / best) for r, s in zip(rows, scores)]
