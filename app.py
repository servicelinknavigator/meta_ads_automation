import os
import sys
import re
import json
import logging
import hashlib
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from datetime import timedelta
import io

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from core.csv_parser import parse_csv, load_dummy_data, validate_csv
from core.analysis import (
    build_campaigns, build_summary, build_ad_chart_data, get_all_ads,
    get_date_range, filter_rows_by_date, build_wow_comparison,
)
from core.generation import generate_insights
from core.reporter import generate_pdf
from core.creative_decoder import decode_winner, decode_loser
from core.axes_mapper import map_axes
from core.smart_generator import generate_testkit

# In-memory creative cache — survives across requests in the same worker process
_CREATIVE_CACHE: dict = {}
_CREATIVE_CACHE_MAX = 120


def _cache_key(ad) -> str:
    s = f"{ad.ad_name}:{ad.campaign_name}:{ad.spend:.2f}:{ad.results}"
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _cache_set(key: str, value: dict) -> None:
    if len(_CREATIVE_CACHE) >= _CREATIVE_CACHE_MAX:
        _CREATIVE_CACHE.pop(next(iter(_CREATIVE_CACHE)))
    _CREATIVE_CACHE[key] = value


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", 50)) * 1024 * 1024
app.permanent_session_lifetime = timedelta(hours=4)

UPLOAD_FOLDER = Path(__file__).parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)


def _compute_thresholds(form=None) -> dict:
    preset = (form.get("threshold_preset", "auto") if form else "auto")
    if preset == "fit20":
        return {"winner": 40, "mid": 60, "preset": "fit20"}
    if preset == "belladonna":
        return {"winner": 30, "mid": 50, "preset": "belladonna"}
    if preset == "custom" and form:
        try:
            w = max(1, int(form.get("threshold_winner", 30)))
            m = max(w + 1, int(form.get("threshold_mid", 50)))
            return {"winner": w, "mid": m, "preset": "custom"}
        except (ValueError, TypeError):
            pass
    return {"winner": 30, "mid": 50, "preset": "auto"}


def _process_df(rows: list, campaign_type_override: str = "",
                date_from: str = "", date_to: str = "") -> dict:
    valid, errors = validate_csv(rows)
    if not valid:
        return {"error": "; ".join(errors)}

    # Date range info (always from the full unfiltered rows)
    full_from, full_to = get_date_range(rows)
    if date_from or date_to:
        rows = filter_rows_by_date(rows, date_from, date_to)
        if not rows:
            return {"error": "Geen data gevonden voor de geselecteerde periode."}

    date_range = None
    if full_from:
        cur_from, cur_to = get_date_range(rows)
        date_range = {
            "from": cur_from or full_from,
            "to":   cur_to   or full_to,
            "full_from": full_from,
            "full_to":   full_to,
        }

    wow = build_wow_comparison(rows)

    campaigns = build_campaigns(rows)
    summary = build_summary(rows, campaigns, campaign_type_override=campaign_type_override)
    ad_chart_data = build_ad_chart_data(campaigns, summary.campaign_type)
    all_ads = sorted(get_all_ads(campaigns), key=lambda a: a.spend, reverse=True)
    insights = generate_insights(summary, all_ads)

    # Urgent actions: geld-verbrandende ads en ad fatigue
    urgent_actions = []
    for a in all_ads:
        if a.results == 0 and a.spend > 50:
            urgent_actions.append({
                "type": "burning", "ad_name": a.ad_name,
                "ad_set_name": a.ad_set_name, "spend": round(a.spend),
            })
        elif a.frequency > 3.5 and a.results > 0:
            urgent_actions.append({
                "type": "fatigue", "ad_name": a.ad_name,
                "ad_set_name": a.ad_set_name, "frequency": round(a.frequency, 1),
            })

    all_ads_json = json.dumps([{
        "ad_name":       a.ad_name,
        "ad_set_name":   a.ad_set_name,
        "campaign_name": a.campaign_name,
        "spend":         a.spend,
        "cpl":           a.cost_per_result,
        "ctr":           a.ctr,
        "results":       a.results,
        "cpc":           a.cpc,
        "roas":          a.roas,
        "impressions":   a.impressions,
        "cpm":           a.cpm,
        "frequency":     a.frequency,
    } for a in all_ads])

    session["top_ads"] = [{
        "ad_name":        a.ad_name,
        "ad_set_name":    a.ad_set_name,
        "campaign_name":  a.campaign_name,
        "spend":          a.spend,
        "results":        a.results,
        "cost_per_result": a.cost_per_result,
        "roas":           a.roas,
        "ctr":            a.ctr,
        "frequency":      a.frequency,
    } for a in all_ads[:10]]
    session["date_range"] = date_range

    session["summary"] = {
        "total_spend":        summary.total_spend,
        "total_impressions":  summary.total_impressions,
        "total_reach":        summary.total_reach,
        "total_clicks":       summary.total_clicks,
        "total_link_clicks":  summary.total_link_clicks,
        "total_results":      summary.total_results,
        "avg_ctr":            summary.avg_ctr,
        "avg_cpc":            summary.avg_cpc,
        "avg_cpm":            summary.avg_cpm,
        "avg_roas":           summary.avg_roas,
        "avg_frequency":      summary.avg_frequency,
        "avg_cost_per_result":summary.avg_cost_per_result,
        "num_campaigns":      summary.num_campaigns,
        "num_ad_sets":        summary.num_ad_sets,
        "num_ads":            summary.num_ads,
        "campaign_type":      summary.campaign_type,
        "top_ad":             summary.top_ad,
        "top_ad_set":         summary.top_ad_set,
        "worst_ad":           summary.worst_ad,
        "worst_ad_set":       summary.worst_ad_set,
        "has_click_data":     summary.has_click_data,
    }
    session["insights"] = insights

    return {
        "summary":         summary,
        "all_ads_json":    all_ads_json,
        "ad_chart_data":   json.dumps(ad_chart_data),
        "insights_html":   _md_to_html(insights),
        "date_range":      date_range,
        "wow":             wow,
        "urgent_actions":  urgent_actions,
    }


