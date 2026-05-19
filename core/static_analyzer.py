"""
Analyzes static ad images with Claude Vision.
Returns 2 copy variants + headline based on the image, account performance data,
and the client's existing copy patterns (word count, style, hook distribution).
"""
from __future__ import annotations
from core.ai_client import call_json, call_json_with_image, call_text_with_image, has_api, _SLN_SYSTEM_JSON

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
    existing_copies: list[dict] | None = None,
) -> dict:
    """
    Analyze a static ad image and return 2 copy variants + headline suggestions.

    existing_copies: list of dicts with keys:
        ad_name, copy, hook_type (optional), cpl (optional), results (optional)

    Returns dict with: hook_type, visual_samenvatting, copy_1, copy_1_aanpak,
                       copy_2, copy_2_aanpak, headline, verbeterpunt.
    """
    if not has_api():
        return _fallback()

    perf_ctx = _build_perf_context(hook_perf, top_ads)
    client_block = _build_client_block(client_name, client_context)
    copy_ctx = _build_copy_context(existing_copies)

    prompt = f"""Analyseer deze Meta Ads static afbeelding.{client_block}{perf_ctx}{copy_ctx}

Opdracht:
1. Bepaal welke hook-strategie het beeld communiceert.
2. Vat samen wat het beeld zegt (1-2 zinnen).
3. Analyseer de bestaande copy-patronen van dit account:
   - Welke woordlengte (kort vs lang) presteert beter?
   - Welke schrijfstijl (direct/emotioneel/bewijs) scoort het beste?
   - Wat ontbreekt nog als invalshoek?
4. Schrijf TWEE copy-varianten die elkaar aanvullen:
   - Variant 1: bouw voort op de bewezen aanpak (veilige keuze — gebruik de best presterende hook + woordlengte)
   - Variant 2: test een nieuwe invalshoek (andere hook of woordlengte die nog niet getest is, of een sterke tegenstelling)
5. Schrijf één headline die past bij het beeld.
6. Geef één concrete tip om de prestaties van dit type static te verbeteren.

Schrijf copy vanuit het perspectief van de klant ({client_name or 'de adverteerder'}).
De kijker is een potentiële klant, niet een ondernemer die advertentiediensten zoekt.
Gebruik GEEN em dashes (—). Gebruik een punt of komma in plaats daarvan.
Geen herhaling tussen de twee varianten — ze moeten elk een eigen invalshoek hebben.

Return ALLEEN dit JSON:
{{
  "hook_type": "een van: {_HOOK_OPTS}",
  "visual_samenvatting": "1-2 zinnen: wat communiceert dit beeld precies?",
  "copy_1": "Variant 1 copy tekst. Spreektaal, persoonlijk, aansluitend op de bewezen hook.",
  "copy_1_aanpak": "1 zin: welke hook + woordlengte + waarom dit de veilige keuze is",
  "copy_2": "Variant 2 copy tekst. Andere hook of woordlengte als test.",
  "copy_2_aanpak": "1 zin: welke hook + woordlengte + waarom dit de testoptie is",
  "headline": "max 8 woorden, pakkend en actiegericht",
  "verbeterpunt": "1 concrete, specifieke tip om de prestaties van dit static-type te verhogen"
}}"""

    result = call_json_with_image(prompt, image_data, media_type, system=_SYSTEM, max_tokens=1200)
    if "_error" in result:
        return _fallback(error=result["_error"])
    return result


def _build_perf_context(hook_perf: list[dict] | None, top_ads: list | None) -> str:
    parts = []
    if hook_perf:
        winners = [r for r in hook_perf[:8] if r.get("results") and r["results"] > 0]
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


