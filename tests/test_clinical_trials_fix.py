"""TDD RED tests for clinical-trials tab fixes (t_e44f4b49).

Three blocking defects:
1. ?tab=trials deep-link opens 文献速览 instead of 临床试验
2. data/clinical-trials-data.js is empty scaffold (0 records)
3. Decision signals and facets have no real data
"""
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


# ── Defect 1: deep-link ?tab=trials must activate 临床试验 tab ────────

def test_literature_js_reads_tab_query_param():
    """literature.js must read ?tab= from URL and pass as initialKey to initTabs."""
    js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    # Must extract tab param from URL
    assert re.search(r"params\.get\(['\"]tab['\"]\)", js), (
        "literature.js must read 'tab' from URLSearchParams"
    )
    # Must pass it as initialKey to hub.initTabs
    assert "initialKey" in js, (
        "literature.js must pass initialKey to hub.initTabs for deep-link support"
    )


# ── Defect 2: builder must produce nonzero records from real caches ──

def test_builder_script_exists():
    """A deterministic builder script must exist for clinical-trials-data.js."""
    candidates = list(PROJECT.glob("scripts/build*clinical*"))
    assert candidates, (
        "A builder script (scripts/build*clinical*) must exist to generate "
        "data/clinical-trials-data.js from cache files"
    )


def test_builder_produces_nonzero_ctgov_records():
    """Running the builder must produce CT.gov records from pipeline cache."""
    builder = _find_builder()
    result = subprocess.run(
        [sys.executable, str(builder)],
        cwd=str(PROJECT),
        capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "MG_SKIP_CLINICALTRIALS": "1"},
    )
    assert result.returncode == 0, f"Builder failed: {result.stderr}"

    data = _load_trials_data()
    ct_source = _get_source(data, "ClinicalTrials.gov")
    assert len(ct_source["records"]) > 0, (
        "ClinicalTrials.gov records must be nonzero (cache has 313 items)"
    )


def test_builder_produces_nonzero_chictr_records():
    """Running the builder must produce ChiCTR records from chictr cache."""
    builder = _find_builder()
    subprocess.run(
        [sys.executable, str(builder)],
        cwd=str(PROJECT),
        capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "MG_SKIP_CLINICALTRIALS": "1"},
    )
    data = _load_trials_data()
    chictr_source = _get_source(data, "ChiCTR")
    assert len(chictr_source["records"]) > 0, (
        "ChiCTR records must be nonzero (cache has 4 items)"
    )


def test_builder_total_count_matches_sum():
    """meta.total_count must equal sum of all source record counts."""
    builder = _find_builder()
    subprocess.run(
        [sys.executable, str(builder)],
        cwd=str(PROJECT),
        capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "MG_SKIP_CLINICALTRIALS": "1"},
    )
    data = _load_trials_data()
    total = sum(len(s.get("records", [])) for s in data.get("sources", []))
    assert data["meta"]["total_count"] == total, (
        f"total_count={data['meta']['total_count']} != sum={total}"
    )


# ── Defect 3: decision signals and facets must have real data ────────

def test_builder_produces_decision_signals():
    """Builder must generate at least one decision signal from real data."""
    builder = _find_builder()
    subprocess.run(
        [sys.executable, str(builder)],
        cwd=str(PROJECT),
        capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "MG_SKIP_CLINICALTRIALS": "1"},
    )
    data = _load_trials_data()
    signals = data.get("decision_signals", [])
    assert len(signals) > 0, "decision_signals must be non-empty"
    # Each signal must have title and detail
    for s in signals:
        assert s.get("title"), f"Signal missing title: {s}"
        assert s.get("detail"), f"Signal missing detail: {s}"


