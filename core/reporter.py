import io
import re
from datetime import date
from fpdf import FPDF
from models.campaign import AnalysisSummary

_REPLACEMENTS = {
    "—": "-", "–": "-", "‒": "-",
    "'": "'", "'": "'", """: '"', """: '"',
    "•": "-", "…": "...", "€": "EUR",
    "\xe9": "e", "\xe8": "e", "\xea": "e", "\xeb": "e",
    "\xe0": "a", "\xe2": "a", "\xe4": "a",
    "\xfc": "u", "\xfb": "u", "\xf9": "u",
    "\xf6": "o", "\xf4": "o",
    "\xee": "i", "\xef": "i",
    "\xe7": "c",
}


def _t(text: str) -> str:
    for char, replacement in _REPLACEMENTS.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class _PDF(FPDF):
    def header(self):
        self.set_fill_color(10, 37, 64)
        self.rect(0, 0, 210, 18, "F")
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 4)
        self.cell(0, 10, _t("Meta Ads Rapport — SLN Solutions"), align="L")
        self.set_font("Helvetica", "", 9)
        self.set_xy(0, 4)
        self.cell(200, 10, date.today().strftime("%d-%m-%Y"), align="R")
        self.set_text_color(0, 0, 0)
        self.ln(16)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Pagina {self.page_no()} - Meta Ads Analyzer", align="C")
        self.set_text_color(0, 0, 0)


def _kpi_box(pdf: _PDF, label: str, value: str, x: float, y: float,
             w: float = 44, good: bool | None = None):
    fill_r, fill_g, fill_b = 240, 242, 245
    if good is True:
        fill_r, fill_g, fill_b = 209, 250, 229
    elif good is False:
        fill_r, fill_g, fill_b = 254, 226, 226
    pdf.set_fill_color(fill_r, fill_g, fill_b)
    pdf.rect(x, y, w, 18, "F")
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.set_xy(x + 2, y + 2)
    pdf.cell(w - 4, 5, _t(label.upper()))
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(10, 37, 64)
    pdf.set_xy(x + 2, y + 7)
    pdf.cell(w - 4, 8, _t(value))
    pdf.set_text_color(0, 0, 0)


def _section(pdf: _PDF, title: str):
    pdf.set_fill_color(24, 58, 92)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, _t(f"  {title}"), fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


def _strip_md(text: str) -> str:
    text = re.sub(r"#{1,4}\s*", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"> ", "", text)
    return _t(text).strip()


