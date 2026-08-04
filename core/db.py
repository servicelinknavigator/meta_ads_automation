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
from datetime import datetime, date as dt, timedelta

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
        _pool = pg_pool.ThreadedConnectionPool(
            2, 20, url,
            connect_timeout=10,
            # Detect silently-dropped connections (e.g. Render spin-down,
            # Supabase idle disconnects) quickly instead of hanging until
            # the OS-level TCP timeout on the next query.
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
        )
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


def _reset_pool() -> None:
    """Discard the current pool so the next request builds a fresh one."""
    global _pool
    if _pool is not None:
        try:
            _pool.closeall()
        except Exception:
            pass
    _pool = None


def _is_alive(conn) -> bool:
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        return True
    except Exception:
        return False


@contextmanager
def _conn():
    pool = _get_pool()
    if pool is None:
        raise RuntimeError(f"DB niet beschikbaar: {_pool_error or 'onbekende fout'}")
    conn = pool.getconn()
    if not _is_alive(conn):
        # Stale/dead connection (e.g. dropped by Supabase or Render spin-down).
        # Discard it and the whole pool, then retry once with a fresh pool.
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        _reset_pool()
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
            client_context TEXT,
            created_at  TIMESTAMP DEFAULT NOW()
        );

        ALTER TABLE clients ADD COLUMN IF NOT EXISTS client_context TEXT;

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

        CREATE TABLE IF NOT EXISTS ad_name_mappings (
            id          SERIAL PRIMARY KEY,
            client_id   INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            ad_name     VARCHAR(500) NOT NULL,
            hook_type   VARCHAR(50),
            format_type VARCHAR(50),
            created_at  TIMESTAMP DEFAULT NOW(),
            UNIQUE(client_id, ad_name)
        );

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

        CREATE TABLE IF NOT EXISTS ad_creatives (
            id              SERIAL PRIMARY KEY,
            client_id       INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            ad_naam         VARCHAR(500) NOT NULL,
            script          TEXT,
            headline        VARCHAR(500),
            ad_copy_1       TEXT,
            ad_copy_2       TEXT,
            ad_copy_3       TEXT,
            afbeelding_pad  VARCHAR(500),
            created_at      TIMESTAMP DEFAULT NOW(),
            updated_at      TIMESTAMP DEFAULT NOW(),
            UNIQUE(client_id, ad_naam)
        );
        """)
        # Enable RLS on all tables — blocks public REST access while
        # the service-role connection (psycopg2) still bypasses RLS.
        for table in (
            "clients", "uploads", "ad_name_mappings", "hook_snapshots",
            "shoot_briefs", "insights_history", "ad_creatives",
        ):
            cur.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

        # Migrations: add columns introduced after initial schema creation
        cur.execute("ALTER TABLE ad_creatives ADD COLUMN IF NOT EXISTS headline_2 VARCHAR(500)")
        cur.execute("ALTER TABLE ad_creatives ADD COLUMN IF NOT EXISTS headline_3 VARCHAR(500)")
        cur.execute("ALTER TABLE ad_creatives ADD COLUMN IF NOT EXISTS hook_type VARCHAR(100)")
        cur.execute("ALTER TABLE ad_creatives ADD COLUMN IF NOT EXISTS format_type VARCHAR(100)")

        # Meta connection storage
        cur.execute("""
        CREATE TABLE IF NOT EXISTS meta_connections (
            id               SERIAL PRIMARY KEY,
            client_id        INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            ad_account_id    TEXT,
            access_token     TEXT,
            token_expires_at TIMESTAMP,
            last_sync_at     TIMESTAMP,
            created_at       TIMESTAMP DEFAULT NOW()
        )
        """)
        cur.execute("ALTER TABLE meta_connections ENABLE ROW LEVEL SECURITY")

        # Sales transcript storage
        cur.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            id                   SERIAL PRIMARY KEY,
            client_id            INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            transcript_text      TEXT,
            extracted_hooks      TEXT,
            extracted_objections TEXT,
            extracted_phrases    TEXT,
            created_at           TIMESTAMP DEFAULT NOW()
        )
        """)
        cur.execute("ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY")

        # ICP columns on clients
        cur.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS icp_learned TEXT")
        cur.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS icp_updated_at TIMESTAMP")

        cur.close()
    logger.info("DB schema OK")


