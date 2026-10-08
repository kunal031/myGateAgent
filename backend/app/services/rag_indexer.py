import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
import chromadb
from chromadb.config import Settings

CHROMA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "chroma_db"
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "documents"

os.makedirs(CHROMA_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# Initialize persistent ChromaDB client
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_or_create_collection(
    name="gate_notes_kb",
    metadata={"hnsw:space": "cosine"}
)

def extract_text_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Extracts text page by page with metadata from a PDF file."""
    pages_data = []
    try:
        doc = fitz.open(pdf_path)
        file_name = os.path.basename(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            if text:
                pages_data.append({
                    "file_name": file_name,
                    "file_path": str(pdf_path),
                    "page_number": page_num + 1,
                    "text": text
                })
        doc.close()
    except Exception as e:
        print(f"Error parsing PDF {pdf_path}: {e}")
    return pages_data

def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
    """Splits long text into overlapping chunks for semantic retrieval."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def index_all_documents(docs_dir: Optional[str] = None) -> int:
    """Scans documents directory and indexes all PDFs and notes into ChromaDB."""
    target_dir = Path(docs_dir) if docs_dir else DOCS_DIR
    if not target_dir.exists():
        return 0

    indexed_count = 0
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                full_path = os.path.join(root, file)
                pages = extract_text_from_pdf(full_path)
                
                for page in pages:
                    chunks = chunk_text(page["text"])
                    for idx, chunk in enumerate(chunks):
                        doc_id = f"{page['file_name']}_p{page['page_number']}_c{idx}"
                        
                        collection.upsert(
                            ids=[doc_id],
                            documents=[chunk],
                            metadatas=[{
                                "file_name": page["file_name"],
                                "page_number": page["page_number"],
                                "file_path": page["file_path"],
                                "chunk_index": idx
                            }]
                        )
                        indexed_count += 1
                        
            elif file.lower().endswith((".txt", ".md")):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    chunks = chunk_text(content)
                    for idx, chunk in enumerate(chunks):
                        doc_id = f"{file}_c{idx}"
                        collection.upsert(
                            ids=[doc_id],
                            documents=[chunk],
                            metadatas=[{
                                "file_name": file,
                                "page_number": 1,
                                "file_path": full_path,
                                "chunk_index": idx
                            }]
                        )
                        indexed_count += 1
                except Exception as e:
                    print(f"Error reading text file {file}: {e}")
                    
    print(f"Indexing completed: {indexed_count} chunks stored in ChromaDB.")
    return indexed_count

def search_knowledge_base(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """Searches the indexed notes and returns the top relevant excerpts."""
    try:
        results = collection.query(
            query_texts=[query],
            n_results=top_k
        )
        matches = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metadatas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
            for doc, meta in zip(docs, metadatas):
                matches.append({
                    "content": doc,
                    "file_name": meta.get("file_name", "Handwritten Notes"),
                    "page_number": meta.get("page_number", 1)
                })
        return matches
    except Exception as e:
        print(f"Error querying knowledge base: {e}")
        return []

if __name__ == "__main__":
    index_all_documents()
