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

# ── Structured name parser ─────────────────────────────────────────────────────
# Convention: "Format - Hook - V# - Beschrijving"

_STRUCTURED_FORMAT_MAP: dict[str, str] = {
    "static":        "static",
    "short":         "reels",
    "reel":          "reels",
    "reels":         "reels",
    "ugc":           "ugc",
    "testimonial":   "testimonial",
    "carousel":      "carousel",
    "talking head":  "talking_head",
    "th":            "talking_head",
    "animation":     "animation",
    "before after":  "before_after",
    "product demo":  "product_demo",
    "demo":          "product_demo",
}

_STRUCTURED_HOOK_MAP: dict[str, str] = {
    "proof":          "proof",
    "promise":        "promise",
    "frustration":    "frustration",
    "frust":          "frustration",
    "recognition":    "recognition",
    "recog":          "recognition",
    "curiosity":      "curiosity",
    "curio":          "curiosity",
    "social proof":   "social_proof",
    "social_proof":   "social_proof",   # underscore variant
    "social":         "social_proof",
    "problem solve":  "problem_solve",
    "problem_solve":  "problem_solve",  # underscore variant
    "problem":        "problem_solve",
    "educational":    "educational",
    "edu":            "educational",
    "confrontation":  "confrontation",
    "confr":          "confrontation",
    "urgency":        "urgency",
}

_parsed_cache: dict[str, dict] = {}


def parse_ad_name(ad_name: str) -> dict:
    """
    Parse a structured ad name: "Format - Hook - V# - Beschrijving"
    Returns {hook, format, version, description, structured}.
    Falls back to keyword matching when the name doesn't follow the convention.
    """
    if ad_name in _parsed_cache:
        return _parsed_cache[ad_name]

    parts = [p.strip() for p in ad_name.split(" - ")]
    result = None

    if len(parts) >= 3:
        fmt_key  = parts[0].lower()
        hook_key = parts[1].lower()
        fmt  = _STRUCTURED_FORMAT_MAP.get(fmt_key)
        hook = _STRUCTURED_HOOK_MAP.get(hook_key)

        if fmt and hook:
            version = None
            desc_start = 2
            v_match = re.match(r"[vV](\d+)$", parts[2])
            if v_match:
                version = int(v_match.group(1))
                desc_start = 3
            description = " - ".join(parts[desc_start:]) if len(parts) > desc_start else ""
            result = {
                "hook": hook,
                "format": fmt,
                "version": version,
                "description": description,
                "structured": True,
            }

    if result is None:
        # Keyword fallback
        lower = ad_name.lower()
        hook = "unknown"
        for keywords, hook_type in _HOOK_KEYWORDS:
            if any(kw in lower for kw in keywords):
                hook = hook_type
                break
        if hook == "unknown" and "?" in ad_name:
            hook = "curiosity"

        fmt = "talking_head"
        for keywords, fmt_type in _FORMAT_KEYWORDS:
            if any(kw in lower for kw in keywords):
                fmt = fmt_type
                break

        m = _VERSION_RE.search(ad_name)
        version = int(m.group(1) or m.group(2) or m.group(3)) if m else None

        result = {
            "hook": hook,
            "format": fmt,
            "version": version,
            "description": ad_name,
            "structured": False,
        }

    _parsed_cache[ad_name] = result
    return result


# ── Detection helpers (thin wrappers around parse_ad_name) ───────────────────

def detect_hook(ad_name: str) -> str:
    return parse_ad_name(ad_name)["hook"]


def detect_format(ad_name: str) -> str:
    return parse_ad_name(ad_name)["format"]


def detect_version(ad_name: str) -> int | None:
    return parse_ad_name(ad_name)["version"]


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


def _resolve_hook(ad_name: str, overrides: dict) -> str:
    return overrides.get(ad_name, {}).get("hook") or detect_hook(ad_name)


def _resolve_format(ad_name: str, overrides: dict) -> str:
    return overrides.get(ad_name, {}).get("format") or detect_format(ad_name)


def aggregate_hook_performance(ads: list[Ad], overrides: dict | None = None) -> list[dict]:
    overrides = overrides or {}
    buckets: dict[str, dict] = defaultdict(_perf_record)
    for ad in ads:
        hook = _resolve_hook(ad.ad_name, overrides)
        _add_to(buckets[hook], ad)
    rows = []
    for hook, rec in buckets.items():
        row = {"hook_type": hook}
        row.update(_finalize(rec))
        rows.append(row)
    rows.sort(key=lambda r: (r["cpl"] is None, r["cpl"] or 0))
    return rows


def aggregate_format_performance(ads: list[Ad], overrides: dict | None = None) -> list[dict]:
    overrides = overrides or {}
    buckets: dict[str, dict] = defaultdict(_perf_record)
    for ad in ads:
        fmt = _resolve_format(ad.ad_name, overrides)
        _add_to(buckets[fmt], ad)
    rows = []
    for fmt, rec in buckets.items():
        row = {"format_type": fmt}
        row.update(_finalize(rec))
        rows.append(row)
    rows.sort(key=lambda r: (r["cpl"] is None, r["cpl"] or 0))
    return rows


def get_winning_combinations(ads: list[Ad], top_n: int = 3, overrides: dict | None = None) -> list[dict]:
    overrides = overrides or {}
    buckets: dict[tuple[str, str], dict] = defaultdict(_perf_record)
    for ad in ads:
        key = (_resolve_hook(ad.ad_name, overrides), _resolve_format(ad.ad_name, overrides))
        _add_to(buckets[key], ad)
    combos = []
    for (hook, fmt), rec in buckets.items():
        fin = _finalize(rec)
        if fin["results"] > 0:
            combos.append({"hook_type": hook, "format_type": fmt, **fin})
    combos.sort(key=lambda r: (r["cpl"] is None, r["cpl"] or 0))
    return combos[:top_n]


def get_untested_hooks(ads: list[Ad], overrides: dict | None = None) -> list[str]:
    overrides = overrides or {}
    tested = {_resolve_hook(a.ad_name, overrides) for a in ads}
    return [h for h in HOOK_TYPES if h not in tested and h != "unknown"]


def get_untested_formats(ads: list[Ad], overrides: dict | None = None) -> list[str]:
    overrides = overrides or {}
    tested = {_resolve_format(a.ad_name, overrides) for a in ads}
    return [f for f in FORMAT_TYPES if f not in tested]


def get_unknown_ads(ads: list[Ad], overrides: dict | None = None) -> list[dict]:
    """Return unique ads with hook=unknown that are not in overrides, sorted by spend desc."""
    overrides = overrides or {}
    seen: set[str] = set()
    result = []
    for ad in sorted(ads, key=lambda a: a.spend, reverse=True):
        if ad.ad_name in seen:
            continue
        seen.add(ad.ad_name)
        if ad.ad_name not in overrides and detect_hook(ad.ad_name) == "unknown" and ad.spend > 0:
            result.append({
                "ad_name": ad.ad_name,
                "campaign_name": ad.campaign_name,
                "spend": round(ad.spend, 2),
                "results": ad.results,
            })
    return result[:30]


def get_version_distribution(ads: list[Ad]) -> dict[str, int]:
    """Count how many V1/V2/V3+ ads each hook type has tested."""
    versions: dict[str, int] = defaultdict(int)
    for ad in ads:
        v = detect_version(ad.ad_name)
        if v:
            hook = detect_hook(ad.ad_name)
            versions[hook] = max(versions[hook], v)
    return dict(versions)
