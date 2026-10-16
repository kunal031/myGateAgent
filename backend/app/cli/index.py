"""Embed and index any chunks that are not yet searchable.

Ingestion stores chunks; embedding makes them findable by semantic search.
Those are separate steps, and a run interrupted between them leaves chunks
in the database that retrieval cannot see. This closes that gap without
re-running ingestion.

    ./venv/bin/python -m app.cli.index
    ./venv/bin/python -m app.cli.index --status   # no API calls
"""

import argparse

from ..ai.rate_limit import DailyQuotaExceeded
from ..core.database import SessionLocal
from ..services.retrieval import index_pending_chunks, index_stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true",
                        help="report what is pending and exit")
    parser.add_argument("--batch-limit", type=int, default=None,
                        help="stop after this many chunks")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = index_stats(db)
        print(f"  chunks  : {stats['total_chunks']}")
        print(f"  embedded: {stats['vectors_total']}")
        print(f"  pending : {stats['pending_embedding']}")

        if args.status:
            calls = -(-stats["pending_embedding"] // 32)
            print(f"\n  ~{calls} API calls to finish (~{calls * 6 / 60:.0f} min)")
            return

        if not stats["pending_embedding"]:
            print("\nNothing to do.")
            return

        print("\nEmbedding...")
        try:
            print("  ", index_pending_chunks(db, batch_limit=args.batch_limit))
        except DailyQuotaExceeded as exc:
            print(f"  stopped: {exc}")
            print("  Progress is saved; re-run to continue.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
