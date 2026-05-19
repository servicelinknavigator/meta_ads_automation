"""
Meta Marketing API integration.
Handles OAuth flow, data fetching, and normalization to the internal ad format.
Requires env vars: META_APP_ID, META_APP_SECRET, META_REDIRECT_URI.
"""
from __future__ import annotations
import os
import logging
import time
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE = "https://graph.facebook.com/v19.0"
_SCOPES = "ads_read,ads_management,business_management"

_INSIGHTS_FIELDS = (
    "spend,impressions,clicks,ctr,cpm,cpc,frequency,"
    "actions,cost_per_action_type,purchase_roas,reach"
)


# ── OAuth ─────────────────────────────────────────────────────────────────────

def get_auth_url(state: str = "") -> str:
    """Return the Meta OAuth dialog URL the user must visit to grant access."""
    app_id = os.getenv("META_APP_ID", "")
    redirect = os.getenv("META_REDIRECT_URI", "")
    params = (
        f"client_id={app_id}"
        f"&redirect_uri={redirect}"
        f"&scope={_SCOPES}"
        f"&response_type=code"
        + (f"&state={state}" if state else "")
    )
    return f"https://www.facebook.com/dialog/oauth?{params}"


def exchange_code_for_token(code: str) -> dict:
    """
    Exchange the short-lived OAuth code for a long-lived access token.
    Returns dict with 'access_token' and 'expires_in' (seconds).
    """
    try:
        resp = requests.get(
            f"{_BASE}/oauth/access_token",
            params={
                "client_id":     os.getenv("META_APP_ID", ""),
                "client_secret": os.getenv("META_APP_SECRET", ""),
                "redirect_uri":  os.getenv("META_REDIRECT_URI", ""),
                "code":          code,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        # Exchange short-lived for long-lived token
        ll_resp = requests.get(
            f"{_BASE}/oauth/access_token",
            params={
                "grant_type":        "fb_exchange_token",
                "client_id":         os.getenv("META_APP_ID", ""),
                "client_secret":     os.getenv("META_APP_SECRET", ""),
                "fb_exchange_token": data.get("access_token", ""),
            },
            timeout=15,
        )
        ll_resp.raise_for_status()
        return ll_resp.json()
    except Exception as e:
        logger.error("exchange_code_for_token failed: %s", e)
        return {"error": str(e)}


def refresh_token(token: str) -> dict:
    """Extend a nearly-expired long-lived token. Returns new token dict."""
    try:
        resp = requests.get(
            f"{_BASE}/oauth/access_token",
            params={
                "grant_type":        "fb_exchange_token",
                "client_id":         os.getenv("META_APP_ID", ""),
                "client_secret":     os.getenv("META_APP_SECRET", ""),
                "fb_exchange_token": token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("refresh_token failed: %s", e)
        return {"error": str(e)}


# ── Data fetching ─────────────────────────────────────────────────────────────

def get_ad_accounts(token: str) -> list[dict]:
    """Return all ad accounts accessible with the given token."""
    try:
        resp = requests.get(
            f"{_BASE}/me/adaccounts",
            params={
                "access_token": token,
                "fields": "id,name,account_status,currency,timezone_name",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as e:
        logger.error("get_ad_accounts failed: %s", e)
        return []


def get_campaigns(token: str, ad_account_id: str,
                  date_from: str, date_to: str) -> list[dict]:
    """
    Fetch campaigns with spend + insight metrics for the given date range.
    date_from / date_to format: 'YYYY-MM-DD'
    """
    try:
        resp = requests.get(
            f"{_BASE}/{ad_account_id}/campaigns",
            params={
                "access_token": token,
                "fields": f"id,name,status,objective,insights{{"
                          f"fields={_INSIGHTS_FIELDS},"
                          f"time_range={{since:'{date_from}',until:'{date_to}'}}}}",
                "limit": 200,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as e:
        logger.error("get_campaigns failed: %s", e)
        return []


def get_adsets(token: str, ad_account_id: str,
               date_from: str, date_to: str) -> list[dict]:
    """Fetch ad sets with insight metrics for the given date range."""
    try:
        resp = requests.get(
            f"{_BASE}/{ad_account_id}/adsets",
            params={
                "access_token": token,
                "fields": f"id,name,status,campaign_id,insights{{"
                          f"fields={_INSIGHTS_FIELDS},"
                          f"time_range={{since:'{date_from}',until:'{date_to}'}}}}",
                "limit": 200,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as e:
        logger.error("get_adsets failed: %s", e)
        return []


def get_ads(token: str, ad_account_id: str,
            date_from: str, date_to: str) -> list[dict]:
    """
    Fetch ad-level performance data via the /insights endpoint (level=ad).
    This is the reliable approach — avoids nested field expansion issues.
    Returns rows that already include ad_name, campaign_name, adset_name + all metrics.
    """
    import json as _json

    _INSIGHT_FIELDS = (
        "ad_id,ad_name,campaign_id,campaign_name,adset_id,adset_name,"
        "spend,impressions,clicks,reach,frequency,ctr,cpm,cpc,"
        "actions,cost_per_action_type,purchase_roas"
    )

    try:
        resp = requests.get(
            f"{_BASE}/{ad_account_id}/insights",
            params={
                "access_token": token,
                "level":        "ad",
                "fields":       _INSIGHT_FIELDS,
                "time_range":   _json.dumps({"since": date_from, "until": date_to}),
                "limit":        500,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        raw  = data.get("data", [])

        # Paginate through all results (max 200 pages = 100k rows)
        paging = data.get("paging", {})
        page_count = 0
        while paging.get("next") and page_count < 200:
            page_count += 1
            try:
                page = requests.get(paging["next"], timeout=30)
                page.raise_for_status()
                page_data = page.json()
            except Exception as page_err:
                logger.warning("Pagination request %d failed, returning partial results: %s", page_count, page_err)
                break
            raw.extend(page_data.get("data", []))
            paging = page_data.get("paging", {})

        logger.info("get_ads: %d rows for %s (%s → %s)",
                    len(raw), ad_account_id, date_from, date_to)
        return raw
    except Exception as e:
        logger.error("get_ads failed: %s", e)
        return []


def get_ad_creative(token: str, creative_id: str) -> dict:
    """Fetch creative details: thumbnail, body text, title."""
    try:
        resp = requests.get(
            f"{_BASE}/{creative_id}",
            params={
                "access_token": token,
                "fields": "id,name,body,title,thumbnail_url,image_url",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("get_ad_creative %s failed: %s", creative_id, e)
        return {}


# ── Normalization ─────────────────────────────────────────────────────────────

def _extract_metric(insights: dict, key: str, default: float = 0.0) -> float:
    """Safely extract a numeric metric from an insights dict."""
    try:
        return float(insights.get(key, default) or default)
    except (ValueError, TypeError):
        return default


def _extract_results(insights: dict) -> int:
    """
    Pull conversion 'results' from Meta's actions array.
    Checks known conversion types first, then custom pixel conversions
    (offsite_conversion.custom.*). Never counts engagement/reach actions.
    """
    actions = insights.get("actions", []) or []
    if not actions:
        return 0

    action_map = {a.get("action_type"): a for a in actions}

    # 1. Known standard conversion types (most specific first)
    priority = [
        "offsite_conversion.fb_pixel_purchase",
        "offsite_conversion.fb_pixel_lead",
        "onsite_conversion.lead_grouped",
        "lead",
        "contact",
        "schedule",
        "omni_complete_registration",
        "omni_purchase",
    ]
    for p in priority:
        if p in action_map:
            try:
                return int(float(action_map[p].get("value", 0)))
            except (ValueError, TypeError):
                pass

    # 2. Custom pixel conversions (e.g. "Lead fit20 Roermond" → offsite_conversion.custom.XXXXX)
    # These are always real conversions created by the advertiser in Meta Business Manager.
    custom_total = 0
    for action_type, a in action_map.items():
        if action_type.startswith("offsite_conversion.custom."):
            try:
                custom_total += int(float(a.get("value", 0)))
            except (ValueError, TypeError):
                pass
    if custom_total > 0:
        return custom_total

    return 0


def _extract_roas(insights: dict) -> float:
    """Extract purchase ROAS from insights, 0.0 if not present."""
    roas_list = insights.get("purchase_roas", []) or []
    if roas_list:
        try:
            return float(roas_list[0].get("value", 0))
        except (ValueError, TypeError):
            pass
    return 0.0


def normalize_meta_data(raw_ads: list[dict]) -> list[dict]:
    """
    Convert /insights (level=ad) rows → internal CSV-parser format.
    The insights endpoint already returns flat fields — no nested unwrapping needed.

    Output fields match parse_csv() output:
      ad_id, ad_name, campaign_id, campaign_name, adset_id, adset_name,
      spend, impressions, clicks, link_clicks, results, frequency, roas,
      ctr, cpc, cpm, cost_per_result, reach, day
    """
    normalized: list[dict] = []

    for row in raw_ads:
        # /insights rows are flat — metrics live directly on the row
        spend       = _extract_metric(row, "spend")
        impressions = _extract_metric(row, "impressions")
        clicks      = _extract_metric(row, "clicks")
        reach       = _extract_metric(row, "reach")
        frequency   = _extract_metric(row, "frequency")
        ctr         = _extract_metric(row, "ctr")
        cpm         = _extract_metric(row, "cpm")
        cpc         = _extract_metric(row, "cpc")
        results     = _extract_results(row)
        roas        = _extract_roas(row)

        cost_per_result = round(spend / results, 2) if results > 0 else 0.0

        normalized.append({
            "ad_id":           row.get("ad_id", ""),
            "ad_name":         row.get("ad_name", ""),
            "campaign_id":     row.get("campaign_id", ""),
            "campaign_name":   row.get("campaign_name", ""),
            "adset_id":        row.get("adset_id", ""),
            "adset_name":      row.get("adset_name", ""),
            "spend":           round(spend, 2),
            "impressions":     int(impressions),
            "clicks":          int(clicks),
            "link_clicks":     int(clicks),
            "results":         results,
            "frequency":       round(frequency, 2),
            "roas":            round(roas, 2),
            "ctr":             round(ctr, 2),
            "cpc":             round(cpc, 2),
            "cpm":             round(cpm, 2),
            "cost_per_result": cost_per_result,
            "reach":           int(reach),
            "day":             row.get("date_start", ""),
            "creative_id":     "",
            "status":          "",
        })

    return normalized
