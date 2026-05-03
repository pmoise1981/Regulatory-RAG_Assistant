from fastapi import FastAPI
from pydantic import BaseModel
from pathlib import Path
from typing import List
import json, urllib.request, logging, re, time

from chromadb import PersistentClient
from app.core.settings import settings
from app.core.logging import configure_logging
from app.embeddings.loader import embed_texts
from app.retrievers.hybrid import HybridRetriever
from app.ui.main import router as ui_router

# ---------- App setup ----------
configure_logging()
log = logging.getLogger("api")
app = FastAPI(title="Regulatory RAG", version="1.3")
COLL = "regulatory_chunks"
CHUNK_FILE = Path("data/chunks/chunks.jsonl")

def ensure_coll():
    c = PersistentClient(path=settings.CHROMA_DIR)
    try:
        c.get_collection(COLL)
    except Exception:
        c.create_collection(COLL, metadata={"hnsw:space": "cosine"})
ensure_coll()

# UI at /
app.include_router(ui_router, prefix="")

# ---------- Schemas ----------
class AskRequest(BaseModel):
    query: str
    top_k: int = 6

class AskResponse(BaseModel):
    answer: str
    contexts: List[str]
    sources: List[dict]

# ---------- Helpers ----------
def _ollama_call(payload: dict, timeout=20):
    # Force no-proxy and create a dedicated opener
    import urllib.request, json, os
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=timeout) as resp:
        return json.load(resp)

def ask_ollama(prompt: str) -> str:
    """Call Ollama if LLM_BACKEND=local; otherwise return empty string to trigger fallback."""
    if settings.LLM_BACKEND != "local":
        return ""
    try:
        out = _ollama_call({"model": settings.LLM_MODEL, "prompt": prompt, "stream": False})
        return out.get("response", "")
    except Exception as e:
        log.warning("ollama error: %s", e)
        return ""

# Concise extractive fallback (no-LLM mode)
_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')
_WORDS      = re.compile(r'\w+')
def _score_sentence(sent: str, q_terms: set[str]) -> float:
    s = sent.lower()
    hits = sum(s.count(t) for t in q_terms)
    return hits + 0.25 / max(1, len(sent))  # prefer dense/shorter sentences

def _load_chunk_file() -> List[dict]:
    if not CHUNK_FILE.exists():
        return []
    rows = []
    with CHUNK_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("text"):
                rows.append(obj)
    return rows

def lexical_chunk_search(query: str, top_k: int = 6) -> List[dict]:
    """Fallback retrieval for demos before Chroma/embeddings are ready."""
    rows = _load_chunk_file()
    if not rows:
        return []
    q_terms = set(w.lower() for w in _WORDS.findall(query) if len(w) > 2)
    scored = []
    for row in rows:
        text = row.get("text", "")
        metadata = row.get("metadata") or {}
        haystack = f"{metadata.get('source', '')} {metadata.get('title', '')} {text}".lower()
        term_hits = sum(haystack.count(term) for term in q_terms)
        title_boost = sum(str(metadata.get("title", "")).lower().count(term) for term in q_terms)
        source_boost = sum(str(metadata.get("source", "")).lower().count(term) for term in q_terms)
        score = term_hits + (2 * title_boost) + source_boost
        if score > 0:
            scored.append((score, row))
    if not scored:
        return []
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {"id": row["id"], "text": row["text"], "metadata": row.get("metadata", {})}
        for _, row in scored[: max(1, top_k)]
    ]

def extractive_answer(query: str, hits: List[dict], max_bullets: int = 6, max_chars: int = 220) -> str:
    if not hits:
        return "No context available."
    q_terms = set(w.lower() for w in _WORDS.findall(query) if len(w) > 2)
    cand = []
    for h in hits[:4]:
        meta = h.get("metadata") or {}
        src  = f'{meta.get("source","doc")} :: {meta.get("title","")}'
        for s in _SENT_SPLIT.split(h["text"]):
            s = " ".join(s.split())
            if len(s) < 30:
                continue
            cand.append((_score_sentence(s, q_terms), s, src))
    cand.sort(key=lambda x: -x[0])

    picked, seen = [], set()
    for _, s, src in cand:
        if len(picked) >= max_bullets: break
        key = s[:60].lower()
        if key in seen: continue
        seen.add(key)
        if len(s) > max_chars:
            s = s[:max_chars-1].rstrip() + "…"
        picked.append(f"- {s} [{src}]")

    return "\n".join(picked) if picked else "No concise context found in the indexed documents."

# ---------- Routes ----------
@app.get("/health")
def health():
    return {"status": "ok", "env": settings.APP_ENV}

@app.get("/mode")
def mode():
    """Check LLM mode & Ollama connectivity."""
    backend = settings.LLM_BACKEND
    model   = settings.LLM_MODEL
    ok, msg = False, ""
    t0 = time.time()
    if backend == "local":
        try:
            _ = _ollama_call({"model": model, "prompt": "ok", "stream": False}, timeout=8)
            ok = True
        except Exception as e:
            msg = str(e)
    return {"backend": backend, "model": model, "ollama_ok": ok, "error": msg, "latency_ms": int((time.time()-t0)*1000)}

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    # Retrieve
    try:
        ret = HybridRetriever(settings.CHROMA_DIR, COLL)
        qv  = embed_texts([req.query], settings.EMBEDDING_MODEL)[0]
        hits = ret.search(req.query, qv, top_k=max(1, req.top_k))
    except Exception as e:
        log.warning("vector retrieval failed, using lexical fallback: %s", e)
        hits = lexical_chunk_search(req.query, top_k=max(1, req.top_k))

    if not hits:
        return AskResponse(
            answer="No context available. Add PDFs or markdown files to `data/source_docs/` and rerun `make ingest`.",
            contexts=[],
            sources=[],
        )

    contexts = [h["text"] for h in hits]
    sources  = [{"id": h["id"], **(h.get("metadata") or {})} for h in hits]

    # Generate (or fallback)
    prompt = (
        "You are a compliance assistant. Answer succinctly (bullets, 5–7 lines) using ONLY the provided context. "
        "Cite inline like [source :: title].\n\n"
        f"Question: {req.query}\n\nContext:\n" + "\n\n---\n\n".join(contexts[: max(1, req.top_k//2)]) + "\n\nAnswer:"
    )
    answer = ask_ollama(prompt) or extractive_answer(req.query, hits, max_bullets=6, max_chars=220)
    return AskResponse(answer=answer, contexts=contexts, sources=sources)
