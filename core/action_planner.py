"""
Weekly action plan generator.
Produces concrete, data-driven recommendations: what to pause, scale, shoot, and test.
"""
from __future__ import annotations
import logging
from datetime import datetime

import core.db as db
from core.ai_client import call_text

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Je bent een directe performance marketeer. Geef alleen concrete acties, geen opties. "
    "Noem altijd het specifieke getal waarop je je baseert. "
    "Zeg wat je verwacht dat het oplevert en hoe je dat meet. "
    "Geen marketingtaal. Geen 'overweeg'. Alleen: doe dit, stop dat, maak dit."
)


def generate_action_plan(client_id: int) -> str:
    """
    Generate a concrete weekly action plan for a client based on their data.
    Returns markdown text with five sections: stop, scale, produce, test, effect.
    """
    try:
        client = db.get_client(client_id)
        if not client:
            return "Klant niet gevonden."

        uploads     = db.get_uploads(client_id)
        hook_perf   = db.get_all_hook_performance(client_id)
        full_context = db.get_full_client_context(client_id)

        if not uploads:
            return "Geen uploaddata beschikbaar. Upload eerst een CSV of synchroniseer Meta Ads."

        latest = uploads[0]
        ad_rows = _get_latest_ad_rows(client_id, latest)

        return _build_plan(client, ad_rows, hook_perf, full_context, latest)
    except Exception as e:
        logger.error("generate_action_plan failed for client %s: %s", client_id, e)
        return f"Actieplan kon niet worden gegenereerd: {e}"


def _get_latest_ad_rows(client_id: int, latest_upload: dict) -> list[dict]:
    """Reconstruct ad rows from the stored CSV content of the latest upload."""
    csv_content = db.get_upload_csv_content(latest_upload["id"])
    if not csv_content:
        return []
    try:
        from core.csv_parser import parse_csv_string
        rows, _ = parse_csv_string(csv_content)
        return rows or []
    except Exception:
        return []


def _build_plan(client: dict, ad_rows: list[dict], hook_perf: list[dict],
                full_context: str, latest_upload: dict) -> str:
    """Compose the prompt and call Claude."""

    campaign_type = client.get("campaign_type", "leads")
    cpl_bench     = float(client.get("cpl_benchmark") or 0)
    roas_bench    = float(client.get("roas_benchmark") or 0)

    # Summarise top and bottom performers
    sorted_ads = sorted(
        [r for r in ad_rows if float(r.get("spend", 0) or 0) >= 20
         and int(r.get("results", 0) or 0) > 0],
        key=lambda r: float(r.get("spend", 0) or 0) /
                      max(int(r.get("results", 1) or 1), 1)
    )
    top3    = sorted_ads[:3]
    bottom3 = sorted_ads[-3:] if len(sorted_ads) >= 3 else []

    # Burning ads (high spend, no results)
    burning = [
        r for r in ad_rows
        if float(r.get("spend", 0) or 0) >= 50
        and int(r.get("results", 0) or 0) == 0
    ]

    best_hook  = hook_perf[0] if hook_perf else {}
    worst_hook = hook_perf[-1] if hook_perf else {}

    def _fmt(rows: list[dict]) -> str:
        lines = []
        for r in rows:
            spend = float(r.get("spend", 0) or 0)
            res   = int(r.get("results", 0) or 0)
            cpl   = round(spend / res, 2) if res else 0
            roas  = float(r.get("roas", 0) or 0)
            lines.append(
                f"  - {r.get('ad_name', '?')}: €{spend:.0f} spend, "
                f"{res} resultaten, CPL €{cpl}, ROAS {roas}"
            )
        return "\n".join(lines) if lines else "  (geen)"

    period = (
        f"{latest_upload.get('date_from', '?')} — {latest_upload.get('date_to', '?')}"
    )

    prompt = f"""Maak een weekplan voor {client.get('name')} ({client.get('industry', '')}).
Campagnetype: {campaign_type} | CPL-benchmark: €{cpl_bench} | ROAS-benchmark: {roas_bench}
Periode: {period} | Totaal spend: €{latest_upload.get('total_spend', 0):.0f}

Klantcontext:
{full_context or '(geen)'}

TOP 3 ads (beste CPL):
{_fmt(top3)}

BOTTOM 3 ads (slechtste CPL):
{_fmt(bottom3)}

ADS DIE GELD VERBRANDEN (hoge spend, 0 resultaten):
{_fmt(burning)}

Beste hook-type: {best_hook.get('hook_type', '?')} (CPL €{best_hook.get('overall_cpl', '?')}, {best_hook.get('total_results', 0)} resultaten)
Slechtste hook-type: {worst_hook.get('hook_type', '?')} (CPL €{worst_hook.get('overall_cpl', '?')})

Schrijf een concreet weekplan met exact deze 5 secties:

## Stop direct
[welke specifieke ads pauzeren en waarom — noem naam en getal]

## Schaal nu
[welke specifieke ads meer budget verdienen en hoeveel — noem naam en onderbouwing]

## Produceer deze week
[welke shoot als eerste met korte brief: hook-type, format, openingszin, call-to-action]

## Test volgende week
[wat er klaar moet staan — hook-type, angle, format]

## Verwacht effect
[concrete CPL-verwachting als je dit plan uitvoert en hoe je dat meet]"""

    return call_text(prompt, system=_SYSTEM, max_tokens=1400)
