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
