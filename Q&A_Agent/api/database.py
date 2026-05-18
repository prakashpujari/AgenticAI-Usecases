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

CREATE TABLE IF NOT EXISTS qa_reviews (
    review_id        TEXT        PRIMARY KEY,
    rating           INTEGER     CHECK(rating IS NULL OR rating BETWEEN 1 AND 5),
    review_text      TEXT,
    use_case         TEXT,
    output_mode      TEXT,
    job_id           TEXT,
    identity         TEXT,
    reviewer_name    TEXT,
    parent_review_id TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sentiment        TEXT,
    sentiment_score  REAL
);

CREATE TABLE IF NOT EXISTS uploaded_files (
    file_id     TEXT        PRIMARY KEY,
    filename    TEXT        NOT NULL,
    file_path   TEXT,
    pipeline_id TEXT,
    size_bytes  BIGINT,
    mime_type   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS access_logs (
    log_id       TEXT        PRIMARY KEY,
    ip           TEXT,
    country      TEXT,
    country_code TEXT,
    region       TEXT,
    city         TEXT,
    request_type TEXT,
    endpoint     TEXT,
    latency_ms   REAL,
    status_code  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qa_jobs_status      ON qa_jobs(status);
CREATE INDEX IF NOT EXISTS idx_qa_jobs_created_at  ON qa_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stage_pipeline_id   ON qa_stage_timings(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_reviews_created_at  ON qa_reviews(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_rating      ON qa_reviews(rating);
CREATE INDEX IF NOT EXISTS idx_files_pipeline      ON uploaded_files(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_created ON access_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_logs_country ON access_logs(country_code);
"""

# Migrations applied after _SCHEMA_SQL — each wrapped individually so one
# failure cannot abort the others.  Ordered: columns first, then indexes that
# depend on those columns.
_MIGRATIONS_PG = [
    "ALTER TABLE qa_reviews ADD COLUMN IF NOT EXISTS reviewer_name TEXT",
    "ALTER TABLE qa_reviews ADD COLUMN IF NOT EXISTS parent_review_id TEXT",
    # Index depends on the column above — must run after
    "CREATE INDEX IF NOT EXISTS idx_reviews_parent ON qa_reviews(parent_review_id)",
    # Allow NULL rating so reply rows (no rating) can be stored
    "ALTER TABLE qa_reviews ALTER COLUMN rating DROP NOT NULL",
    "ALTER TABLE qa_reviews DROP CONSTRAINT IF EXISTS qa_reviews_rating_check",
    "ALTER TABLE qa_reviews ADD CONSTRAINT qa_reviews_rating_check CHECK (rating IS NULL OR rating BETWEEN 1 AND 5)",
]


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
        logger.info("PostgreSQL base schema ready")
    except Exception as exc:
        logger.error("Failed to init PostgreSQL base schema: %s — falling back to SQLite", exc)
        _init_sqlite()
        return

    # Run each migration individually; log failures but never abort startup
    for migration in _MIGRATIONS_PG:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(migration)
            logger.debug("Migration OK: %s", migration[:60])
        except Exception as exc:
            logger.warning("Migration skipped (already applied or error): %s | %s", migration[:60], exc)

    logger.info("PostgreSQL schema ready (qa_jobs, qa_stage_timings, qa_reviews, uploaded_files, access_logs)")


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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qa_reviews (
                review_id        TEXT PRIMARY KEY,
                rating           INTEGER CHECK(rating IS NULL OR (rating BETWEEN 1 AND 5)),
                review_text      TEXT,
                use_case         TEXT,
                output_mode      TEXT,
                job_id           TEXT,
                identity         TEXT,
                reviewer_name    TEXT,
                parent_review_id TEXT,
                created_at       TEXT NOT NULL,
                sentiment        TEXT,
                sentiment_score  REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_files (
                file_id     TEXT PRIMARY KEY,
                filename    TEXT NOT NULL,
                file_path   TEXT,
                pipeline_id TEXT,
                size_bytes  INTEGER,
                mime_type   TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS access_logs (
                log_id       TEXT PRIMARY KEY,
                ip           TEXT,
                country      TEXT,
                country_code TEXT,
                region       TEXT,
                city         TEXT,
                request_type TEXT,
                endpoint     TEXT,
                latency_ms   REAL,
                status_code  INTEGER,
                created_at   TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON qa_reviews(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_rating ON qa_reviews(rating)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_created ON access_logs(created_at DESC)")
        # Migrations for existing tables
        for col_sql in [
            "ALTER TABLE qa_reviews ADD COLUMN reviewer_name TEXT",
            "ALTER TABLE qa_reviews ADD COLUMN parent_review_id TEXT",
        ]:
            try:
                conn.execute(col_sql)
            except Exception:
                pass
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

        # Compute avg_duration_ms in Python (same approach as PostgreSQL path)
        completed_rows = conn.execute(
            "SELECT created_at, updated_at FROM qa_jobs WHERE status='completed'"
        ).fetchall()
        durations = [_duration_ms(str(r[0]), str(r[1])) for r in completed_rows]
        valid = [d for d in durations if d is not None and d >= 0]
        stats["avg_duration_ms"] = round(sum(valid) / len(valid)) if valid else 0

        by_mode_rows = conn.execute(
            "SELECT output_mode, COUNT(*) FROM qa_jobs GROUP BY output_mode"
        ).fetchall()
        stats["by_mode"] = {r[0]: r[1] for r in by_mode_rows}

        stage_rows = conn.execute(
            "SELECT stage_name, AVG(duration_ms), COUNT(*) FROM qa_stage_timings GROUP BY stage_name"
        ).fetchall()
        stats["stage_avg_ms"] = {
            r[0]: {"avg_ms": round(r[1], 0), "runs": r[2]} for r in stage_rows
        }

        stats["hourly"] = []
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


# ── Reviews ───────────────────────────────────────────────────────────────────

def save_review(review: dict[str, Any]) -> None:
    """Persist a user review/rating."""
    now = datetime.now(timezone.utc).isoformat()
    rid = review["review_id"]

    # None rating is valid for reply rows (no star rating given)
    raw_rating = review.get("rating")
    rating_val = int(raw_rating) if raw_rating is not None else None

    if _using_postgres:
        sql = """
            INSERT INTO qa_reviews
              (review_id, rating, review_text, use_case, output_mode,
               job_id, identity, reviewer_name, parent_review_id, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (review_id) DO NOTHING
        """
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (
                        rid,
                        rating_val,
                        review.get("review_text"),
                        review.get("use_case"),
                        review.get("output_mode"),
                        review.get("job_id"),
                        review.get("identity"),
                        review.get("reviewer_name"),
                        review.get("parent_review_id"),
                        now,
                    ))
            return
        except Exception as exc:
            logger.warning("PG save_review failed, using SQLite: %s", exc)

    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.execute("""
            INSERT OR IGNORE INTO qa_reviews
              (review_id, rating, review_text, use_case, output_mode,
               job_id, identity, reviewer_name, parent_review_id, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            rid,
            rating_val,
            review.get("review_text"),
            review.get("use_case"),
            review.get("output_mode"),
            review.get("job_id"),
            review.get("identity"),
            review.get("reviewer_name"),
            review.get("parent_review_id"),
            now,
        ))
        conn.commit()


def get_reviews(limit: int = 20) -> list[dict]:
    """Return recent reviews ordered newest first."""
    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT review_id, rating, review_text, use_case,
                               output_mode, job_id, reviewer_name, created_at,
                               sentiment, sentiment_score
                        FROM qa_reviews ORDER BY created_at DESC LIMIT %s
                    """, (limit,))
                    cols = [d[0] for d in cur.description]
                    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                    for r in rows:
                        if hasattr(r.get("created_at"), "isoformat"):
                            r["created_at"] = r["created_at"].isoformat()
                    return rows
        except Exception as exc:
            logger.warning("PG get_reviews failed: %s", exc)

    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT review_id, rating, review_text, use_case,
                   output_mode, job_id, reviewer_name, created_at,
                   sentiment, sentiment_score
            FROM qa_reviews ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_review_stats() -> dict:
    """Return aggregate rating statistics."""
    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*)          AS total,
                            ROUND(AVG(rating)::numeric, 2) AS avg_rating,
                            COUNT(*) FILTER (WHERE rating=5) AS five,
                            COUNT(*) FILTER (WHERE rating=4) AS four,
                            COUNT(*) FILTER (WHERE rating=3) AS three,
                            COUNT(*) FILTER (WHERE rating=2) AS two,
                            COUNT(*) FILTER (WHERE rating=1) AS one
                        FROM qa_reviews
                        WHERE parent_review_id IS NULL AND rating IS NOT NULL
                    """)
                    row = cur.fetchone()
                    cols = [d[0] for d in cur.description]
                    r = dict(zip(cols, row))
                    return {
                        "total":        int(r["total"] or 0),
                        "avg_rating":   float(r["avg_rating"] or 0),
                        "distribution": {5: int(r["five"] or 0), 4: int(r["four"] or 0),
                                         3: int(r["three"] or 0), 2: int(r["two"] or 0),
                                         1: int(r["one"] or 0)},
                    }
        except Exception as exc:
            logger.warning("PG get_review_stats failed: %s", exc)

    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                AVG(CAST(rating AS REAL)) AS avg_rating,
                SUM(CASE WHEN rating=5 THEN 1 ELSE 0 END) AS five,
                SUM(CASE WHEN rating=4 THEN 1 ELSE 0 END) AS four,
                SUM(CASE WHEN rating=3 THEN 1 ELSE 0 END) AS three,
                SUM(CASE WHEN rating=2 THEN 1 ELSE 0 END) AS two,
                SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) AS one
            FROM qa_reviews
            WHERE parent_review_id IS NULL AND rating IS NOT NULL
        """).fetchone()
        r = dict(row)
        return {
            "total":        int(r["total"] or 0),
            "avg_rating":   round(float(r["avg_rating"] or 0), 2),
            "distribution": {5: int(r["five"] or 0), 4: int(r["four"] or 0),
                             3: int(r["three"] or 0), 2: int(r["two"] or 0),
                             1: int(r["one"] or 0)},
        }


def get_reviews_with_replies(limit: int = 20) -> list[dict]:
    """Return top-level reviews with nested replies."""
    # Fetch all reviews (top-level + replies) in one query
    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT review_id, rating, review_text, use_case, output_mode,
                               job_id, reviewer_name, parent_review_id, created_at,
                               sentiment, sentiment_score
                        FROM qa_reviews
                        ORDER BY created_at ASC
                        LIMIT %s
                    """, (limit * 5,))  # fetch extra to include replies
                    cols = [d[0] for d in cur.description]
                    all_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                    for r in all_rows:
                        if hasattr(r.get("created_at"), "isoformat"):
                            r["created_at"] = r["created_at"].isoformat()
        except Exception as exc:
            logger.warning("PG get_reviews_with_replies failed: %s", exc)
            all_rows = []
    else:
        with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            all_rows = [dict(r) for r in conn.execute("""
                SELECT review_id, rating, review_text, use_case, output_mode,
                       job_id, reviewer_name, parent_review_id, created_at,
                       sentiment, sentiment_score
                FROM qa_reviews ORDER BY created_at ASC LIMIT ?
            """, (limit * 5,)).fetchall()]

    # Build threaded structure: top-level reviews with replies list
    by_id = {r["review_id"]: {**r, "replies": []} for r in all_rows}
    roots = []
    for r in all_rows:
        pid = r.get("parent_review_id")
        if pid and pid in by_id:
            by_id[pid]["replies"].append(by_id[r["review_id"]])
        elif not pid:
            roots.append(by_id[r["review_id"]])

    # Return newest-first top-level reviews
    roots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return roots[:limit]


def save_review_reply(reply: dict[str, Any]) -> None:
    """Save a reply to an existing review (parent_review_id set)."""
    save_review(reply)  # reuse save_review — parent_review_id is stored


# ── Uploaded Files ────────────────────────────────────────────────────────────

def save_uploaded_file(file_data: dict[str, Any]) -> None:
    """Track an uploaded file associated with a pipeline job."""
    now = datetime.now(timezone.utc).isoformat()
    fid = file_data["file_id"]

    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO uploaded_files
                          (file_id, filename, file_path, pipeline_id, size_bytes, mime_type, created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (file_id) DO NOTHING
                    """, (
                        fid, file_data.get("filename"), file_data.get("file_path"),
                        file_data.get("pipeline_id"), file_data.get("size_bytes"),
                        file_data.get("mime_type"), now,
                    ))
            return
        except Exception as exc:
            logger.warning("PG save_uploaded_file failed: %s", exc)

    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.execute("""
            INSERT OR IGNORE INTO uploaded_files
              (file_id, filename, file_path, pipeline_id, size_bytes, mime_type, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (fid, file_data.get("filename"), file_data.get("file_path"),
              file_data.get("pipeline_id"), file_data.get("size_bytes"),
              file_data.get("mime_type"), now))
        conn.commit()


def get_uploaded_files(limit: int = 50) -> list[dict]:
    """Return recently uploaded files, newest first."""
    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT f.file_id, f.filename, f.file_path, f.pipeline_id,
                               f.size_bytes, f.mime_type, f.created_at,
                               j.status AS job_status, j.output_mode
                        FROM uploaded_files f
                        LEFT JOIN qa_jobs j ON j.pipeline_id = f.pipeline_id
                        ORDER BY f.created_at DESC LIMIT %s
                    """, (limit,))
                    cols = [d[0] for d in cur.description]
                    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                    for r in rows:
                        if hasattr(r.get("created_at"), "isoformat"):
                            r["created_at"] = r["created_at"].isoformat()
                    return rows
        except Exception as exc:
            logger.warning("PG get_uploaded_files failed: %s", exc)

    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT f.file_id, f.filename, f.file_path, f.pipeline_id,
                   f.size_bytes, f.mime_type, f.created_at,
                   j.status AS job_status, j.output_mode
            FROM uploaded_files f
            LEFT JOIN qa_jobs j ON j.pipeline_id = f.pipeline_id
            ORDER BY f.created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def delete_uploaded_file(file_id: str) -> dict | None:
    """Delete file record and return file_path so caller can remove from disk."""
    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM uploaded_files WHERE file_id=%s RETURNING file_path, pipeline_id",
                        (file_id,)
                    )
                    row = cur.fetchone()
                    return {"file_path": row[0], "pipeline_id": row[1]} if row else None
        except Exception as exc:
            logger.warning("PG delete_uploaded_file failed: %s", exc)

    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT file_path, pipeline_id FROM uploaded_files WHERE file_id=?", (file_id,)
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM uploaded_files WHERE file_id=?", (file_id,))
        conn.commit()
        return dict(row)


# ── Access Logs ───────────────────────────────────────────────────────────────

def save_access_log(log: dict[str, Any]) -> None:
    """Persist an access log entry (non-blocking — caller should use BackgroundTask)."""
    now = datetime.now(timezone.utc).isoformat()
    lid = log.get("log_id") or __import__("uuid").uuid4().hex

    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO access_logs
                          (log_id, ip, country, country_code, region, city,
                           request_type, endpoint, latency_ms, status_code, created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (log_id) DO NOTHING
                    """, (
                        lid, log.get("ip"), log.get("country"), log.get("country_code"),
                        log.get("region"), log.get("city"), log.get("request_type"),
                        log.get("endpoint"), log.get("latency_ms"), log.get("status_code"), now,
                    ))
            return
        except Exception as exc:
            logger.warning("PG save_access_log failed: %s", exc)

    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.execute("""
            INSERT OR IGNORE INTO access_logs
              (log_id, ip, country, country_code, region, city,
               request_type, endpoint, latency_ms, status_code, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (lid, log.get("ip"), log.get("country"), log.get("country_code"),
              log.get("region"), log.get("city"), log.get("request_type"),
              log.get("endpoint"), log.get("latency_ms"), log.get("status_code"), now))
        conn.commit()


def get_analytics_stats() -> dict:
    """Return aggregated analytics: country breakdown, latency trend, request types."""
    if _using_postgres:
        try:
            with _pg_conn() as conn:
                with conn.cursor() as cur:
                    # Total requests
                    cur.execute("SELECT COUNT(*) FROM access_logs")
                    total = cur.fetchone()[0] or 0

                    # By country (with avg latency, exclude unmapped local entries)
                    cur.execute("""
                        SELECT country_code, country,
                               COUNT(*) AS cnt,
                               ROUND(AVG(NULLIF(latency_ms, 0))::numeric, 0)::float AS avg_ms
                        FROM access_logs
                        WHERE country_code IS NOT NULL
                          AND country_code != 'LO'
                        GROUP BY country_code, country
                        ORDER BY cnt DESC LIMIT 50
                    """)
                    by_country = [
                        {"country_code": r[0], "country": r[1],
                         "count": r[2], "avg_ms": float(r[3] or 0)}
                        for r in cur.fetchall()
                    ]

                    # By request type (with avg latency)
                    cur.execute("""
                        SELECT COALESCE(request_type,'unknown') AS rt,
                               COUNT(*) AS cnt,
                               ROUND(AVG(NULLIF(latency_ms, 0))::numeric, 0)::float AS avg_ms
                        FROM access_logs GROUP BY rt ORDER BY cnt DESC
                    """)
                    by_type = [
                        {"type": r[0], "count": r[1], "avg_ms": float(r[2] or 0)}
                        for r in cur.fetchall()
                    ]

                    # Latency over last 24 h (hourly buckets)
                    cur.execute("""
                        SELECT
                            date_trunc('hour', created_at) AS hour,
                            ROUND(AVG(latency_ms)::numeric, 1) AS avg_ms,
                            COUNT(*) AS requests
                        FROM access_logs
                        WHERE created_at > NOW() - INTERVAL '24 hours'
                        GROUP BY hour ORDER BY hour
                    """)
                    latency_trend = [
                        {"hour": str(r[0]), "avg_ms": float(r[1] or 0), "requests": r[2]}
                        for r in cur.fetchall()
                    ]

                    # Recent accesses
                    cur.execute("""
                        SELECT ip, country, country_code, city, request_type,
                               latency_ms, created_at
                        FROM access_logs ORDER BY created_at DESC LIMIT 20
                    """)
                    cols = [d[0] for d in cur.description]
                    recent = [dict(zip(cols, r)) for r in cur.fetchall()]
                    for r in recent:
                        if hasattr(r.get("created_at"), "isoformat"):
                            r["created_at"] = r["created_at"].isoformat()

                    return {
                        "total_requests": total,
                        "by_country":     by_country,
                        "by_type":        by_type,
                        "latency_trend":  latency_trend,
                        "recent":         recent,
                    }
        except Exception as exc:
            logger.warning("PG get_analytics_stats failed: %s", exc)

    # SQLite fallback (simplified — no date_trunc)
    with _sqlite_lock, sqlite3.connect(str(_SQLITE_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) FROM access_logs").fetchone()[0] or 0
        by_country = [dict(r) for r in conn.execute("""
            SELECT country_code, country, COUNT(*) AS count,
                   AVG(CASE WHEN latency_ms > 0 THEN latency_ms END) AS avg_ms
            FROM access_logs
            WHERE country_code IS NOT NULL AND country_code != 'LO'
            GROUP BY country_code, country ORDER BY count DESC LIMIT 50
        """).fetchall()]
        by_type = [dict(r) for r in conn.execute("""
            SELECT COALESCE(request_type,'unknown') AS type, COUNT(*) AS count,
                   AVG(CASE WHEN latency_ms > 0 THEN latency_ms END) AS avg_ms
            FROM access_logs GROUP BY request_type ORDER BY count DESC
        """).fetchall()]
        recent = [dict(r) for r in conn.execute("""
            SELECT ip, country, country_code, city, request_type, latency_ms, created_at
            FROM access_logs ORDER BY created_at DESC LIMIT 20
        """).fetchall()]
        return {
            "total_requests": total,
            "by_country":     by_country,
            "by_type":        by_type,
            "latency_trend":  [],
            "recent":         recent,
        }
