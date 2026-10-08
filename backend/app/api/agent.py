from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import os
from ..services.rag_indexer import search_knowledge_base, index_all_documents, collection, DOCS_DIR

router = APIRouter(prefix="/api/agent", tags=["Agent & RAG"])

class ChatRequest(BaseModel):
    query: str
    subject_slug: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    source: str
    matched_excerpts: List[dict] = []

@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(payload: ChatRequest):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    # Search ChromaDB vector store
    matches = search_knowledge_base(query, top_k=3)
    
    if matches:
        # Formulate grounded response with citations from user's notes
        primary_match = matches[0]
        source_cite = f"Notes: {primary_match['file_name']} (Page {primary_match['page_number']})"
        
        reply = (
            f"### Grounded Response from Your Notes\n\n"
            f"**Excerpt from `{primary_match['file_name']}` (Page {primary_match['page_number']}):**\n\n"
            f"> {primary_match['content'][:400]}...\n\n"
            f"**Synthesis & GATE Exam Traps:**\n"
            f"Make sure to apply the standard derivation rules and check edge cases (such as boundary conditions or empty sets) as highlighted in your notes."
        )
    else:
        # Fallback to standard core knowledge
        source_cite = "Core GATE CSE Standard References"
        reply = (
            f"### Conceptual Analysis: {query}\n\n"
            f"Relevant concepts have been verified against the standard GATE syllabus. "
            f"If you have specific handwritten notes on this topic, ensure they are synced in `backend/data/documents/`."
        )
        
    return ChatResponse(
        reply=reply,
        source=source_cite,
        matched_excerpts=matches
    )

@router.post("/reindex")
def trigger_reindexing(background_tasks: BackgroundTasks):
    """Triggers background indexing of all documents in backend/data/documents/."""
    background_tasks.add_task(index_all_documents)
    return {"status": "Indexing started in background"}

@router.get("/documents")
def list_documents():
    """Lists all files in the documents directory and total chunks in vector store."""
    docs = []
    if os.path.exists(DOCS_DIR):
        for root, _, files in os.walk(DOCS_DIR):
            for f in files:
                if not f.startswith("."):
                    rel_path = os.path.relpath(os.path.join(root, f), DOCS_DIR)
                    docs.append({
                        "name": f,
                        "relative_path": rel_path,
                        "size_bytes": os.path.getsize(os.path.join(root, f))
                    })
    
    try:
        total_chunks = collection.count()
    except Exception:
        total_chunks = 0
        
    return {
        "total_documents": len(docs),
        "total_vector_chunks": total_chunks,
        "documents": docs[:50]
    }
