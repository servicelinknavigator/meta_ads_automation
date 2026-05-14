import csv
import io
from pathlib import Path


COLUMN_MAP = {
    # ── Engels ────────────────────────────────────────────────────────────────
    "campaign name": "campaign_name",
    "campaign id": "campaign_id",
    "ad set name": "ad_set_name",
    "ad set id": "ad_set_id",
    "ad name": "ad_name",
    "ad id": "ad_id",
    "day": "day",
    # Meta summary-format exports (one row per ad for entire period, no Day column)
    "reporting starts": "day",          # use period start as the day for dedup/range
    "reporting period start date": "day",
    "reporting ends": "reporting_ends",  # keep but don't use as day
    "reach": "reach",
    "impressions": "impressions",
    "frequency": "frequency",
    "amount spent (eur)": "spend",
    "amount spent (usd)": "spend",
    "amount spent": "spend",
    "clicks (all)": "clicks",
    "link clicks": "link_clicks",
    "ctr (all)(%)": "ctr",
    "ctr (all) (%)": "ctr",
    "ctr (link click-through rate)(%)": "ctr_link",
    "ctr (link click-through rate) (%)": "ctr_link",
    "cpc (all) (eur)": "cpc",
    "cpc (all) (usd)": "cpc",
    "cpc (all)": "cpc",
    "cost per link click (eur)": "cpc_link",
    "cost per link click (usd)": "cpc_link",
    "cost per link click": "cpc_link",
    "cpm (cost per 1,000 impressions reached) (eur)": "cpm",
    "cpm (cost per 1,000 impressions reached) (usd)": "cpm",
    "cpm (cost per 1,000 impressions reached)": "cpm",
    "results": "results",
    "cost per result (eur)": "cost_per_result",
    "cost per result (usd)": "cost_per_result",
    "cost per result": "cost_per_result",
    "cost per results (eur)": "cost_per_result",
    "cost per results (usd)": "cost_per_result",
    "cost per results": "cost_per_result",
    "result indicator": "result_indicator",
    "purchase roas (return on ad spend)": "roas",
    "website purchase roas (return on ad spend)": "roas",
    # Engels — leads
    "leads": "results",
    "on-facebook leads": "results",
    "website leads": "results",
    "messaging conversations started": "results",
    "cost per lead (eur)": "cost_per_result",
    "cost per lead (usd)": "cost_per_result",
    "cost per lead": "cost_per_result",
    "cost per messaging conversation started (eur)": "cost_per_result",
    "cost per messaging conversation started (usd)": "cost_per_result",
    "cost per on-facebook lead (eur)": "cost_per_result",
    "cost per on-facebook lead (usd)": "cost_per_result",

    # ── Nederlands ────────────────────────────────────────────────────────────
    "naam campagne": "campaign_name",
    "campagnenaam": "campaign_name",
    "campagne-id": "campaign_id",
    "campagne id": "campaign_id",
    "naam advertentieset": "ad_set_name",
    "advertentiesetnaam": "ad_set_name",
    "id advertentieset": "ad_set_id",
    "advertentieset-id": "ad_set_id",
    "naam advertentie": "ad_name",
    "advertentienaam": "ad_name",
    "advertentie-id": "ad_id",
    "dag": "day",
    "bereik": "reach",
    "vertoningen": "impressions",
    "weergaven": "impressions",            # alternatief NL woord voor impressions
    "frequentie": "frequency",
    "besteed bedrag (eur)": "spend",
    "besteed bedrag (usd)": "spend",
    "besteed bedrag": "spend",
    # clicks
    "klikken (alle)": "clicks",
    "linkkliks": "link_clicks",
    "link-kliks": "link_clicks",
    "klikken op links": "link_clicks",     # variant in sommige NL exports
    # CTR varianten (met en zonder %-teken)
    "ctr (alle)(%)": "ctr",
    "ctr (alle) (%)": "ctr",
    "ctr (alle)": "ctr",
    "ctr (klikfrequentie van links)(%)": "ctr_link",
    "ctr (klikfrequentie van links) (%)": "ctr_link",
    "ctr (klikfrequentie van links)": "ctr_link",
    "ctr (doorklikratio voor klikken op link)": "ctr_link",
    "ctr (doorklikratio voor klikken op link) (%)": "ctr_link",
    # CPC varianten (KPK én CPC notatie)
    "kpk (alle) (eur)": "cpc",
    "kpk (alle) (usd)": "cpc",
    "kpk (alle)": "cpc",
    "cpc (alle) (eur)": "cpc",             # NL export met CPC afkorting
    "cpc (alle) (usd)": "cpc",
    "cpc (alle)": "cpc",
    "kosten per linkklik (eur)": "cpc_link",
    "kosten per linkklik (usd)": "cpc_link",
    "kosten per linkklik": "cpc_link",
    "cpc (kosten per klik op link) (eur)": "cpc_link",
    "cpc (kosten per klik op link) (usd)": "cpc_link",
    "cpc (kosten per klik op link)": "cpc_link",
    # CPM varianten (KPM én CPM notatie, vertoningen én weergaven)
    "kpm (kosten per 1.000 vertoningen bereikt) (eur)": "cpm",
    "kpm (kosten per 1.000 vertoningen bereikt) (usd)": "cpm",
    "kpm (kosten per 1.000 vertoningen bereikt)": "cpm",
    "cpm (kosten per 1.000 vertoningen bereikt) (eur)": "cpm",
    "cpm (kosten per 1.000 vertoningen bereikt) (usd)": "cpm",
    "cpm (kosten per 1000 weergaven) (eur)": "cpm",
    "cpm (kosten per 1000 weergaven) (usd)": "cpm",
    "cpm (kosten per 1.000 weergaven) (eur)": "cpm",
    "cpm (kosten per 1.000 weergaven) (usd)": "cpm",
    # results
    "resultaten": "results",
    "kosten per resultaat (eur)": "cost_per_result",
    "kosten per resultaat (usd)": "cost_per_result",
    "kosten per resultaat": "cost_per_result",
    "kosten per resultaten (eur)": "cost_per_result",  # variant met 'en'
    "kosten per resultaten (usd)": "cost_per_result",
    "kosten per resultaten": "cost_per_result",
    # result indicator varianten
    "resultaatindicator": "result_indicator",
    "resultaat-indicator": "result_indicator",
    "resultatenindicator": "result_indicator",  # variant met 'en'
    # ROAS
    "aankoop-roas (rendement op advertentie-uitgaven)": "roas",
    "aankoop roas (rendement op advertentie-uitgaven)": "roas",
    "website-aankoop-roas (rendement op advertentie-uitgaven)": "roas",
    # Ad delivery status (EN + NL)
    "ad delivery": "ad_delivery",
    "advertentieweergave": "ad_delivery",
    "levering advertentie": "ad_delivery",

    # Nederlands — leads
    "facebook-leads": "results",
    "websiteleads": "results",
    "gestarte gesprekken via berichten": "results",
    "kosten per lead (eur)": "cost_per_result",
    "kosten per lead (usd)": "cost_per_result",
    "kosten per lead": "cost_per_result",
    "kosten per gestart gesprek via berichten (eur)": "cost_per_result",
    "kosten per gestart gesprek via berichten (usd)": "cost_per_result",
    "kosten per facebook-lead (eur)": "cost_per_result",
    "kosten per facebook-lead (usd)": "cost_per_result",
}

