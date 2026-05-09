"""
Hook & format intelligence derived entirely from ad names — no API calls needed.
Parses naming conventions SLN uses in shoots (V1/V2, hook codes, format tags).
"""
from __future__ import annotations
import re
from collections import defaultdict
from models.campaign import Ad


# ── Taxonomies ────────────────────────────────────────────────────────────────

HOOK_TYPES = [
    "recognition",    # "Ken jij dit gevoel...", "Herken jij..."
    "frustration",    # "Ziek van...", "Moe van...", "Ben jij ook..."
    "curiosity",      # "Wist je dat...", "Dit weten weinigen..."
    "proof",          # "Klant resultaat", "testimonial", "review", "case"
    "promise",        # "Resultaat in X weken", "Zo bereik je..."
    "confrontation",  # "Stop met...", "Waarom je nog steeds niet..."
    "urgency",        # "Nog X plekken", "Laatste kans", "deadline"
    "problem_solve",  # "Zo los je op", "Oplossing voor", "Fix"
    "social_proof",   # "500+ klanten", "Als gezien op", "#1 in"
    "educational",    # "Hoe werkt", "Tutorial", "Uitleg", "Gids"
]

FORMAT_TYPES = [
    "talking_head",   # Presenter speaks to camera
    "testimonial",    # Client/customer on camera
    "ugc",            # User generated content style
    "problem_solve",  # Show problem then solution
    "story",          # Narrative arc
    "carousel",       # Multiple images/slides
    "static",         # Single image
    "reels",          # Short-form vertical video (≤60s)
    "product_demo",   # Product shown in use
    "before_after",   # Transformation comparison
    "animation",      # Motion graphics or illustrated
]

# Keyword → hook type
_HOOK_KEYWORDS: list[tuple[list[str], str]] = [
    (["herken", "ken jij", "ken je", "herkenbaar", "zoals jij"], "recognition"),
    (["ziek van", "moe van", "gefrustreerd", "frustratie", "irritant", "tired of", "fed up"], "frustration"),
    (["wist je", "weet je dat", "weinigen weten", "geheim", "secret", "did you know"], "curiosity"),
    (["klant", "testimonial", "review", "case", "resultaat van", "zo deed", "ervaringen"], "proof"),
    (["resultaat in", "binnen", "weken", "dagen", "maanden", "belofte", "guarantee", "garanderen"], "promise"),
    (["stop met", "waarom nog steeds", "fout die", "misschien doe je", "confrontatie"], "confrontation"),
    (["laatste kans", "nog maar", "deadline", "beperkt", "limited", "urgentie", "vandaag nog"], "urgency"),
    (["oplossing", "zo los je", "fix", "hoe je", "stap voor stap", "probleem opgelost"], "problem_solve"),
    (["500+", "1000+", "klanten", "#1", "als gezien", "vertrouwd door", "meest gekozen"], "social_proof"),
    (["hoe werkt", "tutorial", "uitleg", "gids", "leer hoe", "alles over", "wat is"], "educational"),
]

# Keyword → format type
_FORMAT_KEYWORDS: list[tuple[list[str], str]] = [
    (["testimonial", "klantreview", "ervaringen", "client", "getuigenis"], "testimonial"),
    (["ugc", "user generated", "authentiek", "organic"], "ugc"),
    (["before after", "voor na", "transformatie", "vergelijking"], "before_after"),
    (["demo", "product demo", "in gebruik", "product shot"], "product_demo"),
    (["carousel", "slides", "meerdere afbeeldingen"], "carousel"),
    (["static", "afbeelding", "image", "banner", "foto"], "static"),
    (["animatie", "animation", "motion", "geanimeerd"], "animation"),
    (["reels", "short", "60s", "30s", "15s"], "reels"),
    (["story", "verhaal", "narrative", "achtergrond"], "story"),
    (["talking head", "to camera", "direct"], "talking_head"),
    (["probleem oplossing", "problem solve", "voor en na"], "problem_solve"),
]

# Version pattern: V1, V2, V3, v1, version 1, hook 1, etc.
_VERSION_RE = re.compile(r"\b[vV](\d+)\b|\bversie\s*(\d+)\b|\bhook\s*(\d+)\b", re.IGNORECASE)


