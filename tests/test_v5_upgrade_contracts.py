import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from scripts.common.io import atomic_write_js_global, atomic_write_text, load_js_global


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_msl_frontend_is_china_only_and_never_requests_international_shard():
    html = (ROOT / "pages" / "msl.html").read_text(encoding="utf-8")
    js = (ROOT / "assets" / "msl.js").read_text(encoding="utf-8")

    assert "expert-profiles-international.js" not in html
    assert "expert-profiles-international.js" not in js
    assert "MG_EXPERT_PROFILE_INTERNATIONAL" not in js
    assert 'value="international"' not in html
    assert 'name="region"' not in html
    assert "国外" not in html
    assert "加载国外" not in js
    assert "中国作者索引" in html
    assert "快速候选" in html


def test_expert_output_module_always_writes_both_regional_shards(tmp_path):
    from scripts.common.expert_outputs import write_expert_outputs

    payload = {
        "generated_at": "2026-07-15T00:00:00Z",
        "experts": [],
        "china_expert_index": [{"id": "cn-1"}],
        "international_expert_index": [{"id": "intl-1"}],
        "quick_expert_ids": {"china": ["cn-1"]},
        "summary": {},
    }
    write_expert_outputs(payload, tmp_path)

    manifest = load_js_global(tmp_path / "expert-profiles.js", "MG_EXPERT_PROFILES")
    china = load_js_global(tmp_path / "expert-profiles-china.js", "MG_EXPERT_PROFILE_CHINA")
    international = load_js_global(
        tmp_path / "expert-profiles-international.js", "MG_EXPERT_PROFILE_INTERNATIONAL"
    )
    assert [item["id"] for item in manifest["shards"]] == ["china", "international"]
    assert china["items"] == [{"id": "cn-1"}]
    assert international["items"] == [{"id": "intl-1"}]
    assert "china_expert_index" not in manifest
    assert "international_expert_index" not in manifest


def test_atomic_write_failure_preserves_target_and_cleans_unique_temp(tmp_path, monkeypatch):
    target = tmp_path / "artifact.json"
    target.write_text("old", encoding="utf-8")

    def fail_replace(source, destination):
        assert Path(source).parent == target.parent
        assert Path(source).name != target.name + ".tmp"
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".artifact.json.*.tmp")) == []


def test_mg_core_relevance_excludes_single_background_mention_and_keeps_true_mg():
    from scripts.common.mg_relevance import assess_mg_core

    incidental = {
        "title": "Titin expression and outcomes in gastrointestinal malignancies",
        "abstract": (
            "Titin variants are described in several disorders including myasthenia gravis. "
            "We evaluated titin expression in 412 patients with gastrointestinal malignancies."
        ),
        "keywords": ["Gastrointestinal Neoplasms", "Titin"],
    }
    trial = {
        "title": "A randomized trial of FcRn inhibition in generalized myasthenia gravis",
        "abstract": "Patients with generalized myasthenia gravis were randomized to treatment or placebo.",
    }
    ici_safety = {
        "title": "Immune-checkpoint-inhibitor-associated myasthenia gravis: safety outcomes",
        "abstract": "We evaluated clinical safety outcomes in patients with ICI-associated MG.",
    }

    assert assess_mg_core(incidental).is_core is False
    assert assess_mg_core(incidental).reason_code in {
        "single_background_mention", "secondary_non_mg_disease_title"
    }
    assert assess_mg_core(trial).is_core is True
    assert assess_mg_core(trial).reason_code == "explicit_mg_title"
    assert assess_mg_core(ici_safety).is_core is True
    assert assess_mg_core(ici_safety).reason_code == "explicit_mg_title"


def test_china_builder_defensively_enforces_mg_core_and_evidence_gate():
    module = load_script("build-frontend-data.py")
    records = [
        {
            "pmid": "keep",
            "title": "Generalized myasthenia gravis cohort in China",
            "china_related": True,
            "evidence_level": "III",
        },
        {
            "pmid": "non-core",
            "title": "Gastrointestinal malignancy cohort in China",
            "abstract": "Myasthenia gravis was mentioned once as background.",
            "china_related": True,
            "evidence_level": "III",
        },
        {
            "pmid": "ungraded",
            "title": "Myasthenia gravis guideline from China",
            "china_related": True,
            "evidence_level": None,
        },
    ]

    payload = module.build_china(records)

    assert payload["summary"]["recent_year_articles"] == 1
    assert [item["pmid"] for item in payload["pubmed_articles"]] == ["keep"]
    assert payload["pubmed_articles"][0]["mg_core"] is True
    assert payload["pubmed_articles"][0]["evidence_level"] == "III"


