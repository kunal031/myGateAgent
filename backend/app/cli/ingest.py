"""Ingest files from data/inbox/ into the searchable corpus.

    ./venv/bin/python -m app.cli.ingest --pattern "**/Silly_Mistakes_Log.pdf"
    ./venv/bin/python -m app.cli.ingest --max-files 3

Resumable: pages already transcribed are read from the on-disk cache, and a
file already ingested is skipped, so re-running after an interruption costs
nothing.
"""

import argparse

from ..core.database import SessionLocal
from ..services.ingestion.pipeline import ingest_inbox
from ..services.retrieval import index_pending_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", default="**/*.pdf")
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument("--max-pages", type=int, default=None,
                        help="cap pages per file, for a cheap trial run")
    parser.add_argument("--no-index", action="store_true",
                        help="extract only; skip embedding")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        reports = ingest_inbox(
            db, pattern=args.pattern,
            max_files=args.max_files, max_pages=args.max_pages,
        )
        for report in reports:
            status = report["status"]
            if status == "ingested":
                print(f"  {report['file']}: {report['pages']} pages, "
                      f"{report['chunks']} chunks ({report['kind']})")
            elif status != "excluded":
                print(f"  {report['file']}: {status}")

        ingested = sum(1 for r in reports if r["status"] == "ingested")
        print(f"\n{ingested} file(s) ingested.")

        if not args.no_index and ingested:
            print("Embedding and indexing...")
            print("  ", index_pending_chunks(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