def test_builder_records_have_facet_fields():
    """Records must carry drug_class, indication, status_label for facets."""
    builder = _find_builder()
    subprocess.run(
        [sys.executable, str(builder)],
        cwd=str(PROJECT),
        capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "MG_SKIP_CLINICALTRIALS": "1"},
    )
    data = _load_trials_data()
    all_records = []
    for src in data.get("sources", []):
        all_records.extend(src.get("records", []))
    assert len(all_records) > 0, "No records at all"
    # At least some records must have facet fields populated
    with_drug = [r for r in all_records if r.get("drug_class")]
    with_indication = [r for r in all_records if r.get("indication")]
    with_status = [r for r in all_records if r.get("status_label")]
    assert len(with_status) > 0, "No records have status_label"
    # drug_class and indication may not be extractable for all, but some must exist
    assert len(with_drug) > 0 or len(with_indication) > 0, (
        "No records have drug_class or indication — facets will be empty"
    )


def test_builder_source_order():
    """Sources must appear in order: ClinicalTrials.gov → ChiCTR → ChinaDrugTrials."""
    builder = _find_builder()
    subprocess.run(
        [sys.executable, str(builder)],
        cwd=str(PROJECT),
        capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "MG_SKIP_CLINICALTRIALS": "1"},
    )
    data = _load_trials_data()
    source_names = [s["source"] for s in data.get("sources", [])]
    assert source_names == ["ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials"], (
        f"Source order wrong: {source_names}"
    )


def test_builder_china_drug_trials_empty_with_warning():
    """ChinaDrugTrials may be empty but must have explicit mode/warning."""
    builder = _find_builder()
    subprocess.run(
        [sys.executable, str(builder)],
        cwd=str(PROJECT),
        capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "MG_SKIP_CLINICALTRIALS": "1"},
    )
    data = _load_trials_data()
    cdt = _get_source(data, "ChinaDrugTrials")
    if not cdt["records"]:
        # Must have explicit unavailable/audited mode
        assert cdt["meta"].get("mode") in ("unavailable", "audited"), (
            f"Empty ChinaDrugTrials must have explicit mode, got: {cdt['meta']}"
        )


def test_builder_writes_lightweight_dashboard_summary():
    """首页摘要必须独立于完整矩阵，避免首页加载大体量试验明细。"""
    builder = _find_builder()
    result = subprocess.run(
        [sys.executable, str(builder)],
        cwd=str(PROJECT),
        capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "MG_SKIP_CLINICALTRIALS": "1"},
    )
    assert result.returncode == 0, f"Builder failed: {result.stderr}"

    summary_path = PROJECT / "data" / "clinicalTrialsSummary.js"
    summary_text = summary_path.read_text(encoding="utf-8")
    match = re.search(r'=\s*(\{.*\})\s*;?\s*$', summary_text, re.S)
    assert match, f"Cannot parse JSON from {summary_path}"
    summary = json.loads(match.group(1))
    full_data = _load_trials_data()

    assert summary["meta"]["total_count"] == full_data["meta"]["total_count"]
    assert summary["pipeline_matrix_count"] == len(full_data["pipeline_matrix"])
    assert len(summary["source_counts"]) == 3
    assert summary_path.stat().st_size < 10_000


# ── Helpers ───────────────────────────────────────────────────────────

def _find_builder():
    candidates = sorted(PROJECT.glob("scripts/build*clinical*"))
    assert candidates, "No builder script found matching scripts/build*clinical*"
    return candidates[0]


def _load_trials_data():
    js_path = PROJECT / "data" / "clinical-trials-data.js"
    text = js_path.read_text(encoding="utf-8")
    # Strip window.MG_CLINICAL_TRIALS_DATA = ... ;
    match = re.search(r'=\s*(\{.*\})\s*;?\s*$', text, re.S)
    assert match, f"Cannot parse JSON from {js_path}"
    return json.loads(match.group(1))


def _get_source(data, name):
    for s in data.get("sources", []):
        if s["source"] == name:
            return s
    raise AssertionError(f"Source '{name}' not found in data")