def _build_copy_context(existing_copies: list[dict] | None) -> str:
    if not existing_copies:
        return ""

    lines = []
    short_cpls = []   # <= 20 woorden
    medium_cpls = []  # 21-40 woorden
    long_cpls = []    # > 40 woorden

    for c in existing_copies[:20]:
        copy_text = c.get("copy", "").strip()
        if not copy_text:
            continue
        word_count = len(copy_text.split())
        cpl = c.get("cpl")
        results = c.get("results")
        hook = c.get("hook_type", "")
        ad_name = c.get("ad_name", "")

        stats_parts = []
        if cpl:
            stats_parts.append(f"CPL €{cpl:.0f}")
        if results:
            stats_parts.append(f"{results} results")
        stats = " | ".join(stats_parts) if stats_parts else "geen stats"

        lines.append(
            f'  Ad: "{ad_name}" | Hook: {hook or "?"} | {word_count} woorden | {stats}\n'
            f'  Copy: "{copy_text[:200]}{"..." if len(copy_text) > 200 else ""}"'
        )

        if cpl and results and results > 0:
            if word_count <= 20:
                short_cpls.append(cpl)
            elif word_count <= 40:
                medium_cpls.append(cpl)
            else:
                long_cpls.append(cpl)

    if not lines:
        return ""

    summary_parts = []
    if short_cpls:
        summary_parts.append(f"korte copy (≤20 woorden): gem. CPL €{sum(short_cpls)/len(short_cpls):.0f}")
    if medium_cpls:
        summary_parts.append(f"middellange copy (21-40 woorden): gem. CPL €{sum(medium_cpls)/len(medium_cpls):.0f}")
    if long_cpls:
        summary_parts.append(f"lange copy (>40 woorden): gem. CPL €{sum(long_cpls)/len(long_cpls):.0f}")

    block = "\n\nBestaande copies van dit account (gebruik dit voor stijl- en woordtellinganalyse):\n"
    block += "\n\n".join(lines)
    if summary_parts:
        block += "\n\nWoordtelling vs. prestatie:\n  " + "\n  ".join(summary_parts)
    block += "\n\nGebruik bovenstaande diagnose om de twee copy-varianten te onderbouwen."
    return block


def _build_client_block(client_name: str, client_context: str) -> str:
    if not client_name and not client_context:
        return ""
    lines = ["\n\nKlantcontext:"]
    if client_name:
        lines.append(f"Klant: {client_name}")
    if client_context:
        lines.append(f"ICP/Context: {client_context[:400]}")
    return "\n".join(lines)


def detect_hook_from_image(image_data: bytes, media_type: str) -> dict:
    """
    Detecteer hook_type, visual_summary en pain_point uit afbeelding.
    Één JSON vision call geeft alles tegelijk terug (betrouwbaarder dan twee losse calls).
    """
    if not has_api():
        return {"hook_type": "promise", "visual_summary": "", "pain_point": "", "_fallback": True}

    hook_opts = (
        "promise, proof, urgency, recognition, frustration, curiosity, "
        "confrontation, problem_solve, social_proof, educational"
    )

    result = call_json_with_image(
        f"""Analyseer deze Meta advertentie afbeelding.

Geef terug als JSON:
{{
  "hook_type": "kies uit: {hook_opts}",
  "visual_summary": "2-5 woorden: wat zie je op de afbeelding (bijv. 'vrouw traint in gym', '20 minuten resultaat', 'voor na vergelijking')",
  "pain_point": "1 zin: welk probleem of verlangen speelt de afbeelding in?"
}}""",
        image_data,
        media_type,
        max_tokens=200,
    )

    if "_error" in result:
        return {"hook_type": "promise", "visual_summary": "", "pain_point": "", "_error": result["_error"]}

    return {
        "hook_type": result.get("hook_type", "promise").lower().replace(" ", "_"),
        "visual_summary": result.get("visual_summary", "").strip(),
        "pain_point": result.get("pain_point", ""),
    }


def _fallback(error: str = "") -> dict:
    return {
        "hook_type": "unknown",
        "visual_samenvatting": "Analyse niet beschikbaar — controleer de API verbinding.",
        "copy_1": "",
        "copy_1_aanpak": "",
        "copy_2": "",
        "copy_2_aanpak": "",
        "headline": "",
        "verbeterpunt": "",
        "_fallback": True,
        **({"_error": error} if error else {}),
    }
