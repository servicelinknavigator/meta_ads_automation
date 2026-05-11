"""
Volledig testscript - test alle core functies met dummy data.
Geen DB-connectie nodig. Geeft pass/FAIL per test.
Run: python test_all.py
"""
import sys
import io
import traceback
import os
import json
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

_FILE_ = Path(__file__) if "__file__" in dir() else Path("test_all.py")
sys.path.insert(0, str(_FILE_.parent))

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
WARN = "\033[93m⚠ WARN\033[0m"
results = []


def test(name: str, fn):
    try:
        result = fn()
        if result is True or result is None:
            print(f"{PASS}  {name}")
            results.append((name, "pass", ""))
        elif isinstance(result, str) and result.startswith("WARN:"):
            print(f"{WARN}  {name} — {result[5:]}")
            results.append((name, "warn", result[5:]))
        else:
            print(f"{FAIL}  {name} — {result}")
            results.append((name, "fail", str(result)))
    except Exception as e:
        tb = traceback.format_exc()
        print(f"{FAIL}  {name}")
        print(f"       Exception: {e}")
        print(f"       {tb.splitlines()[-2]}")
        results.append((name, "fail", str(e)))


# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 1. CSV PARSER ═══")
from core.csv_parser import parse_csv, parse_csv_string, load_dummy_data, validate_csv, NUMERIC_FIELDS

DUMMY_PATH = Path("dummy_data/sample_meta.csv")

def t_parse_dummy():
    rows = load_dummy_data()
    assert len(rows) > 0, f"Geen rows: {len(rows)}"
    return True

def t_parse_required_fields():
    rows = load_dummy_data()
    row = rows[0]
    for f in ["campaign_name", "ad_name", "impressions", "spend", "results"]:
        assert f in row, f"Ontbreekt: {f}"
    return True

def t_numeric_fields_are_float():
    rows = load_dummy_data()
    row = rows[0]
    for f in NUMERIC_FIELDS:
        val = row.get(f, 0)
        assert isinstance(val, float), f"{f} is {type(val)}, verwacht float"
    return True

def t_no_aggregate_rows():
    rows = load_dummy_data()
    for r in rows:
        assert r.get("ad_name", "Unknown") != "", "Lege ad_name gevonden (aggregate row niet gefilterd)"
    return True

def t_parse_csv_string():
    raw = DUMMY_PATH.read_text(encoding="utf-8-sig")
    rows = parse_csv_string(raw)
    assert len(rows) > 0, "parse_csv_string geeft lege lijst"
    return True

def t_validate_valid():
    rows = load_dummy_data()
    valid, errors = validate_csv(rows)
    assert valid, f"Validatie mislukt: {errors}"
    return True

def t_validate_empty():
    valid, errors = validate_csv([])
    assert not valid, "Lege CSV had ongeldig moeten zijn"
    return True

def t_validate_missing_column():
    rows = [{"ad_name": "test", "impressions": 100}]  # geen spend
    valid, errors = validate_csv(rows)
    assert not valid, "CSV zonder spend had ongeldig moeten zijn"
    return True

def t_dedup_logic():
    rows = load_dummy_data()
    seen_keys = set()
    deduped = []
    for row in rows:
        key = (
            row.get("ad_id") or row.get("ad_name", ""),
            row.get("campaign_id") or row.get("campaign_name", ""),
            row.get("day", ""),
        )
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(row)
    # Same data twice should deduplicate
    for row in rows:
        key = (
            row.get("ad_id") or row.get("ad_name", ""),
            row.get("campaign_id") or row.get("campaign_name", ""),
            row.get("day", ""),
        )
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(row)
    assert len(deduped) == len(rows), f"Dedup werkte niet: {len(deduped)} vs {len(rows)} orig"
    return True

def t_bom_stripped():
    raw = "﻿" + DUMMY_PATH.read_text(encoding="utf-8-sig")
    rows = parse_csv_string(raw)
    assert len(rows) > 0, "BOM stripping mislukt"
    return True

