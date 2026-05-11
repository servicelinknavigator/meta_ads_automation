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


def _strip_em_dashes(text: str) -> str:
    """Replace em dashes with natural spoken alternatives."""
    return text.replace(" — ", ". ").replace("— ", ". ").replace(" —", ".")


def _clean_script(script: list[dict]) -> list[dict]:
    """Remove em dashes from all script lines."""
    return [{"time": s["time"], "tekst": _strip_em_dashes(s["tekst"])} for s in script]


def _build_script(hook: str, cta: str, client_name: str) -> list[dict]:
    """
    Returns a fallback script written from the CLIENT's perspective.
    The client is advertising to their own customers, not SLN to leads.
    Scripts are calm, personal and recognition-based (fit20 ICP-inspired).
    No em dashes anywhere.
    """
    n = client_name or "ons"

    scripts: dict[str, list[dict]] = {
        "recognition": [
            {"time": "0-5s",   "tekst": "Herken je dat gevoel? Je wil wel iets doen, maar de drempel voelt groot."},
            {"time": "5-18s",  "tekst": f"Veel mensen denken: ik moet eigenlijk iets doen. Maar ze weten niet waar te beginnen. Of ze hebben het al geprobeerd en het hield toch niet vol. Bij {n} snappen we dat. Daarom doen we het anders."},
            {"time": "18-25s", "tekst": f"Persoonlijke begeleiding, op jouw tempo, zonder dat het je leven overneemt. Dat is wat {n} biedt."},
            {"time": "25-30s", "tekst": f"{cta}. Gebruik de link in de bio."},
        ],
        "frustration": [
            {"time": "0-5s",   "tekst": "Je hebt het al zo vaak geprobeerd. En het houdt toch nooit vol."},
            {"time": "5-18s",  "tekst": "Dat frustrerende gevoel is begrijpelijk. En het ligt echt niet aan jou. De meeste aanpakken zijn gewoon niet gemaakt voor mensen met een druk leven, lichamelijke klachten, of een hekel aan de sportschool."},
            {"time": "18-25s", "tekst": f"Bij {n} is het anders. Laagdrempelig, persoonlijk, en wel vol te houden."},
            {"time": "25-30s", "tekst": f"{cta}. Link in de bio."},
        ],
        "curiosity": [
            {"time": "0-5s",   "tekst": "Wist je dat je maar 20 minuten per week nodig hebt om echt sterker te worden?"},
            {"time": "5-18s",  "tekst": f"De meeste mensen denken dat je uren moet investeren om resultaat te zien. Dat is een misvatting. Bij {n} werken we met een wetenschappelijk onderbouwde methode die in 20 minuten meer doet dan een uur in de sportschool."},
            {"time": "18-25s", "tekst": "Geen zweten, geen gedoe, geen volle zaal. Gewoon resultaat."},
            {"time": "25-30s", "tekst": f"{cta}. Gebruik de link."},
        ],
        "proof": [
            {"time": "0-5s",   "tekst": "Dit is wat onze leden zeggen na een paar maanden."},
            {"time": "5-18s",  "tekst": f"Eindelijk iets dat ik volhoud. Ik loop de trap op zonder moeite. Ik voel me sterker dan in jaren. Geen grote beloftes, gewoon wat mensen ervaren als ze beginnen met een aanpak die echt bij ze past. Bij {n}."},
            {"time": "18-25s", "tekst": f"Bij {n} staat persoonlijke begeleiding centraal. Niet een schema, maar een trainer die echt naar jou kijkt."},
            {"time": "25-30s", "tekst": f"{cta}. Gebruik de link in de bio."},
        ],
        "promise": [
            {"time": "0-5s",   "tekst": "Stel je voor: in 20 minuten per week fitter, sterker en meer energie."},
            {"time": "5-18s",  "tekst": f"Dat klinkt bijna te goed om waar te zijn. Maar het is precies wat onze leden ervaren. {n} werkt met EMS-technologie die in één sessie 90% van je spieren activeert. Wetenschappelijk bewezen, veilig en effectief. Ook voor 50 plus."},
            {"time": "18-25s", "tekst": "Geen lange contracten. Geen gedoe. Gewoon resultaat dat je voelt."},
            {"time": "25-30s", "tekst": f"{cta}. Gebruik de link."},
        ],
        "confrontation": [
            {"time": "0-5s",   "tekst": "Stop met wachten op het perfecte moment. Dat moment komt toch niet."},
            {"time": "5-18s",  "tekst": "Elke maand dat je wacht, is een maand dat je je minder fit voelt. Minder energie. Meer stijfheid. Dat hoeft niet. Een kleine stap, gewoon eens kennismaken, kan alles veranderen."},
            {"time": "18-25s", "tekst": f"Bij {n} is de eerste stap gratis. Geen verplichtingen, geen druk."},
            {"time": "25-30s", "tekst": f"{cta}. Link in de bio."},
        ],
        "urgency": [
            {"time": "0-5s",   "tekst": "We hebben nog een beperkt aantal plekken beschikbaar voor nieuwe leden."},
            {"time": "5-18s",  "tekst": f"Bij {n} werken we bewust met kleine groepen, zodat je altijd persoonlijke aandacht krijgt. Dat betekent dat we niet onbeperkt nieuwe leden aannemen. En elke maand zijn die plekken snel bezet."},
            {"time": "18-25s", "tekst": "Wil je dit kwartaal nog beginnen? Dan is nu het moment."},
            {"time": "25-30s", "tekst": f"{cta}. Gebruik de link voordat de plekken vol zijn."},
        ],
        "problem_solve": [
            {"time": "0-5s",   "tekst": "Dit is het probleem dat veel mensen hebben. En zo lossen we het op."},
            {"time": "5-18s",  "tekst": f"Je wil fitter worden, maar een drukke sportschool past niet bij je. Je hebt weinig tijd. Je hebt misschien lichamelijke klachten. Je wil begeleiding die echt naar jou kijkt, niet een schema dat voor iedereen hetzelfde is. Dat is precies waarom {n} bestaat."},
            {"time": "18-25s", "tekst": f"Persoonlijk, laagdrempelig, en vol te houden. Dat is {n}."},
            {"time": "25-30s", "tekst": f"{cta}. Link in de bio."},
        ],
        "social_proof": [
            {"time": "0-5s",   "tekst": "Honderden mensen gingen je al voor. Dit is waarom ze bleven."},
            {"time": "5-18s",  "tekst": f"Ze kwamen bij {n} met twijfels. Is dit iets voor mij? Houd ik het vol? Maar na de eerste proefles wisten ze het: dit is anders. Persoonlijk. Rustig. Zonder oordeel. Met aantoonbaar resultaat."},
            {"time": "18-25s", "tekst": "Geen hype. Geen grote beloftes. Gewoon tevreden leden die zich eindelijk sterker voelen."},
            {"time": "25-30s", "tekst": f"{cta}. Gebruik de link."},
        ],
        "educational": [
            {"time": "0-5s",   "tekst": "Ik leg je in 30 seconden uit waarom 20 minuten per week echt genoeg is."},
            {"time": "5-18s",  "tekst": f"De EMS-methode van {n} activeert 90% van je spiergroepen tegelijk. Bij gewone training is dat zo'n 30 tot 40 procent. Dat betekent: in één sessie van 20 minuten doe je effectief wat je normaal in 90 minuten zou doen. Zonder je versleten te voelen."},
            {"time": "18-25s", "tekst": "Wetenschappelijk onderbouwd, veilig, en al bewezen bij duizenden mensen."},
            {"time": "25-30s", "tekst": f"{cta}. Gebruik de link om het zelf te ervaren."},
        ],
    }

    return scripts.get(hook, [
        {"time": "0-5s",   "tekst": _default_opening(hook)},
        {"time": "5-18s",  "tekst": f"Bij {n} staat persoonlijke begeleiding centraal. Op jouw tempo, afgestemd op jouw situatie, zonder gedoe."},
        {"time": "18-25s", "tekst": "Mensen die twijfelden, zijn nu onze trouwste leden. Gewoon omdat het bij ze past."},
        {"time": "25-30s", "tekst": f"{cta}. Link in de bio."},
    ])


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
    client_name: str = "",
    client_context: str = "",
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
        return _fallback_brief(safe_hook, safe_format, new_hook, test_format,
                               summary, top_ad, client_name)

    ctx = _summary_context(summary, hook_perf, fmt_perf, untested_hooks)
    top_ad_str = f"Beste huidige ad: \"{top_ad.ad_name}\" (CPL €{top_ad.cost_per_result}, {top_ad.results} leads)" if top_ad else ""

    client_block = ""
    if client_name or client_context:
        client_block = f"""
KLANT INFORMATIE:
Naam: {client_name or 'onbekend'}
{('Context / ICP:\n' + client_context) if client_context else ''}

KRITISCH: Schrijf alle scripts en openingszinnen vanuit het perspectief van de KLANT ({client_name}).
De klant adverteert aan hun eigen doelgroep voor hun eigen product/dienst.
NIET vanuit het perspectief van een marketingbureau.
De kijker van de advertentie is een potentiële klant van {client_name}, geen ondernemer die advertentiediensten zoekt.
Gebruik NOOIT em dashes (het teken —) in scripts of openingszinnen. Gebruik in plaats daarvan een punt of komma.
"""

    prompt = f"""Genereer een shoot planning met 3 shoots op basis van deze performance data:

{ctx}
{top_ad_str}
{client_block}
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
        return _fallback_brief(safe_hook, safe_format, new_hook, test_format,
                               summary, top_ad, client_name)
    # Sanitize AI output: strip em dashes from all script lines and openingszin
    shoots = result["shoots"]
    for shoot in shoots:
        if shoot.get("script"):
            shoot["script"] = _clean_script(shoot["script"])
        if shoot.get("openingszin"):
            shoot["openingszin"] = _strip_em_dashes(shoot["openingszin"])
    return shoots


def _fallback_brief(
    safe_hook: str, safe_format: str,
    new_hook: str, test_format: str,
    summary: AnalysisSummary,
    top_ad: Ad | None,
    client_name: str = "",
) -> list[dict]:
    is_leads = summary.campaign_type != "purchases"
    cta = "Plan een gratis proefles" if is_leads else "Bestel nu"
    name = client_name or "ons"

    def _base(shoot_type: str, hook: str, fmt: str, duur: int) -> dict:
        script = _build_script(hook, cta, client_name)
        opening = script[0]["tekst"] if script else _default_opening(hook)
        return {
            "type": shoot_type,
            "naam_suggestie": f"{hook.replace('_', '-').title()} {fmt.replace('_', '-').title()} V1",
            "concept": f"{_HOOK_NL.get(hook, hook)} gecombineerd met {_FORMAT_NL.get(fmt, fmt)}.",
            "hook_type": hook,
            "openingszin": opening,
            "format": fmt,
            "aspect_ratio": "9:16",
            "duur_seconden": duur,
            "talent": "Lid/klant of trainer (authentiek, warm — geen acteur)",
            "locatie": "In de studio of locatie van de klant — herkenbare omgeving",
            "shots": [
                "Shot 1: close-up gezicht bij opening — kijker moet zich herkend voelen",
                "Shot 2: de situatie of het probleem visueel tonen (herkenbaar voor doelgroep)",
                f"Shot 3: de oplossing — wat {name} biedt, liefst in actie",
                "Shot 4: resultaat of bewijs — blije klant, zichtbaar verschil",
                "Shot 5: directe CTA — kijker aankijken, actie benoemen",
            ],
            "key_message": f"Persoonlijke begeleiding bij {name} — eindelijk iets dat vol te houden is.",
            "cta": cta,
            "hypothese": f"Test of de {hook}-hook beter converteert dan het huidige gemiddelde (CPL €{summary.avg_cost_per_result}).",
            "script": script,
            "_fallback": True,
        }

    return [
        _base("safe", safe_hook, safe_format, 30),
        _base("new_hook", new_hook, safe_format, 30),
        _base("format_test", safe_hook, test_format, 45),
    ]


def _default_opening(hook: str) -> str:
    """Fallback opening lines written from the client's perspective. No em dashes."""
    defaults = {
        "recognition": "Herken je dat gevoel? Je wil iets veranderen, maar weet niet waar te beginnen.",
        "frustration": "Je hebt het al zo vaak geprobeerd. En het houdt toch nooit vol.",
        "curiosity": "Wist je dat je maar 20 minuten per week nodig hebt om echt resultaat te zien?",
        "proof": "Dit zeggen onze klanten na een paar maanden.",
        "promise": "Stel je voor: in 20 minuten per week fitter, sterker en meer energie.",
        "confrontation": "Stop met wachten op het perfecte moment. Dat moment komt toch niet.",
        "urgency": "We hebben nog een beperkt aantal plekken beschikbaar voor nieuwe leden.",
        "problem_solve": "Dit is het probleem dat veel mensen hebben. En zo lossen we het op.",
        "social_proof": "Honderden mensen gingen je al voor. Dit is waarom ze bleven.",
        "educational": "Ik leg je in 30 seconden uit waarom 20 minuten per week echt genoeg is.",
    }
    return defaults.get(hook, "Heb jij dit ook? Dan is dit iets voor jou.")
