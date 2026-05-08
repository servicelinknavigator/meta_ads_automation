import os
import anthropic
from models.campaign import AnalysisSummary


def _build_prompt(summary: AnalysisSummary, all_ads=None) -> str:
    is_leads = summary.campaign_type != "purchases"
    result_label = summary.result_label
    main_metric = f"Gemiddeld CPL: €{summary.avg_cost_per_result}" if is_leads else f"Gemiddeld ROAS: {summary.avg_roas}"
    top_label = "laagste CPL" if is_leads else "hoogste ROAS"
    worst_label = "hoogste CPL" if is_leads else "laagste ROAS"

    ad_lines = []
    if all_ads:
        for a in sorted(all_ads, key=lambda x: x.spend, reverse=True)[:15]:
            metric_val = f"CPL €{a.cost_per_result}" if is_leads else f"ROAS {a.roas}"
            ad_lines.append(
                f"  - [{a.campaign_name} > {a.ad_set_name}] '{a.ad_name}': "
                f"spend €{a.spend}, {metric_val}, CTR {a.ctr}%, "
                f"{result_label.lower()} {a.results}, CPC €{a.cpc}"
            )
    ads_text = "\n".join(ad_lines) if ad_lines else "  Geen ad data beschikbaar"

    return f"""Je bent een Meta Ads specialist voor een leadgeneratie bureau. Analyseer de prestaties PER ADVERTENTIE en geef concrete aanbevelingen in het Nederlands.

Campagnetype: {summary.campaign_type} | Doel: {result_label} genereren

## Account Overzicht
- Totaal budget: €{summary.total_spend}
- Totaal {result_label.lower()}: {summary.total_results}
- {main_metric}
- Gemiddeld CTR: {summary.avg_ctr}% | CPC: €{summary.avg_cpc} | CPM: €{summary.avg_cpm}
- Beste advertentie ({top_label}): {summary.top_ad} ({summary.top_ad_set})
- Advertentie met aandacht ({worst_label}): {summary.worst_ad} ({summary.worst_ad_set})

## Advertenties (gesorteerd op spend)
{ads_text}

Analyseer op AD-niveau. Geef je analyse in dit formaat:

### Sterke Advertenties
[Welke ads presteren goed en waarom, met concrete cijfers]

### Underperformers
[Welke ads presteren slecht, met specifieke problemen]

### Aanbevelingen
[3-4 concrete acties: welke ads stoppen/schalen/aanpassen en waarom]

### Budget Advies
[Budgetverdeling op basis van CPL per advertentie]

Wees specifiek, noem advertentienamen, gebruik de data."""


def generate_insights(summary: AnalysisSummary, all_ads=None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        return _fallback_insights(summary)

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(summary, all_ads)

    try:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system="Je bent een ervaren Meta Ads specialist die adverteerders helpt hun campagnes te optimaliseren.",
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception:
        return _fallback_insights(summary, all_ads)


def _fallback_insights(summary: AnalysisSummary, all_ads=None) -> str:
    is_leads = summary.campaign_type != "purchases"
    lines = ["### Automatische Analyse (zonder AI)\n"]

    if is_leads:
        cpl = summary.avg_cost_per_result
        if cpl > 0 and cpl < 30:
            lines.append(f"**Sterke CPL:** Gemiddelde CPL van €{cpl} ligt onder €30 — goede prestatie.")
        elif cpl < 50:
            lines.append(f"**Gemiddelde CPL:** Gemiddelde CPL van €{cpl} — optimalisatie mogelijk.")
        elif cpl > 0:
            lines.append(f"**Hoge CPL:** Gemiddelde CPL van €{cpl} overschrijdt €50 — heroverweeg targeting of creatief.")
    else:
        if summary.avg_roas >= 3.0:
            lines.append(f"**Sterke ROAS:** Gemiddelde ROAS van {summary.avg_roas} is uitstekend (doel: >2.0).")
        elif summary.avg_roas >= 1.5:
            lines.append(f"**Matige ROAS:** Gemiddelde ROAS van {summary.avg_roas} heeft optimalisatie nodig.")
        else:
            lines.append(f"**Lage ROAS:** Gemiddelde ROAS van {summary.avg_roas} is zorgwekkend.")

    if summary.top_ad:
        lines.append(f"\n**Beste advertentie:** '{summary.top_ad}' ({summary.top_ad_set}) — overweeg budget te verhogen.")

    if summary.worst_ad:
        lines.append(f"\n**Aandacht vereist:** '{summary.worst_ad}' ({summary.worst_ad_set}) — analyseer targeting en creatief.")

    if summary.avg_ctr < 1.0:
        lines.append("\n**Lage CTR:** Overweeg creatief te vernieuwen of doelgroep te verfijnen.")
    elif summary.avg_ctr > 2.5:
        lines.append("\n**Goede CTR:** De advertenties spreken de doelgroep aan.")

    lines.append(f"\n> Stel je ANTHROPIC_API_KEY in voor gedetailleerde AI-aanbevelingen.")
    return "\n".join(lines)
