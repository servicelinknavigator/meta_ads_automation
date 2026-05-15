"""
Analyzes static ad images with Claude Vision.
Returns copy, headline, hook type and improvement tips based on the image
and the account's performance data.
"""
from __future__ import annotations
from core.ai_client import call_json_with_image, has_api, _SLN_SYSTEM_JSON

_SYSTEM = (
    _SLN_SYSTEM_JSON + " "
    "Je analyseert Meta Ads static afbeeldingen en schrijft advertentieteksten "
    "vanuit het perspectief van de klant — niet vanuit het bureau."
)

_HOOK_OPTS = (
    "proof, promise, frustration, recognition, curiosity, "
    "social_proof, problem_solve, educational, confrontation, urgency"
)


def analyze_static(
    image_data: bytes,
    media_type: str,
    client_name: str = "",
    client_context: str = "",
    hook_perf: list[dict] | None = None,
    top_ads: list | None = None,
) -> dict:
    """
    Analyze a static ad image and return copy + headline suggestions.

    Returns dict with: hook_type, visual_samenvatting, copy, headline, verbeterpunt.
    Falls back gracefully when API is unavailable.
    """
    if not has_api():
        return _fallback()

    perf_ctx = _build_perf_context(hook_perf, top_ads)
    client_block = _build_client_block(client_name, client_context)

    prompt = f"""Analyseer deze Meta Ads static afbeelding.{client_block}{perf_ctx}

Doe het volgende:
1. Bepaal welke hook-strategie het beeld communiceert.
2. Vat samen wat het beeld zegt (1-2 zinnen).
3. Schrijf een geoptimaliseerde copy op basis van wat je in het beeld ziet én de sterkst presterende hooks in het account.
4. Schrijf een headline die past bij het beeld.
5. Geef één concrete tip om de prestaties van dit type static te verbeteren.

Schrijf copy en headline vanuit het perspectief van de klant ({client_name or 'de adverteerder'}).
De kijker is een potentiële klant, niet een ondernemer die advertentiediensten zoekt.
Gebruik GEEN em dashes (—). Gebruik een punt of komma in plaats daarvan.

Return ALLEEN dit JSON:
{{
  "hook_type": "een van: {_HOOK_OPTS}",
  "visual_samenvatting": "1-2 zinnen: wat communiceert dit beeld precies?",
  "copy": "3-5 zinnen advertentietekst voor in de feed. Spreektaal, persoonlijk, aansluitend op de sterkste hook in het account.",
  "headline": "max 8 woorden, pakkend en actiegericht",
  "verbeterpunt": "1 concrete, specifieke tip om de prestaties van dit static-type te verhogen"
}}"""

    result = call_json_with_image(prompt, image_data, media_type, system=_SYSTEM, max_tokens=900)
    if "_error" in result:
        return _fallback(error=result["_error"])
    return result


def _build_perf_context(hook_perf: list[dict] | None, top_ads: list | None) -> str:
    parts = []
    if hook_perf:
        winners = [r for r in hook_perf[:6] if r.get("results") and r["results"] > 0]
        if winners:
            lines = "\n".join(
                f"  - {r['hook_type']}: CPL €{r['cpl']}, {r['results']} resultaten, CTR {r.get('avg_ctr') or '?'}%"
                for r in winners
            )
            parts.append(f"\nBest presterende hooks in dit account:\n{lines}")
    if top_ads:
        lines = "\n".join(
            f'  - "{a.ad_name}" | CPL €{a.cost_per_result} | {a.results} leads'
            for a in top_ads[:5]
        )
        parts.append(f"\nTop advertenties (laagste CPL):\n{lines}")
    return "".join(parts)


def _build_client_block(client_name: str, client_context: str) -> str:
    if not client_name and not client_context:
        return ""
    lines = ["\n\nKlantcontext:"]
    if client_name:
        lines.append(f"Klant: {client_name}")
    if client_context:
        lines.append(f"ICP/Context: {client_context[:400]}")
    return "\n".join(lines)


def _fallback(error: str = "") -> dict:
    return {
        "hook_type": "unknown",
        "visual_samenvatting": "Analyse niet beschikbaar — controleer de API verbinding.",
        "copy": "",
        "headline": "",
        "verbeterpunt": "",
        "_fallback": True,
        **({"_error": error} if error else {}),
    }