def generate_pdf(summary: AnalysisSummary, insights: str,
                 top_ads: list | None = None,
                 date_range: dict | None = None) -> bytes:
    pdf = _PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    is_leads = summary.campaign_type != "purchases"
    metric_label = summary.metric_label
    result_label = summary.result_label

    # ── Periode ──────────────────────────────────────────────────────────────
    if date_range and date_range.get("from"):
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, _t(f"Periode: {date_range['from']} t/m {date_range['to']}"), ln=True)
        pdf.ln(2)
        pdf.set_text_color(0, 0, 0)

    # ── KPI's ─────────────────────────────────────────────────────────────────
    _section(pdf, "Overzicht KPI's")
    y = pdf.get_y()
    _kpi_box(pdf, "Totaal Budget",   f"EUR {summary.total_spend:,.0f}", 10, y)
    _kpi_box(pdf, f"Gem. {metric_label}",
             f"EUR {summary.avg_cost_per_result:.2f}" if is_leads else f"{summary.avg_roas:.2f}",
             56, y)
    _kpi_box(pdf, "Gem. CTR",    f"{summary.avg_ctr:.2f}%",   102, y)
    _kpi_box(pdf, result_label,  str(summary.total_results),  148, y)
    pdf.ln(24)

    y2 = pdf.get_y()
    _kpi_box(pdf, "Impressies",  f"{summary.total_impressions:,}",     10,  y2)
    _kpi_box(pdf, "Gem. CPM",   f"EUR {summary.avg_cpm:.2f}",         56,  y2)
    _kpi_box(pdf, "Gem. CPC",   f"EUR {summary.avg_cpc:.2f}",         102, y2)
    _kpi_box(pdf, "Gem. Freq.", f"{summary.avg_frequency:.1f}",        148, y2)
    pdf.ln(26)

    # ── Campagne tabel ────────────────────────────────────────────────────────
    _section(pdf, "Campagne Prestaties")
    col_w = [70, 22, 22, 18, 22, 26]
    headers = ["Campagne", "Budget", metric_label, "CTR", result_label, "Gem. Freq."]
    pdf.set_fill_color(220, 230, 245)
    pdf.set_font("Helvetica", "B", 8)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align="L" if i == 0 else "R")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for idx, c in enumerate(summary.campaigns):
        fill = idx % 2 == 0
        pdf.set_fill_color(248, 249, 250) if fill else pdf.set_fill_color(255, 255, 255)
        name    = _t(c.campaign_name[:36] + "..." if len(c.campaign_name) > 36 else c.campaign_name)
        m_val   = f"EUR {c.cost_per_result:.2f}" if is_leads and c.cost_per_result > 0 \
                  else (f"{c.roas:.2f}" if not is_leads and c.roas > 0 else "-")
        freq_s  = f"{c.frequency:.1f}" if c.frequency > 0 else "-"
        row = [name, f"EUR {c.spend:,.0f}", m_val, f"{c.ctr:.2f}%", str(c.results), freq_s]
        for i, val in enumerate(row):
            pdf.cell(col_w[i], 6, val, border=1, fill=fill, align="L" if i == 0 else "R")
        pdf.ln()
    pdf.ln(6)

    # ── Top 10 advertenties ───────────────────────────────────────────────────
    if top_ads:
        _section(pdf, f"Top Advertenties (op spend) — {metric_label} per ad")
        ad_cols = [68, 22, 24, 18, 22, 26]
        ad_hdrs = ["Advertentie", "Budget", metric_label, "CTR", result_label, "Freq."]
        pdf.set_fill_color(220, 230, 245)
        pdf.set_font("Helvetica", "B", 8)
        for i, h in enumerate(ad_hdrs):
            pdf.cell(ad_cols[i], 7, h, border=1, fill=True, align="L" if i == 0 else "R")
        pdf.ln()

        pdf.set_font("Helvetica", "", 7)
        for idx, a in enumerate(top_ads):
            fill = idx % 2 == 0
            pdf.set_fill_color(248, 249, 250) if fill else pdf.set_fill_color(255, 255, 255)
            name = _t(a["ad_name"][:38] + "..." if len(a["ad_name"]) > 38 else a["ad_name"])
            cpr  = a.get("cost_per_result", 0)
            roas = a.get("roas", 0)
            m_val = f"EUR {cpr:.2f}" if is_leads and cpr > 0 \
                    else (f"{roas:.2f}" if not is_leads and roas > 0 else "-")
            freq = a.get("frequency", 0)
            freq_s = f"{freq:.1f}" if freq > 0 else "-"
            # Highlight frequency warning
            if freq > 3.5:
                pdf.set_text_color(180, 0, 0)
                freq_s += "!"
            row = [name, f"EUR {a['spend']:,.0f}", m_val,
                   f"{a.get('ctr', 0):.2f}%", str(a.get("results", 0)), freq_s]
            for i, val in enumerate(row):
                pdf.cell(ad_cols[i], 5, val, border=1, fill=fill,
                         align="L" if i == 0 else "R")
            pdf.set_text_color(0, 0, 0)
            pdf.ln()
        pdf.ln(6)

    # ── AI Analyse ────────────────────────────────────────────────────────────
    _section(pdf, "AI Analyse & Aanbevelingen")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, _strip_md(insights))

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ── Shoot Brief PDF ───────────────────────────────────────────────────────────

