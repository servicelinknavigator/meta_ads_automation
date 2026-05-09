from models.campaign import Ad, AnalysisSummary
from core.ai_client import has_api, call_json, _SLN_SYSTEM_JSON
from core.hook_analyzer import HOOK_TYPES, FORMAT_TYPES

_CREATIVE_SYSTEM = (
    _SLN_SYSTEM_JSON + " "
    "Je schrijft scherpe, specifieke Nederlandstalige ad copy voor Meta. "
    "Hooks zijn concreet en prikkelend — geen vage algemeenheden. "
    "primary_text bevat emoji waar passend en is 3-4 zinnen."
)


def generate_testkit(ad_name: str, decoded: dict, axes: dict) -> dict:
    if not has_api():
        return {"_no_api": True}

    hook_type = decoded.get("hook_type", "")
    hook_expl = decoded.get("hook_explanation", "")
    promise   = decoded.get("promise", "")
    pain      = decoded.get("audience_pain", "")
    fmt       = decoded.get("format", "")
    driver    = decoded.get("psychological_driver", "")
    why_wins  = decoded.get("why_wins", "")
    test_hyp  = decoded.get("test_hypothesis", "")

    axes_text = "\n".join([
        f"A – Angle variaties: {', '.join(axes.get('A_angle_variation', []))}",
        f"B – Pain variaties: {', '.join(axes.get('B_pain_variation', []))}",
        f"C – Promise variaties: {', '.join(axes.get('C_promise_variation', []))}",
        f"D – Format variaties: {', '.join(axes.get('D_format_variation', []))}",
        f"E – Opposite angles: {', '.join(axes.get('E_opposite_angle', []))}",
        f"F – Nieuwe segmenten: {', '.join(axes.get('F_new_segment', []))}",
    ])

    prompt = f"""Genereer een complete test kit voor SLN Solutions op basis van deze winnende Meta advertentie.

WINNAAR: "{ad_name}"
- Hook type: {hook_type} — {hook_expl}
- Promise: {promise}
- Pain: {pain}
- Format: {fmt}
- Driver: {driver}
- Waarom wint: {why_wins}
- Te testen hypothese: {test_hyp}

CREATIEVE ASSEN:
{axes_text}

REGELS:
- Alles in het Nederlands
- Hooks zijn SPECIFIEK en prikkelend (geen "Ben jij ook..." of "Wil jij ook...")
- primary_text = 3-4 zinnen volledige advertentietekst met emoji waar passend
- safe_variants = kleine variaties op bewezen concept (andere formulering, zelfde hook)
- fresh_variants = andere hook type of format, zelfde psychologie
- risky_variant = tegenovergesteld of onverwacht — kan floppen maar ook uitblinken
- Elke variant heeft een shoot_spec met praktische productie-instructies

Beschikbare hook types: {', '.join(HOOK_TYPES)}
Beschikbare formats: {', '.join(FORMAT_TYPES)}

Return ALLEEN dit JSON:
{{
  "safe_variants": [
    {{
      "hook": "exacte openingszin",
      "primary_text": "volledige ad tekst (3-4 zinnen)",
      "headline": "headline ≤40 tekens",
      "why_this_works": "1 zin",
      "shoot_spec": {{"format": "format type", "duur_seconden": 30, "aspect_ratio": "9:16", "talent": "wie", "locatie": "waar"}}
    }},
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "...", "shoot_spec": {{"format": "...", "duur_seconden": 30, "aspect_ratio": "9:16", "talent": "...", "locatie": "..."}}}},
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "...", "shoot_spec": {{"format": "...", "duur_seconden": 30, "aspect_ratio": "9:16", "talent": "...", "locatie": "..."}}}}
  ],
  "fresh_variants": [
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "...", "shoot_spec": {{"format": "...", "duur_seconden": 45, "aspect_ratio": "9:16", "talent": "...", "locatie": "..."}}}},
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "...", "shoot_spec": {{"format": "...", "duur_seconden": 30, "aspect_ratio": "9:16", "talent": "...", "locatie": "..."}}}},
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "...", "shoot_spec": {{"format": "...", "duur_seconden": 30, "aspect_ratio": "9:16", "talent": "...", "locatie": "..."}}}}
  ],
  "risky_variant": {{
    "hook": "...",
    "primary_text": "...",
    "headline": "...",
    "why_this_works": "...",
    "shoot_spec": {{"format": "...", "duur_seconden": 30, "aspect_ratio": "9:16", "talent": "...", "locatie": "..."}}
  }},
  "testimonial_brief": {{
    "angle": "welk verhaal de klant moet vertellen (1-2 zinnen)",
    "questions": ["vraag 1", "vraag 2", "vraag 3"],
    "desired_outcome": "wat de kijker moet voelen/denken na het zien"
  }},
  "static_concept": {{
    "visual": "beschrijving van het beeld of ontwerp",
    "headline": "grote tekst op de static ≤35 tekens",
    "subtext": "ondersteunende tekst",
    "cta": "call-to-action knoptekst"
  }},
  "shootlist": [
    "Shot 1: beschrijving",
    "Shot 2: beschrijving",
    "Shot 3: beschrijving",
    "Shot 4: beschrijving",
    "Shot 5: beschrijving",
    "Shot 6: beschrijving"
  ],
  "test_priority": {{
    "first_3": ["naam/omschrijving van variant 1", "variant 2", "variant 3"],
    "reasoning": "waarom deze 3 eerst — wat je wilt leren en welke hypothese je test"
  }}
}}"""

    result = call_json(prompt, system=_CREATIVE_SYSTEM, max_tokens=2800)
    if "_error" in result:
        return {"_no_api": True}
    return result