def test_weekly_processing_applies_mg_gate_before_evidence_and_routes_guidelines(tmp_path):
    module = load_script("enrich-weekly-literature.py")
    guideline_cache = tmp_path / "guidelines.json"
    articles = [
        {
            "pmid": "1",
            "title": "International consensus guidance for management of myasthenia gravis",
            "abstract": "Myasthenia gravis management recommendations from an international expert panel.",
            "study_types": ["Consensus"],
            "evidence_level": None,
        },
        {
            "pmid": "2",
            "title": "Generalized myasthenia gravis randomized controlled trial",
            "abstract": "Generalized myasthenia gravis participants were randomized against placebo in this trial.",
            "study_types": ["RCT"],
            "evidence_level": "II",
        },
        {
            "pmid": "3",
            "title": "Titin expression in gastrointestinal malignancy",
            "abstract": "Myasthenia gravis is one background association. This study concerns gastrointestinal cancer.",
            "study_types": ["Adjusted Retrospective Cohort"],
            "evidence_level": "III",
        },
    ]

    result = module.processArticles(articles, {}, {}, guideline_cache)

    assert [item["pmid"] for item in result["kept"]] == ["2"]
    assert result["counters"]["dropped_not_mg_core"] == 1
    assert result["counters"]["routed_guideline_consensus"] == 1
    cached = json.loads(guideline_cache.read_text(encoding="utf-8"))
    assert [item["pmid"] for item in cached["records"]] == ["1"]


def test_guideline_channel_requires_primary_guideline_or_consensus_markers():
    from scripts.common.guideline_consensus import isGuidelineConsensus

    assert isGuidelineConsensus({
        "title": "International consensus guidance for management of myasthenia gravis",
        "study_types": ["Consensus"],
        "pub_types": ["Journal Article"],
    }) is True
    assert isGuidelineConsensus({
        "title": "Guidance for the management of myasthenia gravis during the COVID-19 pandemic",
        "study_types": ["Practice Guideline"],
        "pub_types": ["Journal Article", "Practice Guideline"],
    }) is True
    assert isGuidelineConsensus({
        "title": "Refinement of a rat myasthenia gravis model: an update to the guidelines",
        "study_types": ["Guideline/Consensus"],
        "pub_types": ["Journal Article"],
    }) is False
    assert isGuidelineConsensus({
        "title": "Efficacy and safety of tacrolimus as long-term monotherapy for myasthenia gravis",
        "study_types": ["Guideline/Consensus"],
        "pub_types": ["Journal Article"],
    }) is False


def test_merge_defensively_rejects_non_mg_and_non_evidence_records():
    module = load_script("merge-weekly-literature.py")
    incoming = [
        {"pmid": "keep", "title": "Generalized myasthenia gravis trial", "evidence_level": "II"},
        {"pmid": "background", "title": "Gastrointestinal malignancy study", "abstract": "Myasthenia gravis is mentioned once.", "evidence_level": "III"},
        {"pmid": "guideline", "title": "Myasthenia gravis guideline", "evidence_level": None},
    ]
    eligible, counters = module.filterEligibleIncoming(incoming)
    assert [item["pmid"] for item in eligible] == ["keep"]
    assert counters == {"not_mg_core": 1, "missing_evidence_level": 1}


def test_public_derivation_filters_mixed_historical_base_and_routes_only_mg_guidelines(tmp_path):
    module = load_script("merge-weekly-literature.py")
    cache = tmp_path / "guideline-consensus-cache.json"
    cache.write_text(json.dumps({
        "schema_version": "1.0",
        "source": "test",
        "records": [{"pmid": "guide", "title": "Old MG consensus", "study_types": ["Consensus"]}],
    }), encoding="utf-8")
    records = [
        {
            "pmid": "keep",
            "title": "Generalized myasthenia gravis randomized trial",
            "evidence_level": "II",
        },
        {
            "pmid": "titin",
            "title": "Titin expression in gastrointestinal malignancy",
            "abstract": "Myasthenia gravis is mentioned as background.",
            "evidence_level": "III",
        },
        {
            "pmid": "guide",
            "title": "Updated international consensus for myasthenia gravis",
            "abstract": "Myasthenia gravis management recommendations.",
            "study_types": ["Consensus"],
            "evidence_level": None,
        },
        {
            "pmid": "unknown",
            "title": "Myasthenia gravis news item",
            "evidence_level": None,
        },
        {
            "pmid": "not-mg-guideline",
            "title": "International consensus for gastrointestinal cancer",
            "study_types": ["Consensus"],
            "evidence_level": None,
        },
    ]

    eligible, counters = module.derivePublicArticles(records, guidelineCachePath=cache)

    assert [item["pmid"] for item in eligible] == ["keep"]
    assert counters["kept"] == 1
    assert counters["not_mg_core"] == 2
    assert counters["guideline_consensus"] == 1
    assert counters["missing_evidence_level"] == 1
    assert counters["mg_core_reason_codes"]
    cached = json.loads(cache.read_text(encoding="utf-8"))
    assert [item["pmid"] for item in cached["records"]] == ["guide"]
    assert cached["records"][0]["title"].startswith("Updated")


