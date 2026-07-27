"""Contract tests for 情报中心临床试验三源模块。

TDD RED phase: these tests define the required behavior before implementation.
"""
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


# ── 1. Tab structure: 情报中心 gains 临床试验 tab ──────────────────────

def test_literature_html_has_clinical_trials_tab():
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    assert 'data-tab="trials"' in html, "情报中心 must have a 临床试验 tab button"
    assert 'id="tab-trials"' in html, "情报中心 must have a tab-trials panel"


def test_literature_html_tab_order():
    """Tabs: 文献速览/信号板/中国情报 | 会议资讯 | 临床试验"""
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    tab_order = re.findall(r'data-tab="(\w+)"', html)
    assert tab_order == ["literature", "signals", "china", "conference", "trials"], (
        f"Tab order wrong: {tab_order}"
    )


# ── 2. 诊治格局 removes Clinical Pipeline ─────────────────────────────

def test_landscape_html_no_clinical_pipeline_section():
    html = (PROJECT / "pages" / "landscape.html").read_text(encoding="utf-8")
    assert "clinicalPipelineMatrix" not in html, (
        "Clinical Pipeline matrix must be removed from 诊治格局"
    )
    assert "chinaTrialRegistrySignals" not in html, (
        "ChiCTR signals section must be removed from 诊治格局"
    )


def test_landscape_js_no_clinical_pipeline_render():
    js = (PROJECT / "assets" / "landscape.js").read_text(encoding="utf-8")
    assert "renderClinicalPipelineMatrix" not in js, (
        "renderClinicalPipelineMatrix must be removed from landscape.js"
    )
    assert "renderChinaTrialRegistrySignals" not in js, (
        "renderChinaTrialRegistrySignals must be removed from landscape.js"
    )


# ── 3. 临床试验 tab content structure ─────────────────────────────────

def test_trials_tab_has_decision_signals_section():
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    # The trials panel must contain a decision-signals container
    assert 'id="trialsDecisionSignals"' in html


def test_trials_tab_has_three_source_modules_in_order():
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    # Extract the tab-trials section
    panel_match = re.search(
        r'id="tab-trials".*?(?=<section class="intel-tab-panel"|</main>)',
        html, re.S,
    )
    assert panel_match, "tab-trials panel not found"
    panel = panel_match.group(0)
    # Three source module containers in exact order
    ct_pos = panel.find('id="trialsClinicalTrialsGov"')
    chictr_pos = panel.find('id="trialsChiCTR"')
    cdt_pos = panel.find('id="trialsChinaDrugTrials"')
    assert ct_pos != -1, "ClinicalTrials.gov module missing"
    assert chictr_pos != -1, "ChiCTR module missing"
    assert cdt_pos != -1, "ChinaDrugTrials module missing"
    assert ct_pos < chictr_pos < cdt_pos, (
        f"Source order wrong: CT={ct_pos}, ChiCTR={chictr_pos}, CDT={cdt_pos}"
    )


# ── 4. Shared facets ──────────────────────────────────────────────────

def test_trials_tab_has_shared_facets():
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    panel_match = re.search(
        r'id="tab-trials".*?(?=<section class="intel-tab-panel"|</main>)',
        html, re.S,
    )
    assert panel_match
    panel = panel_match.group(0)
    # Shared facet controls: 药物分类→适应症→状态→时间
    assert 'id="trialsFacetDrugClass"' in panel, "Missing 药物分类 facet"
    assert 'id="trialsFacetIndication"' in panel, "Missing 适应症 facet"
    assert 'id="trialsFacetStatus"' in panel, "Missing 状态 facet"
    assert 'id="trialsFacetTime"' in panel, "Missing 时间 facet"


# ── 5. ChinaDrugTrials adapter (Python backend) ──────────────────────

def test_china_drug_trials_adapter_importable():
    from scripts.common.clinical_registry import (
        load_china_drug_trials_cache,
        normalize_china_drug_trials_record,
    )
    assert callable(load_china_drug_trials_cache)
    assert callable(normalize_china_drug_trials_record)


def test_china_drug_trials_cache_deterministic_fallback(tmp_path):
    from scripts.common.clinical_registry import load_china_drug_trials_cache

    # Non-existent path returns empty schema, not an error
    result = load_china_drug_trials_cache(tmp_path / "nonexistent.json")
    assert result["source"] == "ChinaDrugTrials.org.cn"
    assert result["records"] == []
    assert result["mode"] == "unavailable"


