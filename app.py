import os
import sys
import re
import json
import logging
import hashlib
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from datetime import timedelta
import io

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from core.csv_parser import parse_csv, parse_csv_string, load_dummy_data, validate_csv
from core.analysis import (
    build_campaigns, build_summary, build_ad_chart_data, get_all_ads,
    get_date_range, filter_rows_by_date, build_wow_comparison,
)
from core.generation import generate_insights
from core.reporter import generate_pdf
from core.creative_decoder import decode_winner, decode_loser
from core.axes_mapper import map_axes
from core.smart_generator import generate_testkit
from core.hook_analyzer import (
    aggregate_hook_performance, aggregate_format_performance,
    get_winning_combinations, get_untested_hooks, get_untested_formats,
)
from core.shoot_brief import generate_shoot_brief
import core.db as db

# ── In-memory creative cache ───────────────────────────────────────────────────
_CREATIVE_CACHE: dict = {}
_CREATIVE_CACHE_MAX = 120


def _cache_key(ad) -> str:
    s = f"{ad.ad_name}:{ad.campaign_name}:{ad.spend:.2f}:{ad.results}"
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _cache_set(key: str, value: dict) -> None:
    if len(_CREATIVE_CACHE) >= _CREATIVE_CACHE_MAX:
        _CREATIVE_CACHE.pop(next(iter(_CREATIVE_CACHE)))
    _CREATIVE_CACHE[key] = value


# ── App setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", 50)) * 1024 * 1024
app.permanent_session_lifetime = timedelta(hours=4)

UPLOAD_FOLDER = Path(__file__).parent / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Init DB schema on startup
with app.app_context():
    try:
        db.init_schema()
    except Exception as e:
        logger.warning("DB init skipped: %s", e)


# ── Auth ───────────────────────────────────────────────────────────────────────

def _get_users() -> dict:
    """Parse APP_USERS=dominique:pass1,rick:pass2 from env."""
    raw = os.getenv("APP_USERS", "")
    users = {}
    for part in raw.split(","):
        part = part.strip()
        if ":" in part:
            u, p = part.split(":", 1)
            users[u.strip().lower()] = p.strip()
    return users


def _auth_enabled() -> bool:
    return bool(os.getenv("APP_USERS", "").strip())


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if _auth_enabled() and not session.get("username"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ── Helpers ────────────────────────────────────────────────────────────────────

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
                date_from: str = "", date_to: str = "",
                csv_content: str | None = None) -> dict:
    valid, errors = validate_csv(rows)
    if not valid:
        return {"error": "; ".join(errors)}

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
        "ad_name":         a.ad_name,
        "ad_set_name":     a.ad_set_name,
        "campaign_name":   a.campaign_name,
        "spend":           a.spend,
        "results":         a.results,
        "cost_per_result": a.cost_per_result,
        "roas":            a.roas,
        "ctr":             a.ctr,
        "frequency":       a.frequency,
    } for a in all_ads[:10]]
    session["date_range"] = date_range
    session["summary"] = {
        "total_spend":         summary.total_spend,
        "total_impressions":   summary.total_impressions,
        "total_reach":         summary.total_reach,
        "total_clicks":        summary.total_clicks,
        "total_link_clicks":   summary.total_link_clicks,
        "total_results":       summary.total_results,
        "avg_ctr":             summary.avg_ctr,
        "avg_cpc":             summary.avg_cpc,
        "avg_cpm":             summary.avg_cpm,
        "avg_roas":            summary.avg_roas,
        "avg_frequency":       summary.avg_frequency,
        "avg_cost_per_result": summary.avg_cost_per_result,
        "num_campaigns":       summary.num_campaigns,
        "num_ad_sets":         summary.num_ad_sets,
        "num_ads":             summary.num_ads,
        "campaign_type":       summary.campaign_type,
        "top_ad":              summary.top_ad,
        "top_ad_set":          summary.top_ad_set,
        "worst_ad":            summary.worst_ad,
        "worst_ad_set":        summary.worst_ad_set,
        "has_click_data":      summary.has_click_data,
    }
    session["insights"] = insights

    # ── Persist to DB if a client is active ──────────────────────────────────
    client_id = session.get("client_id")
    if client_id and db.is_available():
        try:
            filename = Path(session.get("data_source", "")).name
            upload_id = db.save_upload(
                client_id=client_id,
                filename=filename,
                date_from=date_range["from"] if date_range else None,
                date_to=date_range["to"] if date_range else None,
                total_spend=summary.total_spend,
                total_results=summary.total_results,
                avg_cpl=summary.avg_cost_per_result if summary.campaign_type != "purchases" else None,
                avg_roas=summary.avg_roas if summary.campaign_type == "purchases" else None,
                avg_ctr=summary.avg_ctr,
                avg_frequency=summary.avg_frequency,
                num_ads=summary.num_ads,
                campaign_type=summary.campaign_type,
                csv_content=csv_content,
            )
            session["upload_id"] = upload_id

            # Hook + format snapshots
            hook_perf = aggregate_hook_performance(all_ads)
            fmt_perf  = aggregate_format_performance(all_ads)
            db.save_hook_snapshots(client_id, upload_id, hook_perf)
            db.save_hook_snapshots(client_id, upload_id,
                                   [{**r, "hook_type": None} for r in fmt_perf])

            db.save_insights(client_id, upload_id, insights)
        except Exception as e:
            logger.warning("DB save failed: %s", e)

    return {
        "summary":        summary,
        "all_ads_json":   all_ads_json,
        "ad_chart_data":  json.dumps(ad_chart_data),
        "insights_html":  _md_to_html(insights),
        "date_range":     date_range,
        "wow":            wow,
        "urgent_actions": urgent_actions,
    }


