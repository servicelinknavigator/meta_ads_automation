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
        self.cell(0, 10, "Meta Ads Rapport — SLN Solutions", align="L")
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
