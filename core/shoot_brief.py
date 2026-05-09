"""
Generates production-ready shoot briefs for SLN's hook testing workflow.
Always produces 3 shoots: safe (proven hook), new_hook (untested angle), format_test.
Falls back to rule-based briefs without API.
"""
from __future__ import annotations
from models.campaign import Ad, AnalysisSummary
from core.ai_client import has_api, call_json, _SLN_SYSTEM_JSON
from core.hook_analyzer import (
    aggregate_hook_performance,
    aggregate_format_performance,
    get_untested_hooks,
    get_untested_formats,
    detect_hook,
    detect_format,
    HOOK_TYPES,
    FORMAT_TYPES,
)


_SHOOT_SYSTEM = (
    _SLN_SYSTEM_JSON + " "
    "Je schrijft shoot briefs voor video shoots. "
    "Geef altijd praktische productie-instructies: aspect ratio, duur, talent, locatie."
)

_HOOK_NL: dict[str, str] = {
    "recognition": "Herkenning — de kijker voelt zich aangesproken ('Ken jij dit...')",
    "frustration": "Frustratie — benoem een concrete pijn ('Ziek van...')",
    "curiosity": "Nieuwsgierigheid — verrassend feit of vraag",
    "proof": "Bewijs — klantresultaat of testimonial",
    "promise": "Belofte — concreet resultaat in X tijd",
    "confrontation": "Confrontatie — directe aanspraak ('Stop met...')",
    "urgency": "Urgentie — beperkte beschikbaarheid of deadline",
    "problem_solve": "Probleem-oplossing — laat het probleem zien, dan de oplossing",
    "social_proof": "Sociale bewijskracht — cijfers en autoriteit",
    "educational": "Educatief — waardevolle kennis die vertrouwen opbouwt",
    "unknown": "Organisch / ongesorteerd",
}

_FORMAT_NL: dict[str, str] = {
    "talking_head": "Talking head — presentator direct in camera",
    "testimonial": "Testimonial — klant aan het woord",
    "ugc": "UGC-stijl — authentiek, handheld, no-budget look",
    "problem_solve": "Problem-solve — probleem tonen → oplossing",
    "story": "Verhalend — begin–midden–eind narratief",
    "carousel": "Carousel — meerdere slides of frames",
    "static": "Static — beeld met tekst overlay",
    "reels": "Reels / Short-form — ≤60s verticaal",
    "product_demo": "Product demo — product in gebruik tonen",
    "before_after": "Before/After — transformatie vergelijking",
    "animation": "Animatie — motion graphics of illustratie",
}


def _best_hook(hook_perf: list[dict]) -> str:
    for row in hook_perf:
        if row["hook_type"] != "unknown" and row["results"] and row["results"] > 0:
            return row["hook_type"]
    return "proof"


def _best_format(fmt_perf: list[dict]) -> str:
    for row in fmt_perf:
        if row["results"] and row["results"] > 0:
            return row["format_type"]
    return "talking_head"


def _summary_context(summary: AnalysisSummary, hook_perf: list[dict], fmt_perf: list[dict],
                     untested_hooks: list[str]) -> str:
    is_leads = summary.campaign_type != "purchases"
    metric = f"gem. CPL €{summary.avg_cost_per_result}" if is_leads else f"gem. ROAS {summary.avg_roas}"
    hook_lines = "\n".join(
        f"  {r['hook_type']}: {r['ads']} ads, {r['results']} resultaten, "
        f"CPL €{r['cpl'] or '?'}, CTR {r['avg_ctr'] or '?'}%"
        for r in hook_perf[:6]
    )
    fmt_lines = "\n".join(
        f"  {r['format_type']}: {r['ads']} ads, {r['results']} resultaten, CPL €{r['cpl'] or '?'}"
        for r in fmt_perf[:5]
    )
    return (
        f"Account: {summary.num_ads} ads | {metric} | {summary.total_results} resultaten\n"
        f"Campagnetype: {summary.campaign_type}\n\n"
        f"Hook prestaties (gesorteerd op CPL):\n{hook_lines}\n\n"
        f"Format prestaties:\n{fmt_lines}\n\n"
        f"Nog niet geteste hooks: {', '.join(untested_hooks) if untested_hooks else 'geen'}"
    )


