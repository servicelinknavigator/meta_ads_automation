import os
import sys
import re
import json
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from dotenv import load_dotenv
import io

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from core.csv_parser import parse_csv, load_dummy_data, validate_csv
from core.analysis import build_campaigns, build_summary, build_ad_chart_data, get_all_ads
from core.generation import generate_insights
from core.reporter import generate_pdf

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", 50)) * 1024 * 1024

UPLOAD_FOLDER = Path(__file__).parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)


def _process_df(rows: list) -> dict:
    valid, errors = validate_csv(rows)
    if not valid:
        return {"error": "; ".join(errors)}

    campaigns = build_campaigns(rows)
    summary = build_summary(rows, campaigns)
    ad_chart_data = build_ad_chart_data(campaigns, summary.campaign_type)
    all_ads = sorted(get_all_ads(campaigns), key=lambda a: a.spend, reverse=True)
    insights = generate_insights(summary, all_ads)

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
    }
    session["insights"] = insights

    return {
        "summary":       summary,
        "all_ads_json":  all_ads_json,
        "ad_chart_data": json.dumps(ad_chart_data),
        "insights_html": _md_to_html(insights),
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
        campaigns=[],
    )


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", result=None)


@app.route("/demo", methods=["GET"])
def demo():
    rows = load_dummy_data()
    result = _process_df(rows)
    if "error" in result:
        flash(result["error"], "danger")
        return redirect(url_for("index"))
    return render_template("index.html", result=result, demo=True)


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

    save_path = UPLOAD_FOLDER / file.filename
    file.save(save_path)
    try:
        rows = parse_csv(save_path)
    except Exception as e:
        flash(f"Fout bij inlezen CSV: {e}", "danger")
        return redirect(url_for("index"))

    result = _process_df(rows)
    if "error" in result:
        flash(result["error"], "danger")
        return redirect(url_for("index"))
    return render_template("index.html", result=result, demo=False)


@app.route("/export/pdf", methods=["GET"])
def export_pdf():
    summary_data = session.get("summary")
    insights_raw = session.get("insights", "Geen inzichten beschikbaar.")
    if not summary_data:
        flash("Geen actieve analyse. Upload eerst een CSV.", "warning")
        return redirect(url_for("index"))
    summary = _session_to_summary(summary_data)
    pdf_bytes = generate_pdf(summary, insights_raw)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="meta_ads_rapport.pdf",
    )


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug, port=5000)
