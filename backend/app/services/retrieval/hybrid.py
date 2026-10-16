"""Hybrid retrieval: fuse semantic and keyword results.

Each half covers the other's blind spot. Vectors find a chunk that explains
dependency preservation without using the phrase; BM25 finds the chunk that
says "BCNF" when that exact token is what matters.

Fusion uses Reciprocal Rank Fusion, which combines rankings rather than raw
scores. That matters because cosine similarity and normalised BM25 are not
on comparable scales, so averaging them would let one silently dominate.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ...core.database import IS_SQLITE
from ...models.sources import Source, SourceChunk
from . import keyword
from .embeddings import embed_query
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

# RRF damping. 60 is the value from the original paper and behaves well
# without tuning; lower values weight the top ranks more aggressively.
RRF_K = 60


@dataclass
class Match:
    chunk_id: int
    content: str
    page_number: int
    file_name: str
    citation: str
    score: float
    subject_id: int | None = None
    topic_id: int | None = None


def _rrf(ranked_lists: list[list[int]]) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return scores


def search(
    db: Session,
    query: str,
    *,
    top_k: int = 6,
    subject_id: int | None = None,
    topic_id: int | None = None,
    store: VectorStore | None = None,
    semantic: bool = True,
) -> list[Match]:
    """Retrieve the most relevant chunks for a query.

    Passing subject_id (or the narrower topic_id) scopes the search, which
    matters for accuracy rather than speed: GATE vocabulary collides across
    subjects, so an unscoped query for "deadlock" while studying OS can
    return the DBMS answer. Chunks with no subject tag stay eligible, since
    a cross-subject source such as the mistakes log applies everywhere.

    `semantic=False` skips the embedding API call, which keeps keyword-only
    search available when the Gemini quota is exhausted.
    """
    pool = max(top_k * 4, 20)
    ranked_lists: list[list[int]] = []

    # Both halves come from whichever backend is configured. On Postgres
    # that is tsvector and pgvector; on SQLite, FTS5 and the .npy store.
    if IS_SQLITE:
        kw = keyword.search(db, query, top_k=pool,
                            subject_id=subject_id, topic_id=topic_id)
    else:
        from .pg_search import keyword_search
        kw = keyword_search(db, query, top_k=pool,
                            subject_id=subject_id, topic_id=topic_id)
    if kw:
        ranked_lists.append([cid for cid, _ in kw])

    if semantic:
        try:
            if IS_SQLITE:
                store = store if store is not None else VectorStore.load()
                hits = store.search(
                    embed_query(query), top_k=pool,
                    subject_id=subject_id, topic_id=topic_id,
                ) if len(store) else []
            else:
                from .pg_search import semantic_search
                hits = semantic_search(db, query, top_k=pool,
                                       subject_id=subject_id, topic_id=topic_id)
            if hits:
                ranked_lists.append([cid for cid, _ in hits])
        except Exception as exc:  # quota, network: degrade to keyword only
            logger.warning("Semantic search unavailable (%s); using keyword only", exc)

    if not ranked_lists:
        return []

    fused = _rrf(ranked_lists)
    candidate_ids = sorted(fused, key=lambda c: -fused[c])

    rows = (
        db.query(SourceChunk, Source)
        .join(Source, SourceChunk.source_id == Source.id)
        .filter(SourceChunk.id.in_(candidate_ids[: pool * 2]))
        .all()
    )
    by_id = {chunk.id: (chunk, source) for chunk, source in rows}

    matches: list[Match] = []
    for chunk_id in candidate_ids:
        entry = by_id.get(chunk_id)
        if entry is None:
            continue
        chunk, source = entry
        if topic_id is not None and chunk.topic_id not in (None, topic_id):
            continue
        if subject_id is not None and chunk.subject_id not in (None, subject_id):
            continue
        matches.append(Match(
            chunk_id=chunk.id,
            content=chunk.content,
            page_number=chunk.page_number,
            file_name=source.file_name,
            citation=chunk.citation,
            score=fused[chunk_id],
            subject_id=chunk.subject_id,
            topic_id=chunk.topic_id,
        ))
        if len(matches) >= top_k:
            break

    return matches
