"""
Automatic ICP (Ideal Customer Profile) updater.
Analyses upload data to derive which pains/promises convert best, then
regenerates the ICP text via Claude and persists it in the clients table.
Called automatically after every sync or upload.
"""
from __future__ import annotations
import logging

import core.db as db
from core.ai_client import call_text

logger = logging.getLogger(__name__)


def update_icp(client_id: int, upload_data: list[dict]) -> str:
    """
    Analyse upload rows to derive pain/promise patterns, generate an updated
    ICP text with Claude, and persist it.  Returns the generated text.

    upload_data: list of normalised ad rows (same format as csv_parser output).
    """
    try:
        client = db.get_client(client_id)
        if not client:
            logger.warning("update_icp: client %s not found", client_id)
            return ""

        winners, losers = _classify_ads(upload_data, client)
        hook_perf = db.get_all_hook_performance(client_id)
        transcript_ctx = db.get_transcript_context(client_id)
        existing_context = client.get("client_context", "") or ""
        existing_icp = client.get("icp_learned", "") or ""

        icp_text = _generate_icp(
            client=client,
            winners=winners,
            losers=losers,
            hook_perf=hook_perf,
            transcript_ctx=transcript_ctx,
            existing_context=existing_context,
            existing_icp=existing_icp,
        )

        if icp_text and not icp_text.startswith("[AI"):
            db.update_icp_learned(client_id, icp_text)
            logger.info("ICP updated for client %s", client_id)

        return icp_text
    except Exception as e:
        logger.error("update_icp failed for client %s: %s", client_id, e)
        return ""


def _classify_ads(rows: list[dict], client: dict) -> tuple[list[dict], list[dict]]:
    """
    Split ads into winners (low CPL / high ROAS) and losers.
    Thresholds are derived from client benchmarks if available.
    """
    campaign_type = client.get("campaign_type", "leads")
    cpl_bench = float(client.get("cpl_benchmark") or 0)

    winners: list[dict] = []
    losers:  list[dict] = []

    for row in rows:
        spend   = float(row.get("spend", 0) or 0)
        results = int(row.get("results", 0) or 0)
        roas    = float(row.get("roas", 0) or 0)

        if spend < 20 or results == 0:
            continue

        cpl = spend / results if results else 0

        if campaign_type == "ecommerce":
            if roas >= 2.5:
                winners.append(row)
            elif roas > 0 and roas < 1.5:
                losers.append(row)
        else:
            threshold = cpl_bench if cpl_bench > 0 else 50
            if cpl <= threshold * 0.8:
                winners.append(row)
            elif cpl >= threshold * 1.5:
                losers.append(row)

    return winners, losers


def _generate_icp(client: dict, winners: list[dict], losers: list[dict],
                   hook_perf: list[dict], transcript_ctx: str,
                   existing_context: str, existing_icp: str) -> str:
    """Build the AI prompt and call Claude to produce an updated ICP text."""

    winner_names = [r.get("ad_name", "") for r in winners[:10]]
    loser_names  = [r.get("ad_name", "") for r in losers[:10]]

    best_hook = hook_perf[0]["hook_type"] if hook_perf else "onbekend"
    worst_hooks = [h["hook_type"] for h in hook_perf[-3:]] if len(hook_perf) >= 3 else []

    prompt = f"""Je analyseert de prestaties van Meta-advertenties voor {client.get('name', 'deze klant')} (branche: {client.get('industry', 'onbekend')}).

Bestaande handmatige klantcontext:
{existing_context or '(geen)'}

Vorige automatische ICP:
{existing_icp or '(geen)'}

Winnende advertenties (lage CPL / hoge ROAS):
{chr(10).join(winner_names) or '(geen data)'}

Verliezende advertenties (hoge CPL / lage ROAS):
{chr(10).join(loser_names) or '(geen data)'}

Best presterende hook-type: {best_hook}
Slechtst presterende hooks: {', '.join(worst_hooks) or 'onbekend'}

{"Inzichten uit verkoopgesprekken:" + chr(10) + transcript_ctx if transcript_ctx else ''}

Schrijf een beknopte ICP-update (max 300 woorden) met:
1. Wie de ideale klant is op basis van wat converteert
2. Welke pijnpunten het beste aanslaan (afgeleid uit winning ad-namen)
3. Welke beloftes niet werken (afgeleid uit losing ad-namen en slechte hooks)
4. Wat Claude de volgende keer moet weten bij het genereren van scripts/hooks

Schrijf alsof je notities maakt voor een strateeg. Bondig en feitelijk."""

    return call_text(prompt, max_tokens=500)
