"""Retrieval endpoints over ingested source material.

This replaces the previous ChromaDB-backed implementation. The reply here
is still retrieval-only: the Gemini-backed multilingual assistant that
synthesises answers lands in its own module, so that change stays
reviewable on its own.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import admin_user
from ..core.database import get_db
from ..models.sources import Source, SourceChunk
from ..services import retrieval

router = APIRouter(prefix="/api/agent", tags=["Agent & Retrieval"])


class SearchRequest(BaseModel):
    query: str
    subject_id: int | None = None
    top_k: int = 6
    semantic: bool = True


class ExcerptOut(BaseModel):
    chunk_id: int
    content: str
    page_number: int
    file_name: str
    citation: str
    score: float


class SearchResponse(BaseModel):
    query: str
    excerpts: list[ExcerptOut]
    result_count: int


@router.post("/search", response_model=SearchResponse)
def search_sources(payload: SearchRequest, db: Session = Depends(get_db)):
    """Hybrid keyword + semantic search over the indexed corpus.

    Every excerpt carries its citation, so anything built from this result
    can be traced back to a page.
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    matches = retrieval.search(
        db,
        query,
        top_k=min(payload.top_k, 20),
        subject_id=payload.subject_id,
        semantic=payload.semantic,
    )

    return SearchResponse(
        query=query,
        result_count=len(matches),
        excerpts=[
            ExcerptOut(
                chunk_id=m.chunk_id,
                content=m.content,
                page_number=m.page_number,
                file_name=m.file_name,
                citation=m.citation,
                score=round(m.score, 5),
            )
            for m in matches
        ],
    )


@router.get("/index/status")
def index_status(db: Session = Depends(get_db)):
    """Indexing progress, so a partial ingest is visible rather than silent."""
    stats = retrieval.index_stats(db)
    stats["sources"] = db.query(Source).count()
    return stats


@router.post("/index/build")
def build_index(
batch_limit: int = Query(default=200, le=2000),
    db: Session = Depends(get_db),
    _admin=Depends(admin_user),
):
    """Embed and index chunks that are not yet indexed.

    Batched and resumable: run it again to continue. Kept synchronous so
    quota errors surface to the caller instead of vanishing into a
    background task.
    """
    return retrieval.index_pending_chunks(db, batch_limit=batch_limit)


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    """Every ingested file with its extraction and indexing progress."""
    sources = db.query(Source).order_by(Source.kind, Source.file_name).all()
    return [
        {
            "id": s.id,
            "file_name": s.file_name,
            "kind": s.kind,
            "author_credit": s.author_credit,
            "origin": s.origin,
            "exam_year": s.exam_year,
            "total_pages": s.total_pages,
            "pages_extracted": s.pages_extracted,
            "extraction_method": s.extraction_method,
            "is_indexed": s.is_indexed,
            "chunk_count": db.query(SourceChunk)
                             .filter(SourceChunk.source_id == s.id).count(),
        }
        for s in sources
    ]