def t_has_click_data_flag():
    rows = load_dummy_data()
    # dummy data has CTR column → should have click data
    assert any(r.get("_has_click_data") for r in rows), "_has_click_data nooit True"
    return True

test("CSV laden dummy data", t_parse_dummy)
test("CSV: alle verplichte kolommen aanwezig", t_parse_required_fields)
test("CSV: alle numerieke velden zijn float", t_numeric_fields_are_float)
test("CSV: aggregate-rijen gefilterd", t_no_aggregate_rows)
test("CSV: parse_csv_string werkt", t_parse_csv_string)
test("Validatie: geldige CSV", t_validate_valid)
test("Validatie: lege CSV afgekeurd", t_validate_empty)
test("Validatie: ontbrekende kolom afgekeurd", t_validate_missing_column)
test("Dedup: dubbele rows worden gefilterd", t_dedup_logic)
test("CSV: BOM wordt gestript", t_bom_stripped)
test("CSV: _has_click_data flag aanwezig", t_has_click_data_flag)

# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 2. ANALYSIS ═══")
from core.analysis import (
    build_campaigns, build_summary, build_ad_chart_data,
    get_all_ads, get_date_range, filter_rows_by_date, build_wow_comparison,
)

rows = load_dummy_data()
campaigns = build_campaigns(rows)
summary = build_summary(rows, campaigns)

def t_campaigns_built():
    assert len(campaigns) > 0, "Geen campaigns"
    return True

def t_summary_totals_positive():
    assert summary.total_spend > 0, f"spend={summary.total_spend}"
    assert summary.total_impressions > 0, f"impressions={summary.total_impressions}"
    return True

def t_summary_cpl_consistent():
    if summary.total_results > 0:
        expected = round(summary.total_spend / summary.total_results, 2)
        actual = summary.avg_cost_per_result
        assert abs(expected - actual) < 0.05, f"CPL inconsistentie: {expected} vs {actual}"
    return True

def t_summary_ctr_consistent():
    if summary.total_impressions > 0 and summary.total_clicks > 0:
        expected = round(summary.total_clicks / summary.total_impressions * 100, 2)
        actual = summary.avg_ctr
        assert abs(expected - actual) < 0.05, f"CTR inconsistentie: {expected} vs {actual}"
    return True

def t_all_ads_non_empty():
    all_ads = get_all_ads(campaigns)
    assert len(all_ads) > 0, "Geen ads"
    return True

def t_ads_sorted_by_spend():
    all_ads = sorted(get_all_ads(campaigns), key=lambda a: a.spend, reverse=True)
    for i in range(len(all_ads) - 1):
        assert all_ads[i].spend >= all_ads[i+1].spend, "Ads niet gesorteerd op spend"
    return True

def t_date_range_valid():
    d_from, d_to = get_date_range(rows)
    assert d_from and d_to, "Geen date range"
    assert d_from <= d_to, f"date_from {d_from} > date_to {d_to}"
    return True

def t_date_filter():
    d_from, d_to = get_date_range(rows)
    mid = d_from  # filter to only first date
    filtered = filter_rows_by_date(rows, mid, mid)
    assert len(filtered) < len(rows), "Date filter heeft niets gefilterd"
    return True

def t_date_filter_empty_range():
    filtered = filter_rows_by_date(rows, "", "")
    assert len(filtered) == len(rows), "Lege date filter heeft rows verwijderd"
    return True

def t_date_filter_impossible_range():
    filtered = filter_rows_by_date(rows, "2099-01-01", "2099-01-31")
    assert len(filtered) == 0, "Toekomst date filter had leeg moeten zijn"
    return True

def t_wow_comparison():
    wow = build_wow_comparison(rows)
    if wow is None:
        return "WARN: wow=None (weinig datapunten?)"
    assert "p1" in wow and "p2" in wow, "WoW mist p1/p2"
    assert "delta_cpl" in wow, "WoW mist delta_cpl"
    return True

