from collections import defaultdict
from models.campaign import Campaign, AdSet, Ad, AnalysisSummary


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b else default


def _sum(rows: list[dict], field: str) -> float:
    return sum(float(r.get(field, 0) or 0) for r in rows)


def _mean(rows: list[dict], field: str) -> float:
    vals = [float(r.get(field, 0) or 0) for r in rows]
    return sum(vals) / len(vals) if vals else 0.0


def _weighted_avg(rows: list[dict], value_field: str, weight_field: str) -> float:
    total_weight = _sum(rows, weight_field)
    if total_weight == 0:
        return 0.0
    return sum(
        float(r.get(value_field, 0) or 0) * float(r.get(weight_field, 0) or 0)
        for r in rows
    ) / total_weight


def _group_by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row.get(key, "Unknown")].append(row)
    return dict(groups)


def _aggregate(rows: list[dict], name_key: str, name_val: str) -> dict:
    impressions = _sum(rows, "impressions")
    reach = _sum(rows, "reach")
    clicks = _sum(rows, "clicks")
    link_clicks = _sum(rows, "link_clicks")
    spend = _sum(rows, "spend")
    results = _sum(rows, "results")
    frequency = _mean(rows, "frequency")
    roas = _weighted_avg(rows, "roas", "spend")

    return {
        name_key: name_val,
        "impressions": int(impressions),
        "reach": int(reach),
        "clicks": int(clicks),
        "link_clicks": int(link_clicks),
        "spend": round(spend, 2),
        "results": int(results),
        "frequency": round(frequency, 2),
        "ctr": round(_safe_div(clicks, impressions) * 100, 2),
        "cpc": round(_safe_div(spend, clicks), 2),
        "cpm": round(_safe_div(spend, impressions) * 1000, 2),
        "cost_per_result": round(_safe_div(spend, results), 2),
        "roas": round(roas, 2),
    }


def get_all_ads(campaigns: list[Campaign]) -> list[Ad]:
    return [ad for c in campaigns for adset in c.ad_sets for ad in adset.ads]


def build_campaigns(rows: list[dict]) -> list[Campaign]:
    campaigns = []

    for camp_name, camp_rows in _group_by(rows, "campaign_name").items():
        camp_agg = _aggregate(camp_rows, "campaign_name", camp_name)
        camp_id = camp_rows[0].get("campaign_id", "0")

        ad_sets = []
        for adset_name, adset_rows in _group_by(camp_rows, "ad_set_name").items():
            adset_agg = _aggregate(adset_rows, "ad_set_name", adset_name)
            adset_id = adset_rows[0].get("ad_set_id", "0")

            ads = []
            for ad_name, ad_rows in _group_by(adset_rows, "ad_name").items():
                ad_agg = _aggregate(ad_rows, "ad_name", ad_name)
                ad_id = ad_rows[0].get("ad_id", "0")
                ads.append(Ad(
                    ad_id=str(ad_id),
                    ad_name=ad_name,
                    ad_set_name=adset_name,
                    campaign_name=camp_name,
                    impressions=ad_agg["impressions"],
                    reach=ad_agg["reach"],
                    clicks=ad_agg["clicks"],
                    link_clicks=ad_agg["link_clicks"],
                    spend=ad_agg["spend"],
                    results=ad_agg["results"],
                    ctr=ad_agg["ctr"],
                    cpc=ad_agg["cpc"],
                    cpm=ad_agg["cpm"],
                    roas=ad_agg["roas"],
                    frequency=ad_agg["frequency"],
                    cost_per_result=ad_agg["cost_per_result"],
                ))

            ad_sets.append(AdSet(
                ad_set_id=str(adset_id),
                ad_set_name=adset_name,
                campaign_name=camp_name,
                impressions=adset_agg["impressions"],
                reach=adset_agg["reach"],
                clicks=adset_agg["clicks"],
                link_clicks=adset_agg["link_clicks"],
                spend=adset_agg["spend"],
                results=adset_agg["results"],
                ctr=adset_agg["ctr"],
                cpc=adset_agg["cpc"],
                cpm=adset_agg["cpm"],
                roas=adset_agg["roas"],
                frequency=adset_agg["frequency"],
                cost_per_result=adset_agg["cost_per_result"],
                ads=ads,
            ))

        campaigns.append(Campaign(
            campaign_id=str(camp_id),
            campaign_name=camp_name,
            impressions=camp_agg["impressions"],
            reach=camp_agg["reach"],
            clicks=camp_agg["clicks"],
            link_clicks=camp_agg["link_clicks"],
            spend=camp_agg["spend"],
            results=camp_agg["results"],
            ctr=camp_agg["ctr"],
            cpc=camp_agg["cpc"],
            cpm=camp_agg["cpm"],
            roas=camp_agg["roas"],
            frequency=camp_agg["frequency"],
            cost_per_result=camp_agg["cost_per_result"],
            ad_sets=ad_sets,
        ))

    return sorted(campaigns, key=lambda c: c.spend, reverse=True)


