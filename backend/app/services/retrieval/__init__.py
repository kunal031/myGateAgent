"""Hybrid retrieval over ingested source material.

No vector database: at ~1,800 chunks a brute-force matrix multiply runs in
~0.1 ms, so vectors live in a .npy file and keyword search uses SQLite
FTS5. Measured locally: keyword 1.2 ms, vector 0.1 ms, query embedding
~700 ms (cached to 0.2 ms).
"""

from .hybrid import Match, search
from .index import index_pending_chunks, index_stats

__all__ = ["Match", "search", "index_pending_chunks", "index_stats"]
