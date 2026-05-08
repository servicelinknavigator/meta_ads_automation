import os
import json
import anthropic
from models.campaign import AnalysisSummary


def generate_copy(
    summary: AnalysisSummary,
    product: str,
    doelgroep: str,
    tone: str,
    variaties: int = 3,
) -> list[dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-ant-your"):
        return _fallback_copy(product, variaties)

    top = next(
        (c for c in summary.campaigns if c.campaign_name == summary.top_campaign),
        summary.campaigns[0] if summary.campaigns else None,
    )

    context = ""
    if top:
        context = (
            f"\nBeste campagne ter referentie: '{top.campaign_name}' "
            f"(ROAS {top.roas}, CTR {top.ctr}%, {top.results} conversies)"
        )

    prompt = f"""Je bent een ervaren Meta Ads copywriter. Schrijf {variaties} advertentievariaties in het Nederlands.

Product/dienst: {product}
Doelgroep: {doelgroep}
Tone of voice: {tone}{context}
Totaal campagne ROAS: {summary.avg_roas} | CTR: {summary.avg_ctr}%

Regels:
- Headline: max 40 tekens, pakkend en direct
- Primary text: max 150 tekens, focus op voordeel voor de doelgroep
- CTA: kies uit Shop Nu / Meer info / Ontdek nu / Bestel vandaag / Gratis proberen

Geef ALLEEN geldige JSON terug, geen uitleg, geen markdown:
[
  {{"headline": "...", "primary_text": "...", "cta": "..."}},
  ...
]"""

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            system="Je bent een Meta Ads copywriter. Je geeft altijd alleen JSON terug zonder uitleg.",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        variations = json.loads(raw)
        return variations[:variaties]
    except Exception:
        return _fallback_copy(product, variaties)


def _fallback_copy(product: str, variaties: int) -> list[dict]:
    templates = [
        {
            "headline": f"Ontdek {product} vandaag",
            "primary_text": f"Benieuwd naar {product}? Bekijk ons aanbod en profiteer van onze beste deals. Beperkte tijd beschikbaar.",
            "cta": "Shop Nu",
        },
        {
            "headline": f"{product} — Mis het niet",
            "primary_text": f"Duizenden tevreden klanten gingen je voor. Ontdek waarom {product} zo populair is en bestel vandaag nog.",
            "cta": "Ontdek nu",
        },
        {
            "headline": f"Jouw {product} wacht",
            "primary_text": f"Hoogste kwaliteit, scherpe prijs. {product} voor mensen die het beste willen. Snel geleverd, niet goed = geld terug.",
            "cta": "Bestel vandaag",
        },
    ]
    return templates[:variaties]