# ── Markdown → HTML with styled section boxes ──────────────────────────────

_SECTION_STYLES = [
    (["sterke", "goed", "top", "winner"],       "bi-check-circle-fill",       "#ecfdf5", "#059669"),
    (["verbeter", "under", "aandacht", "slecht","probleem"], "bi-exclamation-triangle-fill", "#fef2f2", "#dc2626"),
    (["aanbevel", "actie", "optimali", "tip"],  "bi-lightbulb-fill",          "#fffbeb", "#d97706"),
    (["budget", "verdeling", "schaal", "inves"],"bi-pie-chart-fill",          "#eff6ff", "#2563eb"),
]

def _section_style(title: str):
    t = title.lower()
    for keywords, icon, bg, color in _SECTION_STYLES:
        if any(k in t for k in keywords):
            return icon, bg, color
    return "bi-info-circle-fill", "#f8fafc", "#64748b"


def _render_body(text: str) -> str:
    lines = [l.rstrip() for l in text.strip().split("\n")]
    out, in_list = [], False
    for line in lines:
        if not line:
            continue
        if line.startswith(("- ", "* ", "• ")):
            if not in_list:
                out.append('<ul style="padding-left:1.1rem;margin:.25rem 0 0;">')
                in_list = True
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line[2:])
            out.append(f'<li style="margin-bottom:4px;line-height:1.5;">{content}</li>')
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            content = re.sub(r"\*(.+?)\*", r"<em>\1</em>", content)
            out.append(f'<p style="margin:0 0 4px;">{content}</p>')
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _md_to_html(text: str) -> str:
    parts = re.split(r"^#{1,4}\s+(.+)$", text, flags=re.MULTILINE)
    html = []
    # text before first section
    if parts[0].strip():
        html.append(f'<p style="font-size:.82rem;color:#374151;">{parts[0].strip()}</p>')

    for i in range(1, len(parts), 2):
        title   = parts[i].strip()
        content = parts[i + 1] if i + 1 < len(parts) else ""
        icon, bg, color = _section_style(title)
        body = _render_body(content)
        html.append(f"""
<div style="background:{bg};border-radius:9px;padding:.85rem 1rem;margin-bottom:.6rem;">
  <div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:{color};margin-bottom:.5rem;">
    <i class="bi {icon}" style="margin-right:5px;"></i>{title}
  </div>
  <div style="font-size:.8rem;color:#1f2937;">{body}</div>
</div>""")
    return "\n".join(html)


