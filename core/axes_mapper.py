import os
import json
import anthropic


def _has_api() -> bool:
    k = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(k) and not k.startswith("sk-ant-your")


def _call(prompt: str) -> dict:
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            system="Je bent een Meta Ads creative director. Antwoord ALLEEN met geldig JSON, geen uitleg.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else parts[0]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return {}


def map_axes(decoded: dict, ad_name: str) -> dict:
    if not _has_api():
        return _fallback_axes(decoded)

    prompt = f"""Winner ad: "{ad_name}"
Hook: {decoded.get('hook_type', '')} — {decoded.get('hook_explanation', '')}
Promise: {decoded.get('promise', '')}
Pain: {decoded.get('audience_pain', '')}
Format: {decoded.get('format', '')}
Psychological driver: {decoded.get('psychological_driver', '')}

Genereer 6 creatieve test-assen voor variaties op deze winnende ad. Elk idee = 1 concrete zin.

Return ALLEEN dit JSON (geen tekst eromheen):
{{
  "A_angle_variation": ["angle idee 1", "angle idee 2", "angle idee 3"],
  "B_pain_variation": ["ander pijnpunt 1", "ander pijnpunt 2", "ander pijnpunt 3"],
  "C_promise_variation": ["sterkere belofte 1", "andere formulering 2", "urgentere versie 3"],
  "D_format_variation": ["alternatief format 1", "alternatief format 2"],
  "E_opposite_angle": ["tegenovergestelde benadering 1", "contraire hook 2"],
  "F_new_segment": ["nieuw doelgroep segment 1", "ander segment 2"]
}}"""

    result = _call(prompt)
    return result if result and "A_angle_variation" in result else _fallback_axes(decoded)


def _fallback_axes(decoded: dict) -> dict:
    hook = decoded.get("hook_type", "proof")
    pain = decoded.get("audience_pain", "onzekerheid")
    return {
        "A_angle_variation": [
            "Resultaat-first: begin met het eindresultaat dat de kijker wil",
            "Proces-gedreven: laat zien HOE het werkt, stap voor stap",
            "Community angle: anderen doen het al — doe jij mee?",
        ],
        "B_pain_variation": [
            f"Tijdgebrek als pijn: geen tijd voor {pain}",
            f"Onzekerheid als pijn: weet je zeker dat je aanpak werkt?",
            "Gemiste kansen als pijn: wat verlies je door te wachten?",
        ],
        "C_promise_variation": [
            "Sneller resultaat: binnen X weken/dagen",
            "Eenvoudiger aanpak: zonder gedoe of complexiteit",
            "Gegarandeerd resultaat: of je geld terug",
        ],
        "D_format_variation": [
            "Testimonial video: klant vertelt zijn/haar verhaal",
            "Before/after carousel: transformatie in beeld",
        ],
        "E_opposite_angle": [
            "Negatieve hook: wat als je niets doet? Wat verlies je?",
            "Anti-verkoop: 'Dit is niet voor iedereen'",
        ],
        "F_new_segment": [
            "Starters 25-35: eerste keer, weten niet waar beginnen",
            "Retargeting warme bezoekers: hebben al gekeken maar niet gehandeld",
        ],
    }
