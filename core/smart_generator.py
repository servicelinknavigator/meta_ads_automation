import os
import re
import json
import anthropic


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


def _call(prompt: str, max_tokens: int = 2500) -> dict:
    try:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=(
                "Je bent een top Meta Ads creative director. "
                "Schrijf originele, specifieke Nederlandstalige ad copy. "
                "Hooks moeten concreet zijn — geen vage algemeenheden. "
                "Antwoord ALLEEN met geldig JSON, geen uitleg eromheen."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(_extract_json(msg.content[0].text))
    except Exception as e:
        return {"_error": str(e)}


def generate_testkit(ad_name: str, decoded: dict, axes: dict) -> dict:
    if not _has_api():
        return {"_no_api": True}

    axes_text = "\n".join([
        f"A – Angle variaties: {', '.join(axes.get('A_angle_variation', []))}",
        f"B – Pain variaties: {', '.join(axes.get('B_pain_variation', []))}",
        f"C – Promise variaties: {', '.join(axes.get('C_promise_variation', []))}",
        f"D – Format variaties: {', '.join(axes.get('D_format_variation', []))}",
        f"E – Opposite angles: {', '.join(axes.get('E_opposite_angle', []))}",
        f"F – Nieuwe segmenten: {', '.join(axes.get('F_new_segment', []))}",
    ])

    prompt = f"""Genereer een complete 11-item test kit voor deze winnende Meta advertentie.

WINNAAR: "{ad_name}"
DECODE:
- Hook: {decoded.get('hook_type')} — {decoded.get('hook_explanation', '')}
- Promise: {decoded.get('promise', '')}
- Pain: {decoded.get('audience_pain', '')}
- Format: {decoded.get('format', '')}
- Driver: {decoded.get('psychological_driver', '')}
- Waarom wint: {decoded.get('why_wins', '')}

CREATIEVE ASSEN:
{axes_text}

REGELS:
- Alles in het Nederlands
- Hooks zijn SPECIFIEK (geen "Ben jij ook..." of "Wil jij ook...")
- primary_text = 3-4 zinnen volledige advertentietekst met emoji waar passend
- safe_variants = bewezen angle, kleine variaties op het winnende concept
- fresh_variants = zelfde psychologie, ander format/invalshoek
- risky_variant = tegenovergesteld of onverwacht — kan floppen of winnen

Return ALLEEN dit JSON:
{{
  "safe_variants": [
    {{"hook": "openingszin", "primary_text": "volledige ad tekst", "headline": "korte headline ≤40 tekens", "why_this_works": "1 zin"}},
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "..."}},
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "..."}}
  ],
  "fresh_variants": [
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "..."}},
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "..."}},
    {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "..."}}
  ],
  "risky_variant": {{"hook": "...", "primary_text": "...", "headline": "...", "why_this_works": "..."}},
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
    "reasoning": "waarom deze 3 eerst — wat je wilt leren"
  }}
}}"""

    result = _call(prompt, max_tokens=2500)
    if "_error" in result:
        return {"_no_api": True}
    return result