# ── Clients ───────────────────────────────────────────────────────────────────

def get_correct_totals(client_id: int) -> dict:
    """
    Compute total spend, results, and CPL using only non-overlapping upload periods.
    Newer uploads are authoritative for any date they cover; older uploads fill in
    uncovered periods. This prevents double-counting when upload date ranges overlap.
    """
    valid_ids = _non_redundant_upload_ids(client_id)
    if not valid_ids:
        return {"total_spend": 0.0, "total_results": 0, "avg_cpl": None}
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(total_spend), 0), COALESCE(SUM(total_results), 0)
            FROM uploads WHERE client_id = %s AND id = ANY(%s)
        """, (client_id, valid_ids))
        row = cur.fetchone()
        cur.close()
    spend   = float(row[0] or 0)
    results = int(row[1] or 0)
    cpl     = round(spend / results, 2) if results > 0 else None
    return {"total_spend": spend, "total_results": results, "avg_cpl": cpl}


def get_clients() -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.name, c.industry, c.campaign_type,
                   c.cpl_benchmark, c.roas_benchmark, c.notes, c.created_at,
                   COUNT(u.id) AS upload_count,
                   MAX(u.uploaded_at) AS last_upload
            FROM clients c
            LEFT JOIN uploads u ON u.client_id = c.id
            GROUP BY c.id
            ORDER BY c.name
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    for row in rows:
        totals = get_correct_totals(row["id"])
        row["total_spend"]           = totals["total_spend"]
        row["total_results"]         = totals["total_results"]
        row["pending_content_count"] = get_pending_content_count(row["id"])
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
                  notes: str = "", client_context: str = "") -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clients (name, industry, campaign_type, cpl_benchmark, roas_benchmark, notes, client_context)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (name, industry, campaign_type, cpl_benchmark, roas_benchmark, notes, client_context))
        client_id = cur.fetchone()[0]
        cur.close()
    return client_id


def update_client(client_id: int, name: str, industry: str, campaign_type: str,
                  cpl_benchmark: float | None, roas_benchmark: float | None,
                  notes: str, client_context: str = "") -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE clients SET name=%s, industry=%s, campaign_type=%s,
                cpl_benchmark=%s, roas_benchmark=%s, notes=%s, client_context=%s
            WHERE id=%s
        """, (name, industry, campaign_type, cpl_benchmark, roas_benchmark,
              notes, client_context, client_id))
        cur.close()


def delete_upload(upload_id: int) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM uploads WHERE id = %s", (upload_id,))
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


# ── Ad name mappings ──────────────────────────────────────────────────────────

def get_ad_name_mappings(client_id: int) -> dict[str, dict]:
    """Return {ad_name: {hook, format}} for all saved mappings of this client."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT ad_name, hook_type, format_type FROM ad_name_mappings
            WHERE client_id = %s
        """, (client_id,))
        rows = cur.fetchall()
        cur.close()
    return {r[0]: {"hook": r[1], "format": r[2]} for r in rows}


def save_ad_name_mappings(client_id: int, mappings: list[dict]) -> int:
    """
    Upsert a list of {ad_name, hook_type, format_type} dicts.
    Returns the number of rows saved.
    """
    if not mappings:
        return 0
    with _conn() as conn:
        cur = conn.cursor()
        for m in mappings:
            cur.execute("""
                INSERT INTO ad_name_mappings (client_id, ad_name, hook_type, format_type)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (client_id, ad_name)
                DO UPDATE SET hook_type = EXCLUDED.hook_type,
                              format_type = EXCLUDED.format_type
            """, (client_id, m["ad_name"], m["hook_type"], m["format_type"]))
        cur.close()
    return len(mappings)


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


