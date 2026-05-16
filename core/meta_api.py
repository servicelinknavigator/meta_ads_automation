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
_SCOPES = "ads_read,ads_management,read_insights"

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
    Fetch individual ads with name, metrics, and creative_id.
    Returns raw Meta API response rows.
    """
    try:
        resp = requests.get(
            f"{_BASE}/{ad_account_id}/ads",
            params={
                "access_token": token,
                "fields": f"id,name,status,campaign_id,campaign{{name}},"
                          f"adset_id,adset{{name}},creative{{id}},"
                          f"insights{{fields={_INSIGHTS_FIELDS},"
                          f"time_range={{since:'{date_from}',until:'{date_to}'}}}}",
                "limit": 500,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("data", [])

        # Handle pagination
        paging = resp.json().get("paging", {})
        while paging.get("next"):
            page = requests.get(paging["next"], timeout=30)
            page.raise_for_status()
            raw.extend(page.json().get("data", []))
            paging = page.json().get("paging", {})

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
    Pull 'results' from Meta's actions array.
    Prefers lead/purchase actions; falls back to total link clicks.
    """
    actions = insights.get("actions", []) or []
    priority = ["lead", "offsite_conversion.fb_pixel_purchase",
                "offsite_conversion.fb_pixel_lead", "link_click"]
    for p in priority:
        for a in actions:
            if a.get("action_type") == p:
                try:
                    return int(float(a.get("value", 0)))
                except (ValueError, TypeError):
                    pass
    # fallback: first available action
    if actions:
        try:
            return int(float(actions[0].get("value", 0)))
        except (ValueError, TypeError):
            pass
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
    Convert Meta API ad rows → internal CSV-parser format so all existing
    analysis functions work without modification.

    Output fields match parse_csv() output:
      ad_id, ad_name, campaign_id, campaign_name, adset_id, adset_name,
      spend, impressions, clicks, link_clicks, results, frequency, roas,
      ctr, cpc, cpm, cost_per_result, reach, day
    """
    normalized: list[dict] = []

    for ad in raw_ads:
        insights_wrapper = ad.get("insights", {})
        if isinstance(insights_wrapper, dict):
            ins_list = insights_wrapper.get("data", [{}])
        else:
            ins_list = [{}]

        ins = ins_list[0] if ins_list else {}

        spend       = _extract_metric(ins, "spend")
        impressions = _extract_metric(ins, "impressions")
        clicks      = _extract_metric(ins, "clicks")
        reach       = _extract_metric(ins, "reach")
        frequency   = _extract_metric(ins, "frequency")
        ctr         = _extract_metric(ins, "ctr")
        cpm         = _extract_metric(ins, "cpm")
        cpc         = _extract_metric(ins, "cpc")
        results     = _extract_results(ins)
        roas        = _extract_roas(ins)

        cost_per_result = round(spend / results, 2) if results > 0 else 0.0

        campaign     = ad.get("campaign", {}) or {}
        adset        = ad.get("adset", {}) or {}
        creative_obj = ad.get("creative", {}) or {}

        normalized.append({
            "ad_id":          ad.get("id", ""),
            "ad_name":        ad.get("name", ""),
            "campaign_id":    ad.get("campaign_id", campaign.get("id", "")),
            "campaign_name":  campaign.get("name", ""),
            "adset_id":       ad.get("adset_id", adset.get("id", "")),
            "adset_name":     adset.get("name", ""),
            "spend":          round(spend, 2),
            "impressions":    int(impressions),
            "clicks":         int(clicks),
            "link_clicks":    int(clicks),  # Meta doesn't always split these
            "results":        results,
            "frequency":      round(frequency, 2),
            "roas":           round(roas, 2),
            "ctr":            round(ctr, 2),
            "cpc":            round(cpc, 2),
            "cpm":            round(cpm, 2),
            "cost_per_result": cost_per_result,
            "reach":          int(reach),
            "day":            "",
            "creative_id":    creative_obj.get("id", ""),
            "status":         ad.get("status", ""),
        })

    return normalized
