from pathlib import Path
from typing import Iterable, List, Tuple
from pypdf import PdfReader
from pdfminer.high_level import extract_text as pdfminer_extract_text
from docx import Document

TEXT_EXTS = {".txt", ".md"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}

def iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file():
            if p.suffix.lower() in TEXT_EXTS | PDF_EXTS | DOCX_EXTS:
                yield p

def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def read_pdf(path: Path) -> str:
    # Try pypdf first; fallback to pdfminer for stubborn PDFs
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return pdfminer_extract_text(str(path)) or ""

def read_docx(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)

def load_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in TEXT_EXTS:
        return read_text_file(path)
    if ext in PDF_EXTS:
        return read_pdf(path)
    if ext in DOCX_EXTS:
        return read_docx(path)
    return ""

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