# ── Markdown → styled HTML ─────────────────────────────────────────────────────

_SECTION_STYLES = [
    (["sterke", "goed", "top", "winner", "schalen"],    "bi-check-circle-fill",          "#ecfdf5", "#059669"),
    (["verbeter", "under", "aandacht", "slecht", "stop", "kill"], "bi-exclamation-triangle-fill", "#fef2f2", "#dc2626"),
    (["aanbevel", "actie", "optimali", "tip", "hook", "creative"], "bi-lightbulb-fill",          "#fffbeb", "#d97706"),
    (["budget", "verdeling", "schaal", "reallocat"],    "bi-pie-chart-fill",              "#eff6ff", "#2563eb"),
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


def _load_rows_from_session() -> list | None:
    source = session.get("data_source")
    if not source:
        return None
    if source == "demo":
        return load_dummy_data()
    try:
        return parse_csv(Path(source))
    except Exception:
        logger.exception("Fout bij opnieuw laden CSV: %s", source)
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
        "hook_counts":     dict(Counter(hooks)),
        "format_counts":   dict(Counter(formats)),
        "dominant_hook":   Counter(hooks).most_common(1)[0][0] if hooks else None,
        "dominant_format": Counter(formats).most_common(1)[0][0] if formats else None,
        "drivers": drivers,
        "untested_formats": [f for f in ["ugc", "carousel", "static", "testimonial"] if f not in formats],
    }


