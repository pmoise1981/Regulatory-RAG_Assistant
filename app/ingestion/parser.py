from pathlib import Path
from typing import List
import docx2txt
from pypdf import PdfReader
from bs4 import BeautifulSoup
def read_pdf(p: Path) -> str:
    out=[]; rdr=PdfReader(str(p))
    for pg in rdr.pages: out.append(pg.extract_text() or "")
    return "\n".join(out)
def read_docx(p: Path) -> str: return docx2txt.process(str(p)) or ""
def read_html(p: Path) -> str:
    soup=BeautifulSoup(Path(p).read_text(errors="ignore"),"lxml")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()
    main = (
        soup.select_one(".field--name-body")
        or soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )
    return main.get_text(" ")
def load_file(p: Path) -> str:
    ext=p.suffix.lower()
    if ext==".pdf": return read_pdf(p)
    if ext==".docx": return read_docx(p)
    if ext in (".html",".htm"): return read_html(p)
    return Path(p).read_text(errors="ignore")
def chunk_text(text:str, size:int=1200, overlap:int=200)->List[str]:
    w=text.split(); i=0; out=[]
    while i<len(w):
        out.append(" ".join(w[i:i+size])); i += max(1, size-overlap)
    return out