# Kolomnamen die aangeven dat click-data aanwezig is (EN + NL)
_CLICK_COLUMNS = {
    # Engels
    "clicks (all)", "link clicks",
    "ctr (all)(%)", "ctr (all) (%)",
    "ctr (link click-through rate)(%)", "ctr (link click-through rate) (%)",
    "cpc (all) (eur)", "cpc (all) (usd)", "cpc (all)",
    "cost per link click (eur)", "cost per link click (usd)", "cost per link click",
    # Nederlands — klikken
    "klikken (alle)", "linkkliks", "link-kliks", "klikken op links",
    # Nederlands — CTR
    "ctr (alle)(%)", "ctr (alle) (%)", "ctr (alle)",
    "ctr (doorklikratio voor klikken op link)",
    "ctr (klikfrequentie van links)", "ctr (klikfrequentie van links) (%)",
    # Nederlands — CPC/KPK
    "kpk (alle) (eur)", "kpk (alle) (usd)", "kpk (alle)",
    "cpc (alle) (eur)", "cpc (alle) (usd)", "cpc (alle)",
    "kosten per linkklik (eur)", "kosten per linkklik (usd)", "kosten per linkklik",
    "cpc (kosten per klik op link) (eur)", "cpc (kosten per klik op link) (usd)",
}

