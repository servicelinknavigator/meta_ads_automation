"""
Generates production-ready shoot briefs: 16 scripts per shoot day (70/20/10 rule).
10 long video scripts + 1 testimonial + 5 short (15s) scripts + b-roll list.
Falls back to rule-based briefs without API.
"""
from __future__ import annotations
import logging
from models.campaign import Ad, AnalysisSummary
from core.ai_client import has_api, call_json, _SLN_SYSTEM_JSON

logger = logging.getLogger(__name__)
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
    "Je schrijft video shoot briefs. Spreektaal, knipmomenten na elke 2-3 zinnen, "
    "altijd vanuit klantperspectief (ik). Geen marketingclichés. Geen em-dashes. "
    "Letterlijk te lezen op papier door de studio eigenaar."
)

_HOOK_NL: dict[str, str] = {
    "recognition":  "Herkenning",
    "frustration":  "Frustratie",
    "curiosity":    "Nieuwsgierigheid",
    "proof":        "Bewijs",
    "promise":      "Belofte",
    "confrontation":"Confrontatie",
    "urgency":      "Urgentie",
    "problem_solve":"Probleem-oplossing",
    "social_proof": "Sociale bewijskracht",
    "educational":  "Educatief",
    "unknown":      "Onbekend",
}


def _strip_em_dashes(text: str) -> str:
    return text.replace(" — ", ". ").replace("— ", ". ").replace(" —", ".")


def _clean_script(script) -> list[dict]:
    if isinstance(script, list):
        return [{"time": s.get("time",""), "tekst": _strip_em_dashes(str(s.get("tekst","")))} for s in script]
    return []


def _build_script(hook: str, cta: str, client_name: str) -> list[dict]:
    data = _fallback_script(hook, 1, client_name, cta)
    return [{"time": k, "tekst": _strip_em_dashes(v)} for k, v in data["tijdcodes"].items()]


def _best_hook(hook_perf: list[dict]) -> str:
    for row in hook_perf:
        if row["hook_type"] != "unknown" and row.get("results") and row["results"] > 0:
            return row["hook_type"]
    return "proof"


def _best_format(fmt_perf: list[dict]) -> str:
    for row in fmt_perf:
        if row.get("results") and row["results"] > 0:
            return row["format_type"]
    return "reels"


def _avg_script_length(all_ads: list[Ad]) -> str:
    """Bereken gemiddelde scriptlengte op basis van bestaande ad namen — heuristisch."""
    return "30-60 seconden"


def _summary_context(summary: AnalysisSummary, hook_perf: list[dict], fmt_perf: list[dict],
                     untested_hooks: list[str], all_ads: list | None = None,
                     winning_scripts: str = "") -> str:
    is_leads = summary.campaign_type != "purchases"
    metric = f"gem. CPL €{summary.avg_cost_per_result}" if is_leads else f"gem. ROAS {summary.avg_roas}"
    hook_lines = "\n".join(
        f"  {r['hook_type']}: {r['ads']} ads, {r['results']} resultaten, "
        f"CPL €{r['cpl'] or '?'}, CTR {r['avg_ctr'] or '?'}%"
        for r in hook_perf[:8]
    )
    fmt_lines = "\n".join(
        f"  {r['format_type']}: {r['ads']} ads, {r['results']} resultaten, CPL €{r['cpl'] or '?'}"
        for r in fmt_perf[:5]
    )

    top_ads_lines = ""
    if all_ads:
        winners = [a for a in all_ads if a.results > 0 and a.cost_per_result > 0][:8]
        if winners:
            top_ads_lines = "\nTop presterende advertenties (op CPL):\n" + "\n".join(
                f"  #{i+1} \"{a.ad_name}\" | CPL €{a.cost_per_result} | {a.results} leads"
                f" | spend €{round(a.spend)} | CTR {a.ctr}% | hook: {detect_hook(a.ad_name)}"
                f" | format: {detect_format(a.ad_name)}"
                for i, a in enumerate(sorted(winners, key=lambda x: x.cost_per_result))
            )

    scripts_block = f"\n\nWinnende scripts (stijlreferentie):\n{winning_scripts}" if winning_scripts else ""

    return (
        f"Account: {summary.num_ads} ads | {metric} | {summary.total_results} resultaten\n"
        f"Campagnetype: {summary.campaign_type}\n\n"
        f"Hook prestaties (gesorteerd op CPL, laagste = best):\n{hook_lines}\n\n"
        f"Format prestaties:\n{fmt_lines}\n\n"
        f"Ongeteste hooks: {', '.join(untested_hooks) if untested_hooks else 'geen'}"
        f"{top_ads_lines}"
        f"{scripts_block}"
    )


