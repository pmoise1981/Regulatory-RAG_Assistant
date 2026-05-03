import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.core.settings import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS query_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    retrieval_mode TEXT NOT NULL,
    source_count INTEGER NOT NULL,
    sources_json TEXT NOT NULL,
    latency_ms INTEGER NOT NULL
)
"""


def _db_path() -> Path:
    path = Path(settings.AUDIT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_audit_db() -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.execute(SCHEMA)
        conn.commit()


def log_query(
    *,
    query: str,
    answer: str,
    retrieval_mode: str,
    sources: list[dict[str, Any]],
    latency_ms: int,
) -> int:
    init_audit_db()
    with sqlite3.connect(_db_path()) as conn:
        cur = conn.execute(
            """
            INSERT INTO query_audit
                (created_at, query, answer, retrieval_mode, source_count, sources_json, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                query,
                answer,
                retrieval_mode,
                len(sources),
                json.dumps(sources, ensure_ascii=False),
                latency_ms,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def recent_queries(limit: int = 25) -> list[dict[str, Any]]:
    init_audit_db()
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, created_at, query, answer, retrieval_mode, source_count, sources_json, latency_ms
            FROM query_audit
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        item["sources"] = json.loads(item.pop("sources_json") or "[]")
        out.append(item)
    return out
