from pathlib import Path
import json, hashlib
from tqdm import tqdm
from app.core.settings import settings
from app.embeddings.loader import embed_texts
from app.ingestion.parser import load_file, chunk_text
from app.retrievers.hybrid import HybridRetriever
SRC=Path("data/source_docs"); CHUNK=Path("data/chunks")
def h(s:str)->str: return hashlib.sha1(s.encode()).hexdigest()
def main():
    files=[p for p in SRC.rglob("*") if p.is_file()]
    chunks=[]
    for p in tqdm(files, desc="Parsing"):
        try: text=load_file(p)
        except Exception as e: print(f"[warn] {p}: {e}"); continue
        base=h(str(p.resolve()))
        for i,ch in enumerate(chunk_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)):
            chunks.append({"id":f"{base}:{i}","text":ch,"metadata":{"title":p.stem,"path":str(p),"source":p.parent.name,"chunk":i}})
    CHUNK.mkdir(parents=True, exist_ok=True)
    with open(CHUNK/"chunks.jsonl","w",encoding="utf-8") as f:
        for c in chunks: f.write(json.dumps(c, ensure_ascii=False)+"\n")
    ret=HybridRetriever(settings.CHROMA_DIR,"regulatory_chunks")
    ids=[c["id"] for c in chunks]; tx=[c["text"] for c in chunks]; meta=[c["metadata"] for c in chunks]
    vecs=embed_texts(tx, settings.EMBEDDING_MODEL)
    ret.add_texts(ids, tx, meta, vecs)
    print(f"[ingest] {len(ids)} chunks indexed.")
if __name__=="__main__": main()
