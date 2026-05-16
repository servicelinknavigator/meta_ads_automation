"""
Meta Ad Library API integration.
Searches public competitor ads and extracts hook patterns.
Requires env var: META_AD_LIBRARY_TOKEN
"""
from __future__ import annotations
import os
import logging
from typing import Any

import requests

from core.ai_client import call_text

logger = logging.getLogger(__name__)

_BASE = "https://graph.facebook.com/v19.0/ads_archive"

_AD_FIELDS = (
    "id,page_name,ad_creative_bodies,ad_creative_link_titles,"
    "ad_snapshot_url,ad_delivery_start_time,ad_delivery_stop_time,"
    "impressions,spend,age_country_gender_reach_breakdown"
)


def search_ads(query: str, country: str = "NL",
               ad_type: str = "ALL", limit: int = 50) -> list[dict]:
    """
    Search the Meta Ad Library for active ads matching the query string.
    Returns a list of ad dicts with page_name, body, snapshot URL, start date.
    """
    token = os.getenv("META_AD_LIBRARY_TOKEN", "")
    if not token:
        logger.warning("META_AD_LIBRARY_TOKEN is not set — Ad Library unavailable")
        return []

    try:
        resp = requests.get(
            _BASE,
            params={
                "access_token":    token,
                "search_terms":    query,
                "ad_type":         ad_type,
                "ad_reached_countries": country,
                "fields":          _AD_FIELDS,
                "limit":           min(limit, 100),
            },
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])
        return [_normalize_library_ad(ad) for ad in raw]
    except Exception as e:
        logger.error("search_ads failed (query=%s): %s", query, e)
        return []


def _normalize_library_ad(ad: dict) -> dict:
    """Flatten a raw Ad Library response into a clean dict."""
    bodies = ad.get("ad_creative_bodies") or []
    titles = ad.get("ad_creative_link_titles") or []
    return {
        "page_name":      ad.get("page_name", ""),
        "ad_creative_body": bodies[0] if bodies else "",
        "ad_title":       titles[0] if titles else "",
        "ad_snapshot_url": ad.get("ad_snapshot_url", ""),
        "started_running": ad.get("ad_delivery_start_time", ""),
        "stopped_running": ad.get("ad_delivery_stop_time", ""),
        "impressions":    ad.get("impressions", {}).get("lower_bound", ""),
    }


def get_competitor_hooks(industry_keywords: list[str],
                          country: str = "NL") -> list[dict]:
    """
    Search the Ad Library on each industry keyword and return a deduplicated
    list of competitor ads.  Stops after 50 unique ads total.
    """
    seen_pages: set[str] = set()
    all_ads: list[dict] = []

    for kw in industry_keywords[:5]:  # cap at 5 keywords
        ads = search_ads(kw, country=country, limit=20)
        for ad in ads:
            page = ad.get("page_name", "")
            if page not in seen_pages:
                seen_pages.add(page)
                all_ads.append(ad)
            if len(all_ads) >= 50:
                break
        if len(all_ads) >= 50:
            break

    return all_ads


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

    client_hooks_str = ", ".join(client_hooks) if client_hooks else "onbekend"

    prompt = f"""Analyseer deze Meta-advertenties van concurrenten in de Nederlandse markt.

Concurrentie-advertenties:
{ad_lines}

Hooks die {client_name or 'de klant'} al gebruikt: {client_hooks_str}

Geef een analyse met:
1. Welke hook-types concurrenten het meest gebruiken (met voorbeeldzin)
2. Welke hooks/angles de klant nog NIET gebruikt maar kans heeft
3. Top 3 concrete openingszinnen die je zou testen, gebaseerd op wat werkt bij concurrenten

Schrijf concreet en actionable. Geen marketingtaal."""

    return call_text(prompt, max_tokens=1200)
