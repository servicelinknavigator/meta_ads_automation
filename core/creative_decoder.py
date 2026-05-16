from models.campaign import Ad, AnalysisSummary
from core.ai_client import has_api, call_json
from core.hook_analyzer import detect_hook, detect_format, HOOK_TYPES, FORMAT_TYPES

_HOOK_TYPES = HOOK_TYPES
_FORMATS    = FORMAT_TYPES


def decode_winner(ad: Ad, summary: AnalysisSummary) -> dict:
    if not has_api():
        return _fallback_winner(ad, summary)

    is_leads = summary.campaign_type != "purchases"
    avg_metric = summary.avg_cost_per_result if is_leads else summary.avg_roas
    ad_metric  = ad.cost_per_result if is_leads else ad.roas

    if is_leads and avg_metric > 0 and ad_metric > 0:
        delta = round((avg_metric - ad_metric) / avg_metric * 100, 1)
        perf  = f"CPL €{ad_metric} (account gem. €{avg_metric} — {delta}% beter)"
    elif not is_leads and avg_metric > 0:
        delta = round((ad_metric - avg_metric) / avg_metric * 100, 1)
        perf  = f"ROAS {ad_metric} (account gem. {avg_metric} — {delta}% beter)"
    else:
        perf = "bovengemiddelde prestatie"

    prompt = f"""Analyseer deze winnende Meta advertentie. Leid alles af uit de naam + prestaties.

Ad naam: "{ad.ad_name}"
Campagne: "{ad.campaign_name}" | Ad Set: "{ad.ad_set_name}"
Spend: €{ad.spend} | {perf} | CTR: {ad.ctr}% | Resultaten: {ad.results} | Frequentie: {ad.frequency}

Return ALLEEN dit JSON object (geen tekst eromheen):
{{
  "hook_type": "één van: {', '.join(_HOOK_TYPES)}",
  "hook_explanation": "waarom dit hook type past bij deze ad naam en prestatie (1-2 zinnen)",
  "promise": "de kernbelofte die deze ad waarschijnlijk maakt (1 beknopte zin)",
  "audience_pain": "het specifieke pijnpunt dat wordt aangepakt",
  "format": "één van: {', '.join(_FORMATS)}",
  "cta_intent": "gewenste actie + waarom laagdrempelig",
  "psychological_driver": "het diepere mechanisme: FOMO / zekerheid / identiteit / sociale bewijskracht / status / angst / aspiratie",
  "why_wins": "2-3 concrete redenen waarom dit wint t.o.v. de gemiddelde ad",
  "test_hypothesis": "wat kun je testen om dit resultaat te verbeteren of bevestigen (1 concrete hypothese)"
}}"""

    result = call_json(prompt, max_tokens=900)
    if "_error" in result or not result.get("hook_type"):
        return _fallback_winner(ad, summary)
    result["_fallback"] = False
    return result


def decode_loser(ad: Ad, summary: AnalysisSummary) -> dict:
    if not has_api():
        return _fallback_loser(ad, summary)

    is_leads = summary.campaign_type != "purchases"
    avg_metric = summary.avg_cost_per_result if is_leads else summary.avg_roas

    if is_leads:
        metric_str = f"CPL €{ad.cost_per_result}" if ad.results > 0 else "0 resultaten"
        bench      = f"account gem. CPL €{avg_metric}"
    else:
        metric_str = f"ROAS {ad.roas}" if ad.roas > 0 else "0 conversies"
        bench      = f"account gem. ROAS {avg_metric}"

    prompt = f"""Analyseer waarom deze Meta advertentie underperformt bij SLN Solutions.

Ad naam: "{ad.ad_name}"
Campagne: "{ad.campaign_name}" | Ad Set: "{ad.ad_set_name}"
Spend: €{ad.spend} | {metric_str} | CTR: {ad.ctr}% | CPC: €{ad.cpc} | Frequentie: {ad.frequency}
{bench}

Return ALLEEN dit JSON:
{{
  "failure_reason": "één van: hook_generic / wrong_audience / format_mismatch / weak_cta / ad_fatigue / budget_insufficient / creative_mismatch",
  "failure_explanation": "specifieke uitleg waarom deze ad waarschijnlijk faalt (2-3 zinnen)",
  "fix_direction": "concrete fix-richting: welke hook angle of format proberen (2-3 zinnen)",
  "should_kill": true,
  "kill_reasoning": "waarom stoppen of doorgaan met testen",
  "test_hypothesis": "één specifieke test die de oorzaak van het falen zou bewijzen of ontkrachten"
}}"""

    result = call_json(prompt, max_tokens=700)
    if "_error" in result or not result.get("failure_reason"):
        return _fallback_loser(ad, summary)
    result["_fallback"] = False
    return result


def _fallback_winner(ad: Ad, summary: AnalysisSummary) -> dict:
    hook = detect_hook(ad.ad_name)
    if hook == "unknown":
        hook = "proof" if any(w in ad.ad_name.lower() for w in ["testimonial", "review", "case"]) else "promise"
    return {
        "hook_type": hook,
        "hook_explanation": f"Afgeleid van naam en bovengemiddelde prestatie (CTR {ad.ctr}%, {ad.results} resultaten).",
        "promise": "Concrete resultaten met lage drempel",
        "audience_pain": "Onzekerheid over aanpak en resultaat",
        "format": detect_format(ad.ad_name),
        "cta_intent": "Laagdrempelige kennismaking — gratis of vrijblijvend",
        "psychological_driver": "Sociale bewijskracht",
        "why_wins": f"Bovengemiddelde CTR ({ad.ctr}%) en {ad.results} resultaten bij €{ad.spend} spend suggereren sterke match met doelgroep.",
        "test_hypothesis": "Test een V2 met dezelfde hook maar een sterkere openingszin om te zien of de CTR verder stijgt.",
        "_fallback": True,
    }


def _fallback_loser(ad: Ad, summary: AnalysisSummary) -> dict:
    if ad.ctr < 0.5:
        reason = "hook_generic"
        expl   = f"CTR van {ad.ctr}% wijst op een zwakke hook — mensen stoppen niet met scrollen."
        fix    = "Test een frustration of proof hook. Ververs de openingszin volledig."
        hyp    = "Maak een V2 met een curiosity of confrontation hook en meet of CTR boven 1.5% komt."
    elif ad.results == 0:
        reason = "weak_cta"
        expl   = f"Clicks maar geen resultaten bij €{ad.spend} spend. De CTA of landingspagina sluit niet aan."
        fix    = "Test een zachtere CTA (gratis adviesgesprek vs. nu kopen). Check ook de landingspagina."
        hyp    = "Test de ad met een nieuwe landingspagina of een directe WhatsApp CTA om de drempel te verlagen."
    else:
        reason = "format_mismatch"
        expl   = f"Hoge CPL (€{ad.cost_per_result}) bij voldoende CTR. Format sluit niet aan bij de doelgroep."
        fix    = "Probeer een ander format: testimonial of problem-solve in plaats van het huidige."
        hyp    = "Test een testimonial variant van deze hook — bewijs vermindert twijfel bij de conversiestap."
    return {
        "failure_reason": reason,
        "failure_explanation": expl,
        "fix_direction": fix,
        "should_kill": ad.results == 0 and ad.spend > 50,
        "kill_reasoning": (
            "Geen resultaten bij voldoende budget — stop en herstructureer met nieuw concept."
            if ad.results == 0 and ad.spend > 50
            else "Budget te laag voor conclusie — breng eerst boven €50 voor betrouwbare data."
        ),
        "test_hypothesis": hyp,
        "_fallback": True,
    }
