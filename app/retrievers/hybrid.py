from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi
import numpy as np
from chromadb import PersistentClient

def _tok(t: str) -> List[str]:
    return [w.lower() for w in t.split()]

def _none_to_list(x):
    return [] if x is None else x

class HybridRetriever:
    def __init__(self, chroma_dir: str, collection: str):
        self.client = PersistentClient(path=chroma_dir)
        self.col = self.client.get_or_create_collection(
            collection, metadata={"hnsw:space": "cosine"}
        )
        self._bm25 = None
        self._bm25_ids = []

    def add_texts(
        self,
        ids: List[str],
        texts: List[str],
        metas: List[Dict[str, Any]],
        vecs: List[List[float]],
    ):
        self.col.upsert(ids=ids, documents=texts, metadatas=metas, embeddings=vecs)
        self._bm25 = None

    # ---------- internals ----------
    def _ensure_bm25(self):
        if self._bm25 is not None:
            return
        got = self.col.get(include=["documents"])
        self._bm25_ids = _none_to_list(got.get("ids"))
        docs = got.get("documents")
        docs = _none_to_list(docs)
        if len(docs) == 0:
            self._bm25 = None
            self._bm25_ids = []
            return
        toks = [_tok(d or "") for d in docs]
        if all(len(t) == 0 for t in toks):
            self._bm25 = None
            self._bm25_ids = []
            return
        self._bm25 = BM25Okapi(toks)

    def _vsearch(self, qv, k=10) -> List[Tuple[str, float]]:
        got = self.col.get(include=["embeddings"])
        embs = got.get("embeddings")
        ids  = got.get("ids")
        embs = _none_to_list(embs)
        ids  = _none_to_list(ids)
        if len(embs) == 0 or len(ids) == 0:
            return []
        emb = np.array(embs)
        sims = emb @ np.array(qv)
        order = np.argsort(-sims)[:k]
        return [(ids[i], float(sims[i])) for i in order]

    def _bsearch(self, q: str, k=10) -> List[Tuple[int, float]]:
        self._ensure_bm25()
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tok(q))
        if len(scores) == 0:
            return []
        order = np.argsort(-np.array(scores))[:k]
        return [(int(i), float(scores[i])) for i in order]

    # ---------- public ----------
    def search(self, query: str, qv: List[float], top_k: int = 8):
        # vector first
        v = self._vsearch(qv, k=top_k * 3)
        v_rank = {doc_id: r for r, (doc_id, _) in enumerate(v, 1)}

        # bm25 (indices -> ids)
        self._ensure_bm25()
        idx_to_id = {i: self._bm25_ids[i] for i in range(len(self._bm25_ids))}
        b_idx = self._bsearch(query, k=top_k * 3)
        b = [(idx_to_id[i], score) for i, score in b_idx] if idx_to_id else []
        b_rank = {doc_id: r for r, (doc_id, _) in enumerate(b, 1)}

        # RRF fuse
        k_rrf = 60.0
        cands = set([d for d, _ in v] + [d for d, _ in b])
        fused = []
        for d in cands:
            rv = 1.0 / (k_rrf + v_rank.get(d, 1e9))
            rb = 1.0 / (k_rrf + b_rank.get(d, 1e9))
            fused.append((d, rv + rb))
        fused.sort(key=lambda x: -x[1])

        # fetch payloads
        id_list = [d for d, _ in fused[:top_k]]
        if not id_list:
            return []
        got2 = self.col.get(ids=id_list, include=["documents","metadatas"])
        ids = _none_to_list(got2.get("ids"))
        docs = _none_to_list(got2.get("documents"))
        metas = _none_to_list(got2.get("metadatas"))
        id_to_doc = {i: d for i, d in zip(ids, docs)}
        id_to_meta = {i: m for i, m in zip(ids, metas)}

        return [{"id": i, "text": id_to_doc.get(i, ""), "metadata": id_to_meta.get(i, {})}
                for i in id_list]