def test_full_derivation_rebuilds_guideline_cache_without_stale_valid_records(tmp_path):
    module = load_script("merge-weekly-literature.py")
    cache = tmp_path / "guideline-consensus-cache.json"
    cache.write_text(json.dumps({
        "records": [{
            "pmid": "stale",
            "title": "Old myasthenia gravis guideline",
            "study_types": ["Guideline"],
        }],
    }), encoding="utf-8")
    records = [{
        "pmid": "current",
        "title": "Current myasthenia gravis consensus",
        "study_types": ["Consensus"],
    }]

    module.derivePublicArticles(
        records,
        guidelineCachePath=cache,
        replaceGuidelineCache=True,
    )

    cached = json.loads(cache.read_text(encoding="utf-8"))
    assert [item["pmid"] for item in cached["records"]] == ["current"]


def test_recent_fallback_preserves_declared_semantic_full_count(tmp_path, monkeypatch):
    module = load_script("merge-weekly-literature.py")
    recent_path = tmp_path / "literature-recent.js"
    recent_path.write_text(
        "window.MG_PUBLIC_ROLLING_COUNT = 1;\n"
        "window.MG_SEMANTIC_FULL_COUNT = 10672;\n"
        "window.MG_TOTAL_COUNT = 10672;\n"
        "window.MG_LITERATURE_DATA = "
        + json.dumps([{"pmid": "1", "title": "Myasthenia gravis cohort", "evidence_level": "III"}])
        + ";\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "FULL_PATH", tmp_path / "missing-full.json")
    monkeypatch.setattr(module, "RECENT_JS_PATH", recent_path)
    monkeypatch.setattr(module, "RECENT_JSON_CACHE_PATH", tmp_path / "missing-recent.json")

    base, source, has_full, semantic_count = module.loadBaseArticles()

    assert len(base) == 1
    assert source == "literature-recent.js"
    assert has_full is False
    assert semantic_count == 10672


def test_recent_fallback_merge_writes_previous_semantic_count(tmp_path, monkeypatch):
    module = load_script("merge-weekly-literature.py")
    recent_path = tmp_path / "literature-recent.js"
    weekly_path = tmp_path / "weekly.json"
    recent_path.write_text(
        "window.MG_PUBLIC_ROLLING_COUNT = 1;\n"
        "window.MG_SEMANTIC_FULL_COUNT = 10672;\n"
        "window.MG_TOTAL_COUNT = 10672;\n"
        "window.MG_LITERATURE_DATA = "
        + json.dumps([{
            "pmid": "1",
            "title": "Myasthenia gravis cohort",
            "entry_date": "2026-07-01",
            "evidence_level": "III",
        }])
        + ";\n",
        encoding="utf-8",
    )
    weekly_path.write_text(json.dumps([{
        "pmid": "2",
        "title": "Generalized myasthenia gravis trial",
        "entry_date": "2026-07-02",
        "evidence_level": "II",
    }]), encoding="utf-8")
    monkeypatch.setattr(module, "FULL_PATH", tmp_path / "missing-full.json")
    monkeypatch.setattr(module, "RECENT_JS_PATH", recent_path)
    monkeypatch.setattr(module, "RECENT_JSON_CACHE_PATH", tmp_path / "missing-recent.json")
    monkeypatch.setattr(module, "GUIDELINE_CACHE_PATH", tmp_path / "guidelines.json")
    monkeypatch.setattr(sys, "argv", [
        "merge-weekly-literature.py", "--weekly", str(weekly_path),
    ])

    module.main()

    text = recent_path.read_text(encoding="utf-8")
    assert "window.MG_SEMANTIC_FULL_COUNT = 10672;" in text
    assert "window.MG_TOTAL_COUNT = 10672;" in text
    assert len(load_js_global(recent_path, "MG_LITERATURE_DATA")) == 2


def test_derive_only_never_requires_weekly_or_mutates_full(tmp_path, monkeypatch):
    module = load_script("merge-weekly-literature.py")
    full = tmp_path / "literature-full.json"
    recent = tmp_path / "literature-recent.js"
    cache = tmp_path / "guideline-consensus-cache.json"
    full.write_text(json.dumps([
        {
            "pmid": "keep",
            "title": "Generalized myasthenia gravis cohort",
            "entry_date": "2026-07-01",
            "evidence_level": "III",
        },
        {
            "pmid": "drop",
            "title": "Gastrointestinal malignancy Titin study",
            "abstract": "Myasthenia gravis is background only.",
            "entry_date": "2026-07-01",
            "evidence_level": "III",
        },
    ]), encoding="utf-8")
    before = full.read_bytes()
    monkeypatch.setattr(module, "FULL_PATH", full)
    monkeypatch.setattr(module, "RECENT_JS_PATH", recent)
    monkeypatch.setattr(module, "RECENT_JSON_CACHE_PATH", tmp_path / "recent.json")
    monkeypatch.setattr(module, "GUIDELINE_CACHE_PATH", cache)
    monkeypatch.setattr(module, "DEFAULT_WEEKLY_PATH", tmp_path / "does-not-exist.json")
    monkeypatch.setattr(sys, "argv", ["merge-weekly-literature.py", "--derive-only"])

    module.main()

    assert full.read_bytes() == before
    assert load_js_global(recent, "MG_LITERATURE_DATA")[0]["pmid"] == "keep"
    assert cache.exists()


def test_cloud_expert_fallback_loads_existing_nonempty_regional_shards(tmp_path, monkeypatch):
    module = load_script("build-frontend-data.py")
    manifest_path = tmp_path / "expert-profiles.js"
    china_path = tmp_path / "expert-profiles-china.js"
    international_path = tmp_path / "expert-profiles-international.js"
    manifest = {
        "generated_at": "2026-07-15T00:00:00Z",
        "summary": {"indexed_china_experts": 1, "indexed_international_experts": 1},
        "experts": [],
        "quick_expert_ids": {"china": ["cn-1"]},
        "shards": [],
    }
    atomic_write_js_global(manifest_path, "MG_EXPERT_PROFILES", manifest)
    atomic_write_js_global(china_path, "MG_EXPERT_PROFILE_CHINA", {"items": [{"id": "cn-1"}]})
    atomic_write_js_global(
        international_path,
        "MG_EXPERT_PROFILE_INTERNATIONAL",
        {"items": [{"id": "intl-1"}]},
    )
    monkeypatch.setattr(module, "EXPERT_JS_PATH", manifest_path)
    monkeypatch.setattr(module, "EXPERT_CHINA_JS_PATH", china_path)
    monkeypatch.setattr(module, "EXPERT_INTERNATIONAL_JS_PATH", international_path)

    experts = module.load_or_build_experts(None, [])
    module.write_expert_shards(experts, tmp_path)

    assert load_js_global(china_path, "MG_EXPERT_PROFILE_CHINA")["items"] == [{"id": "cn-1"}]
    assert load_js_global(international_path, "MG_EXPERT_PROFILE_INTERNATIONAL")["items"] == [{"id": "intl-1"}]


def test_default_frontend_build_preserves_nonempty_expert_files_even_when_full_exists(tmp_path, monkeypatch):
    module = load_script("build-frontend-data.py")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    recent_path = data_dir / "literature-recent.js"
    full_path = data_dir / "literature-full.json"
    manifest_path = data_dir / "expert-profiles.js"
    china_path = data_dir / "expert-profiles-china.js"
    international_path = data_dir / "expert-profiles-international.js"

    atomic_write_js_global(recent_path, "MG_LITERATURE_DATA", [])
    full_path.write_text(json.dumps([{"pmid": "full-only"}]), encoding="utf-8")
    manifest_path.write_bytes(b"window.MG_EXPERT_PROFILES = {\"summary\":{\"indexed_experts\":52584}};\n")
    china_path.write_bytes(b"window.MG_EXPERT_PROFILE_CHINA = {\"items\":[{\"id\":\"cn-1\"}]};\n")
    international_path.write_bytes(
        b"window.MG_EXPERT_PROFILE_INTERNATIONAL = {\"items\":[{\"id\":\"intl-1\"}]};\n"
    )
    before = {path.name: path.read_bytes() for path in (manifest_path, china_path, international_path)}

    monkeypatch.setattr(module, "DATA_DIR", data_dir)
    monkeypatch.setattr(module, "FULL_PATH", full_path)
    monkeypatch.setattr(module, "RECENT_JS_PATH", recent_path)
    monkeypatch.setattr(module, "RECENT_JSON_CACHE_PATH", data_dir / "missing-recent.json")
    monkeypatch.setattr(module, "EXPERT_JS_PATH", manifest_path)
    monkeypatch.setattr(module, "EXPERT_CHINA_JS_PATH", china_path)
    monkeypatch.setattr(module, "EXPERT_INTERNATIONAL_JS_PATH", international_path)
    monkeypatch.setattr(module, "semanticFullCountFromOutputs", lambda full: 10672)
    monkeypatch.setattr(
        module,
        "build_experts",
        lambda *args, **kwargs: pytest.fail("default preservation must not rebuild experts from full"),
    )
    monkeypatch.setattr(module, "build_signals", lambda recent: {})
    monkeypatch.setattr(module, "build_china", lambda recent: {})
    monkeypatch.setattr(module, "build_landscape", lambda recent: {})
    monkeypatch.setattr(module, "build_modules", lambda recent, landscape: {})
    monkeypatch.setattr(module, "build_dashboard", lambda *args: {})
    monkeypatch.setattr(module, "write_js", lambda *args: None)
    monkeypatch.setattr(sys, "argv", ["build-frontend-data.py"])

    module.main()

    after = {path.name: path.read_bytes() for path in (manifest_path, china_path, international_path)}
    assert after == before


def test_source_channel_builder_has_stable_schema_and_safe_empty_fallbacks(tmp_path):
    from scripts.common.source_channels import build_source_signals

    payload = build_source_signals(
        literature_signals_path=tmp_path / "missing-signals.js",
        guideline_cache_path=tmp_path / "missing-guidelines.json",
        regulatory_path=tmp_path / "missing-regulatory.json",
        clinicaltrials_path=tmp_path / "missing-ct.json",
        chictr_path=tmp_path / "missing-chictr.json",
        conference_path=tmp_path / "missing-conference.json",
    )

    assert payload["schema_version"] == "1.0"
    assert [channel["id"] for channel in payload["channels"]] == [
        "literatureEvidence",
        "guidelineConsensus",
        "chinaRegulatory",
        "trialRegistry",
        "conference",
    ]
    by_id = {item["id"]: item for item in payload["channels"]}
    assert by_id["literatureEvidence"]["evidence_required"] is True
    assert all(item["items"] == [] for item in payload["channels"])
    assert by_id["trialRegistry"]["sources"] == ["ClinicalTrials.gov", "ChiCTR"]


def test_source_signal_frontend_contract_is_wired_with_safe_rendering():
    html = (ROOT / "pages" / "literature.html").read_text(encoding="utf-8")
    js = (ROOT / "assets" / "literature.js").read_text(encoding="utf-8")

    assert '<script src="../data/source-signals.js"></script>' in html
    assert "sourceSignalChannels" in html
    assert "window.MG_SOURCE_SIGNALS" in js
    assert "safeUrl" in js
    assert "escapeHtml" in js
    assert "innerHTML = item.url" not in js


def test_landscape_exposes_chictr_registry_signals_without_oxford_grading():
    """ChiCTR signals moved from landscape to 情报中心临床试验 tab (v6→v7 pipeline matrix)."""
    lit_html = (ROOT / "pages" / "literature.html").read_text(encoding="utf-8")
    lit_js = (ROOT / "assets" / "literature.js").read_text(encoding="utf-8")
    land_html = (ROOT / "pages" / "landscape.html").read_text(encoding="utf-8")
    # Landscape no longer hosts ChiCTR signals
    assert 'id="chinaTrialRegistrySignals"' not in land_html
    # Literature trials tab now hosts pipeline matrix
    assert 'id="pipelineMatrixContainer"' in lit_html
    assert "renderPipelineMatrix" in lit_js
    # Trials rendering block must not apply Oxford grading
    trials_block = lit_js[lit_js.index("renderPipelineMatrix"):]
    assert "evidence_level" not in trials_block