def generate_shoot_brief(
    summary: AnalysisSummary,
    all_ads: list[Ad],
    top_ad: Ad | None = None,
    client_name: str = "",
    client_context: str = "",
) -> list[dict]:
    """
    Genereert 16 stuks per shoot dag:
      - 10 video scripts (70/20/10 regel)
      - 1 testimonial script (6 interviewvragen)
      - 5 short scripts (15 seconden)
      - b-roll lijst als apart object (type='broll')
    """
    hook_perf       = aggregate_hook_performance(all_ads)
    fmt_perf        = aggregate_format_performance(all_ads)
    untested_hooks  = get_untested_hooks(all_ads)

    best_hook   = _best_hook(hook_perf)
    best_format = _best_format(fmt_perf)
    second_hook = next(
        (r["hook_type"] for r in hook_perf[1:] if r.get("results") and r["results"] > 0 and r["hook_type"] != best_hook),
        untested_hooks[0] if untested_hooks else HOOK_TYPES[(HOOK_TYPES.index(best_hook) + 1) % len(HOOK_TYPES)],
    )
    untested_hook = untested_hooks[0] if untested_hooks else HOOK_TYPES[(HOOK_TYPES.index(best_hook) + 2) % len(HOOK_TYPES)]
    wild_hook = next(
        (h for h in ["confrontation", "frustration", "curiosity"] if h != best_hook and h != second_hook),
        "confrontation",
    )

    if not has_api():
        return _fallback_brief(best_hook, best_format, second_hook, untested_hook, wild_hook,
                               hook_perf, fmt_perf, summary, top_ad, client_name)

    ctx = _summary_context(summary, hook_perf, fmt_perf, untested_hooks, all_ads=all_ads)
    top_ad_str = (
        f"Beste huidige ad: \"{top_ad.ad_name}\" (CPL €{top_ad.cost_per_result}, {top_ad.results} leads)"
        if top_ad else ""
    )

    client_block = ""
    if client_name or client_context:
        client_block = f"""
KLANT INFORMATIE:
Naam: {client_name or 'onbekend'}
{('Context / ICP:\n' + client_context[:1200]) if client_context else ''}

KRITISCH: Schrijf ALLE teksten vanuit het perspectief van de KLANT ({client_name}).
De klant adverteert aan hun eigen doelgroep voor hun eigen product/dienst.
NIET vanuit het perspectief van een marketingbureau.
Gebruik NOOIT em-dashes (—). Gebruik een punt of komma.
Spreektaal. Knipmomenten na elke 2-3 zinnen. Letterlijk te lezen op papier.
Noem altijd concrete cijfers of resultaten waar mogelijk.
"""

    prompt = f"""Genereer een complete shoot dag planning van 16 stuks op basis van deze performance data:

{ctx}
{top_ad_str}
{client_block}

STRUCTUUR (lever exact dit op):
1-7: Bewezen scripts (70%) — best presterende hook ({best_hook}) + variaties op #2 hook ({second_hook})
8-9: Test scripts (20%) — ongeteste hook ({untested_hook}) in bewezen format, bewezen hook + ander concept
10: Wild card (10%) — contrair concept, anti-sell, negatieve hook of onverwachte invalshoek ({wild_hook})
11: Testimonial script — 6 interviewvragen (geen spreektekst, interviewformat)
12-16: Short scripts (15 seconden) — gebaseerd op de 5 sterkste hooks uit scripts 1-10

VEREISTEN PER SCRIPT:
- Elk script is één coherent verhaal: de hook (0-5s) bepaalt het HELE script
- 0-5s: de haak — openingszin die het scrollen stopt, specifiek voor dit hook-type
- 5-20s: bouwt DIRECT voort op de openingszin — verdiept, verbaast of bevestigt wat 0-5s opende
- 20-40s: bewijs, resultaat of concrete oplossing die past bij de belofte van 0-5s
- 40-55s: CTA die logisch volgt op het verhaal — altijd laagdrempelig
- VERBODEN: dezelfde zin of concept in meerdere scripts gebruiken — elk script is 100% uniek
- VERBODEN: generieke merkcopy in 5-20s ("Bij X is het anders", "Persoonlijk en laagdrempelig", "vol te houden") — te vaag
- Noem altijd concrete cijfers of ervaringen uit de klantcontext waar mogelijk
- Vanuit klantperspectief (ik) — nooit marketingbureau-perspectief
- Knipmomenten na elke 2-3 zinnen (markeer met [KNIP])

HOOK-TYPE SCHRIJFGIDS (de hook bepaalt de structuur van het hele script):
- proof: 0-5s = klantresultaat of uitspraak. 5-20s = meer bewijs stapelen. 20-40s = hoe dat resultaat behaald werd.
- problem_solve: 0-5s = het probleem benoemen. 5-20s = verdiep het probleem/de frustratie. 20-40s = de oplossing.
- curiosity: 0-5s = mysterieuze of verrassende stelling. 5-20s = bouw spanning op. 20-40s = onthul het antwoord.
- confrontation: 0-5s = provocatieve uitdaging. 5-20s = ga verder in de confrontatie. 20-40s = de omslag/oplossing.
- recognition: 0-5s = herkenbare situatie. 5-20s = "dat was ik ook" — verdien de identificatie. 20-40s = hoe het veranderde.
- promise: 0-5s = concrete belofte. 5-20s = specificeer de belofte met details. 20-40s = bewijs dat het werkt.
- urgency: 0-5s = urgente situatie of deadline. 5-20s = waarom wachten risico is. 20-40s = de uitweg.
- social_proof: 0-5s = anderen doen het al. 5-20s = wie en met welk resultaat. 20-40s = hoe jij ook kunt starten.
- educational: 0-5s = interessante onbekende feit. 5-20s = leg het uit. 20-40s = wat betekent dit voor de kijker.

B-ROLL:
Na de 16 scripts genereer je één gecombineerde b-roll lijst.
Elk shot is direct gekoppeld aan een concreet moment uit een van de scripts.
Groepeer per categorie. Max 20 shots. Elk in 1 zin.

Return ALLEEN dit JSON (geen tekst eromheen):
{{
  "scripts": [
    {{
      "nummer": 1,
      "type": "bewezen",
      "regel": "70%",
      "hook_type": "{best_hook}",
      "naam": "korte naam ≤40 tekens",
      "logica": "waarom dit script — 1 zin",
      "redenering": "3-4 zinnen onderbouwd met CPL/CTR uit de data",
      "tijdcodes": {{
        "0-5s": "exacte openingszin — stopt met scrollen",
        "5-20s": "probleem of context — 2-3 zinnen",
        "20-40s": "oplossing, bewijs of resultaat — 2-3 zinnen",
        "40-55s": "CTA — laagdrempelige vervolgstap"
      }},
      "volledig_script": "het volledige script als doorlopende tekst met [KNIP] markeringen",
      "cta": "call-to-action tekst"
    }},
    {{
      "nummer": 2,
      "type": "bewezen",
      "regel": "70%",
      "hook_type": "{best_hook}",
      "naam": "...",
      "logica": "...",
      "redenering": "...",
      "tijdcodes": {{"0-5s": "...", "5-20s": "...", "20-40s": "...", "40-55s": "..."}},
      "volledig_script": "...",
      "cta": "..."
    }},
    {{
      "nummer": 3,
      "type": "bewezen",
      "regel": "70%",
      "hook_type": "{second_hook}",
      "naam": "...",
      "logica": "...",
      "redenering": "...",
      "tijdcodes": {{"0-5s": "...", "5-20s": "...", "20-40s": "...", "40-55s": "..."}},
      "volledig_script": "...",
      "cta": "..."
    }},
    {{
      "nummer": 4,
      "type": "bewezen",
      "regel": "70%",
      "hook_type": "{second_hook}",
      "naam": "...",
      "logica": "andere invalshoek dan script 3",
      "redenering": "...",
      "tijdcodes": {{"0-5s": "...", "5-20s": "...", "20-40s": "...", "40-55s": "..."}},
      "volledig_script": "...",
      "cta": "..."
    }},
    {{
      "nummer": 5,
      "type": "bewezen",
      "regel": "70%",
      "hook_type": "{best_hook}",
      "naam": "...",
      "logica": "winner iterate — verse creative om fatigue te voorkomen",
      "redenering": "...",
      "tijdcodes": {{"0-5s": "...", "5-20s": "...", "20-40s": "...", "40-55s": "..."}},
      "volledig_script": "...",
      "cta": "..."
    }},
    {{
      "nummer": 6,
      "type": "bewezen",
      "regel": "70%",
      "hook_type": "{best_hook}",
      "naam": "...",
      "logica": "andere openingszin dan script 5",
      "redenering": "...",
      "tijdcodes": {{"0-5s": "...", "5-20s": "...", "20-40s": "...", "40-55s": "..."}},
      "volledig_script": "...",
      "cta": "..."
    }},
    {{
      "nummer": 7,
      "type": "bewezen",
      "regel": "70%",
      "hook_type": "{best_hook}",
      "naam": "...",
      "logica": "langste bewezen scriptlengte voor dit account",
      "redenering": "...",
      "tijdcodes": {{"0-5s": "...", "5-20s": "...", "20-40s": "...", "40-55s": "..."}},
      "volledig_script": "...",
      "cta": "..."
    }},
    {{
      "nummer": 8,
      "type": "test",
      "regel": "20%",
      "hook_type": "{untested_hook}",
      "naam": "...",
      "logica": "ongeteste hook in bewezen format — één variabele anders",
      "redenering": "...",
      "tijdcodes": {{"0-5s": "...", "5-20s": "...", "20-40s": "...", "40-55s": "..."}},
      "volledig_script": "...",
      "cta": "..."
    }},
    {{
      "nummer": 9,
      "type": "test",
      "regel": "20%",
      "hook_type": "{best_hook}",
      "naam": "...",
      "logica": "bewezen hook, ander concept — andere emotionele trigger",
      "redenering": "...",
      "tijdcodes": {{"0-5s": "...", "5-20s": "...", "20-40s": "...", "40-55s": "..."}},
      "volledig_script": "...",
      "cta": "..."
    }},
    {{
      "nummer": 10,
      "type": "wild_card",
      "regel": "10%",
      "hook_type": "{wild_hook}",
      "naam": "...",
      "logica": "contrair concept — anti-sell, negatieve hook of compleet onverwacht",
      "redenering": "...",
      "tijdcodes": {{"0-5s": "...", "5-20s": "...", "20-40s": "...", "40-55s": "..."}},
      "volledig_script": "...",
      "cta": "..."
    }},
    {{
      "nummer": 11,
      "type": "testimonial",
      "regel": "apart",
      "hook_type": "proof",
      "naam": "Testimonial interview",
      "logica": "klant aan het woord — 6 interviewvragen, geen spreektekst voor de ondernemer",
      "redenering": "Testimonials bouwen sociaal bewijs op. Interviewformat: probleem → beslissing → resultaat → aanbeveling.",
      "vragen": [
        "Vraag 1: specifiek voor deze branche/doelgroep",
        "Vraag 2: ...",
        "Vraag 3: ...",
        "Vraag 4: ...",
        "Vraag 5: ...",
        "Vraag 6: ..."
      ],
      "interviewstructuur": "probleem → beslissing → resultaat → aanbeveling",
      "cta": "..."
    }},
    {{
      "nummer": 12,
      "type": "short",
      "regel": "15s",
      "hook_type": "{best_hook}",
      "naam": "Short 1",
      "logica": "15-seconden versie van script 1",
      "openingszin": "0-3s — stopt met scrollen",
      "kernbelofte": "3-10s — kernbelofte in 1-2 zinnen",
      "cta": "10-15s — directe actie"
    }},
    {{
      "nummer": 13,
      "type": "short",
      "regel": "15s",
      "hook_type": "{second_hook}",
      "naam": "Short 2",
      "logica": "15-seconden versie gebaseerd op hook {second_hook}",
      "openingszin": "...",
      "kernbelofte": "...",
      "cta": "..."
    }},
    {{
      "nummer": 14,
      "type": "short",
      "regel": "15s",
      "hook_type": "{untested_hook}",
      "naam": "Short 3",
      "logica": "15-seconden versie gebaseerd op hook {untested_hook}",
      "openingszin": "...",
      "kernbelofte": "...",
      "cta": "..."
    }},
    {{
      "nummer": 15,
      "type": "short",
      "regel": "15s",
      "hook_type": "{wild_hook}",
      "naam": "Short 4",
      "logica": "15-seconden versie gebaseerd op hook {wild_hook}",
      "openingszin": "...",
      "kernbelofte": "...",
      "cta": "..."
    }},
    {{
      "nummer": 16,
      "type": "short",
      "regel": "15s",
      "hook_type": "{best_hook}",
      "naam": "Short 5",
      "logica": "alternatieve 15-seconden versie van de winnende hook",
      "openingszin": "...",
      "kernbelofte": "...",
      "cta": "..."
    }}
  ],
  "broll": {{
    "studio_shots": [
      "Shot beschrijving — Script X, moment: ...",
      "..."
    ],
    "klant_shots": ["..."],
    "trainer_shots": ["..."],
    "detail_shots": ["..."]
  }}
}}"""

    result = call_json(prompt, system=_SHOOT_SYSTEM, max_tokens=16000)
    if "_error" in result or "scripts" not in result:
        logger.error("Shoot brief AI call failed: %s | keys=%s", result.get("_error", "no 'scripts' key"), list(result.keys()))
        return _fallback_brief(best_hook, best_format, second_hook, untested_hook, wild_hook,
                               hook_perf, fmt_perf, summary, top_ad, client_name)

    scripts = result["scripts"]
    broll   = result.get("broll", {})

    # Opschonen
    for s in scripts:
        if s.get("volledig_script"):
            s["volledig_script"] = _strip_em_dashes(str(s["volledig_script"]))
        if s.get("openingszin"):
            s["openingszin"] = _strip_em_dashes(str(s["openingszin"]))
        for key in ("kernbelofte", "cta"):
            if s.get(key):
                s[key] = _strip_em_dashes(str(s[key]))
        if s.get("tijdcodes") and isinstance(s["tijdcodes"], dict):
            s["tijdcodes"] = {k: _strip_em_dashes(str(v)) for k, v in s["tijdcodes"].items()}

    # Voeg b-roll als apart item toe
    scripts.append({"type": "broll", "broll": broll})
    return scripts