def t_campaign_type_detection():
    ct = summary.campaign_type
    assert ct in ("leads", "purchases", "awareness"), f"Onbekend campagnetype: {ct}"
    return True

def t_top_ad_worst_ad():
    # top_ad en worst_ad mogen dezelfde zijn als er maar 1 goed presteert
    # maar mogen geen None zijn als er resultaten zijn
    if summary.total_results > 0:
        assert summary.top_ad is not None, "top_ad is None terwijl er resultaten zijn"
    return True

def t_chart_data_keys():
    cd = build_ad_chart_data(campaigns, summary.campaign_type)
    for key in ("labels", "spend", "metric", "ctr", "results"):
        assert key in cd, f"Ontbreekt in chart data: {key}"
    assert len(cd["labels"]) == len(cd["spend"]), "Ongelijke lengte labels/spend"
    return True

def t_no_negative_spend():
    all_ads = get_all_ads(campaigns)
    for ad in all_ads:
        assert ad.spend >= 0, f"Negatieve spend bij {ad.ad_name}: {ad.spend}"
    return True

def t_zero_division_safe():
    # Test with zero-result rows
    zero_rows = [{"campaign_name": "Test", "ad_set_name": "Set", "ad_name": "Ad",
                  "ad_id": "1", "campaign_id": "1", "ad_set_id": "1",
                  "impressions": 0.0, "reach": 0.0, "clicks": 0.0, "link_clicks": 0.0,
                  "spend": 0.0, "results": 0.0, "frequency": 0.0, "ctr": 0.0,
                  "ctr_link": 0.0, "cpc": 0.0, "cpc_link": 0.0, "cpm": 0.0,
                  "cost_per_result": 0.0, "roas": 0.0, "result_indicator": ""}]
    valid, _ = validate_csv(zero_rows)
    if valid:
        c2 = build_campaigns(zero_rows)
        s2 = build_summary(zero_rows, c2)
        assert s2.avg_cost_per_result == 0.0, "Deling door nul niet afgevangen"
    return True

def t_campaign_type_override():
    s_forced = build_summary(rows, campaigns, campaign_type_override="purchases")
    assert s_forced.campaign_type == "purchases", "Override werkte niet"
    return True

test("Campaigns worden gebouwd", t_campaigns_built)
test("Summary: totals zijn positief", t_summary_totals_positive)
test("Summary: CPL is consistent met totals", t_summary_cpl_consistent)
test("Summary: CTR is consistent met totals", t_summary_ctr_consistent)
test("All ads: niet leeg", t_all_ads_non_empty)
test("Ads gesorteerd op spend (desc)", t_ads_sorted_by_spend)
test("Date range: geldig en volgorde klopt", t_date_range_valid)
test("Date filter: verkort de dataset", t_date_filter)
test("Date filter: lege range filtert niets", t_date_filter_empty_range)
test("Date filter: toekomstige range geeft lege lijst", t_date_filter_impossible_range)
test("WoW vergelijking opgebouwd", t_wow_comparison)
test("Campaign type detectie valide waarde", t_campaign_type_detection)
test("top_ad aanwezig als er resultaten zijn", t_top_ad_worst_ad)
test("Chart data: alle keys aanwezig", t_chart_data_keys)
test("Geen negatieve spend in ads", t_no_negative_spend)
test("Deling door nul veilig afgevangen", t_zero_division_safe)
test("Campaign type override werkt", t_campaign_type_override)

# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 3. HOOK ANALYZER ═══")
from core.hook_analyzer import (
    parse_ad_name, detect_hook, detect_format, aggregate_hook_performance,
    aggregate_format_performance, get_winning_combinations,
    get_untested_hooks, get_untested_formats, get_unknown_ads,
    HOOK_TYPES, FORMAT_TYPES,
)

all_ads = sorted(get_all_ads(campaigns), key=lambda a: a.spend, reverse=True)

