"""
AI Script Generator — genereert 2 video script aanbevelingen per klant.

Leert van klantdata:
- Hook performance (welke hooks laagste CPL hebben)
- Bestaande scripts (stijl, lengte, structuur die werkt)
- Winnende ad namen (patronen)
- Client ICP en context

Geeft altijd 2 scripts terug: bewezen aanpak + nieuwe testoptie.
"""
from __future__ import annotations
from core.ai_client import call_json, has_api, _SLN_SYSTEM_JSON

_SYSTEM = (
    _SLN_SYSTEM_JSON + " "
    "Je schrijft video scripts voor Meta advertenties. "
    "Scripts zijn authentiek, spreektaal, geen em dashes. "
    "Altijd vanuit het perspectief van de klant, nooit als bureau."
)

_FORMAT_OPTS = "reels, ugc, testimonial, before_after, product_demo, animation"
_HOOK_OPTS   = (
    "proof, promise, frustration, recognition, curiosity, "
    "social_proof, problem_solve, educational, confrontation, urgency"
)


def generate_scripts(
    client_name: str = "",
    client_context: str = "",
    hook_perf: list[dict] | None = None,
    existing_scripts: list[dict] | None = None,
) -> dict:
    """
    Generate 2 video script recommendations for a client.

    hook_perf: list of {hook_type, cpl, results, avg_ctr}
    existing_scripts: list of {ad_name, script_text, hook_type, cpl, results}

    Returns: {script_1: {...}, script_2: {...}, diagnose: str}
    """
    if not has_api():
        return _fallback()

    perf_ctx    = _build_perf_context(hook_perf)
    script_ctx  = _build_script_context(existing_scripts)
    client_block = _build_client_block(client_name, client_context)

    prompt = f"""Genereer 2 video script aanbevelingen voor Meta Reels/UGC advertenties.{client_block}{perf_ctx}{script_ctx}

Analyseer eerst de klantdata:
- Welke hook types hebben de laagste CPL? (dat is de bewezen aanpak)
- Wat is de schrijfstijl en toon van bestaande winnende scripts?
- Welke hook types zijn nog NIET getest of presteren slecht? (dat is de testoptie)
- Wat is de ideale scriptlengte op basis van bestaande data?

Script 1 = bewezen aanpak: gebruik de best presterende hook + bewezen schrijfstijl.
Script 2 = testoptie: gebruik een ongeteste of onderpresterende hook met een frisse invalshoek.

Elk script heeft 4 tijdblokken:
- 0-5s: Hook (pakkend, direct, stopt de scroll)
- 5-18s: Body (probleem/bewijs/verhaal, conversationeel)
- 18-25s: Oplossing/USP (concreet voordeel, geen buzzwords)
- 25-30s: CTA (laagdrempelig, duidelijk)

Schrijf vanuit het perspectief van de klant ({client_name or 'de adverteerder'}).
GEEN em dashes. Spreektaal. Authentiek, alsof iemand dit echt zegt.

Return ALLEEN dit JSON:
{{
  "diagnose": "2-3 zinnen: wat leert de data ons over wat werkt voor {client_name or 'deze klant'}? Benoem specifieke hooks/CPL/patronen.",
  "script_1": {{
    "hook_type": "een van: {_HOOK_OPTS}",
    "format": "een van: {_FORMAT_OPTS}",
    "naam_suggestie": "bijv. Reels - Proof - V1 - [korte beschrijving]",
    "aanpak": "1 zin waarom dit de bewezen keuze is op basis van data",
    "script": [
      {{"time": "0-5s",  "tekst": "..."}},
      {{"time": "5-18s", "tekst": "..."}},
      {{"time": "18-25s","tekst": "..."}},
      {{"time": "25-30s","tekst": "..."}}
    ]
  }},
  "script_2": {{
    "hook_type": "een van: {_HOOK_OPTS}",
    "format": "een van: {_FORMAT_OPTS}",
    "naam_suggestie": "bijv. Reels - Curiosity - V1 - [korte beschrijving]",
    "aanpak": "1 zin waarom dit een waardevolle testoptie is",
    "script": [
      {{"time": "0-5s",  "tekst": "..."}},
      {{"time": "5-18s", "tekst": "..."}},
      {{"time": "18-25s","tekst": "..."}},
      {{"time": "25-30s","tekst": "..."}}
    ]
  }}
}}"""

    result = call_json(prompt, system=_SYSTEM, max_tokens=1800)
    if "_error" in result:
        return _fallback(error=result["_error"])
    return result


def _build_perf_context(hook_perf: list[dict] | None) -> str:
    if not hook_perf:
        return ""
    rows = [r for r in hook_perf if r.get("hook_type")]
    if not rows:
        return ""

    with_results = [r for r in rows if r.get("results") and r["results"] > 0]
    without = [r for r in rows if not r.get("results") or r["results"] == 0]

    lines = []
    if with_results:
        lines.append("Hook prestaties (gesorteerd op CPL):")
        for r in sorted(with_results, key=lambda x: float(x.get("cpl") or x.get("overall_cpl") or 999)):
            cpl = r.get("cpl") or r.get("overall_cpl")
            results = r.get("results") or r.get("total_results")
            ctr = r.get("avg_ctr") or "?"
            lines.append(
                f"  - {r['hook_type']}: CPL €{cpl}, {results} resultaten, CTR {ctr}%"
            )
    if without:
        lines.append("Nog niet getest (kans voor testoptie):")
        for r in without:
            lines.append(f"  - {r['hook_type']}")

    return "\n\n" + "\n".join(lines)


def _build_script_context(existing_scripts: list[dict] | None) -> str:
    if not existing_scripts:
        return ""

    entries = []
    for s in existing_scripts[:10]:
        script_text = s.get("script_text", "").strip()
        if not script_text:
            continue
        ad_name  = s.get("ad_name", "")
        hook     = s.get("hook_type", "?")
        cpl      = s.get("cpl")
        results  = s.get("results")
        words    = len(script_text.split())

        stats = []
        if cpl:      stats.append(f"CPL €{cpl:.0f}")
        if results:  stats.append(f"{results} results")
        stat_str = " | ".join(stats) if stats else "geen stats"

        entries.append(
            f'Script: "{ad_name}" | Hook: {hook} | {words} woorden | {stat_str}\n'
            f'Tekst: "{script_text[:350]}{"..." if len(script_text) > 350 else ""}"'
        )

    if not entries:
        return ""

    return "\n\nBestaande scripts van dit account (leer van toon, lengte en structuur):\n\n" + "\n\n".join(entries)


def _build_client_block(client_name: str, client_context: str) -> str:
    if not client_name and not client_context:
        return ""
    parts = ["\n\nKlantcontext:"]
    if client_name:
        parts.append(f"Klant: {client_name}")
    if client_context:
        parts.append(f"ICP/Context: {client_context[:500]}")
    return "\n".join(parts)


def _fallback(error: str = "") -> dict:
    return {
        "diagnose": "Analyse niet beschikbaar — controleer de API verbinding.",
        "script_1": None,
        "script_2": None,
        "_fallback": True,
        **({"_error": error} if error else {}),
    }
