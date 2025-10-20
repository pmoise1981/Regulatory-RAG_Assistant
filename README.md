# Regulatory RAG — AI-Powered Financial Compliance Assistant

Local Retrieval-Augmented Generation (RAG) system built with **FastAPI**, **Ollama (Llama 3.1 8B)**, and **ChromaDB** to answer Basel III, OCC, and FFIEC regulatory questions with cited responses.  
Includes document ingestion, semantic search, and regulator-aware retrieval.

## Quickstart
```bash
# 1) create venv
python3 -m venv .venv && source .venv/bin/activate

# 2) install
pip install -r requirements.txt

# 3) (optional) set local LLM backend via Ollama
ollama serve
ollama pull llama3.1:8b

# 4) ingest your PDFs into data/source_docs/{basel,ffiec,occ}/ then:
make ingest

# 5) run API
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
