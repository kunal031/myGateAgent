"""Retrieval against PostgreSQL: pgvector for semantic, tsvector for keyword.

Replaces the .npy vector store and SQLite FTS5 when running on Postgres.
Both halves return (chunk_id, score) in the same shape the hybrid fusion
already expects, so nothing above this layer changes.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from .embeddings import embed_query

logger = logging.getLogger(__name__)


def semantic_search(
    db: Session,
    query: str,
    top_k: int = 8,
    *,
    subject_id: int | None = None,
    topic_id: int | None = None,
) -> list[tuple[int, float]]:
    """Nearest chunks by cosine distance, using the HNSW index.

    Untagged chunks stay eligible at every scope: a cross-subject source
    such as the mistakes log is relevant whichever subject is being studied.
    """
    vector = embed_query(query)
    literal = "[" + ",".join(f"{v:.6f}" for v in vector) + "]"

    where = ["embedding IS NOT NULL"]
    params: dict = {"q": literal, "k": top_k}
    if topic_id is not None:
        where.append("(topic_id = :topic_id OR topic_id IS NULL)")
        params["topic_id"] = topic_id
    elif subject_id is not None:
        where.append("(subject_id = :subject_id OR subject_id IS NULL)")
        params["subject_id"] = subject_id

    sql = (
        "SELECT id, 1 - (embedding <=> CAST(:q AS halfvec)) AS score "
        "FROM source_chunks "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY embedding <=> CAST(:q AS halfvec) "
        "LIMIT :k"
    )
    rows = db.execute(text(sql), params).fetchall()
    return [(int(r.id), float(r.score)) for r in rows]


def keyword_search(
    db: Session,
    query: str,
    top_k: int = 8,
    *,
    subject_id: int | None = None,
    topic_id: int | None = None,
) -> list[tuple[int, float]]:
    """Full-text match ranked by ts_rank_cd, normalised to 0..1.

    websearch_to_tsquery accepts natural phrasing and never raises on odd
    punctuation, unlike the hand-built FTS5 expression this replaces.
    """
    where = ["to_tsvector('english', content) @@ websearch_to_tsquery('english', :q)"]
    params: dict = {"q": query, "k": top_k}
    if topic_id is not None:
        where.append("(topic_id = :topic_id OR topic_id IS NULL)")
        params["topic_id"] = topic_id
    elif subject_id is not None:
        where.append("(subject_id = :subject_id OR subject_id IS NULL)")
        params["subject_id"] = subject_id

    sql = (
        "SELECT id, ts_rank_cd(to_tsvector('english', content), "
        "       websearch_to_tsquery('english', :q)) AS score "
        "FROM source_chunks "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY score DESC LIMIT :k"
    )
    rows = db.execute(text(sql), params).fetchall()
    if not rows:
        return []

    best = max(float(r.score) for r in rows) or 1.0
    return [(int(r.id), float(r.score) / best) for r in rows]