def _non_redundant_upload_ids(client_id: int) -> list[int]:
    """
    Return upload IDs to use for trend/aggregate analysis without double-counting.

    Strategy: greedily include uploads from newest to oldest.
    An upload is kept only if it covers at least one day not already covered
    by a newer upload.  Uploads without date info are deduplicated by filename
    so that uploading the same CSV twice does not inflate totals.
    """
    def _parse(s) -> dt | None:
        try:
            return dt.fromisoformat(str(s)[:10]) if s else None
        except ValueError:
            return None

    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, date_from, date_to, COALESCE(filename, '') AS filename
            FROM uploads
            WHERE client_id = %s
            ORDER BY uploaded_at DESC
        """, (client_id,))
        rows = cur.fetchall()
        cur.close()

    covered: set[dt] = set()
    selected: list[int] = []
    # Track filenames already represented among null-date uploads (newest wins)
    seen_null_filenames: set[str] = set()

    for uid, date_from, date_to, filename in rows:
        d_from = _parse(date_from)
        d_to   = _parse(date_to)

        if d_from is None or d_to is None:
            # No date info — deduplicate by filename so the same CSV uploaded
            # twice doesn't count twice.
            fn = filename.strip().lower()
            if fn:
                if fn in seen_null_filenames:
                    logger.debug(
                        "Upload %s skipped (duplicate null-date file %r, newer already included)",
                        uid, filename,
                    )
                    continue
                seen_null_filenames.add(fn)
            selected.append(uid)
            continue

        days: set[dt] = set()
        d = d_from
        while d <= d_to:
            days.add(d)
            d += timedelta(days=1)

        new_days = days - covered
        if new_days:
            selected.append(uid)
            covered |= days
        else:
            logger.debug("Upload %s skipped (all dates already covered by newer upload)", uid)

    return selected


def get_hook_trend(client_id: int, hook_type: str) -> list[dict]:
    """CPL trend for a specific hook, using only non-overlapping uploads."""
    valid_ids = _non_redundant_upload_ids(client_id)
    if not valid_ids:
        return []
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT h.cpl, h.results, h.spend, h.avg_ctr, u.date_from, u.date_to, u.uploaded_at
            FROM hook_snapshots h
            JOIN uploads u ON u.id = h.upload_id
            WHERE h.client_id = %s AND h.hook_type = %s AND h.upload_id = ANY(%s)
            ORDER BY u.date_from ASC NULLS LAST
        """, (client_id, hook_type, valid_ids))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def get_all_hook_performance(client_id: int) -> list[dict]:
    """Aggregate hook performance using only non-overlapping uploads to avoid double-counting."""
    valid_ids = _non_redundant_upload_ids(client_id)
    if not valid_ids:
        return []
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
              AND upload_id = ANY(%s)
            GROUP BY hook_type
            ORDER BY overall_cpl ASC NULLS LAST
        """, (client_id, valid_ids))
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


def delete_shoot_brief(brief_id: int) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM shoot_briefs WHERE id = %s", (brief_id,))
        cur.close()


# ── Insights history ──────────────────────────────────────────────────────────

def save_insights(client_id: int, upload_id: int, insights_text: str) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO insights_history (client_id, upload_id, insights_text)
            VALUES (%s, %s, %s)
        """, (client_id, upload_id, insights_text))
        cur.close()


# ── Ad creatives ──────────────────────────────────────────────────────────────

def get_ad_creatives(client_id: int) -> dict[str, dict]:
    """Return {ad_naam: {script, headline, headline_2, headline_3, ad_copy_1, ...}} for all saved creatives."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT ad_naam, script, headline, headline_2, headline_3,
                   ad_copy_1, ad_copy_2, ad_copy_3, afbeelding_pad,
                   hook_type, format_type
            FROM ad_creatives WHERE client_id = %s
        """, (client_id,))
        rows = cur.fetchall()
        cur.close()
    return {
        r[0]: {
            "script":         r[1] or "",
            "headline":       r[2] or "",
            "headline_2":     r[3] or "",
            "headline_3":     r[4] or "",
            "ad_copy_1":      r[5] or "",
            "ad_copy_2":      r[6] or "",
            "ad_copy_3":      r[7] or "",
            "afbeelding_pad": r[8] or "",
            "hook_type":      r[9] or "",
            "format_type":    r[10] or "",
        }
        for r in rows
    }


