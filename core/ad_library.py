"""
Meta Ad Library API integration.
Searches public competitor ads and extracts hook patterns.

Token priority (automatic — no separate env var required):
  1. App access token via META_APP_ID + META_APP_SECRET (client_credentials)
  2. Client's connected Meta user token (passed in explicitly)
  3. META_AD_LIBRARY_TOKEN env var (explicit override)
"""
from __future__ import annotations
import os
import logging
from typing import Any

import requests

from core.ai_client import call_text

logger = logging.getLogger(__name__)

_BASE = "https://graph.facebook.com/v19.0/ads_archive"

# Only request fields that don't require Meta identity verification.
# spend/impressions/age_country_gender_reach_breakdown require confirmed identity
# and cause 400/403 errors when not verified.
_AD_FIELDS = (
    "id,page_name,ad_creative_bodies,ad_creative_link_titles,"
    "ad_snapshot_url,ad_delivery_start_time,ad_delivery_stop_time"
)


def get_app_token() -> str:
    """
    Fetch a Meta app access token using client_credentials flow.
    Works with META_APP_ID + META_APP_SECRET (already required for OAuth).
    App tokens can access the Ad Library without per-user identity verification.
    """
    app_id     = os.getenv("META_APP_ID", "")
    app_secret = os.getenv("META_APP_SECRET", "")
    if not app_id or not app_secret:
        return ""
    try:
        resp = requests.get(
            "https://graph.facebook.com/oauth/access_token",
            params={
                "client_id":     app_id,
                "client_secret": app_secret,
                "grant_type":    "client_credentials",
            },
            timeout=10,
        )
        data = resp.json()
        if "error" in data:
            logger.warning("get_app_token API error: %s", data["error"])
            return ""
        return data.get("access_token", "")
    except Exception as e:
        logger.error("get_app_token failed: %s", e)
        return ""


def _translate_meta_error(code: int, message: str) -> str:
    """Return a user-friendly Dutch error string for common Meta API errors."""
    msg_lower = message.lower()
    if code == 10 or "does not have permission" in msg_lower or "permission" in msg_lower:
        return (
            "AD_LIBRARY_PERMISSION: Jouw Meta-app heeft geen toegang tot de Ad Library API. "
            "Activeer de Marketing API en vraag Ad Library API-toegang aan via "
            "developers.facebook.com → jouw app → Products → Marketing API."
        )
    if "token" in msg_lower and ("expired" in msg_lower or "invalid" in msg_lower or "session" in msg_lower):
        return "Access token verlopen of ongeldig — vernieuw de Meta-verbinding."
    return message


def search_ads(query: str, token: str = "", country: str = "NL",
               ad_type: str = "ALL", limit: int = 50) -> tuple[list[dict], str]:
    """
    Search the Meta Ad Library for active ads matching the query string.
    Returns (ads_list, error_message). error_message is empty string on success.

    token: explicit access token; falls back to META_AD_LIBRARY_TOKEN env var.
    """
    if not token:
        token = os.getenv("META_AD_LIBRARY_TOKEN", "")
    if not token:
        return [], "Geen token beschikbaar."

    try:
        resp = requests.get(
            _BASE,
            params={
                "access_token":          token,
                "search_terms":          query,
                "ad_type":               ad_type,
                "ad_reached_countries":  country,
                "fields":                _AD_FIELDS,
                "limit":                 min(limit, 100),
            },
            timeout=20,
        )
        data = resp.json()

        if "error" in data:
            err = data["error"]
            raw_msg = err.get("message", str(err))
            code = err.get("code", 0)
            logger.error("search_ads API error (query=%r country=%s code=%s): %s", query, country, code, raw_msg)
            msg = _translate_meta_error(code, raw_msg)
            return [], msg

        resp.raise_for_status()
        raw = data.get("data", [])
        logger.info("search_ads: %d ads for query=%r country=%s", len(raw), query, country)
        return [_normalize_library_ad(ad) for ad in raw], ""

    except requests.HTTPError as e:
        body = e.response.text[:300] if e.response is not None else ""
        msg = f"HTTP {e.response.status_code if e.response is not None else '?'}: {body}"
        logger.error("search_ads HTTP error (query=%r): %s", query, msg)
        return [], msg
    except Exception as e:
        logger.error("search_ads failed (query=%r): %s", query, e)
        return [], str(e)


def _normalize_library_ad(ad: dict) -> dict:
    """Flatten a raw Ad Library response into a clean dict."""
    bodies = ad.get("ad_creative_bodies") or []
    titles = ad.get("ad_creative_link_titles") or []
    return {
        "page_name":         ad.get("page_name", ""),
        "ad_creative_body":  bodies[0] if bodies else "",
        "ad_title":          titles[0] if titles else "",
        "ad_snapshot_url":   ad.get("ad_snapshot_url", ""),
        "started_running":   ad.get("ad_delivery_start_time", ""),
        "stopped_running":   ad.get("ad_delivery_stop_time", ""),
        "impressions":       "",
    }


def get_competitor_hooks(industry_keywords: list[str], token: str = "",
                          country: str = "NL") -> tuple[list[dict], str]:
    """
    Search the Ad Library on each industry keyword and return a deduplicated
    list of competitor ads (max 3 ads per page, 50 total).
    Returns (ads_list, last_error_message).
    """
    seen_pages: dict[str, int] = {}
    all_ads: list[dict] = []
    last_error = ""

    for kw in industry_keywords[:5]:
        ads, error = search_ads(kw, token=token, country=country, limit=25)
        if error:
            last_error = error
            logger.warning("get_competitor_hooks: keyword=%r error=%s", kw, error)
            continue
        for ad in ads:
            page = ad.get("page_name", "")
            count = seen_pages.get(page, 0)
            if count < 3:
                seen_pages[page] = count + 1
                all_ads.append(ad)
            if len(all_ads) >= 50:
                break
        if len(all_ads) >= 50:
            break

    return all_ads, last_error


def analyze_competitor_hooks(ads: list[dict], client_hooks: list[str],
                               client_name: str = "") -> str:
    """
    Send competitor ad bodies to Claude and get a hook-gap analysis.
    Returns markdown text comparing what competitors use vs. what the client hasn't tried.
    """
    if not ads:
        return "Geen concurrentie-advertenties gevonden voor deze branche."

    ad_lines = "\n".join(
        f"- [{a['page_name']}]: {a['ad_creative_body'][:200]}"
        for a in ads[:30]
        if a.get("ad_creative_body")
    )

    if not ad_lines.strip():
        return "Gevonden advertenties bevatten geen advertentietekst om te analyseren."

    client_hooks_str = ", ".join(client_hooks) if client_hooks else "nog geen data beschikbaar"

    prompt = f"""Analyseer deze Meta-advertenties van concurrenten in de Nederlandse markt.

Concurrentie-advertenties:
{ad_lines}

Hooks die {client_name or 'de klant'} al gebruikt: {client_hooks_str}

Geef een analyse met:
1. Welke hook-types concurrenten het meest gebruiken (met voorbeeldzin uit de data)
2. Welke hooks/angles de klant nog NIET gebruikt maar kans heeft
3. Top 3 concrete openingszinnen die je zou testen, gebaseerd op wat werkt bij concurrenten

Schrijf concreet en actionable. Geen marketingtaal. Gebruik korte alinea's."""

    return call_text(prompt, max_tokens=1200)
