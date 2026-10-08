"""Ingest files from the inbox into sources and retrievable chunks.

Idempotent by content hash: re-dropping a file is a no-op, so the inbox can
be topped up at any time and the job re-run without duplicating anything.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from ...core.config import settings
from ...models.models import Subject
from ...models.sources import ExtractionMethod, Source, SourceChunk, SourceKind
from .chunker import chunk_page
from .classify import classify
from .extract import extract_pdf_pages, file_hash

logger = logging.getLogger(__name__)

SKIP_KINDS = {SourceKind.EXCLUDED}


def ingest_file(db: Session, path: Path, *, max_pages: int | None = None) -> dict:
    """Register one file and store its chunks. Returns a short report."""
    inbox = settings.INBOX_DIR
    meta = classify(path, inbox)

    if meta["kind"] in SKIP_KINDS:
        return {"status": "excluded", "file": meta["relative_path"]}
    if not meta["is_supported"] or path.suffix.lower() != ".pdf":
        return {"status": "unsupported", "file": meta["relative_path"]}

    content_hash = file_hash(path)
    existing = db.query(Source).filter(Source.content_hash == content_hash).first()
    if existing and existing.is_indexed:
        return {"status": "already_ingested", "file": meta["relative_path"]}

    subject_id = None
    if meta["subject_slug"]:
        subject = (
            db.query(Subject).filter(Subject.slug == meta["subject_slug"]).first()
        )
        subject_id = subject.id if subject else None

    source = existing or Source(
        content_hash=content_hash,
        file_name=path.name,
        relative_path=meta["relative_path"],
        file_size_bytes=path.stat().st_size,
        file_type=meta["file_type"],
        kind=meta["kind"],
        subject_id=subject_id,
        origin=meta["origin"],
        author_credit=meta["author_credit"],
        exam_year=meta["exam_year"],
    )
    if existing is None:
        db.add(source)
        db.commit()  # close the write transaction before the slow part

    source_id = source.id

    # Extraction is the slow phase: a scanned file is minutes of rate-limited
    # vision calls. Holding a write transaction across it blocks every other
    # writer for that whole time, which is what made concurrent generation
    # fail with "database is locked". Nothing is written until it finishes.
    db.close()
    pages = extract_pdf_pages(path, content_hash, max_pages=max_pages)
    source = db.query(Source).filter(Source.id == source_id).first()

    chunk_count = 0
    for page in pages:
        for index, body in enumerate(chunk_page(page["text"])):
            duplicate = (
                db.query(SourceChunk)
                .filter(
                    SourceChunk.source_id == source_id,
                    SourceChunk.page_number == page["page_number"],
                    SourceChunk.chunk_index == index,
                )
                .first()
            )
            if duplicate:
                continue
            db.add(SourceChunk(
                source_id=source_id,
                page_number=page["page_number"],
                chunk_index=index,
                content=body,
                char_count=len(body),
                subject_id=subject_id,
                extraction_method=page["method"],
            ))
            chunk_count += 1

    source.total_pages = len(pages)
    source.pages_extracted = len(pages)
    source.extraction_method = (
        ExtractionMethod.VISION
        if any(p["method"] == "VISION" for p in pages)
        else ExtractionMethod.DIRECT
    )
    source.is_indexed = True
    db.commit()

    return {
        "status": "ingested",
        "file": meta["relative_path"],
        "kind": meta["kind"],
        "pages": len(pages),
        "chunks": chunk_count,
    }


def ingest_inbox(
    db: Session, *, pattern: str = "**/*.pdf", max_files: int | None = None,
    max_pages: int | None = None,
) -> list[dict]:
    """Ingest matching files from the inbox, newest-smallest first.

    Smallest first is deliberate: a short file validates the pipeline for a
    handful of API calls before a 600-page book commits hours of quota.
    """
    files = sorted(settings.INBOX_DIR.glob(pattern), key=lambda p: p.stat().st_size)
    reports = []
    for path in files[:max_files] if max_files else files:
        try:
            reports.append(ingest_file(db, path, max_pages=max_pages))
        except Exception as exc:
            logger.exception("Failed to ingest %s", path.name)
            reports.append({"status": "failed", "file": path.name, "error": str(exc)})
    return reports