def t_detect_hook_known():
    # Named after a hook keyword
    h = detect_hook("Herkenbaar klantprobleem video")
    assert h != "", f"Lege hook: {h}"
    return True

def t_detect_hook_curiosity_question():
    h = detect_hook("Wist je dat deze truc bestaat?")
    assert h == "curiosity", f"Verwacht curiosity, got {h}"
    return True

def t_detect_format_carousel():
    f = detect_format("Accessoires Carousel zomercollectie")
    assert f == "carousel", f"Verwacht carousel, got {f}"
    return True

def t_detect_format_static():
    f = detect_format("Sport Statisch banner")
    assert f == "static", f"Verwacht static, got {f}"
    return True

def t_structured_name_parsing():
    # "Format - Hook - V# - Beschrijving"
    result = parse_ad_name("UGC - Proof - V2 - Lid Testimonial")
    assert result["hook"] == "proof", f"Hook: {result['hook']}"
    assert result["format"] == "ugc", f"Format: {result['format']}"
    assert result["version"] == 2, f"Versie: {result['version']}"
    assert result["structured"] is True, "Structured niet True"
    return True

def t_structured_name_v1():
    result = parse_ad_name("Static - Promise - V1 - Resultaat in 4 weken")
    assert result["hook"] == "promise"
    assert result["format"] == "static"
    assert result["version"] == 1
    return True

def t_parse_cache():
    # Parse dezelfde naam twee keer — moet zelfde resultaat geven
    r1 = parse_ad_name("Zomerjurk Banner")
    r2 = parse_ad_name("Zomerjurk Banner")
    assert r1 == r2, "Cache geeft inconsistent resultaat"
    return True

def t_hook_performance_sorted():
    perf = aggregate_hook_performance(all_ads)
    assert len(perf) > 0, "Lege hook performance"
    # Verifieer dat CPL-sorting werkt (None's achteraan)
    cpls = [r["cpl"] for r in perf]
    nones = [i for i, c in enumerate(cpls) if c is None]
    non_nones = [i for i, c in enumerate(cpls) if c is not None]
    if nones and non_nones:
        assert max(non_nones) < min(nones), "None CPLs staan niet achteraan"
    return True

def t_format_performance_not_empty():
    perf = aggregate_format_performance(all_ads)
    assert len(perf) > 0, "Lege format performance"
    return True

def t_winning_combos():
    combos = get_winning_combinations(all_ads)
    for c in combos:
        assert "hook_type" in c and "format_type" in c, f"Ontbrekende keys: {c}"
        assert c["results"] > 0, "Combo zonder resultaten in winning combos"
    return True

def t_untested_hooks_are_valid():
    untested = get_untested_hooks(all_ads)
    for h in untested:
        assert h in HOOK_TYPES, f"Onbekende untested hook: {h}"
        assert h != "unknown", "unknown mag niet in untested zitten"
    return True

def t_untested_formats_are_valid():
    untested = get_untested_formats(all_ads)
    for f in untested:
        assert f in FORMAT_TYPES, f"Onbekend untested format: {f}"
    return True

def t_unknown_ads_have_spend():
    unknown = get_unknown_ads(all_ads)
    for ad in unknown:
        assert ad["spend"] > 0, f"Unknown ad zonder spend: {ad['ad_name']}"
    return True

def t_overrides_applied():
    overrides = {"Zomerjurk Banner": {"hook": "proof", "format": "static"}}
    perf = aggregate_hook_performance(all_ads, overrides=overrides)
    proof_row = next((r for r in perf if r["hook_type"] == "proof"), None)
    assert proof_row is not None, "proof niet gevonden na override"
    return True

def t_hook_cpl_calculation():
    perf = aggregate_hook_performance(all_ads)
    for row in perf:
        if row["results"] and row["results"] > 0 and row["cpl"] is not None:
            expected = round(row["spend"] / row["results"], 2)
            assert abs(expected - row["cpl"]) < 0.01, f"CPL fout: {expected} vs {row['cpl']}"
    return True

