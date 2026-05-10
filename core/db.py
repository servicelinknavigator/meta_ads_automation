"""
Supabase/PostgreSQL database layer.
All persistent client data lives here.
Falls back gracefully when DATABASE_URL is not set (local dev without DB).
"""
from __future__ import annotations
import os
import json
import logging
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

_pool = None
_pool_error: str = ""   # stores last connection error for diagnostics


def _get_pool():
    global _pool, _pool_error
    if _pool is not None:
        return _pool
    url = os.getenv("DATABASE_URL", "")
    if not url:
        _pool_error = "DATABASE_URL is niet ingesteld in de omgevingsvariabelen."
        return None
    # Supabase requires SSL — append sslmode if not present
    if "supabase" in url and "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url += f"{sep}sslmode=require"
    try:
        from psycopg2 import pool as pg_pool
        _pool = pg_pool.SimpleConnectionPool(1, 5, url)
        _pool_error = ""
        logger.info("DB pool created OK")
        return _pool
    except Exception as e:
        _pool_error = str(e)
        logger.error("DB pool init failed: %s", e)
        return None


def get_connection_error() -> str:
    """Returns the last DB connection error, empty string if OK."""
    _get_pool()  # trigger attempt if not yet tried
    return _pool_error


@contextmanager
def _conn():
    pool = _get_pool()
    if pool is None:
        raise RuntimeError(f"DB niet beschikbaar: {_pool_error or 'onbekende fout'}")
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def is_available() -> bool:
    """Returns True only if the pool can actually be created."""
    return _get_pool() is not None


# ── Schema init ───────────────────────────────────────────────────────────────

def init_schema() -> None:
    if not is_available():
        return
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(120) NOT NULL UNIQUE,
            industry    VARCHAR(120),
            campaign_type VARCHAR(20) DEFAULT 'leads',
            cpl_benchmark FLOAT,
            roas_benchmark FLOAT,
            notes       TEXT,
            created_at  TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS uploads (
            id            SERIAL PRIMARY KEY,
            client_id     INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            filename      VARCHAR(255),
            uploaded_at   TIMESTAMP DEFAULT NOW(),
            date_from     VARCHAR(20),
            date_to       VARCHAR(20),
            total_spend   FLOAT,
            total_results INTEGER,
            avg_cpl       FLOAT,
            avg_roas      FLOAT,
            avg_ctr       FLOAT,
            avg_frequency FLOAT,
            num_ads       INTEGER,
            campaign_type VARCHAR(20)
        );

        ALTER TABLE uploads ADD COLUMN IF NOT EXISTS csv_content TEXT;

        CREATE TABLE IF NOT EXISTS hook_snapshots (
            id          SERIAL PRIMARY KEY,
            client_id   INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            upload_id   INTEGER REFERENCES uploads(id) ON DELETE CASCADE,
            created_at  TIMESTAMP DEFAULT NOW(),
            hook_type   VARCHAR(50),
            format_type VARCHAR(50),
            ads         INTEGER,
            spend       FLOAT,
            results     INTEGER,
            cpl         FLOAT,
            avg_ctr     FLOAT
        );

        CREATE TABLE IF NOT EXISTS shoot_briefs (
            id          SERIAL PRIMARY KEY,
            client_id   INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            upload_id   INTEGER REFERENCES uploads(id) ON DELETE SET NULL,
            created_at  TIMESTAMP DEFAULT NOW(),
            brief_json  JSONB NOT NULL
        );

        CREATE TABLE IF NOT EXISTS insights_history (
            id          SERIAL PRIMARY KEY,
            client_id   INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            upload_id   INTEGER REFERENCES uploads(id) ON DELETE CASCADE,
            created_at  TIMESTAMP DEFAULT NOW(),
            insights_text TEXT
        );
        """)
        cur.close()
    logger.info("DB schema OK")


# ── Clients ───────────────────────────────────────────────────────────────────

def get_clients() -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.name, c.industry, c.campaign_type,
                   c.cpl_benchmark, c.roas_benchmark, c.notes, c.created_at,
                   COUNT(u.id) AS upload_count,
                   MAX(u.uploaded_at) AS last_upload,
                   MAX(u.total_spend) AS last_spend
            FROM clients c
            LEFT JOIN uploads u ON u.client_id = c.id
            GROUP BY c.id
            ORDER BY c.name
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def get_client(client_id: int) -> dict | None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        cur.close()
    return dict(zip(cols, row))


def create_client(name: str, industry: str = "", campaign_type: str = "leads",
                  cpl_benchmark: float | None = None, roas_benchmark: float | None = None,
                  notes: str = "") -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clients (name, industry, campaign_type, cpl_benchmark, roas_benchmark, notes)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (name, industry, campaign_type, cpl_benchmark, roas_benchmark, notes))
        client_id = cur.fetchone()[0]
        cur.close()
    return client_id


def update_client(client_id: int, name: str, industry: str, campaign_type: str,
                  cpl_benchmark: float | None, roas_benchmark: float | None, notes: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE clients SET name=%s, industry=%s, campaign_type=%s,
                cpl_benchmark=%s, roas_benchmark=%s, notes=%s
            WHERE id=%s
        """, (name, industry, campaign_type, cpl_benchmark, roas_benchmark, notes, client_id))
        cur.close()