# ── Detection helpers ─────────────────────────────────────────────────────────

def detect_hook(ad_name: str) -> str:
    lower = ad_name.lower()
    for keywords, hook_type in _HOOK_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return hook_type
    if "?" in ad_name:
        return "curiosity"
    return "unknown"


def detect_format(ad_name: str) -> str:
    lower = ad_name.lower()
    for keywords, fmt in _FORMAT_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return fmt
    return "talking_head"  # SLN default


def detect_version(ad_name: str) -> int | None:
    m = _VERSION_RE.search(ad_name)
    if m:
        v = m.group(1) or m.group(2) or m.group(3)
        return int(v)
    return None


# ── Aggregate performance ─────────────────────────────────────────────────────

def _perf_record() -> dict:
    return {"ads": 0, "spend": 0.0, "results": 0, "ctr_sum": 0.0, "ctr_count": 0}


def _add_to(rec: dict, ad: Ad) -> None:
    rec["ads"] += 1
    rec["spend"] += ad.spend
    rec["results"] += ad.results
    if ad.ctr > 0:
        rec["ctr_sum"] += ad.ctr
        rec["ctr_count"] += 1


def _finalize(rec: dict) -> dict:
    sp = rec["spend"]
    res = rec["results"]
    ctr_count = rec["ctr_count"]
    return {
        "ads": rec["ads"],
        "spend": round(sp, 2),
        "results": res,
        "cpl": round(sp / res, 2) if res > 0 else None,
        "avg_ctr": round(rec["ctr_sum"] / ctr_count, 2) if ctr_count > 0 else None,
    }


def aggregate_hook_performance(ads: list[Ad]) -> list[dict]:
    buckets: dict[str, dict] = defaultdict(_perf_record)
    for ad in ads:
        hook = detect_hook(ad.ad_name)
        _add_to(buckets[hook], ad)
    rows = []
    for hook, rec in buckets.items():
        row = {"hook_type": hook}
        row.update(_finalize(rec))
        rows.append(row)
    rows.sort(key=lambda r: (r["cpl"] is None, r["cpl"] or 0))
    return rows


def aggregate_format_performance(ads: list[Ad]) -> list[dict]:
    buckets: dict[str, dict] = defaultdict(_perf_record)
    for ad in ads:
        fmt = detect_format(ad.ad_name)
        _add_to(buckets[fmt], ad)
    rows = []
    for fmt, rec in buckets.items():
        row = {"format_type": fmt}
        row.update(_finalize(rec))
        rows.append(row)
    rows.sort(key=lambda r: (r["cpl"] is None, r["cpl"] or 0))
    return rows


def get_winning_combinations(ads: list[Ad], top_n: int = 3) -> list[dict]:
    buckets: dict[tuple[str, str], dict] = defaultdict(_perf_record)
    for ad in ads:
        key = (detect_hook(ad.ad_name), detect_format(ad.ad_name))
        _add_to(buckets[key], ad)
    combos = []
    for (hook, fmt), rec in buckets.items():
        fin = _finalize(rec)
        if fin["results"] > 0:
            combos.append({"hook_type": hook, "format_type": fmt, **fin})
    combos.sort(key=lambda r: (r["cpl"] is None, r["cpl"] or 0))
    return combos[:top_n]


def get_untested_hooks(ads: list[Ad]) -> list[str]:
    tested = {detect_hook(a.ad_name) for a in ads}
    return [h for h in HOOK_TYPES if h not in tested and h != "unknown"]


def get_untested_formats(ads: list[Ad]) -> list[str]:
    tested = {detect_format(a.ad_name) for a in ads}
    return [f for f in FORMAT_TYPES if f not in tested]


def get_version_distribution(ads: list[Ad]) -> dict[str, int]:
    """Count how many V1/V2/V3+ ads each hook type has tested."""
    versions: dict[str, int] = defaultdict(int)
    for ad in ads:
        v = detect_version(ad.ad_name)
        if v:
            hook = detect_hook(ad.ad_name)
            versions[hook] = max(versions[hook], v)
    return dict(versions)
