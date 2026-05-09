from models.campaign import Ad
from core.ai_client import has_api, call_json
from core.hook_analyzer import detect_hook, detect_format, get_untested_hooks, HOOK_TYPES


def map_axes(decoded: dict, ad_name: str, all_ads: list[Ad] | None = None) -> dict:
    if not has_api():
        return _fallback_axes(decoded)

    untested = get_untested_hooks(all_ads) if all_ads else []
    untested_str = f"\nNog niet geteste hooks in account: {', '.join(untested)}" if untested else ""

    prompt = f"""Winnende Meta advertentie voor SLN Solutions: "{ad_name}"
Hook: {decoded.get('hook_type', '')} — {decoded.get('hook_explanation', '')}
Promise: {decoded.get('promise', '')}
Pain: {decoded.get('audience_pain', '')}
Format: {decoded.get('format', '')}
Psychological driver: {decoded.get('psychological_driver', '')}
Test hypothese: {decoded.get('test_hypothesis', '')}
{untested_str}

Genereer 6 creatieve test-assen voor variaties op deze winnende ad.
Verwerk de ongeteste hooks waar relevant als nieuwe angles.
Elk idee = 1 concrete, specifieke zin (geen vaagheden).

Return ALLEEN dit JSON (geen tekst eromheen):
{{
  "A_angle_variation": ["angle idee 1", "angle idee 2", "angle idee 3"],
  "B_pain_variation": ["ander pijnpunt 1", "ander pijnpunt 2", "ander pijnpunt 3"],
  "C_promise_variation": ["sterkere belofte 1", "andere formulering 2", "urgentere versie 3"],
  "D_format_variation": ["alternatief format 1", "alternatief format 2"],
  "E_opposite_angle": ["tegenovergestelde benadering 1", "contraire hook 2"],
  "F_new_segment": ["nieuw doelgroep segment 1", "ander segment 2"]
}}"""

    result = call_json(prompt, max_tokens=700)
    return result if result and "A_angle_variation" in result else _fallback_axes(decoded)


def _fallback_axes(decoded: dict) -> dict:
    pain = decoded.get("audience_pain", "onzekerheid")
    return {
        "A_angle_variation": [
            "Resultaat-first: begin met het eindresultaat dat de kijker wil",
            "Proces-gedreven: laat zien HOE het werkt, stap voor stap",
            "Community angle: anderen doen het al — doe jij mee?",
        ],
        "B_pain_variation": [
            f"Tijdgebrek als pijn: geen tijd voor {pain}",
            "Onzekerheid als pijn: weet je zeker dat je aanpak werkt?",
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
