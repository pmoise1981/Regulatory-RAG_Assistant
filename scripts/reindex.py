from pathlib import Path
import json
from app.core.settings import settings
from app.embeddings.loader import embed_texts
from app.retrievers.hybrid import HybridRetriever

CHUNK_FILE = Path("data/chunks/chunks.jsonl")

def main():
    if not CHUNK_FILE.exists():
        print("[reindex] no chunks.jsonl found. Run `make ingest` first.")
        return
    retriever = HybridRetriever(settings.CHROMA_DIR, "regulatory_chunks")
    ids, texts, metas = [], [], []
    with open(CHUNK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            ids.append(obj["id"]); texts.append(obj["text"]); metas.append(obj["metadata"])
    vecs = embed_texts(texts, settings.EMBEDDING_MODEL)
    retriever.add_texts(ids, texts, metas, vecs)
    print(f"[reindex] reindexed {len(ids)} chunks.")

if __name__ == "__main__":
    main()
