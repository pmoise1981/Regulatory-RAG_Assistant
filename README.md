# Regulatory RAG Assistant

Regulatory RAG Assistant is a local financial-compliance retrieval app for asking cited questions over Basel, OCC, FFIEC, and internal policy documents.

The project is designed as a portfolio-grade example of governed AI in regulated workflows: document ingestion, chunking, hybrid retrieval, cited answers, fallback extractive responses, and a browser UI that keeps source context visible.

## What It Demonstrates

- FastAPI API for regulatory Q&A
- Browser UI for questions, answers, source counts, and cited source metadata
- PDF, DOCX, HTML, Markdown, and text ingestion
- Chroma persistent vector index with SentenceTransformers embeddings
- BM25 + vector reciprocal-rank fusion retrieval
- Optional Ollama generation with `llama3.1:8b`
- Extractive fallback when Ollama is unavailable
- Lexical fallback when the vector index or embedding model is not ready
- Local demo source documents for clean-clone testing

## Architecture

```text
source documents
  -> scripts/ingest.py
  -> parser + chunker
  -> sentence-transformer embeddings
  -> Chroma vector store
  -> HybridRetriever vector + BM25 fusion
  -> FastAPI /ask endpoint
  -> Ollama answer or extractive fallback
  -> browser UI with source metadata
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make ingest
make serve
```

Open:

```text
http://127.0.0.1:8000
```

The repo includes small demo notes under `data/source_docs/` so `make ingest` works from a clean clone. Replace those notes with official PDFs or internal policies for a real demo.

## Optional Local LLM

By default, the app runs without a model server and returns extractive cited answers from retrieved context.

To enable local generation:

```bash
ollama serve
ollama pull llama3.1:8b
LLM_BACKEND=local make serve
```

Environment settings:

```bash
APP_ENV=dev
APP_PORT=8000
CHROMA_DIR=./data/vectors/chroma
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
LLM_BACKEND=none
LLM_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
```

## API

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Ask a question:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the G-SIB systemic importance categories?","top_k":6}'
```

Check LLM mode:

```bash
curl http://127.0.0.1:8000/mode
```

## Data Layout

```text
data/source_docs/
  basel/
  occ/
  ffiec/

data/chunks/chunks.jsonl
data/vectors/chroma/
```

`scripts/ingest.py` reads source documents, writes `data/chunks/chunks.jsonl`, embeds chunks, and upserts them into Chroma.

If the vector index is not available, `/ask` falls back to lexical search over `data/chunks/chunks.jsonl`. That keeps the demo usable while the heavier embedding stack is being set up.

## Commands

```bash
make init      # create venv and install dependencies
make ingest    # parse source docs, chunk, embed, and index
make serve     # run FastAPI app
make clean     # clear cache/tmp/scratch directories
```

Rebuild the vector index from existing chunks:

```bash
python -m scripts.reindex
```

## Docker

```bash
docker compose up --build
```

Open:

```text
http://127.0.0.1:8000
```

The compose file includes an optional Ollama service. Pull the model inside that service before using `LLM_BACKEND=local`.

## Portfolio Talking Points

- Built a regulator-aware RAG assistant rather than a generic chatbot.
- Added source-grounded answer behavior for auditability.
- Used hybrid retrieval to combine semantic relevance with keyword precision.
- Added fallback paths so demos remain usable without external model calls.
- Structured the app for regulated workflows where citations, source metadata, and reviewer trust matter.

## Roadmap

- Add official regulator download scripts with source timestamps.
- Add answer-level citation validation.
- Store query/audit history in SQLite or Postgres.
- Add evaluation datasets for retrieval precision and citation coverage.
- Add role-based access controls for internal policy collections.

## Disclaimer

The included demo notes are synthetic summaries for local testing. They are not legal, compliance, or regulatory advice. Replace them with official source documents before using the app for substantive analysis.
