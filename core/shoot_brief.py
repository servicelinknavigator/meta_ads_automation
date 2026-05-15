"""
Generates production-ready shoot briefs for SLN's hook testing workflow.
Always produces 3 shoots: safe (proven hook), new_hook (untested angle), format_test.
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
    "reels": "Reels / Short-form — ≤60s verticaal (incl. talking head / presentator in camera)",
    "testimonial": "Testimonial — klant aan het woord",
    "ugc": "UGC-stijl — authentiek, handheld, no-budget look",
    "story": "Verhalend — begin–midden–eind narratief",
    "carousel": "Carousel — meerdere slides of frames",
    "static": "Static — beeld met tekst overlay",
    "product_demo": "Product demo — product in gebruik tonen",
    "before_after": "Before/After — transformatie vergelijking",
    "animation": "Animatie — motion graphics of illustratie",
}

_STATIC_FORMATS = {"static", "carousel", "animation", "before_after"}


def _best_hook(hook_perf: list[dict]) -> str:
    for row in hook_perf:
        if row["hook_type"] != "unknown" and row["results"] and row["results"] > 0:
            return row["hook_type"]
    return "proof"


def _best_format(fmt_perf: list[dict]) -> str:
    for row in fmt_perf:
        if row["results"] and row["results"] > 0:
            return row["format_type"]
    return "reels"


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


def _build_copy(hook: str, cta: str, client_name: str) -> str:
    n = client_name or "ons"
    copies: dict[str, str] = {
        "recognition": (
            f"Herken je dat gevoel? Je wil iets doen, maar de drempel voelt groot. "
            f"Bij {n} snappen we dat. Onze aanpak is persoonlijk, laagdrempelig en vol te houden. "
            f"Geen gedoe. Gewoon resultaat op jouw tempo. {cta}."
        ),
        "frustration": (
            f"Heb je het al zo vaak geprobeerd en houdt het toch nooit vol? Dat ligt echt niet aan jou. "
            f"De meeste aanpakken zijn gewoon niet gemaakt voor mensen met een druk leven. "
            f"Bij {n} is het anders. Persoonlijk, laagdrempelig, en eindelijk vol te houden. {cta}."
        ),
        "curiosity": (
            f"Wist je dat je maar 20 minuten per week nodig hebt om echt sterker te worden? "
            f"De methode van {n} activeert in één sessie meer spieren dan een uur in de sportschool. "
            f"Wetenschappelijk onderbouwd, veilig en bewezen effectief. {cta}."
        ),
        "proof": (
            f"Onze leden zeggen het zelf: sterker, fitter en meer energie in minder tijd. "
            f"Bij {n} staat persoonlijke begeleiding centraal. "
            f"Geen schema's voor iedereen. Een trainer die echt naar jou kijkt. {cta}."
        ),
        "promise": (
            f"Stel je voor: in 20 minuten per week fitter, sterker en meer energie. "
            f"{n} werkt met een bewezen methode die in één sessie 90% van je spieren activeert. "
            f"Geen lange contracten. Geen gedoe. Gewoon resultaat dat je voelt. {cta}."
        ),
        "confrontation": (
            f"Stop met wachten op het perfecte moment. Dat moment komt toch niet. "
            f"Elke maand dat je wacht, is een maand minder energie. Bij {n} is de eerste stap gratis. "
            f"Geen verplichtingen, geen druk. Gewoon kennismaken. {cta}."
        ),
        "urgency": (
            f"Nog een beperkt aantal plekken beschikbaar. "
            f"Bij {n} werken we bewust met kleine groepen voor persoonlijke aandacht. "
            f"Dat betekent: we nemen niet onbeperkt nieuwe leden aan. Wil je dit kwartaal beginnen? {cta}."
        ),
        "problem_solve": (
            f"Je wil fitter worden, maar een drukke sportschool past niet bij je. "
            f"Weinig tijd, misschien lichamelijke klachten, en begeleiding die echt naar jou kijkt. "
            f"Dat is precies waarom {n} bestaat. Persoonlijk, laagdrempelig, vol te houden. {cta}."
        ),
        "social_proof": (
            f"Honderden mensen gingen je al voor bij {n}. Ze kwamen met twijfels en bleven vanwege de resultaten. "
            f"Persoonlijk, rustig, zonder oordeel. Aantoonbaar sterker en fitter. "
            f"Geen hype. Gewoon tevreden leden. {cta}."
        ),
        "educational": (
            f"De EMS-methode van {n} activeert 90% van je spiergroepen in één sessie van 20 minuten. "
            f"Bij gewone training is dat 30 tot 40 procent. "
            f"Wetenschappelijk onderbouwd, veilig, en al bewezen bij duizenden mensen. {cta}."
        ),
    }
    return copies.get(
        hook,
        f"Bij {n} staat persoonlijke begeleiding centraal. Op jouw tempo, zonder gedoe. {cta}."
    )


def _build_headline(hook: str) -> str:
    headlines: dict[str, str] = {
        "recognition": "Eindelijk iets dat bij jou past",
        "frustration": "Stop met worstelen. Begin met resultaat.",
        "curiosity": "20 minuten per week, meetbaar resultaat",
        "proof": "Wat onze leden zeggen na 3 maanden",
        "promise": "Fitter in 20 minuten per week",
        "confrontation": "Stop met wachten. Begin vandaag.",
        "urgency": "Nog beperkt aantal plekken beschikbaar",
        "problem_solve": "Jouw oplossing voor een druk leven",
        "social_proof": "500+ tevreden leden. Nu jij.",
        "educational": "Zo werkt EMS-training in 30 seconden",
    }
    return headlines.get(hook, "Persoonlijke begeleiding, meetbaar resultaat")


def _summary_context(summary: AnalysisSummary, hook_perf: list[dict], fmt_perf: list[dict],
                     untested_hooks: list[str], all_ads: list | None = None) -> str:
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

    return (
        f"Account: {summary.num_ads} ads | {metric} | {summary.total_results} resultaten\n"
        f"Campagnetype: {summary.campaign_type}\n\n"
        f"Hook prestaties (gesorteerd op CPL):\n{hook_lines}\n\n"
        f"Format prestaties:\n{fmt_lines}\n\n"
        f"Nog niet geteste hooks: {', '.join(untested_hooks) if untested_hooks else 'geen'}"
        f"{top_ads_lines}"
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

    # Second-best hook + format for winner_scale shoot
    winner_hook = next(
        (r["hook_type"] for r in hook_perf[1:] if r["results"] and r["results"] > 0 and r["hook_type"] != safe_hook),
        new_hook,
    )
    winner_format = next(
        (r["format_type"] for r in fmt_perf[1:] if r["results"] and r["results"] > 0 and r["format_type"] != safe_format),
        safe_format,
    )

    if not has_api():
        return _fallback_brief(safe_hook, safe_format, new_hook, test_format,
                               winner_hook, winner_format, hook_perf, fmt_perf,
                               summary, top_ad, client_name)

    ctx = _summary_context(summary, hook_perf, fmt_perf, untested_hooks, all_ads=all_ads)
    top_ad_str = f"Beste huidige ad: \"{top_ad.ad_name}\" (CPL €{top_ad.cost_per_result}, {top_ad.results} leads)" if top_ad else ""

    client_block = ""
    if client_name or client_context:
        client_block = f"""