# ── Fallback (geen API) ───────────────────────────────────────────────────────

def _fallback_script(hook: str, nummer: int, client_name: str, cta: str) -> dict:
    n = client_name or "ons"
    openings = {
        "recognition":  f"Herken je dat gevoel? Je wil iets veranderen, maar de drempel voelt groot.",
        "frustration":  f"Je hebt het al zo vaak geprobeerd. En het houdt toch nooit vol.",
        "curiosity":    f"Wist je dat je maar 20 minuten per week nodig hebt om echt resultaat te zien?",
        "proof":        f"Dit is wat onze klanten zeggen na een paar maanden bij {n}.",
        "promise":      f"Stel je voor: in 20 minuten per week fitter, sterker en meer energie.",
        "confrontation":f"Stop met wachten op het perfecte moment. Dat moment komt toch niet.",
        "urgency":      f"We hebben nog een beperkt aantal plekken beschikbaar voor nieuwe leden.",
        "problem_solve":f"Dit is het probleem dat veel mensen hebben. En zo lossen we het op.",
        "social_proof": f"Honderden mensen gingen je al voor bij {n}. Dit is waarom ze bleven.",
        "educational":  f"Ik leg je in 30 seconden uit hoe het werkt.",
    }
    opening = openings.get(hook, f"Heb jij dit ook? Dan is dit iets voor jou.")
    return {
        "nummer": nummer,
        "type": "bewezen",
        "regel": "70%",
        "hook_type": hook,
        "naam": f"{hook.replace('_','-')}-reels-v{nummer}",
        "logica": f"{_HOOK_NL.get(hook, hook)} in bewezen format.",
        "redenering": f"Fallback script op basis van {_HOOK_NL.get(hook, hook)} hook.",
        "tijdcodes": {
            "0-5s":   opening,
            "5-20s":  f"Bij {n} is het anders. Persoonlijk, laagdrempelig en vol te houden.",
            "20-40s": f"Onze aanpak is wetenschappelijk onderbouwd en bewezen effectief.",
            "40-55s": f"{cta}. Gebruik de link.",
        },
        "volledig_script": f"{opening} [KNIP] Bij {n} is het anders. Persoonlijk, laagdrempelig en vol te houden. [KNIP] Onze aanpak is bewezen effectief. [KNIP] {cta}.",
        "cta": cta,
        "_fallback": True,
    }


