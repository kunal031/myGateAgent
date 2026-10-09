"""Ingest the whole inbox in value order, then report.

Ordering is deliberate rather than alphabetical:

  1. free-text sources   no vision quota, so they cost nothing and finish fast
  2. topper notes        dense, exam-focused, the best card material
  3. textbooks           broad but least GATE-specific

Within each stage, smallest files first, so a short file proves the stage
before a long one commits hours of quota.

Safe to stop and re-run: transcribed pages are cached per page and ingested
files are skipped, so a resumed run picks up where it left off.

    ./venv/bin/python -m app.cli.build_corpus            # everything
    ./venv/bin/python -m app.cli.build_corpus --free-only
"""

import argparse

from ..ai.rate_limit import DailyQuotaExceeded, generation_limiter
from ..core.database import SessionLocal
from ..services.ingestion.pipeline import ingest_inbox
from ..services.retrieval import index_pending_chunks, index_stats

# (label, glob, needs_vision)
STAGES: list[tuple[str, str, bool]] = [
    ("PYQ papers and answer keys", "pyq/papers/*.pdf", False),
    ("PYQ topicwise compilation", "pyq/topicwise/*.pdf", False),
    ("Topper notes (handwritten)", "notes/handwritten-air50/*.pdf", True),
    ("Topper notes (GitHub)", "notes/github-priyanshu/*.pdf", True),
    ("Other notes", "notes/karan-suthar/**/*.pdf", True),
    # Recursive: books are staged under books/<subject-slug>/ so the
    # classifier can read the subject from the path.
    #
    # Flagged as free rather than vision: the standard texts are digital
    # editions with real text layers -- measured, 6,618 of 9,264 pages
    # extract directly. A book that turns out to be scanned still falls
    # back to vision per page inside the extractor.
    ("Textbooks", "books/**/*.pdf", False),
]


def run_stage(db, label: str, pattern: str, max_pages: int | None) -> dict:
    print(f"\n=== {label} ===")
    totals = {"files": 0, "pages": 0, "chunks": 0}
    try:
        for report in ingest_inbox(db, pattern=pattern, max_pages=max_pages):
            if report["status"] == "ingested":
                print(f"  {report['file']}: {report['pages']}p, {report['chunks']} chunks")
                totals["files"] += 1
                totals["pages"] += report["pages"]
                totals["chunks"] += report["chunks"]
            elif report["status"] == "failed":
                print(f"  {report['file']}: FAILED — {report.get('error', '')[:80]}")
    except DailyQuotaExceeded as exc:
        print(f"  stopped: {exc}")
        raise
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--free-only", action="store_true",
                        help="only sources that need no vision quota")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="cap pages per file, for a trial run")
    parser.add_argument("--no-index", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    grand = {"files": 0, "pages": 0, "chunks": 0}
    try:
        print(f"Vision quota remaining today: "
              f"{generation_limiter.remaining_today()}")

        for label, pattern, needs_vision in STAGES:
            if args.free_only and needs_vision:
                continue
            try:
                stage = run_stage(db, label, pattern, args.max_pages)
            except DailyQuotaExceeded:
                print("\nDaily quota reached. Re-run tomorrow to continue; "
                      "pages already transcribed are cached.")
                break
            for key in grand:
                grand[key] += stage[key]

        print(f"\n{grand['files']} files, {grand['pages']} pages, "
              f"{grand['chunks']} chunks ingested.")

        if not args.no_index and grand["chunks"]:
            print("\nEmbedding and indexing...")
            print("  ", index_pending_chunks(db))

        print("\nCorpus:", index_stats(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