# ── Auth routes ────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if not _auth_enabled():
        session["username"] = "dev"
        return redirect(url_for("clients"))
    if session.get("username"):
        return redirect(url_for("clients"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        users = _get_users()
        if username in users and users[username] == password:
            session.permanent = True
            session["username"] = username
            return redirect(url_for("clients"))
        return render_template("login.html", error="Gebruikersnaam of wachtwoord onjuist.")
    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Client routes ──────────────────────────────────────────────────────────────

@app.route("/debug/db")
@login_required
def debug_db():
    url_raw = os.getenv("DATABASE_URL", "")
    url_safe = ""
    if url_raw:
        # mask password for display
        import re as _re
        url_safe = _re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url_raw)
    err = db.get_connection_error()
    available = db.is_available()
    return f"""<pre style="font-family:monospace;padding:2rem;font-size:.9rem;">
DB Diagnostiek
==============
DATABASE_URL ingesteld : {'JA' if url_raw else 'NEE'}
DATABASE_URL (masked)  : {url_safe or '(leeg)'}
Pool beschikbaar       : {'JA' if available else 'NEE'}
Laatste fout           : {err or '(geen)'}
psycopg2 versie        : {_psycopg2_version()}
</pre>"""


def _psycopg2_version() -> str:
    try:
        import psycopg2
        return psycopg2.__version__
    except ImportError:
        return "NIET GEINSTALLEERD"


@app.route("/clients")
@login_required
def clients():
    try:
        client_list = db.get_clients() if db.is_available() else []
    except Exception as e:
        logger.error("DB get_clients failed: %s", e)
        flash(f"Database fout: {e}", "danger")
        client_list = []
    if not db.is_available():
        err = db.get_connection_error()
        flash(f"Database niet bereikbaar — {err} (ga naar /debug/db voor details)", "danger")
    return render_template("clients.html", clients=client_list)


@app.route("/clients/new", methods=["POST"])
@login_required
def client_new():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Naam is verplicht.", "danger")
        return redirect(url_for("clients"))
    try:
        cpl  = float(request.form["cpl_benchmark"])  if request.form.get("cpl_benchmark")  else None
        roas = float(request.form["roas_benchmark"]) if request.form.get("roas_benchmark") else None
        client_id = db.create_client(
            name=name,
            industry=request.form.get("industry", ""),
            campaign_type=request.form.get("campaign_type", "leads"),
            cpl_benchmark=cpl,
            roas_benchmark=roas,
            notes=request.form.get("notes", ""),
        )
        session["client_id"] = client_id
        flash(f"{name} aangemaakt.", "success")
        return redirect(url_for("client_profile", client_id=client_id))
    except Exception as e:
        flash(f"Fout: {e}", "danger")
        return redirect(url_for("clients"))


@app.route("/clients/<int:client_id>")
@login_required
def client_profile(client_id):
    try:
        client = db.get_client(client_id)
        if not client:
            flash("Klant niet gevonden.", "danger")
            return redirect(url_for("clients"))
        session["client_id"] = client_id
        session.pop("guest_mode", None)
        uploads      = db.get_uploads(client_id)
        shoot_briefs = db.get_shoot_briefs(client_id)
        hook_perf    = db.get_all_hook_performance(client_id)
    except Exception as e:
        logger.error("DB client_profile failed: %s", e)
        flash(f"Database fout: {e}", "danger")
        return redirect(url_for("clients"))
    return render_template("client_profile.html",
                           client=client, uploads=uploads,
                           shoot_briefs=shoot_briefs, hook_perf=hook_perf)


@app.route("/clients/<int:client_id>/edit", methods=["POST"])
@login_required
def client_edit(client_id):
    try:
        cpl  = float(request.form["cpl_benchmark"])  if request.form.get("cpl_benchmark")  else None
        roas = float(request.form["roas_benchmark"]) if request.form.get("roas_benchmark") else None
        db.update_client(
            client_id=client_id,
            name=request.form.get("name", ""),
            industry=request.form.get("industry", ""),
            campaign_type=request.form.get("campaign_type", "leads"),
            cpl_benchmark=cpl,
            roas_benchmark=roas,
            notes=request.form.get("notes", ""),
        )
        flash("Klant bijgewerkt.", "success")
    except Exception as e:
        flash(f"Fout: {e}", "danger")
    return redirect(url_for("client_profile", client_id=client_id))


@app.route("/clients/<int:client_id>/delete")
@login_required
def client_delete(client_id):
    try:
        db.delete_client(client_id)
        if session.get("client_id") == client_id:
            session.pop("client_id", None)
        flash("Klant verwijderd.", "success")
    except Exception as e:
        flash(f"Fout bij verwijderen: {e}", "danger")
    return redirect(url_for("clients"))


@app.route("/clients/<int:client_id>/load/<int:upload_id>")
@login_required
def client_load_upload(client_id, upload_id):
    """Try to reload a historical CSV and run analysis again."""
    session["client_id"] = client_id
    uploads = db.get_uploads(client_id)
    upload  = next((u for u in uploads if u["id"] == upload_id), None)
    if not upload:
        flash("Upload niet gevonden.", "danger")
        return redirect(url_for("client_profile", client_id=client_id))

    # 1. Try to load CSV content from database
    rows = None
    try:
        csv_text = db.get_upload_csv_content(upload_id)
        if csv_text:
            rows = parse_csv_string(csv_text)
            session["data_source"] = f"db:{upload_id}"
    except Exception as e:
        logger.warning("DB csv_content load failed: %s", e)

    # 2. Fall back to disk if DB content not available
    if rows is None:
        file_path = UPLOAD_FOLDER / upload["filename"] if upload.get("filename") else None
        if file_path and file_path.exists():
            try:
                rows = parse_csv(file_path)
                session["data_source"] = str(file_path)
            except Exception as e:
                logger.warning("Disk CSV load failed: %s", e)

    if rows is None:
        flash("CSV niet meer beschikbaar. Upload de export opnieuw.", "warning")
        return redirect(url_for("client_profile", client_id=client_id))

    session.permanent = True
    result = _process_df(rows,
                         campaign_type_override=upload.get("campaign_type", ""),
                         date_from=upload.get("date_from") or "",
                         date_to=upload.get("date_to") or "")
    if "error" in result:
        flash(result["error"], "danger")
        return redirect(url_for("client_profile", client_id=client_id))
    thresholds = session.get("thresholds", {"winner": 30, "mid": 50, "preset": "auto"})
    client = db.get_client(client_id)
    return render_template("index.html", result=result, demo=False,
                           thresholds=thresholds, active_client=client)


# ── Main analysis routes ───────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
@login_required
def index():
    # Redirect to client overview when there's no active context
    has_client = bool(session.get("client_id"))
    is_guest   = bool(session.get("guest_mode"))
    if not has_client and not is_guest:
        return redirect(url_for("clients"))

    client = None
    client_id = session.get("client_id")
    if client_id and db.is_available():
        try:
            client = db.get_client(client_id)
        except Exception:
            pass
    return render_template("index.html", result=None, thresholds=None, active_client=client)


@app.route("/guest")
@login_required
def guest():
    session.pop("client_id", None)
    session["guest_mode"] = True
    return redirect(url_for("index"))


@app.route("/demo", methods=["GET"])
@login_required
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
    return render_template("index.html", result=result, demo=True,
                           thresholds=thresholds, active_client=None)


@app.route("/upload", methods=["POST"])
@login_required
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
        flash(f"CSV bevat {len(rows):,} rijen — maximum is {max_rows:,}.", "danger")
        return redirect(url_for("index"))

    # Read raw text for persistent storage in DB
    try:
        csv_text = save_path.read_text(encoding="utf-8-sig")
    except Exception:
        csv_text = None

    campaign_type_override = request.form.get("campaign_type_override", "")
    thresholds = _compute_thresholds(request.form)
    result = _process_df(rows, campaign_type_override=campaign_type_override,
                         csv_content=csv_text)
    if "error" in result:
        flash(result["error"], "danger")
        return redirect(url_for("index"))

    session.permanent = True
    session["data_source"] = str(save_path)
    session["thresholds"] = thresholds

    client = None
    client_id = session.get("client_id")
    if client_id and db.is_available():
        try:
            client = db.get_client(client_id)
        except Exception:
            pass

    return render_template("index.html", result=result, demo=False,
                           thresholds=thresholds, active_client=client)


@app.route("/reanalyze", methods=["POST"])
@login_required
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

    client = None
    client_id = session.get("client_id")
    if client_id and db.is_available():
        try:
            client = db.get_client(client_id)
        except Exception:
            pass

    return render_template("index.html", result=result, demo=False,
                           thresholds=thresholds, active_client=client)


@app.route("/export/pdf", methods=["GET"])
@login_required
def export_pdf():
    summary_data = session.get("summary")
    insights_raw = session.get("insights", "Geen inzichten beschikbaar.")
    if not summary_data:
        flash("Geen actieve analyse. Upload eerst een CSV.", "warning")
        return redirect(url_for("index"))
    summary   = _session_to_summary(summary_data)
    top_ads   = session.get("top_ads", [])
    date_range = session.get("date_range")
    pdf_bytes = generate_pdf(summary, insights_raw, top_ads=top_ads, date_range=date_range)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="meta_ads_rapport.pdf",
    )