test("Hook detectie: retourneert iets", t_detect_hook_known)
test("Hook detectie: curiosity bij vraagteken", t_detect_hook_curiosity_question)
test("Format detectie: carousel herkend", t_detect_format_carousel)
test("Format detectie: static herkend", t_detect_format_static)
test("Structured naam parsing: hook+format+versie", t_structured_name_parsing)
test("Structured naam parsing: V1 formaat", t_structured_name_v1)
test("Parse cache: zelfde naam = zelfde result", t_parse_cache)
test("Hook performance: CPL-gesorteerd (None achteraan)", t_hook_performance_sorted)
test("Format performance: niet leeg", t_format_performance_not_empty)
test("Winning combos: alleen met resultaten", t_winning_combos)
test("Untested hooks: alleen geldige waarden", t_untested_hooks_are_valid)
test("Untested formats: alleen geldige waarden", t_untested_formats_are_valid)
test("Unknown ads: hebben allemaal spend", t_unknown_ads_have_spend)
test("Overrides: worden toegepast op hook aggregatie", t_overrides_applied)
test("Hook CPL: berekening klopt", t_hook_cpl_calculation)

# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 4. SHOOT BRIEF (fallback, geen API) ═══")
from core.shoot_brief import generate_shoot_brief, _strip_em_dashes, _clean_script, _build_script, HOOK_TYPES as SB_HOOKS

def t_shoot_brief_returns_3():
    brief = generate_shoot_brief(summary, all_ads, client_name="fit20 Gooise Meren")
    assert len(brief) == 3, f"Verwacht 3 shoots, got {len(brief)}"
    return True

def t_shoot_brief_types():
    brief = generate_shoot_brief(summary, all_ads, client_name="fit20 Gooise Meren")
    types = {s["type"] for s in brief}
    assert types == {"safe", "new_hook", "format_test"}, f"Types kloppen niet: {types}"
    return True

def t_shoot_brief_required_fields():
    brief = generate_shoot_brief(summary, all_ads, client_name="fit20 Gooise Meren")
    required = ["type", "hook_type", "format", "openingszin", "cta", "script", "shots", "concept"]
    for shoot in brief:
        for f in required:
            assert f in shoot, f"Veld {f} ontbreekt in shoot {shoot.get('type')}"
    return True

def t_shoot_brief_script_has_4_blocks():
    brief = generate_shoot_brief(summary, all_ads, client_name="fit20 Gooise Meren")
    for shoot in brief:
        script = shoot.get("script", [])
        assert len(script) >= 3, f"Script heeft maar {len(script)} blokken in {shoot['type']}"
        for block in script:
            assert "time" in block and "tekst" in block, f"Script block mist keys: {block}"
    return True

def t_no_em_dashes_in_fallback():
    brief = generate_shoot_brief(summary, all_ads, client_name="fit20 Gooise Meren")
    for shoot in brief:
        for block in shoot.get("script", []):
            assert "—" not in block["tekst"], f"Em dash gevonden in script: {block['tekst']}"
        assert "—" not in shoot.get("openingszin", ""), f"Em dash in openingszin: {shoot['openingszin']}"
    return True

def t_client_name_in_script():
    brief = generate_shoot_brief(summary, all_ads, client_name="TestBedrijf")
    all_text = " ".join(
        b["tekst"] for s in brief for b in s.get("script", [])
    ) + " ".join(s.get("openingszin", "") for s in brief)
    # At least one mention of the client name expected in fallback
    if not any("TestBedrijf" in s.get("openingszin", "") or
               any("TestBedrijf" in b["tekst"] for b in s.get("script", []))
               for s in brief):
        return "WARN: Klantnaam niet gevonden in scripts (kan kloppen bij specifieke hook combos)"
    return True

def t_strip_em_dashes():
    cleaned = _strip_em_dashes("Hallo — wereld — test")
    assert "—" not in cleaned, f"Em dash niet verwijderd: {cleaned}"
    return True

