"""
api/database.py
────────────────
PostgreSQL persistence layer for job metadata and dashboard analytics.

Falls back to SQLite transparently when DATABASE_URL is unset or the
PostgreSQL server is unreachable, so local development without a running
Postgres instance still works.

Public API
──────────
    init_db()                          → None   (create tables + migrate)
    save_job(job)                      → None
    get_job(pipeline_id)               → dict | None
    update_job(pipeline_id, **fields)  → None
    save_stage_timing(pipeline_id, stage, duration_ms, status)
    get_dashboard_stats()              → dict
    get_recent_jobs(limit)             → list[dict]
"""

import json
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any


def _duration_ms(created_at: str | None, updated_at: str | None) -> float | None:
    """
    Compute elapsed milliseconds between two ISO timestamp strings.

    Handles mixed naive/aware timestamps correctly: naive strings are always
    treated as UTC (they were produced by datetime.utcnow() in older code).
    Returns None if either timestamp is missing or the result is negative
    (which indicates a stored timezone mismatch from historical data).
    """
    if not created_at or not updated_at:
        return None
    try:
        def _parse(s: str) -> datetime:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        ms = (_parse(updated_at) - _parse(created_at)).total_seconds() * 1000
        return round(ms) if ms >= 0 else None   # discard bogus negatives
    except Exception:
        return None

import config

logger = logging.getLogger("qa_agent.database")

# ── Connection pool ───────────────────────────────────────────────────────────
_pool = None
_pool_lock = threading.Lock()
_using_postgres = False


def _init_pool() -> bool:
    """Initialise psycopg2 ThreadedConnectionPool. Returns True on success."""
    global _pool, _using_postgres
    if not config.DATABASE_URL:
        return False
    try:
        import psycopg2
        from psycopg2 import pool as pgpool

        _pool = pgpool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=config.DATABASE_URL,
            connect_timeout=5,
        )
        _using_postgres = True
        logger.info("PostgreSQL connection pool initialised: %s", config.DATABASE_URL.split("@")[-1])
        return True
    except Exception as exc:
        logger.warning("PostgreSQL unavailable (%s) — falling back to SQLite", exc)
        _using_postgres = False
        return False


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _init_pool()
    return _pool


@contextmanager
def _pg_conn():
    """Yield a psycopg2 connection from the pool, return it on exit."""
    pool = _get_pool()
    if pool is None:
        raise RuntimeError("PostgreSQL pool not initialised")
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS qa_jobs (
    pipeline_id     TEXT        PRIMARY KEY,
    status          TEXT        NOT NULL DEFAULT 'queued',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    input_source    TEXT        NOT NULL DEFAULT '',
    output_mode     TEXT        NOT NULL DEFAULT 'questions',
    num_questions   INTEGER     NOT NULL DEFAULT 5,
    request_id      TEXT,
    identity        TEXT,
    result_markdown TEXT,
    result_pdf_path TEXT,
    error_message   TEXT,
    cached          BOOLEAN     NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS qa_stage_timings (
    id              SERIAL      PRIMARY KEY,
    pipeline_id     TEXT        NOT NULL REFERENCES qa_jobs(pipeline_id) ON DELETE CASCADE,
    stage_name      TEXT        NOT NULL,
    duration_ms     FLOAT       NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'success',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qa_jobs_status     ON qa_jobs(status);
CREATE INDEX IF NOT EXISTS idx_qa_jobs_created_at ON qa_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stage_pipeline_id  ON qa_stage_timings(pipeline_id);
"""


def init_db() -> None:
    """Create tables and indexes. Called once at server startup."""
    if not _using_postgres and _pool is None:
        if not _init_pool():
            logger.info("PostgreSQL not configured — using SQLite for jobs")
            _init_sqlite()
            return

    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA_SQL)
        logger.info("PostgreSQL schema ready (qa_jobs, qa_stage_timings)")
    except Exception as exc:
        logger.error("Failed to init PostgreSQL schema: %s", exc)
        _init_sqlite()


# ── SQLite fallback ───────────────────────────────────────────────────────────
import sqlite3
from pathlib import Path

_SQLITE_PATH = Path(__file__).parent / "jobs.db"
_sqlite_lock = threading.Lock()


def _init_sqlite() -> None:
    global _using_postgres
    _using_postgres = False
    with sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qa_jobs (
                pipeline_id     TEXT PRIMARY KEY,
                status          TEXT NOT NULL DEFAULT 'queued',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                input_source    TEXT NOT NULL DEFAULT '',
                output_mode     TEXT NOT NULL DEFAULT 'questions',
                num_questions   INTEGER NOT NULL DEFAULT 5,
                request_id      TEXT,
                identity        TEXT,
                result_markdown TEXT,
                result_pdf_path TEXT,
                error_message   TEXT,
                cached          INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qa_stage_timings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pipeline_id TEXT NOT NULL,
                stage_name  TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                status      TEXT NOT NULL DEFAULT 'success',
                created_at  TEXT NOT NULL
            )
        """)
        conn.commit()
    logger.info("SQLite schema ready: %s", _SQLITE_PATH)


# ── Public CRUD ───────────────────────────────────────────────────────────────

def save_job(job: dict[str, Any]) -> None:
    pid = job["pipeline_id"]
    now = datetime.now(timezone.utc).isoformat()

    if _using_postgres:
        sql = """
            INSERT INTO qa_jobs
              (pipeline_id, status, created_at, updated_at, input_source,
               output_mode, num_questions, request_id, identity, cached)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (pipeline_id) DO UPDATE SET
              status=EXCLUDED.status, updated_at=EXCLUDED.updated_at
        """
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (
                        pid,
                        job.get("status", "queued"),
                        job.get("created_at", now),
                        job.get("updated_at", now),
                        job.get("input_source", ""),
                        job.get("output_mode", "questions"),
                        int(job.get("num_questions", 5)),
                        job.get("request_id"),
                        job.get("identity"),
                        bool(job.get("cached", False)),
                    ))
            return
        except Exception as exc:
            logger.warning("PG save_job failed, using SQLite: %s", exc)

    # SQLite fallback
    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO qa_jobs
              (pipeline_id, status, created_at, updated_at, input_source,
               output_mode, num_questions, request_id, identity, cached)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            pid,
            job.get("status", "queued"),
            job.get("created_at", now),
            job.get("updated_at", now),
            job.get("input_source", ""),
            job.get("output_mode", "questions"),
            int(job.get("num_questions", 5)),
            job.get("request_id"),
            job.get("identity"),
            1 if job.get("cached") else 0,
        ))
        conn.commit()


