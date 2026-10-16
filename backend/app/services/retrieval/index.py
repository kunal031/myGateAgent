"""Build and refresh the retrieval indexes from source_chunks.

Replaces the old ChromaDB indexer. Both indexes derive from the database,
so they can always be rebuilt and never hold the only copy of anything.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from ...core.database import IS_SQLITE
from ...models.sources import SourceChunk
from . import keyword
from .embeddings import EMBED_DIMS, embed_texts
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

# Persist progress every this many chunks, so an interrupted run resumes
# instead of starting over. Sized to give the concurrent embedder a full
# set of batches per slice (960 / 32 = 30 in flight).
SAVE_EVERY = 960


def _vector_count(db: Session, store) -> int:
    """How many chunks actually have a vector, per backend."""
    if IS_SQLITE:
        return len(store)
    return int(
        db.execute(
            text("SELECT count(embedding) FROM source_chunks")
        ).scalar() or 0
    )


def _store_vectors_pg(db: Session, chunks: list, vectors) -> None:
    """Write embeddings onto the chunk rows themselves.

    pg_search reads source_chunks.embedding, so this is the only place the
    vectors become visible to retrieval. The literal format matches the cast
    used when querying, keeping one representation across write and read.
    """
    for chunk, vector in zip(chunks, vectors):
        literal = "[" + ",".join(f"{v:.6f}" for v in vector) + "]"
        db.execute(
            text(
                "UPDATE source_chunks "
                "SET embedding = CAST(:v AS halfvec), is_embedded = true "
                "WHERE id = :id"
            ),
            {"v": literal, "id": chunk.id},
        )


def index_pending_chunks(db: Session, *, batch_limit: int | None = None) -> dict:
    """Embed and index any chunk not yet embedded.

    Resumable: already-embedded chunks are skipped, so this can be run
    repeatedly as new material is ingested, or after a quota interruption.

    Where the vectors land depends on the backend. On Postgres they go in
    source_chunks.embedding, which is what pg_search queries; on SQLite they
    go in the .npy store. Resume state is read from whichever of those two
    actually holds the vectors -- never from is_embedded alone, since a flag
    that outlives its vector makes the work unrepeatable.
    """
    store = None if not IS_SQLITE else VectorStore.load()

    if IS_SQLITE:
        known = set(store.ids)
        pending = (
            db.query(SourceChunk)
            .filter(SourceChunk.id.notin_(known) if known else True)
            .order_by(SourceChunk.id)
        )
    else:
        # The column is the source of truth, so a row whose vector is missing
        # is pending however its flag reads.
        pending = (
            db.query(SourceChunk)
            .filter(SourceChunk.embedding.is_(None))
            .order_by(SourceChunk.id)
        )

    if batch_limit:
        pending = pending.limit(batch_limit)
    chunks = pending.all()

    embedded = 0
    if chunks:
        logger.info("Embedding %d chunks...", len(chunks))
        # Save in slices rather than once at the end. A full pass over a
        # large corpus is tens of API calls over several minutes; saving
        # only at the end means an interruption loses all of it and the
        # work is paid for again on the next run.
        for start in range(0, len(chunks), SAVE_EVERY):
            batch = chunks[start:start + SAVE_EVERY]
            vectors = embed_texts([c.content for c in batch])
            if IS_SQLITE:
                store.add(
                    [c.id for c in batch],
                    vectors,
                    subject_ids=[c.subject_id for c in batch],
                    topic_ids=[c.topic_id for c in batch],
                )
                store.save()
                for chunk in batch:
                    chunk.is_embedded = True
            else:
                _store_vectors_pg(db, batch, vectors)
            db.commit()
            embedded += len(batch)
            logger.info("  embedded %d/%d", embedded, len(chunks))

    # Only SQLite keeps a shadow FTS5 table that has to be repopulated.
    # Postgres computes to_tsvector from content at query time against a GIN
    # index, so there is nothing to rebuild -- and sending FTS5 DDL there
    # fails outright on CREATE VIRTUAL TABLE.
    fts_rows = keyword.rebuild(db) if IS_SQLITE else 0

    return {
        "embedded_now": embedded,
        "vectors_total": _vector_count(db, store),
        "fts_rows": fts_rows,
    }


def index_stats(db: Session) -> dict:
    store = VectorStore.load() if IS_SQLITE else None
    total_chunks = db.query(SourceChunk).count()
    vectors = _vector_count(db, store)
    if IS_SQLITE:
        dims = int(store.matrix.shape[1]) if len(store) else 0
    else:
        dims = EMBED_DIMS if vectors else 0
    return {
        "total_chunks": total_chunks,
        "vectors_total": vectors,
        "pending_embedding": max(0, total_chunks - vectors),
        "vector_dims": dims,
    }