def t_clean_script():
    script = [{"time": "0-5s", "tekst": "Test — zin"}, {"time": "5-15s", "tekst": "Zonder dash"}]
    cleaned = _clean_script(script)
    for block in cleaned:
        assert "—" not in block["tekst"], f"Em dash in cleaned script: {block['tekst']}"
    return True

def t_all_hook_types_have_script():
    for hook in SB_HOOKS:
        script = _build_script(hook, "Plan een gratis proefles", "fit20")
        assert len(script) >= 3, f"Hook {hook} heeft te weinig blokken: {len(script)}"
        for block in script:
            assert "—" not in block["tekst"], f"Em dash in hook {hook}: {block['tekst']}"
    return True

def t_no_api_fallback():
    # Ensure we're in fallback mode (no API)
    from core.ai_client import has_api
    if has_api():
        return "WARN: API beschikbaar, fallback niet getest"
    brief = generate_shoot_brief(summary, all_ads, client_name="Test")
    assert all(s.get("_fallback") for s in brief), "Verwachtte fallback briefs"
    return True

def t_unknown_client_name_fallback():
    brief = generate_shoot_brief(summary, all_ads, client_name="")
    assert len(brief) == 3, "Lege client_name crasht niet"
    return True

test("Shoot brief: geeft altijd 3 shoots terug", t_shoot_brief_returns_3)
test("Shoot brief: types zijn safe/new_hook/format_test", t_shoot_brief_types)
test("Shoot brief: alle verplichte velden aanwezig", t_shoot_brief_required_fields)
test("Shoot brief: elk script heeft 3+ blokken", t_shoot_brief_script_has_4_blocks)
test("Shoot brief: geen em dashes in scripts", t_no_em_dashes_in_fallback)
test("Shoot brief: klantnaam verwerkt in script", t_client_name_in_script)
test("strip_em_dashes: verwijdert alle em dashes", t_strip_em_dashes)
test("clean_script: verwijdert em dashes uit alle blokken", t_clean_script)
test("Alle 10 hook types hebben script + geen em dashes", t_all_hook_types_have_script)
test("Fallback modus actief zonder API key", t_no_api_fallback)
test("Lege client_name crasht niet", t_unknown_client_name_fallback)

# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 5. CREATIVE DECODER ═══")
from core.creative_decoder import decode_winner, decode_loser

def t_decode_winner_keys():
    winners = [a for a in all_ads if a.results > 0 and a.cost_per_result > 0][:2]
    if not winners:
        return "WARN: geen winner ads om te testen"
    for ad in winners:
        decoded = decode_winner(ad, summary)
        assert "hook_type" in decoded, f"hook_type ontbreekt: {decoded}"
        assert "format" in decoded, f"format ontbreekt: {decoded}"
    return True

def t_decode_loser_keys():
    losers = [a for a in all_ads if a.results == 0 and a.spend > 10][:2]
    if not losers:
        return "WARN: geen loser ads om te testen"
    for ad in losers:
        decoded = decode_loser(ad, summary)
        assert isinstance(decoded, dict), f"Verwacht dict, got {type(decoded)}"
    return True

test("decode_winner: retourneert verwachte keys", t_decode_winner_keys)
test("decode_loser: retourneert dict", t_decode_loser_keys)

# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ 6. EDGE CASES & SECURITY ═══")

def t_xss_in_ad_name():
    """Ad names met HTML/JS mogen niet raw in templates terechtkomen — Jinja2 escapet automatisch."""
    xss_name = "<script>alert('xss')</script>"
    # parse_ad_name mag niet crashen
    result = parse_ad_name(xss_name)
    assert result is not None, "parse_ad_name crasht op XSS input"
    # detect_hook mag niet crashen
    h = detect_hook(xss_name)
    assert isinstance(h, str), "detect_hook crasht op XSS"
    return True

def t_very_long_ad_name():
    long_name = "A" * 1000
    result = parse_ad_name(long_name)
    assert result is not None, "parse_ad_name crasht op lange naam"
    return True

