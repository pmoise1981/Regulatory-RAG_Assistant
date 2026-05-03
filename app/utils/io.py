from pathlib import Path
from typing import Iterable, List, Tuple
from app.ingestion.parser import load_file

TEXT_EXTS = {".txt", ".md"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
HTML_EXTS = {".html", ".htm"}
SUPPORTED_EXTS = TEXT_EXTS | PDF_EXTS | DOCX_EXTS | HTML_EXTS

def iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            yield p

def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def load_text(path: Path) -> str:
    return load_file(path)

def sliding_window_chunks(text: str, size: int, overlap: int) -> List[Tuple[int, str]]:
    if not text:
        return []
    tokens = text.split()
    if len(tokens) <= size:
        return [(0, text)]
    chunks = []
    i = 0
    idx = 0
    while i < len(tokens):
        chunk_tokens = tokens[i : i + size]
        chunk = " ".join(chunk_tokens)
        chunks.append((idx, chunk))
        idx += 1
        i += size - overlap if size > overlap else size
    return chunks