def _fallback_short(hook: str, nummer: int, script_num: int, client_name: str, cta: str) -> dict:
    n = client_name or "ons"
    openings = {
        "recognition": "Herken je dit?",
        "frustration":  "Ziek van aanpakken die niet werken?",
        "curiosity":    "Wist je dit al?",
        "proof":        "Onze klanten zeggen het zelf.",
        "promise":      "In 20 minuten per week echt resultaat.",
        "confrontation":"Stop met wachten.",
        "urgency":      "Nog beperkt aantal plekken.",
        "problem_solve":"Zo los je het op.",
        "social_proof": "500+ mensen gingen je voor.",
        "educational":  "Dit is hoe het werkt.",
    }
    return {
        "nummer": nummer,
        "type": "short",
        "regel": "15s",
        "hook_type": hook,
        "naam": f"Short {nummer - 11}",
        "logica": f"15s versie van script {script_num}",
        "openingszin": openings.get(hook, "Heb jij dit ook?"),
        "kernbelofte": f"Bij {n} pakken we dit anders aan. Persoonlijk, laagdrempelig.",
        "cta": cta,
        "_fallback": True,
    }


def _fallback_brief(
    best_hook: str, best_format: str,
    second_hook: str, untested_hook: str, wild_hook: str,
    hook_perf: list[dict], fmt_perf: list[dict],
    summary: AnalysisSummary,
    top_ad: Ad | None,
    client_name: str = "",
) -> list[dict]:
    is_leads = summary.campaign_type != "purchases"
    cta = "Plan een gratis proefles" if is_leads else "Bestel nu"
    n = client_name or "ons"

    scripts = []

    # 7 bewezen scripts
    hooks_70 = [best_hook, best_hook, second_hook, second_hook, best_hook, best_hook, best_hook]
    typen_70 = ["bewezen"]*7
    logicas  = [
        "best presterende hook + format, iteratie op winnende script",
        "zelfde hook, andere body — variatie op script 1",
        "op-één-na-beste hook + bewezen format",
        "zelfde als script 3, andere invalshoek",
        "winner iterate — zelfde hook/format, ander concept om fatigue te voorkomen",
        "zelfde als script 5, andere openingszin",
        "beste hook + langste bewezen scriptlengte voor dit account",
    ]
    for i, (hook, logica) in enumerate(zip(hooks_70, logicas), start=1):
        s = _fallback_script(hook, i, client_name, cta)
        s["logica"] = logica
        s["regel"]  = "70%"
        scripts.append(s)

    # 2 test scripts
    for i, (hook, logica) in enumerate([(untested_hook, "ongeteste hook in bewezen format"), (best_hook, "bewezen hook, ander concept")], start=8):
        s = _fallback_script(hook, i, client_name, cta)
        s["type"]   = "test"
        s["regel"]  = "20%"
        s["logica"] = logica
        scripts.append(s)

    # 1 wild card
    s = _fallback_script(wild_hook, 10, client_name, cta)
    s["type"]   = "wild_card"
    s["regel"]  = "10%"
    s["logica"] = "contrair concept — anti-sell of onverwachte invalshoek"
    scripts.append(s)

    # Testimonial
    scripts.append({
        "nummer": 11,
        "type": "testimonial",
        "regel": "apart",
        "hook_type": "proof",
        "naam": "Testimonial interview",
        "logica": "klant aan het woord — interviewformat",
        "redenering": "Sociaal bewijs via echte klantverhalen.",
        "vragen": [
            f"Wat was je grootste uitdaging voordat je bij {n} begon?",
            f"Wat maakte dat je uiteindelijk de stap zette?",
            f"Wat verraste je het meest in de eerste weken?",
            f"Wat is concreet veranderd voor jou na een aantal maanden?",
            f"Wat zou je zeggen tegen iemand die twijfelt?",
            f"Hoe zou je {n} omschrijven aan een vriend?",
        ],
        "interviewstructuur": "probleem → beslissing → resultaat → aanbeveling",
        "cta": cta,
        "_fallback": True,
    })

    # 5 short scripts
    short_hooks = [best_hook, second_hook, untested_hook, wild_hook, best_hook]
    for idx, hook in enumerate(short_hooks):
        scripts.append(_fallback_short(hook, 12 + idx, idx + 1, client_name, cta))

    # B-roll
    scripts.append({
        "type": "broll",
        "broll": {
            "studio_shots": [
                f"Totaaloverzicht studio of locatie van {n} — Script 1, opening",
                f"Close-up van begeleider/trainer in gesprek met klant — Script 3, moment: oplossing",
            ],
            "klant_shots": [
                f"Klant in actie, glimlachend — Script 4, moment: resultaat",
                f"Klant loopt/beweegt zonder moeite — Script 2, moment: bewijs",
            ],
            "trainer_shots": [
                f"Trainer geeft persoonlijke begeleiding — Script 1, moment: oplossing",
            ],
            "detail_shots": [
                f"Close-up materiaal of apparatuur van {n} — Script 7, moment: uitleg",
                f"Locatie-exterrieur of logo in beeld — Script 5, moment: CTA",
            ],
        },
        "_fallback": True,
    })

    return scripts