_TYPE_COLORS = {
    "bewezen":   (16,  185, 129),
    "test":      (59,  130, 246),
    "wild_card": (245, 158,  11),
    "testimonial":(139, 92, 246),
    "short":     (245, 158,  11),
}

_TYPE_LABELS = {
    "bewezen":    "BEWEZEN",
    "test":       "TEST",
    "wild_card":  "WILD CARD",
    "testimonial":"TESTIMONIAL",
    "short":      "SHORT 15s",
}

_HOOK_NL = {
    "recognition":   "Herkenning",
    "frustration":   "Frustratie",
    "curiosity":     "Nieuwsgierigheid",
    "proof":         "Bewijs",
    "promise":       "Belofte",
    "confrontation": "Confrontatie",
    "urgency":       "Urgentie",
    "problem_solve": "Probleem-oplossing",
    "social_proof":  "Sociale bewijskracht",
    "educational":   "Educatief",
}


class _ShootBriefPDF(FPDF):
    def __init__(self, client_name: str = ""):
        super().__init__()
        self._client_name = client_name

    def header(self):
        self.set_fill_color(255, 92, 43)
        self.rect(0, 0, 210, 16, "F")
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 3)
        title = _t(f"Shoot Brief{' — ' + self._client_name if self._client_name else ''}")
        self.cell(140, 10, title, align="L")
        self.set_font("Helvetica", "", 8)
        self.set_xy(0, 4)
        self.cell(200, 8, date.today().strftime("%d-%m-%Y"), align="R")
        self.set_text_color(0, 0, 0)
        self.ln(14)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Pagina {self.page_no()} - Shoot Brief SLN Solutions", align="C")
        self.set_text_color(0, 0, 0)


def _sb_section_title(pdf: _ShootBriefPDF, title: str):
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 7, _t(f"  {title}"), fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _sb_script_block(pdf: _ShootBriefPDF, s: dict):
    stype = s.get("type", "bewezen")
    r, g, b = _TYPE_COLORS.get(stype, (100, 100, 100))
    type_label = _TYPE_LABELS.get(stype, stype.upper())
    hook = s.get("hook_type", "")
    hook_nl = _HOOK_NL.get(hook, hook).replace("_", " ")
    nummer = s.get("nummer", "")
    regel = s.get("regel", "")
    naam = _t(str(s.get("naam", "")))
    logica = _t(str(s.get("logica", "")))

    # Colored top bar
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    bar_text = _t(f"  Script {nummer}  -  {regel}  -  {type_label}  -  {hook_nl}")
    pdf.cell(0, 6, bar_text, fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)

    # Name + logica
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_x(10)
    pdf.cell(0, 5, naam, ln=True)
    if logica:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(10)
        pdf.cell(0, 4, logica, ln=True)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # Tijdcodes table
    tijdcodes = s.get("tijdcodes")
    if tijdcodes and isinstance(tijdcodes, dict):
        pdf.set_fill_color(241, 245, 249)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(10)
        pdf.cell(190, 5, "TIJDCODES", fill=True, ln=True)
        pdf.set_text_color(0, 0, 0)
        for tijd, tekst in tijdcodes.items():
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(r, g, b)
            pdf.set_x(10)
            pdf.cell(20, 5, _t(str(tijd)), border="B")
            pdf.set_text_color(30, 41, 59)
            pdf.set_font("Helvetica", "", 8)
            # Use multi_cell for wrapping, but we need to handle position manually
            x_after = 30
            pdf.set_xy(x_after, pdf.get_y())
            # Check remaining width
            pdf.multi_cell(170, 5, _t(str(tekst)), border="B")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    # Volledig script (collapsed in print — shown small)
    volledig = s.get("volledig_script")
    if volledig:
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(10)
        pdf.cell(0, 4, "VOLLEDIG SCRIPT", ln=True)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(55, 65, 81)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_x(10)
        pdf.multi_cell(190, 4, _t(str(volledig)), fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    # CTA
    cta = s.get("cta")
    if cta:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(255, 92, 43)
        pdf.set_x(10)
        pdf.cell(0, 5, _t(f"CTA: {cta}"), ln=True)
        pdf.set_text_color(0, 0, 0)

    pdf.ln(5)


def _sb_testimonial_block(pdf: _ShootBriefPDF, t: dict):
    r, g, b = _TYPE_COLORS["testimonial"]
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 6, _t("  Script 11  -  APART  -  TESTIMONIAL INTERVIEW"), fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)

    logica = _t(str(t.get("logica", "")))
    if logica:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(10)
        pdf.cell(0, 5, logica, ln=True)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

    vragen = t.get("vragen", [])
    if vragen:
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(10)
        pdf.cell(0, 4, "INTERVIEWVRAGEN", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 8.5)
        for i, v in enumerate(vragen, 1):
            pdf.set_x(10)
            pdf.multi_cell(190, 5, _t(f"{i}. {v}"))
    pdf.ln(5)


