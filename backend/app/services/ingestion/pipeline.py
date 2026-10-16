"""Ingest files from the inbox into sources and retrievable chunks.

Idempotent by content hash: re-dropping a file is a no-op, so the inbox can
be topped up at any time and the job re-run without duplicating anything.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from ...core.config import settings
from ...models.models import Subject
from ...models.sources import (
    ExtractionMethod, IngestStatus, Source, SourceChunk, SourceKind,
)
import pymupdf

from .chunker import chunk_page
from .classify import classify
from .extract import extract_pdf_pages, file_hash, page_has_usable_text

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
    source.ingest_status = IngestStatus.COMPLETE
    source.is_indexed = True
    db.commit()

    return {
        "status": "ingested",
        "file": meta["relative_path"],
        "kind": meta["kind"],
        "pages": len(pages),
        "chunks": chunk_count,
    }


def needs_vision(path: Path, *, samples: int = 3) -> bool:
    """Whether a file's text layer is unusable and it must go to vision.

    Checked per file, not per stage: a stage can hold both a digital
    edition and a scan, and sending the scan first spends hours of quota
    while free books wait behind it.
    """
    if path.suffix.lower() != ".pdf":
        return False
    try:
        doc = pymupdf.open(path)
        total = len(doc)
        if total == 0:
            return True
        indexes = [total // 4, total // 2, (3 * total) // 4][:samples]
        usable = sum(1 for i in indexes if page_has_usable_text(doc[i]))
        doc.close()
        return usable < max(1, len(indexes) - 1)
    except Exception:
        return True


def _mark_failed(db: Session, path: Path, exc: Exception) -> None:
    """Record why a file failed, so it is distinguishable from one in flight."""
    try:
        source = (
            db.query(Source)
            .filter(Source.file_name == path.name)
            .order_by(Source.id.desc())
            .first()
        )
        if source is not None:
            source.ingest_status = IngestStatus.FAILED
            source.ingest_error = str(exc)[:500]
            db.commit()
    except Exception:
        db.rollback()


def ingest_inbox(
    db: Session, *, pattern: str = "**/*.pdf", max_files: int | None = None,
    max_pages: int | None = None, free_only: bool = False,
) -> list[dict]:
    """Ingest matching files from the inbox.

    Ordered free-extraction first, then smallest first. Both matter: a file
    with a usable text layer costs no quota at all, and among the rest a
    short file proves the pipeline before a long one commits hours of it.
    """
    candidates = sorted(settings.INBOX_DIR.glob(pattern),
                        key=lambda p: p.stat().st_size)
    annotated = [(needs_vision(p), p) for p in candidates]
    if free_only:
        annotated = [(v, p) for v, p in annotated if not v]
    files = [p for _, p in sorted(annotated, key=lambda t: t[0])]
    reports = []
    for path in files[:max_files] if max_files else files:
        try:
            reports.append(ingest_file(db, path, max_pages=max_pages))
        except Exception as exc:
            # Roll back before continuing: a failed flush leaves the session
            # unusable, so without this one bad file fails every file after
            # it with a misleading "transaction has been rolled back".
            db.rollback()
            _mark_failed(db, path, exc)
            logger.exception("Failed to ingest %s", path.name)
            reports.append({"status": "failed", "file": path.name, "error": str(exc)})
    return reports