KLANT INFORMATIE:
Naam: {client_name or 'onbekend'}
{('Context / ICP:\n' + client_context) if client_context else ''}

KRITISCH: Schrijf alle teksten vanuit het perspectief van de KLANT ({client_name}).
De klant adverteert aan hun eigen doelgroep voor hun eigen product/dienst.
NIET vanuit het perspectief van een marketingbureau.
De kijker van de advertentie is een potentiële klant van {client_name}, geen ondernemer die advertentiediensten zoekt.
Gebruik NOOIT em dashes (het teken —) in scripts, copy of openingszinnen. Gebruik in plaats daarvan een punt of komma.
"""

    def _media_block(fmt: str, times: list[str] | None = None) -> str:
        """Return format-specific JSON fields: visual_beschrijving for static, shots+script for video."""
        if fmt in _STATIC_FORMATS:
            return (
                '      "visual_beschrijving": "Exacte tekst overlay op het beeld, achtergrondkleur of -afbeelding, '
                'compositie (waar staat wat), sfeer, CTA-element (knoptekst, positie)",'
            )
        t = times or ["0-5s", "5-18s", "18-25s", "25-30s"]
        inner = ",\n        ".join(f'{{"time": "{x}", "tekst": "..."}}' for x in t)
        return (
            '      "shots": ["shot 1", "shot 2", "shot 3", "shot 4", "shot 5"],\n'
            f'      "script": [\n        {inner}\n      ],'
        )

    def _talent_locatie(fmt: str) -> str:
        if fmt in _STATIC_FORMATS:
            return '      "talent": "n.v.t. — grafisch ontwerp",\n      "locatie": "stock beelden of eigen fotografie",'
        return '      "talent": "...",\n      "locatie": "...",'

    def _duur(fmt: str, seconden: int) -> str:
        if fmt in _STATIC_FORMATS:
            return '      "duur_seconden": null,'
        return f'      "duur_seconden": {seconden},'

    _m_safe  = _media_block(safe_format)
    _m_new   = _media_block(safe_format)
    _m_test  = _media_block(test_format, ["0-5s", "5-20s", "20-35s", "35-45s"])
    _m_iter  = _media_block(safe_format)
    _m_scale = _media_block(winner_format)

    _tl_safe  = _talent_locatie(safe_format)
    _tl_test  = _talent_locatie(test_format)
    _tl_scale = _talent_locatie(winner_format)

    _d_safe  = _duur(safe_format, 30)
    _d_test  = _duur(test_format, 45)
    _d_scale = _duur(winner_format, 30)

    prompt = f"""Genereer een shoot planning met 5 shoots op basis van deze performance data:

{ctx}
{top_ad_str}
{client_block}
COPY & HEADLINE (verplicht bij ALLE shoots):
- "copy": 3-5 zinnen advertentietekst voor in de feed. Spreektaal, vanuit klantperspectief, gebaseerd op winnende ads of nieuwe inzichten.
- "headline": max 8 woorden, pakkend en actiegericht (verschijnt als titel onder de creative).
  Baseer copy en headline op de best presterende advertenties in het account en de hook-strategie.

FORMAT-SPECIFIEK:
- Static/carousel/animatie format: GEEN 'shots' en GEEN 'script'. Gebruik 'visual_beschrijving' voor het beeldconcept.
- Video/reels format: 'shots' en 'script' zijn verplicht. Copy en headline zijn de advertentietekst bij het video-ad.

Shoots die je MOET opleveren:
1. "safe" — bewezen hook ({safe_hook}) in bewezen format ({safe_format}), iteratie op best presterende ad
2. "new_hook" — ongeteste hook ({new_hook}), zelfde format als safe
3. "format_test" — beste hook ({safe_hook}) in nieuw format ({test_format})
4. "winner_iterate" — directe herhaling van de winnende ad: ZELFDE hook ({safe_hook}) en format ({safe_format}) als shoot 1, maar volledig nieuwe copy, headline en creatief concept. Doel: vers creatief op dezelfde winnende formule.
5. "winner_scale" — schaal de #2 presterende combinatie op: hook={winner_hook}, format={winner_format}.

KRITISCH: Shoot 4 (winner_iterate) en shoot 1 (safe) hebben DEZELFDE hook+format maar VOLLEDIG ANDERE copy, headline en creatieve invalshoek.
KRITISCH: Het creatieve concept van shoot 3 (format_test) MOET inhoudelijk anders zijn dan shoot 1. Pas copy en openingszin aan op het format {test_format}.

Elk shoot-object bevat een "redenering" veld: 3-5 concrete zinnen onderbouwd met echte CPL-cijfers, resultaten en CTR uit de data.