# Nederlandse kolomnamen voor de advertentienaam (voor aggregate-row detectie)
_AD_NAME_COLUMNS = {"ad name", "naam advertentie", "advertentienaam"}

NUMERIC_FIELDS = [
    "reach", "impressions", "frequency", "spend", "clicks",
    "link_clicks", "ctr", "ctr_link", "cpc", "cpc_link",
    "cpm", "results", "cost_per_result", "roas",
]



def _normalize_key(raw: str) -> str:
    return COLUMN_MAP.get(raw.strip().lower(), raw.strip().lower().replace(" ", "_"))


def _to_float(val: str) -> float:
    if not val or val.strip() == "":
        return 0.0
    cleaned = val.replace(",", "").replace("%", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _normalize_row(raw_row: dict) -> dict:
    row = {}
    for key, val in raw_row.items():
        normalized = _normalize_key(key)
        if normalized in row:
            continue
        row[normalized] = val or ""
    for field in NUMERIC_FIELDS:
        if field in row:
            row[field] = _to_float(str(row[field]))
        else:
            row[field] = 0.0
    row.setdefault("campaign_name", "Unknown")
    row.setdefault("campaign_id", "0")
    row.setdefault("ad_set_name", "Unknown")
    row.setdefault("ad_set_id", "0")
    row.setdefault("ad_name", "Unknown")
    row.setdefault("ad_id", "0")
    row.setdefault("result_indicator", "Purchases")
    row.setdefault("ad_delivery", "")
    return row


def _is_aggregate_row(raw_row: dict) -> bool:
    """Return True for Meta's summary/totals rows (no ad name, EN or NL)."""
    for key, val in raw_row.items():
        if key.strip().lower() in _AD_NAME_COLUMNS:
            return not val or not val.strip()
    return False


def _parse_reader(reader: csv.DictReader) -> list[dict]:
    fieldnames_lower = {h.strip().lower() for h in (reader.fieldnames or [])}
    raw_rows = list(reader)
    has_click_data = bool(fieldnames_lower & _CLICK_COLUMNS)
    rows = []
    for raw in raw_rows:
        if _is_aggregate_row(raw):
            continue
        row = _normalize_row(raw)
        row["_has_click_data"] = has_click_data
        rows.append(row)
    return rows


def parse_csv(filepath: str | Path) -> list[dict]:
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        return _parse_reader(csv.DictReader(f))


def parse_csv_string(content: str) -> list[dict]:
    """Parse CSV from a string (e.g. retrieved from the database)."""
    # Strip BOM if present
    content = content.lstrip("﻿")
    return _parse_reader(csv.DictReader(io.StringIO(content)))


def load_dummy_data() -> list[dict]:
    dummy_path = Path(__file__).parent.parent / "dummy_data" / "sample_meta.csv"
    return parse_csv(dummy_path)


def validate_csv(rows: list[dict]) -> tuple[bool, list[str]]:
    if not rows:
        return False, ["CSV is leeg"]
    required = ["campaign_name", "impressions", "spend"]
    missing = [f for f in required if f not in rows[0]]
    if missing:
        return False, [f"Kolom ontbreekt: {c}" for c in missing]
    return True, []