def _sb_shorts_section(pdf: _ShootBriefPDF, shorts: list[dict]):
    _sb_section_title(pdf, f"Short Scripts 15s ({len(shorts)}x)")
    for s in shorts:
        r, g, b = _TYPE_COLORS["short"]
        hook = s.get("hook_type", "")
        hook_nl = _HOOK_NL.get(hook, hook).replace("_", " ")
        naam = _t(str(s.get("naam", "")))
        opening = _t(str(s.get("openingszin", "")))
        kern = _t(str(s.get("kernbelofte", "")))
        cta = _t(str(s.get("cta", "")))

        pdf.set_fill_color(255, 251, 235)
        pdf.set_draw_color(r, g, b)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(r, g, b)
        pdf.set_x(10)
        pdf.cell(190, 5, f"  {naam}  -  {hook_nl}", fill=True, border="L", ln=True)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_text_color(0, 0, 0)

        # Three time slots inline
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(r, g, b)
        pdf.set_x(10)
        pdf.cell(15, 4, "0-3s:")
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(175, 4, opening)

        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(r, g, b)
        pdf.set_x(10)
        pdf.cell(15, 4, "3-10s:")
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(175, 4, kern)

        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(255, 92, 43)
        pdf.set_x(10)
        pdf.cell(15, 4, "10-15s:")
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(175, 4, cta)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(3)


def _sb_broll_section(pdf: _ShootBriefPDF, broll: dict):
    _sb_section_title(pdf, "B-Roll Lijst (afvinkbaar tijdens shoot)")
    pdf.set_font("Helvetica", "", 8.5)
    for categorie, shots in broll.items():
        if not shots:
            continue
        cat_label = _t(categorie.replace("_", " ").title())
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(10)
        pdf.cell(0, 5, cat_label.upper(), ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 8.5)
        for shot in shots:
            pdf.set_x(10)
            pdf.multi_cell(190, 5, _t(f"[ ]  {shot}"))
        pdf.ln(2)


def generate_shoot_brief_pdf(scripts: list[dict], client_name: str = "") -> bytes:
    long_scripts = [s for s in scripts if s.get("type") in ("bewezen", "test", "wild_card")]
    testimonials = [s for s in scripts if s.get("type") == "testimonial"]
    shorts       = [s for s in scripts if s.get("type") == "short"]
    brolls       = [s for s in scripts if s.get("type") == "broll"]

    pdf = _ShootBriefPDF(client_name)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    if long_scripts:
        _sb_section_title(pdf, f"Video Scripts ({len(long_scripts)}x)")
        for s in long_scripts:
            _sb_script_block(pdf, s)

    for t in testimonials:
        _sb_testimonial_block(pdf, t)

    if shorts:
        _sb_shorts_section(pdf, shorts)

    for b in brolls:
        if b.get("broll"):
            pdf.add_page()
            _sb_broll_section(pdf, b["broll"])

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