@app.route("/creative", methods=["GET"])
@login_required
def creative():
    summary_data = session.get("summary")
    if not summary_data:
        flash("Geen actieve analyse. Upload eerst een CSV.", "warning")
        return redirect(url_for("index"))

    rows = _load_rows_from_session()
    if rows is None:
        flash("Het bestand kon niet worden geladen. Upload je CSV opnieuw.", "warning")
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
            axes    = map_axes(decoded, ad.ad_name, all_ads=all_ads)
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

    patterns   = _extract_patterns(winner_results)
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


@app.route("/hooks", methods=["GET"])
@login_required
def hooks():
    summary_data = session.get("summary")
    if not summary_data:
        flash("Geen actieve analyse. Upload eerst een CSV.", "warning")
        return redirect(url_for("index"))

    rows = _load_rows_from_session()
    if rows is None:
        flash("Het bestand kon niet worden geladen. Upload je CSV opnieuw.", "warning")
        return redirect(url_for("index"))

    campaigns = build_campaigns(rows)
    summary   = build_summary(rows, campaigns)
    all_ads   = sorted(get_all_ads(campaigns), key=lambda a: a.spend, reverse=True)

    hook_perf        = aggregate_hook_performance(all_ads)
    fmt_perf         = aggregate_format_performance(all_ads)
    combos           = get_winning_combinations(all_ads)
    untested_hooks   = get_untested_hooks(all_ads)
    untested_formats = get_untested_formats(all_ads)

    top_ad = next((a for a in all_ads if a.results > 0 and a.cost_per_result > 0), None)
    shoot_brief = generate_shoot_brief(summary, all_ads, top_ad=top_ad)

    # Save shoot brief to DB if client is active
    client_id = session.get("client_id")
    upload_id = session.get("upload_id")
    if client_id and db.is_available():
        try:
            db.save_shoot_brief(client_id, upload_id, shoot_brief)
        except Exception as e:
            logger.warning("Shoot brief save failed: %s", e)

    return render_template(
        "hooks.html",
        summary=summary,
        hook_perf=hook_perf,
        fmt_perf=fmt_perf,
        combos=combos,
        untested_hooks=untested_hooks,
        untested_formats=untested_formats,
        shoot_brief=shoot_brief,
        is_demo=session.get("data_source") == "demo",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
