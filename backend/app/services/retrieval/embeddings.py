"""Embedding generation via Gemini.

Document embeddings are produced at ingest time only; query embeddings are
cached on disk, so searching normally makes no API call. Storage and search
live in vector_store.py.
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

# Gemini accepts batches; keep them modest so one failure costs little.
BATCH_SIZE = 32

# Parallel in-flight batches. Measured: 30 concurrent calls completed with
# no failures, so this is well inside what the API serves.
EMBED_CONCURRENCY = 12


def _embed_batch(batch: list[str], task_type: str) -> list[list[float]]:
    from google.genai import types

    ai_client.generation_limiter.acquire()
    response = ai_client.get_client().models.embed_content(
        model=EMBED_MODEL,
        contents=batch,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return [e.values for e in response.embeddings]


def embed_texts(texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
    """Embed a list of texts, returning L2-normalised row vectors.

    Normalising here means cosine similarity is a plain dot product later.

    Batches are sent concurrently. Each call is a round trip of a few
    hundred milliseconds, so issuing them one at a time left throughput an
    order of magnitude below what the API serves -- measured at roughly 480
    chunks a minute against a limit that allows far more.
    """
    from concurrent.futures import ThreadPoolExecutor

    if not texts:
        return np.zeros((0, EMBED_DIMS), dtype=np.float32)

    batches = [texts[i:i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]

    if len(batches) == 1:
        vectors = _embed_batch(batches[0], task_type)
    else:
        with ThreadPoolExecutor(max_workers=EMBED_CONCURRENCY) as pool:
            # map preserves order, so vectors stay aligned with their chunks.
            results = list(pool.map(lambda b: _embed_batch(b, task_type), batches))
        vectors = [v for batch_vectors in results for v in batch_vectors]

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