def _detect_campaign_type(rows: list[dict]) -> str:
    indicators = [str(r.get("result_indicator", "")).lower() for r in rows if r.get("result_indicator")]
    if not indicators:
        return "leads"
    purchases = sum(1 for i in indicators if "purchase" in i or "sale" in i)
    awareness = sum(1 for i in indicators if "thruplay" in i or ("view" in i and "view_content" not in i))
    leads = sum(1 for i in indicators if
                "lead" in i or "message" in i or "contact" in i or "form" in i
                or "custom" in i)  # custom conversies = doorgaans leads/signups
    counts = {"purchases": purchases, "awareness": awareness, "leads": leads}
    best_count = max(counts.values())
    if best_count == 0:
        return "leads"
    # Bij gelijke stand: leads > purchases > awareness
    for preferred in ("leads", "purchases", "awareness"):
        if counts[preferred] == best_count:
            return preferred
    return "leads"


def _is_primary_result(result_indicator: str, campaign_type: str) -> bool:
    ind = result_indicator.lower().strip()

    # Lege indicator → altijd meenemen
    if not ind:
        return True

    # view_content is nooit een primaire conversie
    if "view_content" in ind:
        return False

    # Purchases-campagne: alleen purchase/sale
    if campaign_type == "purchases":
        return "purchase" in ind or "sale" in ind

    # Leads/awareness/custom: alles behalve expliciete purchases telt mee
    if "purchase" in ind or "sale" in ind:
        return False

    return True


def build_summary(rows: list[dict], campaigns: list[Campaign], campaign_type_override: str = "") -> AnalysisSummary:
    campaign_type = campaign_type_override if campaign_type_override else _detect_campaign_type(rows)

    # Only count results that match the primary objective
    primary_rows = [
        r for r in rows
        if _is_primary_result(str(r.get("result_indicator", "")), campaign_type)
    ]

    # Score only ads whose result type matches the campaign objective
    primary_ad_names = {
        r["ad_name"] for r in primary_rows
        if float(r.get("results", 0) or 0) > 0
    }
    all_ads = get_all_ads(campaigns)
    scored_ads = [
        a for a in all_ads
        if a.ad_name in primary_ad_names and a.results > 0 and a.cost_per_result > 0
    ]

    top_ad = min(scored_ads, key=lambda a: a.cost_per_result, default=None)
    worst_ad = max(scored_ads, key=lambda a: a.cost_per_result, default=None)

    total_spend = _sum(rows, "spend")
    total_impressions = int(_sum(rows, "impressions"))
    total_clicks = int(_sum(rows, "clicks"))
    total_results = int(_sum(primary_rows, "results"))
    has_click_data = any(r.get("_has_click_data", True) for r in rows)

    return AnalysisSummary(
        total_spend=round(total_spend, 2),
        total_impressions=total_impressions,
        total_reach=int(_sum(rows, "reach")),
        total_clicks=total_clicks,
        total_link_clicks=int(_sum(rows, "link_clicks")),
        total_results=total_results,
        avg_ctr=round(_safe_div(total_clicks, total_impressions) * 100, 2),
        avg_cpc=round(_safe_div(total_spend, total_clicks), 2),
        avg_cpm=round(_safe_div(total_spend, total_impressions) * 1000, 2),
        avg_roas=round(_weighted_avg(primary_rows, "roas", "spend"), 2),
        avg_frequency=round(_mean(rows, "frequency"), 2),
        avg_cost_per_result=round(_safe_div(total_spend, total_results), 2),
        num_campaigns=len(campaigns),
        num_ad_sets=sum(len(c.ad_sets) for c in campaigns),
        num_ads=sum(len(a.ads) for c in campaigns for a in c.ad_sets),
        campaign_type=campaign_type,
        top_ad=top_ad.ad_name if top_ad else None,
        top_ad_set=top_ad.ad_set_name if top_ad else None,
        worst_ad=worst_ad.ad_name if worst_ad else None,
        worst_ad_set=worst_ad.ad_set_name if worst_ad else None,
        has_click_data=has_click_data,
        campaigns=campaigns,
    )


