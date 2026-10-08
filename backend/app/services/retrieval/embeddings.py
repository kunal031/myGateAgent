"""Embedding generation and on-disk vector storage.

No vector database. The corpus is ~1,800 chunks, where a brute-force matrix
multiply takes well under a millisecond -- an HNSW index would be pure
overhead. Vectors live in a single .npy file alongside an id list, loaded
once into memory.

Embeddings are produced at ingest time only and cached, so searching never
makes an API call.
"""

import hashlib
import json
import logging
import sqlite3
from pathlib import Path

import numpy as np

from ...ai import client as ai_client
from ...core.config import settings

logger = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMS = 3072

_VECTOR_DIR = settings.DATA_DIR / "vectors"
_VECTOR_PATH = _VECTOR_DIR / "chunks.npy"
_IDS_PATH = _VECTOR_DIR / "chunk_ids.json"

# Gemini accepts batches; keep them modest so one failure costs little.
BATCH_SIZE = 32


def embed_texts(texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
    """Embed a list of texts, returning L2-normalised row vectors.

    Normalising here means cosine similarity is a plain dot product later.
    """
    from google.genai import types

    if not texts:
        return np.zeros((0, EMBED_DIMS), dtype=np.float32)

    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        ai_client.generation_limiter.acquire()
        response = ai_client.get_client().models.embed_content(
            model=EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        vectors.extend(e.values for e in response.embeddings)

    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.maximum(norms, 1e-12)


_QUERY_CACHE_PATH = _VECTOR_DIR / "query_cache.sqlite3"


def _query_cache() -> sqlite3.Connection:
    _VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_QUERY_CACHE_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS query_vectors ("
        " query_hash TEXT PRIMARY KEY, vector BLOB NOT NULL)"
    )
    return conn


def embed_query(text: str) -> np.ndarray:
    """Embed a search query, caching the result on disk.

    Embedding costs a ~700 ms network round trip, which dominates search
    latency -- local keyword and vector search are both ~1 ms. Repeat
    queries (a retried search, a preset prompt, the same topic opened
    twice) are therefore served from cache, and the cache also keeps repeat
    searches off the API quota.
    """
    key = hashlib.sha256(text.strip().lower().encode()).hexdigest()
    conn = _query_cache()
    try:
        row = conn.execute(
            "SELECT vector FROM query_vectors WHERE query_hash = ?", (key,)
        ).fetchone()
        if row is not None:
            return np.frombuffer(row[0], dtype=np.float32)

        vector = embed_texts([text], task_type="RETRIEVAL_QUERY")[0]
        conn.execute(
            "INSERT OR REPLACE INTO query_vectors VALUES (?, ?)",
            (key, vector.tobytes()),
        )
        conn.commit()
        return vector
    finally:
        conn.close()


class VectorStore:
    """Memory-resident vectors with append and atomic save."""

    def __init__(self) -> None:
        self.ids: list[int] = []
        self.matrix: np.ndarray = np.zeros((0, EMBED_DIMS), dtype=np.float32)

    @classmethod
    def load(cls) -> "VectorStore":
        store = cls()
        if _VECTOR_PATH.exists() and _IDS_PATH.exists():
            try:
                store.matrix = np.load(_VECTOR_PATH)
                store.ids = json.loads(_IDS_PATH.read_text())
                if len(store.ids) != store.matrix.shape[0]:
                    logger.error(
                        "Vector store is inconsistent (%d ids vs %d rows); "
                        "treating as empty. Re-run embedding.",
                        len(store.ids), store.matrix.shape[0],
                    )
                    return cls()
            except (OSError, ValueError) as exc:
                logger.error("Could not load vector store: %s", exc)
                return cls()
        return store

    def save(self) -> None:
        _VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        # Write to temp paths then replace, so an interrupted save cannot
        # leave ids and vectors out of sync.
        # np.save appends .npy unless the path already ends in it, so the
        # temp name must keep that suffix or the file lands somewhere else.
        tmp_vec = _VECTOR_PATH.with_name(_VECTOR_PATH.name + ".tmp.npy")
        tmp_ids = _IDS_PATH.with_name(_IDS_PATH.name + ".tmp")
        np.save(tmp_vec, self.matrix)
        tmp_ids.write_text(json.dumps(self.ids))
        tmp_vec.replace(_VECTOR_PATH)
        tmp_ids.replace(_IDS_PATH)

    def add(self, chunk_ids: list[int], vectors: np.ndarray) -> None:
        if not chunk_ids:
            return
        known = set(self.ids)
        keep = [i for i, cid in enumerate(chunk_ids) if cid not in known]
        if not keep:
            return
        self.ids.extend(chunk_ids[i] for i in keep)
        self.matrix = (
            vectors[keep] if self.matrix.shape[0] == 0
            else np.vstack([self.matrix, vectors[keep]])
        )

    def search(self, query_vector: np.ndarray, top_k: int = 8) -> list[tuple[int, float]]:
        """Return (chunk_id, similarity) pairs, best first."""
        if self.matrix.shape[0] == 0:
            return []
        sims = self.matrix @ query_vector
        k = min(top_k, sims.shape[0])
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [(self.ids[i], float(sims[i])) for i in top]

    def __len__(self) -> int:
        return len(self.ids)
