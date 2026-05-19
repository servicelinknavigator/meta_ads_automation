import os
import re
import json
import anthropic

_SLN_SYSTEM_JSON = (
    "Je bent een ervaren Meta Ads creative strategist bij SLN Solutions. "
    "SLN doet uitsluitend Meta advertenties voor Nederlandse klanten, "
    "met focus op hook testing via video shoots. "
    "Antwoord ALLEEN met geldig JSON, geen uitleg eromheen."
)

_SLN_SYSTEM_TEXT = (
    "Je bent een ervaren Meta Ads specialist bij SLN Solutions. "
    "SLN doet uitsluitend Meta advertenties voor Nederlandse klanten, "
    "met focus op hook testing via video shoots. "
    "Schrijf altijd in het Nederlands. Wees concreet en data-gedreven."
)


def has_api() -> bool:
    k = os.getenv("ANTHROPIC_API_KEY", "")
    return bool(k) and not k.startswith("sk-ant-your")


def _extract_json(text: str) -> str:
    text = re.sub(r"```(?:json)?", "", text).strip().strip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def call_json(prompt: str, system: str = _SLN_SYSTEM_JSON, max_tokens: int = 800) -> dict:
    try:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(_extract_json(msg.content[0].text))
    except Exception as e:
        return {"_error": str(e)}


def suggest_ad_tags(ads_info: list[dict]) -> dict[str, dict]:
    """
    Batch-suggest hook and format for unknown ad names.
    ads_info: [{"ad_name": str, "campaign_name": str, "spend": float, "results": int}]
    Returns: {ad_name: {"hook": str, "format": str}}
    """
    if not ads_info or not has_api():
        return {}

    lines = "\n".join(
        f"{i + 1}. \"{a['ad_name']}\" | campagne: {a['campaign_name']} | "
        f"spend: €{a['spend']:.0f} | resultaten: {a['results']}"
        for i, a in enumerate(ads_info)
    )

    hook_opts = "proof, promise, frustration, recognition, curiosity, social_proof, problem_solve, educational, confrontation, urgency"
    fmt_opts  = "static, reels, ugc, testimonial, carousel, animation, before_after, product_demo"

    prompt = f"""Categoriseer deze Meta advertenties op basis van naam, campagne en prestaties.
Kies voor elke advertentie het meest waarschijnlijke hook type en format type.

Hook opties: {hook_opts}
Format opties: {fmt_opts}

Advertenties:
{lines}

Return uitsluitend dit JSON object (sleutels zijn de nummers als string):
{{
  "1": {{"hook": "...", "format": "..."}},
  "2": {{"hook": "...", "format": "..."}}
}}"""

    raw = call_json(prompt, max_tokens=800)
    if "_error" in raw:
        return {}

    result: dict[str, dict] = {}
    for idx_str, tags in raw.items():
        try:
            i = int(idx_str) - 1
            if 0 <= i < len(ads_info):
                result[ads_info[i]["ad_name"]] = {
                    "hook":   tags.get("hook", "unknown"),
                    "format": tags.get("format", "reels"),
                }
        except (ValueError, KeyError):
            continue
    return result


def call_json_with_image(
    prompt: str,
    image_data: bytes,
    media_type: str = "image/jpeg",
    system: str = _SLN_SYSTEM_JSON,
    max_tokens: int = 1000,
) -> dict:
    import base64
    import logging as _log
    _logger = _log.getLogger(__name__)
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        b64 = base64.standard_b64encode(image_data).decode("utf-8")
        _logger.info("call_json_with_image START | model=%s | img_len=%d | media=%s", _VISION_MODEL, len(image_data), media_type)
        msg = client.messages.create(
            model=_VISION_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw = msg.content[0].text
        _logger.info("call_json_with_image OK | raw[:120]=%r", raw[:120])
        return json.loads(_extract_json(raw))
    except Exception as e:
        import traceback as _tb
        _logger.error("call_json_with_image FAILED | type=%s | error=%s\n%s", type(e).__name__, e, _tb.format_exc())
        return {"_error": str(e)}


_VISION_MODEL = "claude-sonnet-4-6"


def call_text_with_image(
    prompt: str,
    image_data: bytes,
    media_type: str = "image/jpeg",
    max_tokens: int = 100,
) -> str:
    """Plain-text vision call — returns raw text, no JSON parsing."""
    import base64
    import logging as _log
    _logger = _log.getLogger(__name__)
    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        b64 = base64.standard_b64encode(image_data).decode("utf-8")
        _logger.info("call_text_with_image START | model=%s | img_len=%d | media=%s", _VISION_MODEL, len(image_data), media_type)
        msg = client.messages.create(
            model=_VISION_MODEL,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        result = msg.content[0].text.strip()
        _logger.info("call_text_with_image OK | result=%r", result[:80])
        return result
    except Exception as e:
        import traceback as _tb
        _logger.error("call_text_with_image FAILED | type=%s | error=%s\n%s", type(e).__name__, e, _tb.format_exc())
        return ""


def call_text(prompt: str, system: str = _SLN_SYSTEM_TEXT, max_tokens: int = 1200) -> str:
    try:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"[AI niet beschikbaar: {e}]"
