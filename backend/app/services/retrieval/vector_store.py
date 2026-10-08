"""On-disk vector store with subject/topic scoped search.

No vector database and no per-subject partitioning: see VectorStore for the
measurements behind both choices.
"""

import json
import logging

import numpy as np

from ...core.config import settings
from .embeddings import EMBED_DIMS

logger = logging.getLogger(__name__)

_VECTOR_DIR = settings.DATA_DIR / "vectors"
_VECTOR_PATH = _VECTOR_DIR / "chunks.npy"
_IDS_PATH = _VECTOR_DIR / "chunk_ids.json"
# Parallel arrays of subject_id / topic_id, aligned with the vector rows.
_META_PATH = _VECTOR_DIR / "chunk_meta.json"


class VectorStore:
    """Memory-resident vectors with append, atomic save, and scoped search.

    Subject and topic ids are stored alongside the vectors rather than in
    separate per-subject arrays. Measured on a 1,800-chunk corpus, a masked
    search costs 0.13 ms against 0.007 ms for pre-partitioned arrays -- a
    0.12 ms difference inside a request whose embedding step takes ~700 ms.
    One array keeps cross-subject search trivial (a feed card may legitimately
    link OS paging to COA caching), avoids rebalancing when a chunk is
    re-tagged, and leaves a single file to save atomically.

    The important win is accuracy, not speed: GATE terms collide across
    subjects ("deadlock" in OS vs DBMS, "address splits into" in OS paging vs
    COA cache), and unscoped search returns the right answer to the wrong
    subject. Scoping fixes that.
    """

    def __init__(self) -> None:
        self.ids: list[int] = []
        self.matrix: np.ndarray = np.zeros((0, EMBED_DIMS), dtype=np.float32)
        self.subject_ids: np.ndarray = np.zeros((0,), dtype=np.int32)
        self.topic_ids: np.ndarray = np.zeros((0,), dtype=np.int32)

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

            try:
                meta = json.loads(_META_PATH.read_text())
                store.subject_ids = np.asarray(meta["subject_ids"], dtype=np.int32)
                store.topic_ids = np.asarray(meta["topic_ids"], dtype=np.int32)
            except (OSError, ValueError, KeyError):
                # Older store without metadata: treat everything as untagged
                # so search still works, just unscoped.
                n = store.matrix.shape[0]
                store.subject_ids = np.zeros((n,), dtype=np.int32)
                store.topic_ids = np.zeros((n,), dtype=np.int32)
        return store

    def save(self) -> None:
        _VECTOR_DIR.mkdir(parents=True, exist_ok=True)
        # Write to temp paths then replace, so an interrupted save cannot
        # leave ids and vectors out of sync.
        # np.save appends .npy unless the path already ends in it, so the
        # temp name must keep that suffix or the file lands somewhere else.
        tmp_vec = _VECTOR_PATH.with_name(_VECTOR_PATH.name + ".tmp.npy")
        tmp_ids = _IDS_PATH.with_name(_IDS_PATH.name + ".tmp")
        tmp_meta = _META_PATH.with_name(_META_PATH.name + ".tmp")
        np.save(tmp_vec, self.matrix)
        tmp_ids.write_text(json.dumps(self.ids))
        tmp_meta.write_text(json.dumps({
            "subject_ids": self.subject_ids.tolist(),
            "topic_ids": self.topic_ids.tolist(),
        }))
        tmp_vec.replace(_VECTOR_PATH)
        tmp_ids.replace(_IDS_PATH)
        tmp_meta.replace(_META_PATH)

    def add(
        self,
        chunk_ids: list[int],
        vectors: np.ndarray,
        subject_ids: list[int | None] | None = None,
        topic_ids: list[int | None] | None = None,
    ) -> None:
        """Append vectors. 0 means untagged for subject/topic."""
        if not chunk_ids:
            return
        known = set(self.ids)
        keep = [i for i, cid in enumerate(chunk_ids) if cid not in known]
        if not keep:
            return

        def column(values: list[int | None] | None) -> np.ndarray:
            if values is None:
                return np.zeros((len(keep),), dtype=np.int32)
            return np.asarray([values[i] or 0 for i in keep], dtype=np.int32)

        self.ids.extend(chunk_ids[i] for i in keep)
        self.matrix = (
            vectors[keep] if self.matrix.shape[0] == 0
            else np.vstack([self.matrix, vectors[keep]])
        )
        self.subject_ids = np.concatenate([self.subject_ids, column(subject_ids)])
        self.topic_ids = np.concatenate([self.topic_ids, column(topic_ids)])

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 8,
        *,
        subject_id: int | None = None,
        topic_id: int | None = None,
    ) -> list[tuple[int, float]]:
        """Return (chunk_id, similarity) pairs, best first.

        Scoping to a subject or topic keeps a same-word different-meaning
        chunk from another subject out of the results. Untagged chunks
        (subject_id 0) stay eligible, since a cross-subject source such as
        the mistakes log is relevant everywhere.
        """
        if self.matrix.shape[0] == 0:
            return []

        rows = np.arange(self.matrix.shape[0])
        if topic_id is not None:
            rows = rows[(self.topic_ids[rows] == topic_id) | (self.topic_ids[rows] == 0)]
        elif subject_id is not None:
            rows = rows[(self.subject_ids[rows] == subject_id) | (self.subject_ids[rows] == 0)]
        if rows.size == 0:
            return []

        sims = self.matrix[rows] @ query_vector
        k = min(top_k, sims.shape[0])
        top = np.argpartition(-sims, k - 1)[:k] if k < sims.shape[0] else np.arange(sims.shape[0])
        top = top[np.argsort(-sims[top])]
        return [(self.ids[int(rows[i])], float(sims[i])) for i in top]

    def __len__(self) -> int:
        return len(self.ids)
