from typing import List, Dict, Any
import requests
import chromadb
from chromadb.utils import embedding_functions
from app.core.settings import settings

COLLECTION_NAME = "regulatory_chunks"

def get_chroma_collection():
    client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.EMBEDDING_MODEL
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

def add_documents_to_chroma(docs: List[Dict[str, Any]]):
    """
    docs: list of dicts containing {id, text, metadata}
    """
    if not docs:
        return
    col = get_chroma_collection()
    col.add(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
        metadatas=[d.get("metadata", {}) for d in docs],
    )

def retrieve(query: str, k: int = 6) -> List[Dict[str, Any]]:
    col = get_chroma_collection()
    res = col.query(query_texts=[query], n_results=k)
    out = []
    for i in range(len(res.get("ids", [[]])[0])):
        out.append(
            {
                "id": res["ids"][0][i],
                "text": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": res.get("distances", [[None]])[0][i],
            }
        )
    return out

def build_prompt(question: str, contexts: List[Dict[str, Any]]) -> str:
    bullets = []
    for c in contexts:
        meta = c.get("metadata", {})
        src = meta.get("source", "unknown")
        section = meta.get("section", "")
        bullets.append(f"- [source: {src}] {section} {c['text'][:900]}")
    context_block = "\n".join(bullets)
    return (
        "You are a careful regulatory analyst. Answer with citations to [source].\n\n"
        f"Question:\n{question}\n\n"
        f"Context:\n{context_block}\n\n"
        "Answer (cite sources inline like [source: OCC_2023-XYZ]):"
    )

def call_ollama(model: str, prompt: str) -> str:
    host = settings.OLLAMA_BASE_URL.rstrip("/")
    try:
        r = requests.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("response", "").strip()
    except Exception as e:
        # Fallback minimal answer
        return f"(LLM unavailable, returning top docs)\n\n{prompt[:1200]}"

def answer(question: str, k: int = 6) -> Dict[str, Any]:
    ctx = retrieve(question, k=k)
    prompt = build_prompt(question, ctx)
    out = call_ollama(settings.LLM_MODEL, prompt)
    return {"answer": out, "context": ctx}
