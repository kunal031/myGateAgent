"""Build and refresh the retrieval indexes from source_chunks.

Replaces the old ChromaDB indexer. Both indexes derive from the database,
so they can always be rebuilt and never hold the only copy of anything.
"""

import logging

from sqlalchemy.orm import Session

from ...models.sources import SourceChunk
from . import keyword
from .embeddings import embed_texts
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


def index_pending_chunks(db: Session, *, batch_limit: int | None = None) -> dict:
    """Embed and index any chunk not yet in the vector store.

    Resumable: already-embedded chunks are skipped, so this can be run
    repeatedly as new material is ingested, or after a quota interruption.
    """
    store = VectorStore.load()
    known = set(store.ids)

    pending = (
        db.query(SourceChunk)
        .filter(SourceChunk.id.notin_(known) if known else True)
        .order_by(SourceChunk.id)
    )
    if batch_limit:
        pending = pending.limit(batch_limit)
    chunks = pending.all()

    embedded = 0
    if chunks:
        logger.info("Embedding %d chunks...", len(chunks))
        vectors = embed_texts([c.content for c in chunks])
        # Carry the tags so search can scope without a DB round trip.
        store.add(
            [c.id for c in chunks],
            vectors,
            subject_ids=[c.subject_id for c in chunks],
            topic_ids=[c.topic_id for c in chunks],
        )
        store.save()
        for chunk in chunks:
            chunk.is_embedded = True
        db.commit()
        embedded = len(chunks)

    fts_rows = keyword.rebuild(db)

    return {
        "embedded_now": embedded,
        "vectors_total": len(store),
        "fts_rows": fts_rows,
    }


def index_stats(db: Session) -> dict:
    store = VectorStore.load()
    total_chunks = db.query(SourceChunk).count()
    return {
        "total_chunks": total_chunks,
        "vectors_total": len(store),
        "pending_embedding": max(0, total_chunks - len(store)),
        "vector_dims": int(store.matrix.shape[1]) if len(store) else 0,
    }
