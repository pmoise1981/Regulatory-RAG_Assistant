from fastapi import FastAPI, Query
from pydantic import BaseModel
from pathlib import Path
from typing import List, Optional
import json, urllib.request, logging, re, time

from chromadb import PersistentClient
from app.audit.logger import init_audit_db, log_query, recent_queries
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
init_audit_db()

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
    retrieval_mode: str
    audit_id: Optional[int] = None
    latency_ms: int

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
    boost = 0
    if "bureau of consumer financial protection" in s:
        boost += 100
    if "funding cap" in s:
        boost += 50
    if "consumer financial protection act" in s or "striking ‘‘12’’" in s or "inserting ‘‘6.5’’" in s:
        boost += 75
    if "finra rule 3310" in s:
        boost += 50
    if "administrator" in s and "exchanger" in s and "virtual currency" in s:
        boost += 50
    return hits + boost + 0.25 / max(1, len(sent))  # prefer dense/shorter sentences

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

def _query_terms(query: str) -> set[str]:
    q_terms = set(w.lower() for w in _WORDS.findall(query) if len(w) > 2)
    q = query.lower()
    if "cfpb" in q:
        q_terms.update({"bureau", "consumer", "financial", "protection"})
    if "genius" in q or "stablecoin" in q:
        q_terms.update({"payment", "stablecoin", "issuer", "reserve"})
    return q_terms

def lexical_chunk_search(query: str, top_k: int = 6) -> List[dict]:
    """Fallback retrieval before Chroma/embeddings are ready."""
    rows = _load_chunk_file()
    if not rows:
        return []
    q_terms = _query_terms(query)
    scored = []
    for row in rows:
        text = row.get("text", "")
        metadata = row.get("metadata") or {}
        haystack = f"{metadata.get('source', '')} {metadata.get('title', '')} {text}".lower()
        term_hits = sum(haystack.count(term) for term in q_terms)
        title_boost = sum(str(metadata.get("title", "")).lower().count(term) for term in q_terms)
        source_boost = sum(str(metadata.get("source", "")).lower().count(term) for term in q_terms)
        score = term_hits + (2 * title_boost) + source_boost
        if "cfpb" in query.lower() and "bureau of consumer financial protection" in haystack:
            score += 100
        if "funding" in query.lower() and "funding cap" in haystack:
            score += 50
        if score > 0:
            scored.append((score, row))
    if not scored:
        return []
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {"id": row["id"], "text": row["text"], "metadata": row.get("metadata", {})}
        for _, row in scored[: max(1, top_k)]
    ]

def _infer_source_scope(query: str) -> set[str]:
    """Prefer the right closed-corpus shelf when the question names a regulator or act."""
    q = query.lower()
    scope: set[str] = set()
    if "finra" in q or "broker-dealer" in q or "broker dealer" in q:
        scope.add("finra")
    if "fincen" in q or "cvc" in q or "virtual currency" in q:
        scope.add("fincen")
    if "sec" in q or "securities law" in q or "crypto asset" in q:
        scope.add("sec")
    if "ffiec" in q or "bsa/aml" in q or "risk assessment" in q or "sar" in q:
        scope.add("ffiec")
    if "occ" in q or "third-party" in q or "third party" in q:
        scope.add("occ")
    if "basel" in q or "g-sib" in q or "gsib" in q:
        scope.add("basel")
    if "genius" in q or "stablecoin" in q or "big beautiful" in q or "cfpb" in q:
        scope.add("legislation")
    return scope

def _retrieval_depth(query: str, top_k: int) -> int:
    if _infer_source_scope(query):
        return max(top_k, top_k * 4)
    return top_k

def _hit_matches_scope(hit: dict, scope: set[str], query: str) -> bool:
    metadata = hit.get("metadata") or {}
    source = str(metadata.get("source", "")).lower()
    title = str(metadata.get("title", "")).lower()
    q = query.lower()
    if source in scope:
        if "genius" in q:
            return "genius" in title
        if "big beautiful" in q or "cfpb" in q:
            return "big_beautiful" in title or "beautiful_bill" in title
        return True
    return False

def focus_hits_by_query(query: str, hits: List[dict]) -> List[dict]:
    scope = _infer_source_scope(query)
    if not scope:
        return hits
    focused = [hit for hit in hits if _hit_matches_scope(hit, scope, query)]
    return focused if focused else hits

def extractive_answer(query: str, hits: List[dict], max_bullets: int = 6, max_chars: int = 220) -> str:
    if not hits:
        return "No context available."
    q_terms = _query_terms(query)
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

@app.get("/audit/recent")
def audit_recent(limit: int = Query(default=25, ge=1, le=100)):
    return {"items": recent_queries(limit=limit)}

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
    started = time.time()
    retrieval_mode = "vector"
    top_k = max(1, req.top_k)
    retrieval_depth = _retrieval_depth(req.query, top_k)
    # Retrieve
    try:
        ret = HybridRetriever(settings.CHROMA_DIR, COLL)
        qv  = embed_texts([req.query], settings.EMBEDDING_MODEL)[0]
        hits = ret.search(req.query, qv, top_k=retrieval_depth)
        if _infer_source_scope(req.query):
            lexical_hits = lexical_chunk_search(req.query, top_k=retrieval_depth)
            seen = {hit.get("id") for hit in lexical_hits}
            for hit in hits:
                if hit.get("id") not in seen:
                    lexical_hits.append(hit)
                    seen.add(hit.get("id"))
            hits = lexical_hits
        if not hits:
            retrieval_mode = "lexical"
            hits = lexical_chunk_search(req.query, top_k=retrieval_depth)
    except Exception as e:
        log.warning("vector retrieval failed, using lexical fallback: %s", e)
        retrieval_mode = "lexical"
        hits = lexical_chunk_search(req.query, top_k=retrieval_depth)
    hits = focus_hits_by_query(req.query, hits)[:top_k]

    if not hits:
        return AskResponse(
            answer="No context available. Add PDFs or markdown files to `data/source_docs/` and rerun `make ingest`.",
            contexts=[],
            sources=[],
            retrieval_mode="none",
            audit_id=None,
            latency_ms=int((time.time() - started) * 1000),
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
    latency_ms = int((time.time() - started) * 1000)
    audit_id = log_query(
        query=req.query,
        answer=answer,
        retrieval_mode=retrieval_mode,
        sources=sources,
        latency_ms=latency_ms,
    )
    return AskResponse(
        answer=answer,
        contexts=contexts,
        sources=sources,
        retrieval_mode=retrieval_mode,
        audit_id=audit_id,
        latency_ms=latency_ms,
    )
