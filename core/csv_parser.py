import csv
from pathlib import Path


COLUMN_MAP = {
    "campaign name": "campaign_name",
    "campaign id": "campaign_id",
    "ad set name": "ad_set_name",
    "ad set id": "ad_set_id",
    "ad name": "ad_name",
    "ad id": "ad_id",
    "day": "day",
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
    # lead generation columns
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
}

_CLICK_COLUMNS = {"clicks (all)", "link clicks", "ctr (all)(%)", "ctr (all) (%)",
                  "ctr (link click-through rate)(%)", "ctr (link click-through rate) (%)",
                  "cpc (all) (eur)", "cpc (all) (usd)", "cpc (all)",
                  "cost per link click (eur)", "cost per link click (usd)", "cost per link click"}

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
    return row


def parse_csv(filepath: str | Path) -> list[dict]:
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames_lower = {h.strip().lower() for h in (reader.fieldnames or [])}
        raw_rows = list(reader)

    has_click_data = bool(fieldnames_lower & _CLICK_COLUMNS)

    rows = []
    for raw in raw_rows:
        row = _normalize_row(raw)
        if not row.get("ad_name"):
            continue  # skip totals/summary rows
        row["_has_click_data"] = has_click_data
        rows.append(row)
    return rows


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