def build_ad_chart_data(campaigns: list[Campaign], campaign_type: str, top_n: int = 10) -> dict:
    all_ads = get_all_ads(campaigns)
    ads_by_spend = sorted(all_ads, key=lambda a: a.spend, reverse=True)[:top_n]

    def short(name: str) -> str:
        return name[:22] + "…" if len(name) > 22 else name

    labels = [short(a.ad_name) for a in ads_by_spend]
    metric_values = [
        round(a.cost_per_result, 2) if campaign_type != "purchases" else round(a.roas, 2)
        for a in ads_by_spend
    ]

    return {
        "labels": labels,
        "spend":   [a.spend for a in ads_by_spend],
        "metric":  metric_values,
        "ctr":     [a.ctr for a in ads_by_spend],
        "results": [a.results for a in ads_by_spend],
    }


def get_date_range(rows: list[dict]) -> tuple[str | None, str | None]:
    dates = sorted({str(r.get("day", "")).strip() for r in rows if str(r.get("day", "")).strip()})
    if not dates:
        return None, None
    return dates[0], dates[-1]


def filter_rows_by_date(rows: list[dict], date_from: str, date_to: str) -> list[dict]:
    if not date_from and not date_to:
        return rows
    out = []
    for r in rows:
        d = str(r.get("day", "")).strip()
        if not d:
            out.append(r)
            continue
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        out.append(r)
    return out


def build_wow_comparison(rows: list[dict]) -> dict | None:
    dated = [(str(r.get("day", "")).strip(), r) for r in rows if str(r.get("day", "")).strip()]
    if not dated:
        return None
    all_dates = sorted({d for d, _ in dated})
    if len(all_dates) < 2:
        return None
    mid = len(all_dates) // 2
    s1, s2 = set(all_dates[:mid]), set(all_dates[mid:])
    r1 = [r for d, r in dated if d in s1]
    r2 = [r for d, r in dated if d in s2]

    def _m(rws: list[dict]) -> dict:
        sp  = _sum(rws, "spend")
        res = int(_sum(rws, "results"))
        imp = int(_sum(rws, "impressions"))
        clk = int(_sum(rws, "clicks"))
        return {
            "spend":   round(sp, 2),
            "results": res,
            "cpl":     round(_safe_div(sp, res), 2),
            "ctr":     round(_safe_div(clk, imp) * 100, 2),
        }

    p1, p2 = _m(r1), _m(r2)
    p1["date_from"], p1["date_to"] = all_dates[0], all_dates[mid - 1]
    p2["date_from"], p2["date_to"] = all_dates[mid], all_dates[-1]

    def _delta(a: float, b: float) -> float | None:
        return round((b - a) / a * 100, 1) if a else None

    return {
        "p1": p1, "p2": p2,
        "delta_spend":   _delta(p1["spend"],   p2["spend"]),
        "delta_results": _delta(p1["results"],  p2["results"]),
        "delta_cpl":     _delta(p1["cpl"],      p2["cpl"]),
        "delta_ctr":     _delta(p1["ctr"],      p2["ctr"]),
    }


def build_chart_data(campaigns: list[Campaign]) -> dict:
    names = [c.campaign_name for c in campaigns]
    return {
        "spend_by_campaign":   {"labels": names, "values": [c.spend for c in campaigns]},
        "roas_by_campaign":    {"labels": names, "values": [c.roas for c in campaigns]},
        "ctr_by_campaign":     {"labels": names, "values": [c.ctr for c in campaigns]},
        "results_by_campaign": {"labels": names, "values": [c.results for c in campaigns]},
    }