def test_china_drug_trials_cache_preserves_last_good(tmp_path):
    from scripts.common.clinical_registry import (
        load_china_drug_trials_cache,
        refresh_china_drug_trials_cache,
    )

    cache = tmp_path / "cdt-cache.json"
    good = {
        "schema_version": "1.0",
        "source": "ChinaDrugTrials.org.cn",
        "mode": "cache",
        "records": [{"registry_id": "CDT-1", "title": "MG study"}],
    }
    cache.write_text(json.dumps(good), encoding="utf-8")
    before = cache.read_bytes()

    # Failed refresh must preserve last-good cache
    bad_input = tmp_path / "bad.json"
    bad_input.write_text("not json", encoding="utf-8")
    result = refresh_china_drug_trials_cache(cache, input_path=bad_input)

    assert cache.read_bytes() == before, "Cache file must not be modified on failure"
    assert result["mode"] == "cache"
    assert result["warning"]


def test_china_drug_trials_normalize_record():
    from scripts.common.clinical_registry import normalize_china_drug_trials_record

    record = normalize_china_drug_trials_record({
        "registration_number": "CTR20260001",
        "drug_name": "Batoclimab",
        "indication": "重症肌无力",
        "status": "招募中",
        "phase": "III期",
    })
    assert record["registry"] == "ChinaDrugTrials"
    assert record["registry_id"] == "CTR20260001"
    assert record["title"] != ""
    # Must not fabricate fields
    assert "evidence_level" not in record


# ── 6. Three-source normalization preserves linked IDs ────────────────

def test_normalize_three_registries_preserves_linked_ids():
    from scripts.common.clinical_registry import normalize_registry_trials

    ct_payload = {
        "studies": [{
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT03896295",
                    "briefTitle": "A Study of Batoclimab in Participants With Generalized Myasthenia Gravis",
                    "orgStudyIdInfo": {"id": "MOM-M281-005"},
                },
                "statusModule": {"overallStatus": "RECRUITING", "lastUpdateSubmitDate": "2026-07-01"},
                "conditionsModule": {"conditions": ["Myasthenia Gravis"]},
            }
        }]
    }
    chictr_payload = {
        "records": [{
            "registry_id": "ChiCTR2500104662",
            "title": "A Study of Batoclimab in Participants With Generalized Myasthenia Gravis",
            "status": "Not yet recruiting",
            "registered_date": "2025-06-20",
            "official_url": "https://www.chictr.org.cn/showprojEN.html?proj=270461",
        }]
    }
    cdt_payload = {
        "records": [{
            "registry_id": "CTR20260001",
            "title": "A Study of Batoclimab in Participants With Generalized Myasthenia Gravis",
            "status": "招募中",
        }]
    }

    result = normalize_registry_trials(ct_payload, chictr_payload, cdt_payload)
    assert len(result) >= 1
    # At least one record should have linked_registries from dedup
    linked = [r for r in result if r.get("linked_registries")]
    assert len(linked) >= 1, "Cross-registry dedup must produce linked_registries"


# ── 7. Frontend data contract: trials data JS file ────────────────────

def test_trials_data_script_referenced_in_literature_html():
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    assert "clinical-trials-data.js" in html or "trials-data.js" in html, (
        "literature.html must reference a trials data script"
    )


# ── 8. CSS responsive contract ────────────────────────────────────────

def test_trials_css_no_horizontal_overflow():
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")
    # Must have overflow-x control for trials cards
    assert "trials-card" in css or "trial-card" in css, (
        "CSS must define trial card styles"
    )
    # Grid/flex must use minmax or wrap to prevent overflow
    assert "minmax" in css or "flex-wrap" in css, (
        "CSS must use responsive grid/flex patterns"
    )


# ── 9. Landscape stats link routes to 临床试验 ────────────────────────

def test_landscape_stats_link_routes_to_trials_tab():
    """Any remaining pipeline stats in landscape must link to 情报中心临床试验 tab."""
    js = (PROJECT / "assets" / "landscape.js").read_text(encoding="utf-8")
    # If clinical_pipeline_count is still rendered in stats, it must link to trials
    if "clinical_pipeline_count" in js:
        assert "literature.html" in js and "trials" in js, (
            "Pipeline stats link must route to 情报中心临床试验 tab"
        )