def _session_to_summary(data: dict):
    from models.campaign import AnalysisSummary
    return AnalysisSummary(
        total_spend=data["total_spend"],
        total_impressions=data["total_impressions"],
        total_reach=data["total_reach"],
        total_clicks=data["total_clicks"],
        total_link_clicks=data["total_link_clicks"],
        total_results=data["total_results"],
        avg_ctr=data["avg_ctr"],
        avg_cpc=data["avg_cpc"],
        avg_cpm=data["avg_cpm"],
        avg_roas=data["avg_roas"],
        avg_frequency=data["avg_frequency"],
        avg_cost_per_result=data["avg_cost_per_result"],
        num_campaigns=data["num_campaigns"],
        num_ad_sets=data["num_ad_sets"],
        num_ads=data["num_ads"],
        campaign_type=data.get("campaign_type", "leads"),
        top_ad=data.get("top_ad"),
        top_ad_set=data.get("top_ad_set"),
        worst_ad=data.get("worst_ad"),
        worst_ad_set=data.get("worst_ad_set"),
        has_click_data=data.get("has_click_data", True),
        campaigns=[],
    )


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", result=None, thresholds=None)


@app.route("/demo", methods=["GET"])
def demo():
    rows = load_dummy_data()
    result = _process_df(rows)
    if "error" in result:
        flash(result["error"], "danger")
        return redirect(url_for("index"))
    thresholds = {"winner": 30, "mid": 50, "preset": "auto"}
    session.permanent = True
    session["data_source"] = "demo"
    session["thresholds"] = thresholds
    return render_template("index.html", result=result, demo=True, thresholds=thresholds)


@app.route("/upload", methods=["POST"])
def upload():
    if "csv_file" not in request.files:
        flash("Geen bestand geselecteerd.", "warning")
        return redirect(url_for("index"))
    file = request.files["csv_file"]
    if file.filename == "":
        flash("Geen bestand geselecteerd.", "warning")
        return redirect(url_for("index"))
    if not file.filename.lower().endswith(".csv"):
        flash("Alleen CSV bestanden zijn toegestaan.", "danger")
        return redirect(url_for("index"))

    save_path = UPLOAD_FOLDER / secure_filename(file.filename)
    file.save(save_path)
    try:
        rows = parse_csv(save_path)
    except Exception as e:
        flash(f"Fout bij inlezen CSV: {e}", "danger")
        return redirect(url_for("index"))

    max_rows = int(os.getenv("MAX_CSV_ROWS", 10000))
    if len(rows) > max_rows:
        flash(f"CSV bevat {len(rows):,} rijen — maximum is {max_rows:,}. Exporteer een kleinere periode.", "danger")
        return redirect(url_for("index"))

    campaign_type_override = request.form.get("campaign_type_override", "")
    thresholds = _compute_thresholds(request.form)
    result = _process_df(rows, campaign_type_override=campaign_type_override)
    if "error" in result:
        flash(result["error"], "danger")
        return redirect(url_for("index"))
    session.permanent = True
    session["data_source"] = str(save_path)
    session["thresholds"] = thresholds
    return render_template("index.html", result=result, demo=False, thresholds=thresholds)


@app.route("/reanalyze", methods=["POST"])
def reanalyze():
    rows = _load_rows_from_session()
    if rows is None:
        flash("Sessie verlopen. Upload je CSV opnieuw.", "warning")
        return redirect(url_for("index"))
    date_from = request.form.get("date_from", "").strip()
    date_to   = request.form.get("date_to",   "").strip()
    campaign_type_override = request.form.get("campaign_type_override", "")
    thresholds = _compute_thresholds(request.form)
    result = _process_df(rows, campaign_type_override=campaign_type_override,
                         date_from=date_from, date_to=date_to)
    if "error" in result:
        flash(result["error"], "danger")
        return redirect(url_for("index"))
    session.permanent = True
    session["thresholds"] = thresholds
    return render_template("index.html", result=result, demo=False, thresholds=thresholds)


@app.route("/export/pdf", methods=["GET"])
def export_pdf():
    summary_data = session.get("summary")
    insights_raw = session.get("insights", "Geen inzichten beschikbaar.")
    if not summary_data:
        flash("Geen actieve analyse. Upload eerst een CSV.", "warning")
        return redirect(url_for("index"))
    summary = _session_to_summary(summary_data)
    top_ads  = session.get("top_ads", [])
    date_range = session.get("date_range")
    pdf_bytes = generate_pdf(summary, insights_raw, top_ads=top_ads, date_range=date_range)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="meta_ads_rapport.pdf",
    )


