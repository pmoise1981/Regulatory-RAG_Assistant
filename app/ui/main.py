from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
router = APIRouter()
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
router.mount("/static", StaticFiles(directory=static_dir), name="static")
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    html = (static_dir / "index.html").read_text(encoding="utf-8") if (static_dir / "index.html").exists() else "<h1>Regulatory RAG</h1>"
    return HTMLResponse(content=html)