def get_ad_creatives_list(client_id: int) -> list[dict]:
    """Return list of all creatives with metadata, newest first — used for history view."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, ad_naam, hook_type, format_type,
                   script, headline, ad_copy_1, afbeelding_pad,
                   created_at, updated_at
            FROM ad_creatives
            WHERE client_id = %s
            ORDER BY created_at DESC
        """, (client_id,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def upsert_ad_creative(client_id: int, ad_naam: str, script: str = "",
                        headline: str = "", headline_2: str = "", headline_3: str = "",
                        ad_copy_1: str = "", ad_copy_2: str = "", ad_copy_3: str = "",
                        afbeelding_pad: str = "",
                        hook_type: str = "", format_type: str = "") -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ad_creatives
                (client_id, ad_naam, script, headline, headline_2, headline_3,
                 ad_copy_1, ad_copy_2, ad_copy_3, afbeelding_pad,
                 hook_type, format_type, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (client_id, ad_naam)
            DO UPDATE SET
                script         = COALESCE(NULLIF(EXCLUDED.script, ''),         ad_creatives.script),
                headline       = COALESCE(NULLIF(EXCLUDED.headline, ''),       ad_creatives.headline),
                headline_2     = COALESCE(NULLIF(EXCLUDED.headline_2, ''),     ad_creatives.headline_2),
                headline_3     = COALESCE(NULLIF(EXCLUDED.headline_3, ''),     ad_creatives.headline_3),
                ad_copy_1      = COALESCE(NULLIF(EXCLUDED.ad_copy_1, ''),      ad_creatives.ad_copy_1),
                ad_copy_2      = COALESCE(NULLIF(EXCLUDED.ad_copy_2, ''),      ad_creatives.ad_copy_2),
                ad_copy_3      = COALESCE(NULLIF(EXCLUDED.ad_copy_3, ''),      ad_creatives.ad_copy_3),
                afbeelding_pad = COALESCE(NULLIF(EXCLUDED.afbeelding_pad, ''), ad_creatives.afbeelding_pad),
                hook_type      = COALESCE(NULLIF(EXCLUDED.hook_type, ''),      ad_creatives.hook_type),
                format_type    = COALESCE(NULLIF(EXCLUDED.format_type, ''),    ad_creatives.format_type),
                updated_at     = NOW()
        """, (client_id, ad_naam, script or None, headline or None,
              headline_2 or None, headline_3 or None,
              ad_copy_1 or None, ad_copy_2 or None, ad_copy_3 or None,
              afbeelding_pad or None,
              hook_type or None, format_type or None))
        cur.close()


def bulk_upsert_ad_creatives(client_id: int, creatives: list[dict]) -> int:
    """Upsert a list of creative dicts in a single transaction."""
    if not creatives:
        return 0
    with _conn() as conn:
        cur = conn.cursor()
        for c in creatives:
            script         = c.get("script", "") or None
            headline       = c.get("headline", "") or None
            headline_2     = c.get("headline_2", "") or None
            headline_3     = c.get("headline_3", "") or None
            ad_copy_1      = c.get("ad_copy_1", "") or None
            ad_copy_2      = c.get("ad_copy_2", "") or None
            ad_copy_3      = c.get("ad_copy_3", "") or None
            afbeelding_pad = c.get("afbeelding_pad", "") or None
            cur.execute("""
                INSERT INTO ad_creatives
                    (client_id, ad_naam, script, headline, headline_2, headline_3,
                     ad_copy_1, ad_copy_2, ad_copy_3, afbeelding_pad, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (client_id, ad_naam)
                DO UPDATE SET
                    script         = COALESCE(NULLIF(EXCLUDED.script, ''),         ad_creatives.script),
                    headline       = COALESCE(NULLIF(EXCLUDED.headline, ''),       ad_creatives.headline),
                    headline_2     = COALESCE(NULLIF(EXCLUDED.headline_2, ''),     ad_creatives.headline_2),
                    headline_3     = COALESCE(NULLIF(EXCLUDED.headline_3, ''),     ad_creatives.headline_3),
                    ad_copy_1      = COALESCE(NULLIF(EXCLUDED.ad_copy_1, ''),      ad_creatives.ad_copy_1),
                    ad_copy_2      = COALESCE(NULLIF(EXCLUDED.ad_copy_2, ''),      ad_creatives.ad_copy_2),
                    ad_copy_3      = COALESCE(NULLIF(EXCLUDED.ad_copy_3, ''),      ad_creatives.ad_copy_3),
                    afbeelding_pad = COALESCE(NULLIF(EXCLUDED.afbeelding_pad, ''), ad_creatives.afbeelding_pad),
                    updated_at     = NOW()
            """, (client_id, c.get("ad_naam", ""), script, headline,
                  headline_2, headline_3, ad_copy_1, ad_copy_2, ad_copy_3, afbeelding_pad))
        cur.close()
    return len(creatives)


def get_pending_content_count(client_id: int) -> int:
    """
    Returns how many ad names in the latest upload have no creative content yet.
    Used to show content-missing warnings on the profile and clients list.
    """
    try:
        uploads = get_uploads(client_id)
        if not uploads:
            return 0
        csv_text = get_upload_csv_content(uploads[0]["id"])
        if not csv_text:
            return 0
        from core.csv_parser import parse_csv_string
        rows = [r for r in parse_csv_string(csv_text)
                if float(r.get("spend", 0) or 0) > 0]
        ad_names = {r.get("ad_name", "") for r in rows
                    if r.get("ad_name") and r.get("ad_name") != "Unknown"}
        if not ad_names:
            return 0
        existing = get_ad_names_with_creatives(client_id)
        return len(ad_names - existing)
    except Exception as e:
        logger.debug("get_pending_content_count failed for client %s: %s", client_id, e)
        return 0


def get_ad_names_with_creatives(client_id: int) -> set[str]:
    """Return set of ad names that already have creative content stored."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT ad_naam FROM ad_creatives
            WHERE client_id = %s
              AND (script IS NOT NULL OR headline IS NOT NULL OR ad_copy_1 IS NOT NULL)
        """, (client_id,))
        rows = cur.fetchall()
        cur.close()
    return {r[0] for r in rows}


def get_industry_cross_client_data(industry: str, exclude_client_id: int | None = None,
                                    min_spend: float = 25.0) -> list[dict]:
    """
    Returns top-performing ad+creative combinations from other clients in the same industry.
    Used for cross-client pattern recognition.
    """
    if not industry or not industry.strip():
        return []
    with _conn() as conn:
        cur = conn.cursor()
        # Only return anonymised performance metrics — no creative content (scripts/copy)
        # from other clients, to prevent accidental exposure of competitor material.
        query = """
            SELECT h.hook_type, h.format_type,
                   h.spend, h.results, h.cpl, h.avg_ctr
            FROM (
                SELECT client_id, hook_type, format_type,
                       SUM(spend) AS spend, SUM(results) AS results,
                       CASE WHEN SUM(results) > 0 THEN SUM(spend)::float / SUM(results) END AS cpl,
                       AVG(avg_ctr) AS avg_ctr
                FROM hook_snapshots
                GROUP BY client_id, hook_type, format_type
            ) h
            JOIN clients c ON c.id = h.client_id
            WHERE LOWER(c.industry) = LOWER(%s)
              AND h.spend >= %s
        """
        params = [industry, min_spend]
        if exclude_client_id:
            query += " AND c.id != %s"
            params.append(exclude_client_id)
        query += " ORDER BY h.cpl ASC NULLS LAST LIMIT 15"
        cur.execute(query, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


# ── Insights history ──────────────────────────────────────────────────────────

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


# ── Meta connections ──────────────────────────────────────────────────────────

def save_meta_connection(client_id: int, ad_account_id: str,
                          token: str, expires_at) -> int:
    """Upsert the Meta connection for a client (one connection per client)."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO meta_connections (client_id, ad_account_id, access_token, token_expires_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (client_id, ad_account_id, token, expires_at))
        # If a row already exists, update it
        cur.execute("""
            UPDATE meta_connections
            SET ad_account_id = %s, access_token = %s, token_expires_at = %s
            WHERE client_id = %s
        """, (ad_account_id, token, expires_at, client_id))
        cur.execute("SELECT id FROM meta_connections WHERE client_id = %s", (client_id,))
        row = cur.fetchone()
        cur.close()
    return row[0] if row else 0


def get_meta_connection(client_id: int) -> dict | None:
    """Return the stored Meta connection for a client, or None."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, client_id, ad_account_id, access_token,
                   token_expires_at, last_sync_at, created_at
            FROM meta_connections WHERE client_id = %s
        """, (client_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            return None
        cols = [d[0] for d in cur.description]
        cur.close()
    return dict(zip(cols, row))


def update_last_sync(client_id: int) -> None:
    """Stamp the current time as last_sync_at for the client's Meta connection."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE meta_connections SET last_sync_at = NOW() WHERE client_id = %s
        """, (client_id,))
        cur.close()


def get_all_meta_connections() -> list[dict]:
    """Return all active Meta connections (used by /sync-all cron endpoint)."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT mc.client_id, mc.ad_account_id, mc.access_token,
                   mc.token_expires_at, mc.last_sync_at, c.name AS client_name,
                   c.campaign_type
            FROM meta_connections mc
            JOIN clients c ON c.id = mc.client_id
            WHERE mc.access_token IS NOT NULL AND mc.access_token != ''
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


# ── Transcripts ───────────────────────────────────────────────────────────────

def save_transcript(client_id: int, transcript_text: str,
                    extracted_hooks: str = "", extracted_objections: str = "",
                    extracted_phrases: str = "") -> int:
    """Store a sales transcript and its AI-extracted insights."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transcripts
                (client_id, transcript_text, extracted_hooks,
                 extracted_objections, extracted_phrases)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, (client_id, transcript_text, extracted_hooks,
              extracted_objections, extracted_phrases))
        tid = cur.fetchone()[0]
        cur.close()
    return tid


def get_transcripts(client_id: int, limit: int = 10) -> list[dict]:
    """Return stored transcripts for a client, newest first."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, created_at, extracted_hooks, extracted_objections,
                   extracted_phrases,
                   LEFT(transcript_text, 200) AS transcript_preview
            FROM transcripts WHERE client_id = %s
            ORDER BY created_at DESC LIMIT %s
        """, (client_id, limit))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
    return rows


def get_transcript_context(client_id: int) -> str:
    """
    Build a concise transcript context string for injection into AI prompts.
    Uses the three most recent transcripts.
    """
    rows = get_transcripts(client_id, limit=3)
    if not rows:
        return ""
    parts = []
    for r in rows:
        if r.get("extracted_phrases"):
            parts.append(f"Klantuitspraken: {r['extracted_phrases']}")
        if r.get("extracted_objections"):
            parts.append(f"Bezwaren: {r['extracted_objections']}")
        if r.get("extracted_hooks"):
            parts.append(f"Hook-openingen: {r['extracted_hooks']}")
    return "\n".join(parts)


# ── ICP (learned) ─────────────────────────────────────────────────────────────

def update_icp_learned(client_id: int, icp_text: str) -> None:
    """Persist the AI-generated ICP summary for a client."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE clients SET icp_learned = %s, icp_updated_at = NOW()
            WHERE id = %s
        """, (icp_text, client_id))
        cur.close()


def get_full_client_context(client_id: int) -> str:
    """
    Combine manual client_context + AI-learned icp_learned into one string
    for use in AI prompts.
    """
    client = get_client(client_id)
    if not client:
        return ""
    parts = []
    if client.get("client_context"):
        parts.append(f"[Handmatige context]\n{client['client_context']}")
    if client.get("icp_learned"):
        parts.append(f"[Geleerd uit data]\n{client['icp_learned']}")
    return "\n\n".join(parts)