def _load_rows_from_session() -> list | None:
    source = session.get("data_source")
    if not source:
        return None
    if source == "demo":
        return load_dummy_data()
    try:
        return parse_csv(Path(source))
    except Exception:
        logger.exception("Fout bij opnieuw laden CSV uit sessie: %s", source)
        return None


def _classify_ads(all_ads, summary):
    is_leads = summary.campaign_type != "purchases"
    if is_leads:
        avg = summary.avg_cost_per_result
        winners = [a for a in all_ads if a.results > 0 and a.cost_per_result > 0 and a.cost_per_result < avg * 0.85]
        losers  = [a for a in all_ads if a.results == 0 and a.spend > 50]
        if not winners:
            winners = sorted([a for a in all_ads if a.results > 0], key=lambda x: x.cost_per_result)[:3]
    else:
        avg = summary.avg_roas
        winners = [a for a in all_ads if a.roas > avg * 1.2 and a.roas > 0]
        losers  = [a for a in all_ads if a.roas < avg * 0.5 and a.spend > 50]
        if not winners:
            winners = sorted([a for a in all_ads if a.roas > 0], key=lambda x: x.roas, reverse=True)[:3]
    return winners[:4], losers[:3]


def _extract_patterns(winner_results: list) -> dict:
    from collections import Counter
    hooks   = [w["decoded"].get("hook_type", "unknown") for w in winner_results]
    formats = [w["decoded"].get("format", "unknown") for w in winner_results]
    drivers = [w["decoded"].get("psychological_driver", "") for w in winner_results if w["decoded"].get("psychological_driver")]
    return {
        "hook_counts":   dict(Counter(hooks)),
        "format_counts": dict(Counter(formats)),
        "dominant_hook": Counter(hooks).most_common(1)[0][0] if hooks else None,
        "dominant_format": Counter(formats).most_common(1)[0][0] if formats else None,
        "drivers": drivers,
        "untested_formats": [f for f in ["ugc", "carousel", "static", "testimonial"] if f not in formats],
    }


@app.route("/creative", methods=["GET"])
def creative():
    summary_data = session.get("summary")
    if not summary_data:
        flash("Geen actieve analyse. Upload eerst een CSV.", "warning")
        return redirect(url_for("index"))

    rows = _load_rows_from_session()
    if rows is None:
        flash("Het bestand kon niet worden geladen. Upload je CSV opnieuw om verder te gaan.", "warning")
        return redirect(url_for("index"))

    campaigns = build_campaigns(rows)
    summary   = build_summary(rows, campaigns)
    all_ads   = sorted(get_all_ads(campaigns), key=lambda a: a.spend, reverse=True)

    winners, losers = _classify_ads(all_ads, summary)

    winner_results = []
    for ad in winners:
        key = _cache_key(ad)
        cached = _CREATIVE_CACHE.get(key)
        if cached:
            winner_results.append({"ad": ad, **cached})
        else:
            decoded = decode_winner(ad, summary)
            axes    = map_axes(decoded, ad.ad_name)
            testkit = generate_testkit(ad.ad_name, decoded, axes)
            entry   = {"decoded": decoded, "axes": axes, "testkit": testkit}
            _cache_set(key, entry)
            winner_results.append({"ad": ad, **entry})

    loser_results = []
    for ad in losers:
        key = _cache_key(ad) + "_loser"
        cached = _CREATIVE_CACHE.get(key)
        if cached:
            loser_results.append({"ad": ad, "decoded": cached})
        else:
            decoded = decode_loser(ad, summary)
            _cache_set(key, decoded)
            loser_results.append({"ad": ad, "decoded": decoded})

    patterns = _extract_patterns(winner_results)

    thresholds = session.get("thresholds", {"winner": 30, "mid": 50, "preset": "auto"})
    return render_template(
        "creative.html",
        summary=summary,
        winners=winner_results,
        losers=loser_results,
        patterns=patterns,
        thresholds=thresholds,
        is_demo=session.get("data_source") == "demo",
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