def get_job(pipeline_id: str) -> dict[str, Any] | None:
    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM qa_jobs WHERE pipeline_id=%s", (pipeline_id,))
                    row = cur.fetchone()
                    if not row:
                        return None
                    cols = [d[0] for d in cur.description]
                    return dict(zip(cols, row))
        except Exception as exc:
            logger.warning("PG get_job failed: %s", exc)

    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM qa_jobs WHERE pipeline_id=?", (pipeline_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_job(pipeline_id: str, **fields) -> None:
    now = datetime.now(timezone.utc).isoformat()
    fields["updated_at"] = now

    if _using_postgres:
        set_clause = ", ".join(f"{k}=%s" for k in fields)
        values = list(fields.values()) + [pipeline_id]
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE qa_jobs SET {set_clause} WHERE pipeline_id=%s",
                        values,
                    )
            return
        except Exception as exc:
            logger.warning("PG update_job failed: %s", exc)

    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [pipeline_id]
    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.execute(f"UPDATE qa_jobs SET {set_clause} WHERE pipeline_id=?", values)
        conn.commit()


def save_stage_timing(pipeline_id: str, stage_name: str,
                      duration_ms: float, status: str = "success") -> None:
    now = datetime.now(timezone.utc).isoformat()
    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO qa_stage_timings
                           (pipeline_id, stage_name, duration_ms, status, created_at)
                           VALUES (%s,%s,%s,%s,%s)""",
                        (pipeline_id, stage_name, duration_ms, status, now),
                    )
            return
        except Exception as exc:
            logger.warning("PG save_stage_timing failed: %s", exc)

    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.execute(
            "INSERT INTO qa_stage_timings (pipeline_id,stage_name,duration_ms,status,created_at) VALUES (?,?,?,?,?)",
            (pipeline_id, stage_name, duration_ms, status, now),
        )
        conn.commit()


# ── Dashboard analytics ───────────────────────────────────────────────────────

def get_dashboard_stats() -> dict:
    """Return aggregate stats for the dashboard."""
    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*)                                           AS total,
                            COUNT(*) FILTER (WHERE status='completed')        AS completed,
                            COUNT(*) FILTER (WHERE status='failed')           AS failed,
                            COUNT(*) FILTER (WHERE status IN ('queued','processing')) AS pending,
                            COUNT(*) FILTER (WHERE cached=TRUE)               AS cache_hits,
                            0 AS avg_duration_ms
                        FROM qa_jobs
                    """)
                    row = cur.fetchone()
                    cols = [d[0] for d in cur.description]
                    stats = dict(zip(cols, row))

                    # Compute avg_duration_ms in Python to handle mixed naive/aware timestamps
                    cur.execute("""
                        SELECT created_at, updated_at FROM qa_jobs WHERE status='completed'
                    """)
                    durations = [
                        _duration_ms(str(r[0]), str(r[1]))
                        for r in cur.fetchall()
                    ]
                    valid = [d for d in durations if d is not None and d >= 0]
                    stats["avg_duration_ms"] = round(sum(valid) / len(valid)) if valid else 0

                    # Per-mode breakdown
                    cur.execute("""
                        SELECT output_mode, COUNT(*) AS cnt
                        FROM qa_jobs GROUP BY output_mode
                    """)
                    stats["by_mode"] = {r[0]: r[1] for r in cur.fetchall()}

                    # Hourly throughput (last 24 h)
                    cur.execute("""
                        SELECT DATE_TRUNC('hour', created_at) AS hour, COUNT(*) AS cnt
                        FROM qa_jobs
                        WHERE created_at >= NOW() - INTERVAL '24 hours'
                        GROUP BY 1 ORDER BY 1
                    """)
                    stats["hourly"] = [{"hour": str(r[0]), "count": r[1]} for r in cur.fetchall()]

                    # Average stage durations
                    cur.execute("""
                        SELECT stage_name,
                               ROUND(AVG(duration_ms)::numeric, 0)::float AS avg_ms,
                               COUNT(*) AS runs
                        FROM qa_stage_timings GROUP BY stage_name ORDER BY avg_ms DESC
                    """)
                    stats["stage_avg_ms"] = {r[0]: {"avg_ms": r[1], "runs": r[2]} for r in cur.fetchall()}

                    return {k: (int(v) if isinstance(v, float) and v == int(v) else v)
                            if v is not None else 0
                            for k, v in stats.items()}
        except Exception as exc:
            logger.warning("PG get_dashboard_stats failed: %s", exc)

    # SQLite fallback
    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT
                COUNT(*)                                            AS total,
                SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status='failed'    THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status IN ('queued','processing') THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN cached=1 THEN 1 ELSE 0 END)           AS cache_hits
            FROM qa_jobs
        """).fetchone()
        stats = dict(row)
        stats["avg_duration_ms"] = 0
        stats["by_mode"] = {}
        stats["hourly"] = []
        stats["stage_avg_ms"] = {}
        return stats


def get_recent_jobs(limit: int = 50) -> list[dict]:
    """Return the most recent jobs for the dashboard table."""
    rows_raw: list[dict] = []

    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT pipeline_id, status, output_mode, num_questions,
                               cached, created_at, updated_at, error_message
                        FROM qa_jobs ORDER BY created_at DESC LIMIT %s
                    """, (limit,))
                    cols = [d[0] for d in cur.description]
                    rows_raw = [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as exc:
            logger.warning("PG get_recent_jobs failed: %s", exc)

    if not rows_raw:
        with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            rows_raw = [dict(r) for r in conn.execute("""
                SELECT pipeline_id, status, output_mode, num_questions,
                       cached, created_at, updated_at, error_message
                FROM qa_jobs ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()]

    for row in rows_raw:
        # Duration — computed in Python to handle mixed naive/aware timestamps.
        row["duration_ms"] = _duration_ms(
            str(row.get("created_at") or ""),
            str(row.get("updated_at") or ""),
        )

        # Human-readable reason for the dashboard "Reason" column.
        status = row.get("status", "")
        err    = row.get("error_message") or ""
        if status == "completed" and row.get("cached"):
            row["reason"] = "Served from cache"
        elif status == "completed":
            row["reason"] = "Pipeline completed"
        elif status == "failed":
            # Shorten Groq rate-limit noise to a clear message
            if "rate limit" in err.lower() or "quota" in err.lower() or "429" in err:
                row["reason"] = "Groq API rate limit — retry later"
            elif "server restarted" in err.lower():
                row["reason"] = "Server restarted mid-job"
            elif "all llm providers" in err.lower():
                row["reason"] = "Groq API rate limit — retry later"
            elif err:
                row["reason"] = err[:80]
            else:
                row["reason"] = "Unknown error"
        elif status == "processing":
            row["reason"] = "Running pipeline…"
        elif status == "queued":
            row["reason"] = "Waiting in queue"
        else:
            row["reason"] = ""

    return rows_raw
