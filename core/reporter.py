import io
import re
from datetime import date
from fpdf import FPDF
from models.campaign import AnalysisSummary

_REPLACEMENTS = {
    "—": "-", "–": "-", "‒": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
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
        self.cell(0, 10, "Meta Ads Rapport", align="L")
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


def _kpi_box(pdf: _PDF, label: str, value: str, x: float, y: float, w: float = 44):
    pdf.set_fill_color(240, 242, 245)
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
    pdf.set_fill_color(24, 119, 242)
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


def generate_pdf(summary: AnalysisSummary, insights: str) -> bytes:
    pdf = _PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    _section(pdf, "Overzicht KPI's")
    y = pdf.get_y()
    _kpi_box(pdf, "Totaal Budget", f"EUR {summary.total_spend:,.0f}", 10, y)
    _kpi_box(pdf, "Gem. ROAS", f"{summary.avg_roas:.2f}", 56, y)
    _kpi_box(pdf, "Gem. CTR", f"{summary.avg_ctr:.2f}%", 102, y)
    _kpi_box(pdf, "Resultaten", str(summary.total_results), 148, y)
    pdf.ln(24)

    y2 = pdf.get_y()
    _kpi_box(pdf, "Impressies", f"{summary.total_impressions:,}", 10, y2)
    _kpi_box(pdf, "Gem. CPM", f"EUR {summary.avg_cpm:.2f}", 56, y2)
    _kpi_box(pdf, "Gem. CPC", f"EUR {summary.avg_cpc:.2f}", 102, y2)
    _kpi_box(pdf, "Kosten/Resultaat", f"EUR {summary.avg_cost_per_result:.2f}", 148, y2)
    pdf.ln(26)

    _section(pdf, "Campagne Prestaties")
    col_w = [72, 22, 20, 18, 22, 26]
    headers = ["Campagne", "Budget", "ROAS", "CTR", "Resultaten", "Kosten/Res."]
    pdf.set_fill_color(220, 230, 245)
    pdf.set_font("Helvetica", "B", 8)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align="L" if i == 0 else "R")
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for idx, c in enumerate(summary.campaigns):
        fill = idx % 2 == 0
        pdf.set_fill_color(248, 249, 250) if fill else pdf.set_fill_color(255, 255, 255)
        name = _t(c.campaign_name[:38] + "..." if len(c.campaign_name) > 38 else c.campaign_name)
        roas_str = f"{c.roas:.2f}" if c.roas > 0 else "-"
        cpr_str = f"EUR {c.cost_per_result:.2f}" if c.cost_per_result > 0 else "-"
        row = [name, f"EUR {c.spend:,.0f}", roas_str, f"{c.ctr:.2f}%", str(c.results), cpr_str]
        for i, val in enumerate(row):
            pdf.cell(col_w[i], 6, val, border=1, fill=fill, align="L" if i == 0 else "R")
        pdf.ln()
    pdf.ln(6)

    _section(pdf, "AI Analyse & Aanbevelingen")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, _strip_md(insights))

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
