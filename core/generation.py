from models.campaign import AnalysisSummary
from core.ai_client import has_api, call_text, _SLN_SYSTEM_TEXT


def _build_prompt(summary: AnalysisSummary, all_ads=None) -> str:
    is_leads = summary.campaign_type != "purchases"
    result_label = summary.result_label
    main_metric = f"Gem. CPL: €{summary.avg_cost_per_result}" if is_leads else f"Gem. ROAS: {summary.avg_roas}"
    top_label = "laagste CPL" if is_leads else "hoogste ROAS"
    worst_label = "hoogste CPL" if is_leads else "laagste ROAS"

    ad_lines = []
    if all_ads:
        for a in sorted(all_ads, key=lambda x: x.spend, reverse=True)[:15]:
            metric_val = f"CPL €{a.cost_per_result}" if is_leads else f"ROAS {a.roas}"
            status = ""
            if a.results == 0 and a.spend > 50:
                status = " ⚠ KILL"
            elif is_leads and a.cost_per_result > 0 and a.cost_per_result < summary.avg_cost_per_result * 0.7:
                status = " ✓ SCHALEN"
            elif not is_leads and a.roas > summary.avg_roas * 1.3:
                status = " ✓ SCHALEN"
            ad_lines.append(
                f"  - [{a.campaign_name} > {a.ad_set_name}] '{a.ad_name}': "
                f"spend €{a.spend}, {metric_val}, CTR {a.ctr}%, "
                f"{result_label.lower()} {a.results}, freq {a.frequency:.1f}{status}"
            )
    ads_text = "\n".join(ad_lines) if ad_lines else "  Geen ad data beschikbaar"

    return f"""Je bent de Meta Ads specialist van SLN Solutions — een bureau dat uitsluitend met Meta advertenties werkt en hook testing doet via video shoots.

Analyseer de prestaties PER ADVERTENTIE en geef beslissingen: welke ads STOPPEN, SCHALEN of TESTEN met nieuwe hooks.

Campagnetype: {summary.campaign_type} | Doel: {result_label} genereren
Accounts: {summary.num_campaigns} campagnes | {summary.num_ad_sets} ad sets | {summary.num_ads} ads

## Account Overzicht
- Totaal budget: €{summary.total_spend}
- Totaal {result_label.lower()}: {summary.total_results}
- {main_metric}
- Gem. CTR: {summary.avg_ctr}% | CPC: €{summary.avg_cpc} | CPM: €{summary.avg_cpm} | Freq: {summary.avg_frequency}
- Beste ad ({top_label}): {summary.top_ad} ({summary.top_ad_set})
- Aandacht vereist ({worst_label}): {summary.worst_ad} ({summary.worst_ad_set})

## Advertenties (gesorteerd op spend — ⚠ KILL = stoppen, ✓ SCHALEN = budget verhogen)
{ads_text}

Geef je analyse in dit exact formaat:

### Sterke Advertenties — SCHALEN
[Welke ads presteren goed, waarom, en hoeveel je het budget kunt verhogen]

### Underperformers — STOPPEN of AANPASSEN
[Welke ads stoppen en waarom. Welke een nieuwe hook of format nodig hebben]

### Hook & Creative Aanbevelingen
[Welke hook types ontbreken, welke formats getest moeten worden, 2-3 concrete shoot ideeën]

### Budget Reallocatie
[Concreet: van welke ad budget afhalen → naar welke ad/campagne verschuiven, met bedragen]

Wees specifiek, noem advertentienamen, gebruik de data. Max 500 woorden."""


def generate_insights(summary: AnalysisSummary, all_ads=None) -> str:
    if not has_api():
        return _fallback_insights(summary)

    prompt = _build_prompt(summary, all_ads)
    return call_text(prompt, system=_SLN_SYSTEM_TEXT, max_tokens=1200)


def _fallback_insights(summary: AnalysisSummary) -> str:
    is_leads = summary.campaign_type != "purchases"
    lines = ["### Automatische Analyse (zonder AI)\n"]

    if is_leads:
        cpl = summary.avg_cost_per_result
        if cpl > 0 and cpl < 30:
            lines.append(f"**Sterke CPL:** Gem. CPL van €{cpl} ligt onder €30 — goede prestatie voor leadcampagnes.")
        elif cpl < 50:
            lines.append(f"**Gemiddelde CPL:** Gem. CPL van €{cpl} — optimalisatie van hook of doelgroep kan helpen.")
        elif cpl > 0:
            lines.append(f"**Hoge CPL:** Gem. CPL van €{cpl} overschrijdt €50 — heroverweeg hook, format of targeting.")
    else:
        if summary.avg_roas >= 3.0:
            lines.append(f"**Sterke ROAS:** Gem. ROAS van {summary.avg_roas} is uitstekend (doel: >2.0).")
        elif summary.avg_roas >= 1.5:
            lines.append(f"**Matige ROAS:** Gem. ROAS van {summary.avg_roas} — creatief en doelgroep testen.")
        else:
            lines.append(f"**Lage ROAS:** Gem. ROAS van {summary.avg_roas} is zorgwekkend — stop underperformers.")

    if summary.top_ad:
        lines.append(f"\n**Schalen:** '{summary.top_ad}' ({summary.top_ad_set}) — verhoog budget 20-30% per dag.")

    if summary.worst_ad:
        lines.append(f"\n**Stoppen:** '{summary.worst_ad}' ({summary.worst_ad_set}) — analyseer hook en format, maak V2.")

    if summary.avg_ctr < 1.0:
        lines.append("\n**Lage CTR:** Hooks werken niet goed genoeg — test curiosity of confrontation hooks.")
    elif summary.avg_ctr > 2.5:
        lines.append("\n**Goede CTR:** Hooks spreken aan — optimaliseer nu de landingspagina of CTA.")

    if summary.avg_frequency > 3.0:
        lines.append(f"\n**Ad Fatigue:** Gem. frequentie {summary.avg_frequency} is hoog — ververs creatief.")

    lines.append(f"\n> Stel je ANTHROPIC_API_KEY in voor volledige AI-aanbevelingen met kill/scale/test beslissingen.")
    return "\n".join(lines)