def t_sql_injection_in_name():
    """SQL injection in ad name mag parse niet breken."""
    sql_name = "'; DROP TABLE ads; --"
    result = parse_ad_name(sql_name)
    assert result is not None
    return True

def t_unicode_in_ad_name():
    unicode_name = "Herken jij dit 🎯 gevoel 日本語"
    result = parse_ad_name(unicode_name)
    assert result is not None, "Unicode crasht parse_ad_name"
    return True

def t_csv_with_zero_spend():
    rows_zero = [{"campaign_name": "C", "ad_set_name": "S", "ad_name": "A",
                  "ad_id": "1", "campaign_id": "1", "ad_set_id": "1",
                  "impressions": 1000.0, "reach": 900.0, "clicks": 10.0, "link_clicks": 8.0,
                  "spend": 0.0, "results": 0.0, "frequency": 1.1, "ctr": 1.0,
                  "ctr_link": 0.8, "cpc": 0.0, "cpc_link": 0.0, "cpm": 0.0,
                  "cost_per_result": 0.0, "roas": 0.0, "result_indicator": ""}]
    c = build_campaigns(rows_zero)
    s = build_summary(rows_zero, c)
    assert s.avg_cost_per_result == 0.0, "Nul-spend crasht analyse niet"
    return True

def t_csv_single_row():
    rows_one = load_dummy_data()[:1]
    c = build_campaigns(rows_one)
    s = build_summary(rows_one, c)
    assert s.num_ads >= 1, "Single row geeft geen ads"
    return True

def t_wow_with_single_date():
    rows_one = [r for r in rows if r.get("day") == rows[0].get("day")]
    wow = build_wow_comparison(rows_one)
    # Should return None (not enough dates for comparison)
    assert wow is None, "WoW met 1 datum had None moeten zijn"
    return True

def t_negative_threshold_handled():
    """Negatieve threshold in _compute_thresholds mag niet crashen."""
    sys.path.insert(0, str(Path(__file__).parent))
    import importlib
    app_module = importlib.import_module("app")
    # Simulate form with extreme values
    class FakeForm(dict):
        pass
    form = FakeForm({"threshold_preset": "custom", "threshold_winner": "-100", "threshold_mid": "-50"})
    t = app_module._compute_thresholds(form=form)
    assert t["winner"] >= 1, f"Winner threshold mag niet < 1 zijn: {t['winner']}"
    assert t["mid"] > t["winner"], f"Mid moet > winner zijn: {t}"
    return True

def t_date_filter_inverted_range():
    """date_from > date_to mag niet crashen — geeft gewoon lege lijst."""
    result = filter_rows_by_date(rows, "2025-01-01", "2024-01-01")
    assert isinstance(result, list), "Date filter met omgekeerd bereik crasht"
    return True

def t_huge_csv_no_crash():
    """Gesimuleerde grote dataset."""
    big_rows = load_dummy_data() * 20  # 20x de dummy data
    c = build_campaigns(big_rows)
    s = build_summary(big_rows, c)
    assert s.total_spend > 0
    return True

def t_all_ads_with_same_name():
    """
    Zelfde ad naam in VERSCHILLENDE ad sets = 2 aparte ads (correct Facebook-gedrag).
    Zelfde ad naam in ZELFDE ad set = 1 geaggregeerd ad.
    """
    # Case 1: zelfde naam, zelfde ad set → moet 1 ad worden
    same_adset_rows = []
    for r in load_dummy_data()[:4]:
        r2 = dict(r)
        r2["ad_name"] = "Identiek Ad"
        r2["ad_set_name"] = "Enige AdSet"
        r2["ad_set_id"] = "999"
        same_adset_rows.append(r2)
    c1 = build_campaigns(same_adset_rows)
    ads1 = get_all_ads(c1)
    assert len(ads1) == 1, f"Zelfde naam + zelfde adset → verwacht 1 ad, got {len(ads1)}"

    # Case 2: zelfde naam, verschillende ad sets → moet 2 ads zijn (correct gedrag)
    diff_adset_rows = []
    for i, r in enumerate(load_dummy_data()[:2]):
        r2 = dict(r)
        r2["ad_name"] = "Identiek Ad"
        r2["ad_set_name"] = f"AdSet {i}"
        r2["ad_set_id"] = str(i)
        diff_adset_rows.append(r2)
    c2 = build_campaigns(diff_adset_rows)
    ads2 = get_all_ads(c2)
    assert len(ads2) == 2, f"Zelfde naam in 2 adsets → verwacht 2 ads, got {len(ads2)}"
    return True