def delete_client(client_id: int) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM clients WHERE id = %s", (client_id,))
        cur.close()


# ── Uploads ───────────────────────────────────────────────────────────────────

def save_upload(client_id: int, filename: str, date_from: str | None, date_to: str | None,
                total_spend: float, total_results: int, avg_cpl: float, avg_roas: float,
                avg_ctr: float, avg_frequency: float, num_ads: int, campaign_type: str,
                csv_content: str | None = None) -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO uploads
                (client_id, filename, date_from, date_to, total_spend, total_results,
                 avg_cpl, avg_roas, avg_ctr, avg_frequency, num_ads, campaign_type, csv_content)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (client_id, filename, date_from, date_to, total_spend, total_results,
              avg_cpl, avg_roas, avg_ctr, avg_frequency, num_ads, campaign_type, csv_content))
        upload_id = cur.fetchone()[0]
        cur.close()
    return upload_id


def get_upload_csv_content(upload_id: int) -> str | None:
    """Return the stored CSV text for a historical upload, or None if not available."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT csv_content FROM uploads WHERE id = %s", (upload_id,))
        row = cur.fetchone()
        cur.close()
    return row[0] if row else None


def get_uploads(client_id: int) -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM uploads WHERE client_id = %s ORDER BY uploaded_at DESC
        """, (client_id,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


# ── Hook snapshots ────────────────────────────────────────────────────────────

def save_hook_snapshots(client_id: int, upload_id: int, hook_perf: list[dict]) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        for row in hook_perf:
            cur.execute("""
                INSERT INTO hook_snapshots
                    (client_id, upload_id, hook_type, format_type, ads, spend, results, cpl, avg_ctr)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                client_id, upload_id,
                row.get("hook_type") or row.get("format_type"),
                row.get("format_type"),
                row.get("ads", 0),
                row.get("spend", 0),
                row.get("results", 0),
                row.get("cpl"),
                row.get("avg_ctr"),
            ))
        cur.close()


def get_hook_trend(client_id: int, hook_type: str) -> list[dict]:
    """CPL trend for a specific hook across all uploads."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT h.cpl, h.results, h.spend, h.avg_ctr, u.date_from, u.date_to, u.uploaded_at
            FROM hook_snapshots h
            JOIN uploads u ON u.id = h.upload_id
            WHERE h.client_id = %s AND h.hook_type = %s
            ORDER BY u.uploaded_at ASC
        """, (client_id, hook_type))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def get_all_hook_performance(client_id: int) -> list[dict]:
    """Aggregate hook performance across ALL uploads for this client."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT hook_type,
                   SUM(ads) AS total_ads,
                   SUM(spend) AS total_spend,
                   SUM(results) AS total_results,
                   CASE WHEN SUM(results) > 0 THEN ROUND(SUM(spend)::numeric / SUM(results), 2) END AS overall_cpl,
                   ROUND(AVG(avg_ctr)::numeric, 2) AS avg_ctr,
                   COUNT(DISTINCT upload_id) AS upload_count
            FROM hook_snapshots
            WHERE client_id = %s AND hook_type IS NOT NULL AND format_type IS NULL
            GROUP BY hook_type
            ORDER BY overall_cpl ASC NULLS LAST
        """, (client_id,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


# ── Shoot briefs ──────────────────────────────────────────────────────────────

def save_shoot_brief(client_id: int, upload_id: int | None, shoots: list[dict]) -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO shoot_briefs (client_id, upload_id, brief_json)
            VALUES (%s, %s, %s) RETURNING id
        """, (client_id, upload_id, json.dumps(shoots)))
        brief_id = cur.fetchone()[0]
        cur.close()
    return brief_id


def get_shoot_briefs(client_id: int, limit: int = 10) -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT sb.id, sb.created_at, sb.brief_json,
                   u.date_from, u.date_to, u.total_spend
            FROM shoot_briefs sb
            LEFT JOIN uploads u ON u.id = sb.upload_id
            WHERE sb.client_id = %s
            ORDER BY sb.created_at DESC
            LIMIT %s
        """, (client_id, limit))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    # parse brief_json back to list
    for row in rows:
        if isinstance(row["brief_json"], str):
            row["brief_json"] = json.loads(row["brief_json"])
    return rows


# ── Insights history ──────────────────────────────────────────────────────────

def save_insights(client_id: int, upload_id: int, insights_text: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO insights_history (client_id, upload_id, insights_text)
            VALUES (%s, %s, %s)
        """, (client_id, upload_id, insights_text))
        cur.close()


def get_insights_history(client_id: int, limit: int = 5) -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT ih.id, ih.created_at, ih.insights_text,
                   u.date_from, u.date_to, u.total_spend, u.total_results
            FROM insights_history ih
            LEFT JOIN uploads u ON u.id = ih.upload_id
            WHERE ih.client_id = %s
            ORDER BY ih.created_at DESC
            LIMIT %s
        """, (client_id, limit))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows
