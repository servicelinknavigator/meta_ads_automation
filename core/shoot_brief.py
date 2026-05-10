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


_DEFAULT_SCRIPTS: dict[str, list[dict]] = {
    "recognition": [
        {"time": "0-5s",   "tekst": "Ken jij dat gevoel dat je weet dat er meer in zit, maar je weet niet hoe je de volgende stap zet?"},
        {"time": "5-18s",  "tekst": "Veel ondernemers herkennen dit. Ze hebben een goed product, een goede dienst — maar de advertenties brengen niet de klanten die ze zoeken. En dat is frustrerend, want je weet dat het potentieel er is."},
        {"time": "18-25s", "tekst": "Wij helpen bedrijven om precies die klanten te bereiken. Met een bewezen aanpak die specifiek op jouw doelgroep is afgestemd."},
        {"time": "25-30s", "tekst": "Plan een gratis gesprek via de link in de bio — en ontdek wat er mogelijk is voor jouw business."},
    ],
    "frustration": [
        {"time": "0-5s",   "tekst": "Ziek van advertenties die veel kosten maar niks opleveren?"},
        {"time": "5-18s",  "tekst": "Je bent niet de enige. Het probleem zit bijna nooit in je product — het zit in de boodschap en de targeting. Verkeerde hook, verkeerde doelgroep, te weinig testen. Dat kost je elke dag omzet."},
        {"time": "18-25s", "tekst": "Wij hebben een systeem ontwikkeld dat exact test wat werkt voor jouw markt — en wat je kunt stoppen."},
        {"time": "25-30s", "tekst": "Gebruik de link in de bio voor een gratis analyse van jouw advertenties."},
    ],
    "curiosity": [
        {"time": "0-5s",   "tekst": "Wist je dat 80% van de Meta advertenties faalt om één reden — en dat de meeste ondernemers die reden nooit ontdekken?"},
        {"time": "5-18s",  "tekst": "Het zit in de eerste drie seconden. Als je kijker in dat moment niet stopt met scrollen, is het geld weg. Maar als je weet welke hook werkt voor jouw doelgroep, verandert alles."},
        {"time": "18-25s", "tekst": "Wij testen systematisch welke opening converteert — en schalen wat werkt."},
        {"time": "25-30s", "tekst": "Benieuwd wat jouw best converterende hook is? Plan een gratis gesprek via de link."},
    ],
    "proof": [
        {"time": "0-5s",   "tekst": "Deze klant daalde zijn CPL met 43% in zes weken — zonder extra budget."},
        {"time": "5-18s",  "tekst": "Niet door meer geld uit te geven, maar door beter te testen. We analyseerden welke advertenties werkten en waarom, stopten met de rest, en schaalden wat bewezen was. Het resultaat spreekt voor zich."},
        {"time": "18-25s", "tekst": "Dit is het systeem dat wij bij elke klant toepassen — data-gedreven, zonder giswerk."},
        {"time": "25-30s", "tekst": "Wil je weten wat dit voor jouw account kan betekenen? Plan een gratis gesprek via de link in de bio."},
    ],
    "promise": [
        {"time": "0-5s",   "tekst": "Binnen 30 dagen meetbaar resultaat — of we stoppen er samen mee."},
        {"time": "5-18s",  "tekst": "Dat is geen loze belofte. Het is een systeem. In de eerste week analyseren we je huidige advertenties. In week twee testen we nieuwe hooks. Vanaf week drie schalen we wat werkt. Na 30 dagen weet je exact wat je account nodig heeft."},
        {"time": "18-25s", "tekst": "Geen langlopende contracten, geen vage beloftes — alleen aantoonbare resultaten."},
        {"time": "25-30s", "tekst": "Plan nu een gratis gesprek via de link in de bio."},
    ],
    "confrontation": [
        {"time": "0-5s",   "tekst": "Stop met geld weggooien aan advertenties die niemand aanspreken."},
        {"time": "5-18s",  "tekst": "Hard om te horen, maar de meeste Meta campagnes zijn simpelweg slecht geconfigureerd. Verkeerde boodschap, verkeerd moment, verkeerde doelgroep. En terwijl jij wacht, groeit je concurrent die het wél goed doet."},
        {"time": "18-25s", "tekst": "Wij laten je zien waar het misgaat — en hoe je het omkeert met een bewezen aanpak."},
        {"time": "25-30s", "tekst": "Gebruik de link in de bio voor een gratis advertentie-analyse."},
    ],
    "urgency": [
        {"time": "0-5s",   "tekst": "Er zijn nog maar vijf plekken beschikbaar voor nieuwe klanten deze maand."},
        {"time": "5-18s",  "tekst": "We werken bewust met een beperkt aantal klanten tegelijk — zodat we elk account de aandacht kunnen geven die het verdient. Vorige maand waren alle plekken binnen tien dagen bezet. Dit is je kans om dit kwartaal nog resultaat te boeken."},
        {"time": "18-25s", "tekst": "Plan een gratis kennismakingsgesprek en ontdek of we een match zijn."},
        {"time": "25-30s", "tekst": "Gebruik de link in de bio — voor de plaatsen vol zijn."},
    ],
    "problem_solve": [
        {"time": "0-5s",   "tekst": "Dit is het probleem dat bijna elke ondernemer heeft met Meta advertenties — en zo los je het op."},
        {"time": "5-18s",  "tekst": "Je gooit geld in een systeem dat je niet begrijpt, en hoopt op resultaat. Maar Meta beloont wie test. Wie data gebruikt. Wie weet welke boodschap aanslaat bij welke doelgroep. Dat is precies wat wij voor je doen."},
        {"time": "18-25s", "tekst": "Stap één is simpel: analyseer wat je nu hebt. Stap twee: test wat werkt. Stap drie: schaal en win."},
        {"time": "25-30s", "tekst": "Plan een gratis gesprek via de link en we beginnen volgende week."},
    ],
    "social_proof": [
        {"time": "0-5s",   "tekst": "Meer dan 500 ondernemers gingen je al voor — dit is waarom ze kozen voor deze aanpak."},
        {"time": "5-18s",  "tekst": "Ze hadden allemaal hetzelfde probleem: te hoge CPL, te weinig leads, te veel giswerk. Door systematisch te testen — hook na hook, format na format — zagen ze gemiddeld 35% daling in advertentiekosten binnen 60 dagen."},
        {"time": "18-25s", "tekst": "Geen uitzondering. Geen toeval. Een bewezen systeem dat voor elke markt werkt."},
        {"time": "25-30s", "tekst": "Plan een gratis gesprek via de link en zie wat het voor jou kan doen."},
    ],
    "educational": [
        {"time": "0-5s",   "tekst": "Ik ga je in 30 seconden uitleggen waarom je Meta advertenties waarschijnlijk te duur zijn."},
        {"time": "5-18s",  "tekst": "Het probleem zit in de hook — de eerste drie seconden van je advertentie. Als die niet resoneert, stopt de kijker niet. En als hij niet stopt, betaal jij voor niets. De meeste adverteerders testen nooit hun hook systematisch, en betalen daarvoor de prijs."},
        {"time": "18-25s", "tekst": "Wij doen niets anders dan dit testen — en optimaliseren op basis van echte data."},
        {"time": "25-30s", "tekst": "Wil je weten welke hook voor jóuw doelgroep werkt? Plan een gratis gesprek via de link."},
    ],
}