Return ALLEEN dit JSON:
{{
  "shoots": [
    {{
      "type": "safe",
      "naam_suggestie": "korte naam voor intern gebruik ≤40 tekens",
      "concept": "1-2 zinnen: wat het ad laat zien en waarom het werkt",
      "redenering": "3-5 zinnen onderbouwd met CPL, resultaten en CTR uit de data.",
      "hook_type": "{safe_hook}",
      "openingszin": "exacte eerste zin / headline van het ad (Nederlands)",
      "format": "{safe_format}",
      "aspect_ratio": "9:16 of 1:1 of 16:9",
      {_d_safe}
      {_tl_safe}
      "copy": "3-5 zinnen advertentietekst voor in de feed, gebaseerd op winnende ads",
      "headline": "max 8 woorden, pakkend en actiegericht",
      "key_message": "de kern van het ad in 1 zin",
      "cta": "call-to-action tekst",
      "hypothese": "wat je wilt bewijzen met deze shoot",
      {_m_safe}
    }},
    {{
      "type": "new_hook",
      "naam_suggestie": "...",
      "concept": "...",
      "redenering": "...",
      "hook_type": "{new_hook}",
      "openingszin": "...",
      "format": "{safe_format}",
      "aspect_ratio": "9:16",
      {_d_safe}
      {_tl_safe}
      "copy": "...",
      "headline": "...",
      "key_message": "...",
      "cta": "...",
      "hypothese": "...",
      {_m_new}
    }},
    {{
      "type": "format_test",
      "naam_suggestie": "...",
      "concept": "...",
      "redenering": "...",
      "hook_type": "{safe_hook}",
      "openingszin": "...",
      "format": "{test_format}",
      "aspect_ratio": "9:16",
      {_d_test}
      {_tl_test}
      "copy": "...",
      "headline": "...",
      "key_message": "...",
      "cta": "...",
      "hypothese": "...",
      {_m_test}
    }},
    {{
      "type": "winner_iterate",
      "naam_suggestie": "...",
      "concept": "...",
      "redenering": "...",
      "hook_type": "{safe_hook}",
      "openingszin": "...",
      "format": "{safe_format}",
      "aspect_ratio": "9:16",
      {_d_safe}
      {_tl_safe}
      "copy": "...",
      "headline": "...",
      "key_message": "...",
      "cta": "...",
      "hypothese": "...",
      {_m_iter}
    }},
    {{
      "type": "winner_scale",
      "naam_suggestie": "...",
      "concept": "...",
      "redenering": "...",
      "hook_type": "{winner_hook}",
      "openingszin": "...",
      "format": "{winner_format}",
      "aspect_ratio": "9:16",
      {_d_scale}
      {_tl_scale}
      "copy": "...",
      "headline": "...",
      "key_message": "...",
      "cta": "...",
      "hypothese": "...",
      {_m_scale}
    }}
  ]
}}"""

    result = call_json(prompt, system=_SHOOT_SYSTEM, max_tokens=5500)
    if "_error" in result or "shoots" not in result:
        logger.warning("Shoot brief AI call failed: %s", result.get("_error", "no 'shoots' key in response"))
        return _fallback_brief(safe_hook, safe_format, new_hook, test_format,
                               winner_hook, winner_format, hook_perf, fmt_perf,
                               summary, top_ad, client_name)
    shoots = result["shoots"]
    for shoot in shoots:
        if shoot.get("script"):
            shoot["script"] = _clean_script(shoot["script"])
        for field in ("openingszin", "copy", "headline"):
            if shoot.get(field):
                shoot[field] = _strip_em_dashes(shoot[field])
    return shoots


def _fallback_brief(
    safe_hook: str, safe_format: str,
    new_hook: str, test_format: str,
    winner_hook: str, winner_format: str,
    hook_perf: list[dict],
    fmt_perf: list[dict],
    summary: AnalysisSummary,
    top_ad: Ad | None,
    client_name: str = "",
) -> list[dict]:
    is_leads = summary.campaign_type != "purchases"
    cta = "Plan een gratis proefles" if is_leads else "Bestel nu"
    name = client_name or "ons"
    top_ad_name = f'"{top_ad.ad_name}"' if top_ad else "beste huidige ad"

    # Pick a third distinct hook for winner_iterate so its script differs from shoot 1
    all_hooks = [h for h in HOOK_TYPES if h not in (safe_hook, new_hook)]
    iterate_script_hook = all_hooks[0] if all_hooks else safe_hook

    def _perf(perf_list: list[dict], key: str, value: str) -> dict:
        return next((r for r in perf_list if r.get(key) == value), {})

    def _perf_str(p: dict) -> str:
        parts = []
        if p.get("results"):
            parts.append(f"{p['results']} resultaten")
        if p.get("cpl"):
            parts.append(f"CPL €{p['cpl']}")
        if p.get("avg_ctr"):
            parts.append(f"CTR {p['avg_ctr']}%")
        if p.get("ads"):
            parts.append(f"{p['ads']} ads")
        return ", ".join(parts) if parts else "nog geen data"

    sh_p  = _perf(hook_perf, "hook_type",   safe_hook)
    nh_p  = _perf(hook_perf, "hook_type",   new_hook)
    wh_p  = _perf(hook_perf, "hook_type",   winner_hook)
    sf_p  = _perf(fmt_perf,  "format_type", safe_format)
    tf_p  = _perf(fmt_perf,  "format_type", test_format)
    wf_p  = _perf(fmt_perf,  "format_type", winner_format)

    def _base(shoot_type: str, hook: str, fmt: str, duur: int,
              script_hook: str | None = None,
              hypothese: str | None = None,
              redenering: str | None = None) -> dict:
        effective_hook = script_hook or hook
        copy_text = _build_copy(effective_hook, cta, client_name)
        headline_text = _build_headline(effective_hook)
        is_static = fmt in _STATIC_FORMATS
        default_hyp = f"Test of de {hook}-hook beter converteert dan het huidige gemiddelde (CPL €{summary.avg_cost_per_result})."

        shoot: dict = {
            "type": shoot_type,
            "naam_suggestie": f"{hook.replace('_', '-').title()} {fmt.replace('_', '-').title()} V1",
            "concept": f"{_HOOK_NL.get(hook, hook)} gecombineerd met {_FORMAT_NL.get(fmt, fmt)}.",
            "redenering": redenering or "",
            "hook_type": hook,
            "openingszin": headline_text if is_static else (_build_script(effective_hook, cta, client_name)[0]["tekst"] if _build_script(effective_hook, cta, client_name) else _default_opening(effective_hook)),
            "format": fmt,
            "aspect_ratio": "1:1 of 4:5" if is_static else "9:16",
            "copy": copy_text,
            "headline": headline_text,
            "key_message": f"Persoonlijke begeleiding bij {name} — eindelijk iets dat vol te houden is.",
            "cta": cta,
            "hypothese": hypothese or default_hyp,
            "_fallback": True,
        }

        if is_static:
            shoot["talent"] = "n.v.t. — grafisch ontwerp"
            shoot["locatie"] = f"Stock beelden of eigen fotografie van {name}"
            shoot["visual_beschrijving"] = (
                f"Rustige achtergrond in huisstijlkleuren. "
                f"Grote headline in beeld: '{headline_text}'. "
                f"Subkop: eerste zin van de copy. "
                f"Onderin CTA-knop: '{cta}'. Logo rechtsboven. "
                f"Sfeer: warm, professioneel, uitnodigend."
            )
        else:
            script = _build_script(effective_hook, cta, client_name)
            shoot["duur_seconden"] = duur
            shoot["talent"] = "Lid/klant of trainer (authentiek, warm — geen acteur)"
            shoot["locatie"] = "In de studio of locatie van de klant — herkenbare omgeving"
            shoot["shots"] = [
                "Shot 1: close-up gezicht bij opening — kijker moet zich herkend voelen",
                "Shot 2: de situatie of het probleem visueel tonen (herkenbaar voor doelgroep)",
                f"Shot 3: de oplossing — wat {name} biedt, liefst in actie",
                "Shot 4: resultaat of bewijs — blije klant, zichtbaar verschil",
                "Shot 5: directe CTA — kijker aankijken, actie benoemen",
            ]
            shoot["script"] = script

        return shoot

    num_hooks_with_data = sum(1 for r in hook_perf if r.get("results") and r["results"] > 0)

    return [
        _base(
            "safe", safe_hook, safe_format, 30,
            redenering=(
                f"De {safe_hook}-hook presteert het best in het account ({_perf_str(sh_p)}). "
                f"Het {safe_format}-format levert de laagste CPL op ({_perf_str(sf_p)}). "
                f"Deze combinatie is de veiligste keuze: bewezen strategie, minimaal risico. "
                f"Een iteratie hierop verhoogt de kans op directe resultaten zonder onbekende variabelen."
            ),
        ),
        _base(
            "new_hook", new_hook, safe_format, 30,
            redenering=(
                f"De {new_hook}-hook is nog niet getest in dit account "
                f"({'terwijl ' + str(num_hooks_with_data) + ' andere hooks al data hebben' if num_hooks_with_data else 'en biedt een kans om het bereik te verbreden'}). "
                f"Door deze te testen in het bewezen {safe_format}-format ({_perf_str(sf_p)}) "
                f"isoleer je de hook als variabele — zo weet je precies of de hook werkt, "
                f"los van het format. Ongeteste hooks zijn kansen: de data kan niet bewijzen dat ze niet werken."
            ),
        ),
        _base(
            "format_test", safe_hook, test_format, 45, script_hook=new_hook,
            redenering=(
                f"De {safe_hook}-hook werkt bewezen ({_perf_str(sh_p)}). "
                f"Het {test_format}-format is nog niet ingezet "
                f"({'terwijl het potentieel heeft op basis van branchedata' if not tf_p.get('results') else _perf_str(tf_p)}). "
                f"Door dezelfde winnende hook in een nieuw format te plaatsen test je of er "
                f"nog hogere conversies mogelijk zijn. Duur 45s geeft ruimte voor de bredere formatopbouw."
            ),
            hypothese=f"Test of {safe_hook}-hook ook converteert in {test_format}-format. "
                      f"Als CPL onder €{summary.avg_cost_per_result} blijft, wordt dit het nieuwe standaard format.",
        ),
        _base(
            "winner_iterate", safe_hook, safe_format, 30,
            script_hook=iterate_script_hook,
            redenering=(
                f"Gebaseerd op {top_ad_name} — de best presterende ad in het account. "
                f"De combinatie {safe_hook} + {safe_format} heeft bewezen te werken ({_perf_str(sh_p)}). "
                f"Ad fatigue is een reëel risico: dezelfde creative verliest over tijd aan effectiviteit. "
                f"Vers creatief op exact dezelfde winnende formule beschermt de prestaties "
                f"zonder de bewezen strategie te veranderen."
            ),
            hypothese=f"Verse creative op {safe_hook} + {safe_format}. "
                      f"Bewijst dat de winnende strategie schaalbaar is met nieuwe inhoud zonder CPL-stijging.",
        ),
        _base(
            "winner_scale", winner_hook, winner_format, 30,
            redenering=(
                f"De combinatie {winner_hook} + {winner_format} is de #2 presterende combo in het account "
                f"({_perf_str(wh_p)} voor de hook, {_perf_str(wf_p)} voor het format). "
                f"Deze combinatie heeft potentie maar is minder intensief getest dan de winnaar. "
                f"Door er een dedicated shoot op te zetten geef je het de kans om te bewijzen "
                f"dat het op hogere budgetten even goed of beter converteert."
            ),
            hypothese=f"Schaal {winner_hook} + {winner_format} op. "
                      f"Test of CPL onder €{summary.avg_cost_per_result} blijft bij hogere investering.",
        ),
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