def generate_shoot_brief(
    summary: AnalysisSummary,
    all_ads: list[Ad],
    top_ad: Ad | None = None,
) -> list[dict]:
    hook_perf = aggregate_hook_performance(all_ads)
    fmt_perf = aggregate_format_performance(all_ads)
    untested_hooks = get_untested_hooks(all_ads)
    untested_formats = get_untested_formats(all_ads)

    safe_hook = _best_hook(hook_perf)
    safe_format = _best_format(fmt_perf)
    new_hook = untested_hooks[0] if untested_hooks else (
        HOOK_TYPES[(HOOK_TYPES.index(safe_hook) + 1) % len(HOOK_TYPES)]
    )
    test_format = untested_formats[0] if untested_formats else "testimonial"

    if not has_api():
        return _fallback_brief(safe_hook, safe_format, new_hook, test_format, summary, top_ad)

    ctx = _summary_context(summary, hook_perf, fmt_perf, untested_hooks)
    top_ad_str = f"Beste huidige ad: \"{top_ad.ad_name}\" (CPL €{top_ad.cost_per_result}, {top_ad.results} leads)" if top_ad else ""

    prompt = f"""Genereer een shoot planning met 3 shoots voor SLN Solutions op basis van deze data:

{ctx}
{top_ad_str}

Shoots die je MOET opleveren:
1. "safe" — bewezen hook ({safe_hook}) in bewezen format ({safe_format}), iteratie op best presterende ad
2. "new_hook" — ongeteste hook ({new_hook}), zelfde format als safe
3. "format_test" — beste hook ({safe_hook}) in nieuw format ({test_format})

Return ALLEEN dit JSON:
{{
  "shoots": [
    {{
      "type": "safe",
      "naam_suggestie": "korte naam voor intern gebruik ≤40 tekens",
      "concept": "1-2 zinnen: wat het ad laat zien en waarom het werkt",
      "hook_type": "{safe_hook}",
      "openingszin": "exacte eerste zin van het script (Nederlands)",
      "format": "{safe_format}",
      "aspect_ratio": "9:16 of 1:1 of 16:9",
      "duur_seconden": 30,
      "talent": "omschrijving van wie voor de camera staat",
      "locatie": "waar de shoot plaatsvindt",
      "shots": ["shot 1 beschrijving", "shot 2", "shot 3", "shot 4", "shot 5"],
      "key_message": "de kern van het ad in 1 zin",
      "cta": "call-to-action tekst",
      "hypothese": "wat je wilt bewijzen met deze shoot"
    }},
    {{
      "type": "new_hook",
      "naam_suggestie": "...",
      "concept": "...",
      "hook_type": "{new_hook}",
      "openingszin": "...",
      "format": "{safe_format}",
      "aspect_ratio": "9:16",
      "duur_seconden": 30,
      "talent": "...",
      "locatie": "...",
      "shots": ["...", "...", "...", "...", "..."],
      "key_message": "...",
      "cta": "...",
      "hypothese": "..."
    }},
    {{
      "type": "format_test",
      "naam_suggestie": "...",
      "concept": "...",
      "hook_type": "{safe_hook}",
      "openingszin": "...",
      "format": "{test_format}",
      "aspect_ratio": "9:16",
      "duur_seconden": 45,
      "talent": "...",
      "locatie": "...",
      "shots": ["...", "...", "...", "...", "..."],
      "key_message": "...",
      "cta": "...",
      "hypothese": "..."
    }}
  ]
}}"""

    result = call_json(prompt, system=_SHOOT_SYSTEM, max_tokens=2000)
    if "_error" in result or "shoots" not in result:
        return _fallback_brief(safe_hook, safe_format, new_hook, test_format, summary, top_ad)
    return result["shoots"]


def _fallback_brief(
    safe_hook: str, safe_format: str,
    new_hook: str, test_format: str,
    summary: AnalysisSummary,
    top_ad: Ad | None,
) -> list[dict]:
    is_leads = summary.campaign_type != "purchases"
    cta = "Plan een gratis gesprek" if is_leads else "Bestel nu"

    def _base(shoot_type: str, hook: str, fmt: str, duur: int) -> dict:
        return {
            "type": shoot_type,
            "naam_suggestie": f"{hook.replace('_', '-').title()} {fmt.replace('_', '-').title()} V1",
            "concept": f"{_HOOK_NL.get(hook, hook)} gecombineerd met {_FORMAT_NL.get(fmt, fmt)}.",
            "hook_type": hook,
            "openingszin": _default_opening(hook),
            "format": fmt,
            "aspect_ratio": "9:16",
            "duur_seconden": duur,
            "talent": "Presentator of klant (authentiek, niet overdreven zakelijk)",
            "locatie": "Kantoor of neutrale achtergrond — professioneel maar warm",
            "shots": [
                "Shot 1: close-up gezicht bij opening — kijker moet connectie voelen",
                "Shot 2: probleem of context visueel tonen",
                "Shot 3: de oplossing of het product/dienst",
                "Shot 4: resultaat of bewijs (scherm, grafiek, klant)",
                "Shot 5: directe CTA — kijker aankijken en actie benoemen",
            ],
            "key_message": f"SLN helpt je {summary.campaign_type}-resultaten te verbeteren.",
            "cta": cta,
            "hypothese": f"Test of de {hook}-hook beter converteert dan het huidige gemiddelde (CPL €{summary.avg_cost_per_result}).",
            "_fallback": True,
        }

    return [
        _base("safe", safe_hook, safe_format, 30),
        _base("new_hook", new_hook, safe_format, 30),
        _base("format_test", safe_hook, test_format, 45),
    ]


def _default_opening(hook: str) -> str:
    defaults = {
        "recognition": "Ken jij dat gevoel dat je weet dat er meer in zit, maar je weet niet hoe?",
        "frustration": "Ik was ook gefrustreerd toen mijn advertenties niks deden — totdat ik dit ontdekte.",
        "curiosity": "Wist je dat 80% van de Meta advertenties faalt om één reden?",
        "proof": "Deze klant behaalde €X resultaat in Y weken — dit is hoe.",
        "promise": "Binnen 30 dagen meetbaar resultaat — of je geld terug.",
        "confrontation": "Stop met geld weggooien aan advertenties die niet werken.",
        "urgency": "Er zijn nog maar 5 plekken beschikbaar deze maand.",
        "problem_solve": "Dit is het probleem dat bijna elke ondernemer heeft — en zo los je het op.",
        "social_proof": "500+ tevreden klanten gingen je al voor. Dit is waarom zij kozen voor ons.",
        "educational": "Ik ga je in 30 seconden uitleggen waarom je Meta advertenties waarschijnlijk te duur zijn.",
    }
    return defaults.get(hook, "Heb jij dit ook? Dan is dit iets voor jou.")