def _default_script(hook: str, cta: str) -> list[dict]:
    if hook in _DEFAULT_SCRIPTS:
        return _DEFAULT_SCRIPTS[hook]
    return [
        {"time": "0-5s",   "tekst": _default_opening(hook)},
        {"time": "5-20s",  "tekst": "Wij hebben een bewezen aanpak ontwikkeld die specifiek op jouw situatie is afgestemd — data-gedreven en zonder giswerk."},
        {"time": "20-25s", "tekst": "Onze klanten zien gemiddeld binnen vier weken meetbaar verschil."},
        {"time": "25-30s", "tekst": f"{cta} — gebruik de link in de bio."},
    ]


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
      "hypothese": "wat je wilt bewijzen met deze shoot",
      "script": [
        {{"time": "0-5s",  "tekst": "exacte openingsregels die de presenter uitspreekt"}},
        {{"time": "5-18s", "tekst": "body: probleem, context of bewijs in spreektaal"}},
        {{"time": "18-25s","tekst": "oplossing of sociale bewijskracht"}},
        {{"time": "25-30s","tekst": "CTA: wat de kijker nu moet doen"}}
      ]
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
      "hypothese": "...",
      "script": [
        {{"time": "0-5s",  "tekst": "..."}},
        {{"time": "5-18s", "tekst": "..."}},
        {{"time": "18-25s","tekst": "..."}},
        {{"time": "25-30s","tekst": "..."}}
      ]
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
      "hypothese": "...",
      "script": [
        {{"time": "0-5s",  "tekst": "..."}},
        {{"time": "5-20s", "tekst": "..."}},
        {{"time": "20-35s","tekst": "..."}},
        {{"time": "35-45s","tekst": "..."}}
      ]
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
            "script": _default_script(hook, cta),
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
