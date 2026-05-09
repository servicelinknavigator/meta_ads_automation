import os
import re
import json
import anthropic
from models.campaign import Ad, AnalysisSummary

_HOOK_TYPES = ["recognition", "frustration", "proof", "curiosity", "confrontation", "promise"]
_FORMATS    = ["talking_head", "testimonial", "problem_solve", "story", "static", "ugc", "carousel"]


def _has_api() -> bool:
    k = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(k) and not k.startswith("sk-ant-your")


def _extract_json(text: str) -> str:
    text = re.sub(r"```(?:json)?", "", text).strip().strip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def _call(prompt: str, max_tokens: int = 800) -> dict:
    try:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system="Je bent een ervaren Meta Ads creative strategist. Antwoord ALLEEN met geldig JSON, geen uitleg eromheen.",
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(_extract_json(msg.content[0].text))
    except Exception as e:
        return {"_error": str(e)}


def decode_winner(ad: Ad, summary: AnalysisSummary) -> dict:
    if not _has_api():
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
Spend: €{ad.spend} | {perf} | CTR: {ad.ctr}% | Leads: {ad.results} | Frequentie: {ad.frequency}

Return ALLEEN dit JSON object (geen tekst eromheen):
{{
  "hook_type": "één van: {', '.join(_HOOK_TYPES)}",
  "hook_explanation": "waarom dit hook type past bij deze ad naam en prestatie (1-2 zinnen)",
  "promise": "de kernbelofte die deze ad waarschijnlijk maakt (1 beknopte zin)",
  "audience_pain": "het specifieke pijnpunt dat wordt aangepakt",
  "format": "één van: {', '.join(_FORMATS)}",
  "cta_intent": "gewenste actie + waarom laagdrempelig",
  "psychological_driver": "het diepere mechanisme: FOMO / zekerheid / identiteit / sociale bewijskracht / status / angst / aspiratie",
  "why_wins": "2-3 concrete redenen waarom dit wint t.o.v. de gemiddelde ad"
}}"""

    result = _call(prompt)
    if "_error" in result or not result.get("hook_type"):
        return _fallback_winner(ad, summary)
    return result


def decode_loser(ad: Ad, summary: AnalysisSummary) -> dict:
    if not _has_api():
        return _fallback_loser(ad, summary)

    is_leads = summary.campaign_type != "purchases"
    avg_metric = summary.avg_cost_per_result if is_leads else summary.avg_roas

    if is_leads:
        metric_str = f"CPL €{ad.cost_per_result}" if ad.results > 0 else "0 leads"
        bench      = f"account gem. CPL €{avg_metric}"
    else:
        metric_str = f"ROAS {ad.roas}" if ad.roas > 0 else "0 conversies"
        bench      = f"account gem. ROAS {avg_metric}"

    prompt = f"""Analyseer waarom deze Meta advertentie underperformt.

Ad naam: "{ad.ad_name}"
Campagne: "{ad.campaign_name}" | Ad Set: "{ad.ad_set_name}"
Spend: €{ad.spend} | {metric_str} | CTR: {ad.ctr}% | CPC: €{ad.cpc} | Frequentie: {ad.frequency}
{bench}

Return ALLEEN dit JSON:
{{
  "failure_reason": "één van: hook_generic / wrong_audience / format_mismatch / weak_cta / ad_fatigue / budget_insufficient / creative_mismatch",
  "failure_explanation": "specifieke uitleg waarom deze ad waarschijnlijk faalt (2-3 zinnen)",
  "fix_direction": "concrete fix-richting: wat aanpassen, welke angle of format proberen (2-3 zinnen)",
  "should_kill": true,
  "kill_reasoning": "waarom stoppen of doorgaan met testen"
}}"""

    result = _call(prompt)
    if "_error" in result or not result.get("failure_reason"):
        return _fallback_loser(ad, summary)
    return result


def _fallback_winner(ad: Ad, summary: AnalysisSummary) -> dict:
    hook = "proof" if "testimonial" in ad.ad_name.lower() or "review" in ad.ad_name.lower() else \
           "curiosity" if "?" in ad.ad_name else \
           "recognition" if any(w in ad.ad_name.lower() for w in ["jij", "jouw", "ken", "herken"]) else \
           "promise"
    return {
        "hook_type": hook,
        "hook_explanation": f"Afgeleid van naam en bovengemiddelde prestatie (CTR {ad.ctr}%, {ad.results} leads).",
        "promise": "Concrete resultaten met lage drempel",
        "audience_pain": "Onzekerheid over aanpak en resultaat",
        "format": "talking_head",
        "cta_intent": "Laagdrempelige kennismaking — gratis of vrijblijvend",
        "psychological_driver": "Sociale bewijskracht",
        "why_wins": f"Bovengemiddelde CTR ({ad.ctr}%) en {ad.results} leads bij €{ad.spend} spend suggereren sterke match met doelgroep en relevante boodschap.",
    }


def _fallback_loser(ad: Ad, summary: AnalysisSummary) -> dict:
    if ad.ctr < 0.5:
        reason = "hook_generic"
        expl   = f"CTR van {ad.ctr}% wijst op een zwakke hook — mensen stoppen niet met scrollen."
        fix    = "Test een frustration of proof hook. Ververs de openingszin volledig."
    elif ad.results == 0:
        reason = "weak_cta"
        expl   = f"Clicks maar geen leads bij €{ad.spend} spend. De landingspagina of CTA sluit niet aan."
        fix    = "Test een zachtere CTA (gratis adviesgesprek vs. nu kopen). Check ook de landingspagina."
    else:
        reason = "format_mismatch"
        expl   = f"Hoge CPL (€{ad.cost_per_result}) bij voldoende CTR. Format sluit niet aan bij de doelgroep."
        fix    = "Probeer een ander format: testimonial of problem-solve in plaats van het huidige."
    return {
        "failure_reason": reason,
        "failure_explanation": expl,
        "fix_direction": fix,
        "should_kill": ad.results == 0 and ad.spend > 50,
        "kill_reasoning": "Geen resultaten bij voldoende budget — stop en herstructureer met nieuw concept." if ad.results == 0 and ad.spend > 50
                          else "Budget te laag voor conclusie — geef €30-50 meer en meet opnieuw.",
    }