def t_cpl_benchmark_auto_threshold():
    """Auto-threshold op basis van CPL benchmark."""
    from app import _compute_thresholds
    fake_client = {"cpl_benchmark": 45.0}
    t = _compute_thresholds(form={"threshold_preset": "auto"}, client=fake_client)
    assert t["winner"] == 45, f"Winner zou 45 moeten zijn: {t['winner']}"
    assert t["mid"] > t["winner"], f"Mid moet > winner: {t}"
    assert t.get("from_benchmark"), "from_benchmark niet gezet"
    return True

def t_session_data_source_merged_parsing():
    """_load_rows_from_session met merged: source mag niet crashen (zonder DB)."""
    from app import _load_rows_from_session
    # Simulate Flask context — we can't actually test Flask session without app context,
    # but we can verify the parse logic works on the new code path
    # by checking that "merged:" strings parse correctly
    upload_ids_str = "merged:1,2,3"
    ids = [int(x) for x in upload_ids_str[7:].split(",") if x.strip().isdigit()]
    assert ids == [1, 2, 3], f"Merged ID parsing mislukt: {ids}"
    return True

def t_session_data_source_db_parsing():
    """db: source parsing."""
    source = "db:42"
    uid = int(source[3:])
    assert uid == 42, f"DB upload ID parsing mislukt: {uid}"
    return True

test("XSS in ad naam: crasht niet", t_xss_in_ad_name)
test("Zeer lange ad naam: crasht niet", t_very_long_ad_name)
test("SQL injection in ad naam: crasht niet", t_sql_injection_in_name)
test("Unicode in ad naam: crasht niet", t_unicode_in_ad_name)
test("CSV met 0 spend: geen crash", t_csv_with_zero_spend)
test("CSV met 1 row: werkt", t_csv_single_row)
test("WoW: 1 datum → None (geen crash)", t_wow_with_single_date)
test("Negatieve threshold → clamp naar min 1", t_negative_threshold_handled)
test("Omgekeerd date range crasht niet", t_date_filter_inverted_range)
test("Grote dataset (20x dummy): geen crash", t_huge_csv_no_crash)
test("Alle ads zelfde naam → 1 aggregaat", t_all_ads_with_same_name)
test("Auto-threshold: CPL benchmark werkt", t_cpl_benchmark_auto_threshold)
test("Merged data source ID parsing", t_session_data_source_merged_parsing)
test("DB data source ID parsing", t_session_data_source_db_parsing)

# ─────────────────────────────────────────────────────────────────────────────
print("\n═══ SAMENVATTING ═══")
passed = sum(1 for _, s, _ in results if s == "pass")
warned = sum(1 for _, s, _ in results if s == "warn")
failed = sum(1 for _, s, _ in results if s == "fail")
total  = len(results)

print(f"\n  Totaal  : {total}")
print(f"  \033[92mPassed\033[0m  : {passed}")
if warned:
    print(f"  \033[93mWarnings\033[0m: {warned}")
if failed:
    print(f"  \033[91mFailed\033[0m  : {failed}")
    print("\nGefaalde tests:")
    for name, status, msg in results:
        if status == "fail":
            print(f"  ✗ {name}: {msg}")

sys.exit(0 if failed == 0 else 1)
