"""临床试验信号的确定性门控、强度上限与专家解读边界。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "scripts" / "enrich-clinical-trial-signals.py"


def load_module():
    scripts = str(PROJECT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("enrich_clinical_trial_signals", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_validator():
    path = PROJECT / "scripts" / "validatePublicRelease.py"
    spec = importlib.util.spec_from_file_location("validate_trial_signal_release", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def candidate(**overrides):
    payload = {
        "candidateId": "ClinicalTrials.gov:NCT00000001:added",
        "registry": "ClinicalTrials.gov",
        "registryId": "NCT00000001",
        "registryRefs": [{
            "registry": "ClinicalTrials.gov",
            "registryId": "NCT00000001",
            "url": "https://clinicaltrials.gov/study/NCT00000001",
        }],
        "title": "A study in generalized myasthenia gravis",
        "phase": "Phase 2",
        "studyType": "INTERVENTIONAL",
        "conditions": ["Myasthenia Gravis"],
        "population": "Adults with generalized myasthenia gravis",
        "interventions": ["Test biologic"],
        "eventType": "added",
        "fromStatus": "",
        "toStatus": "NOT_YET_RECRUITING",
        "status": "NOT_YET_RECRUITING",
        "changes": {},
        "changeSummary": "",
        "whyStopped": "",
        "date": "2026-08-10",
    }
    payload.update(overrides)
    return payload


def test_new_key_phase_three_trial_is_strong():
    module = load_module()
    result = module.deterministic_decision(candidate(phase="Phase 3"))

    assert result["trialImportance"] == "关键"
    assert result["updateMateriality"] == "高"
    assert result["deterministicDecision"] == "include"
    assert result["deterministicStrength"] == "强"


@pytest.mark.parametrize(
    ("event_type", "from_status", "to_status"),
    [
        ("status_change", "NOT_YET_RECRUITING", "RECRUITING"),
        ("status_change", "ACTIVE_NOT_RECRUITING", "COMPLETED"),
        ("results_posted", "COMPLETED", "COMPLETED"),
    ],
)
def test_key_trial_development_milestones_can_be_strong(event_type, from_status, to_status):
    module = load_module()
    result = module.deterministic_decision(candidate(
        phase="Phase 3", eventType=event_type, fromStatus=from_status,
        toStatus=to_status, status=to_status,
    ))

    assert result["trialImportance"] == "关键"
    assert result["updateMateriality"] == "高"
    assert result["deterministicStrength"] == "强"


def test_key_trial_admin_only_update_stays_background():
    module = load_module()
    result = module.deterministic_decision(candidate(
        phase="Phase 3", eventType="updated",
        changes={"contact": {"before": "A", "after": "B"}},
        changeSummary="联系人更新",
    ))

    assert result["trialImportance"] == "关键"
    assert result["updateMateriality"] == "轻微"
    assert result["deterministicDecision"] == "background"
    assert result["deterministicStrength"] == ""


def test_phase_two_unmet_population_is_key_but_sponsor_is_not_a_reason():
    module = load_module()
    importance, rationale, _ = module.classify_trial_importance(candidate(
        title="Phase 2 treatment for MuSK-positive generalized myasthenia gravis",
        phase="Phase 2",
    ))
    general_importance, general_rationale, _ = module.classify_trial_importance(candidate(
        title="Sponsor-backed Phase 2 generalized myasthenia gravis study",
        phase="Phase 2",
    ))

    assert importance == "关键"
    assert "未满足" in rationale
    assert general_importance == "一般"
    assert "申办" not in general_rationale


def test_general_phase_two_high_update_is_medium_and_early_limited_update_is_weak():
    module = load_module()
    general = module.deterministic_decision(candidate(
        eventType="updated",
        changes={"primary_outcome": {"before": "A", "after": "B"}},
        changeSummary="主要终点更新",
    ))
    early = module.deterministic_decision(candidate(
        phase="Phase 1", eventType="added", interventions=["Exploratory biologic"],
    ))

    assert general["trialImportance"] == "一般"
    assert general["updateMateriality"] == "高"
    assert general["deterministicStrength"] == "中"
    assert early["trialImportance"] == "早期/探索"
    assert early["updateMateriality"] == "中等"
    assert early["deterministicStrength"] == "弱"


def test_non_mg_and_lems_records_are_excluded_before_scoring():
    module = load_module()
    lems = module.deterministic_decision(candidate(
        title="Lambert-Eaton myasthenic syndrome in small-cell lung cancer",
        conditions=["Lambert-Eaton Myasthenic Syndrome", "Small Cell Lung Cancer"],
        population="Adults with LEMS and SCLC",
        phase="Phase 3",
    ))

    assert lems["mgCore"] is False
    assert lems["deterministicDecision"] == "exclude"
    assert lems["deterministicStrength"] == ""


def test_cross_registry_duplicate_keeps_all_official_refs():
    module = load_module()
    full_title = "A randomized double-blind controlled study of treatment in generalized myasthenia gravis"
    left = module.deterministic_decision(candidate(title=full_title))
    right = module.deterministic_decision(candidate(
        candidateId="ChiCTR:ChiCTR260000001:added",
        registry="ChiCTR", registryId="ChiCTR260000001",
        title=full_title,
        registryRefs=[{
            "registry": "ChiCTR", "registryId": "ChiCTR260000001",
            "url": "https://www.chictr.org.cn/showproj.html?proj=1",
        }],
    ))

    merged = module.merge_duplicate_candidates([left, right])

    assert len(merged) == 1
    assert {ref["registry"] for ref in merged[0]["registryRefs"]} == {"ClinicalTrials.gov", "ChiCTR"}
    assert {event["registry"] for event in merged[0]["sourceEvents"]} == {"ClinicalTrials.gov", "ChiCTR"}
    assert "NCT00000001" in merged[0]["candidateId"]
    assert "ChiCTR260000001" in merged[0]["candidateId"]


def test_explicit_cross_registration_id_merges_even_when_titles_differ():
    module = load_module()
    ct = module.deterministic_decision(candidate(
        title="Short CT title", crossRegistryIds=["ChiCTR260000001"],
    ))
    chictr = module.deterministic_decision(candidate(
        candidateId="ChiCTR:ChiCTR260000001:added",
        registry="ChiCTR", registryId="ChiCTR260000001", title="不同的中文短标题",
        crossRegistryIds=["NCT00000001"],
        registryRefs=[{
            "registry": "ChiCTR", "registryId": "ChiCTR260000001",
            "url": "https://www.chictr.org.cn/showproj.html?proj=1",
        }],
    ))

    merged = module.merge_duplicate_candidates([ct, chictr])

    assert len(merged) == 1
    assert len(merged[0]["registryRefs"]) == 2


def test_llm_cannot_raise_strength_or_turn_results_registration_into_positive_efficacy():
    module = load_module()
    weak = module.deterministic_decision(candidate(phase="Phase 1"))

    def fake_complete(_prompt, **_kwargs):
        return json.dumps({
            "decisions": [{"candidateId": weak["candidateId"], "decision": "include", "reason": "值得继续跟踪该开发节点"}],
            "signals": [{
                "candidateId": weak["candidateId"], "strength": "强", "type": "开发进展",
                "title": "一项早期重症肌无力试验新增登记",
                "takeaway": "本次新增登记提供了可核实的早期开发节点",
                "whySignal": "可用于跟踪后续招募与设计演进",
                "evidenceBoundary": "尚无疗效或安全性结果可以判断",
                "maUse": "用于准备开发格局讨论",
                "kolQuestion": "该设计对患者筛选有何影响？",
                "mslAction": "核对官方登记的终点与人群。",
            }],
        }, ensure_ascii=False)

    signals, decisions = module.analyze_candidates([weak], complete_fn=fake_complete)

    assert signals[0]["strength"] == "弱"
    assert decisions[0]["strength"] == "弱"

    result_candidate = module.deterministic_decision(candidate(phase="Phase 3", eventType="results_posted"))
    normalized = module.normalize_signal(result_candidate, {
        "title": "关键研究首次上传注册结果",
        "takeaway": "登记结果显示疗效有效并改善患者结局",
        "whySignal": "结果记录出现改变了后续核查优先级",
        "evidenceBoundary": "尚未核对完整结果与统计分析",
        "maUse": "用于结果核查",
        "kolQuestion": "如何看待后续结果披露？",
        "mslAction": "打开官方登记核对结果模块。",
    }, 1)
    assert "疗效有效" not in normalized["takeaway"]
    assert "尚未核对" in normalized["evidenceBoundary"]


def test_incomplete_llm_decisions_fail_closed():
    module = load_module()
    eligible = module.deterministic_decision(candidate(phase="Phase 3"))

    with pytest.raises(RuntimeError, match="decisions mismatch"):
        module.analyze_candidates(
            [eligible],
            complete_fn=lambda *_args, **_kwargs: json.dumps({"decisions": [], "signals": []}),
        )


def test_public_validator_rejects_wrong_registry_ref_and_strength_above_cap(monkeypatch):
    validator = load_validator()
    sources = ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials")
    trial_payload = {
        "source_policy": {"llm_enrichment": True},
        "source_windows": {source: {"source_revision": "rev"} for source in sources},
        "analysis_cohort": [{
            "candidateId": "NCT1:added", "deterministicStrength": "弱",
            "registryRefs": [{"registry": "ClinicalTrials.gov", "registryId": "NCT1", "url": "https://clinicaltrials.gov/study/NCT1"}],
        }],
        "selection_decisions": [{"candidateId": "NCT1:added", "decision": "include", "strength": "弱"}],
        "signals": [{
            "id": "T01", "candidateId": "NCT1:added", "strength": "强",
            "strengthScale": "trial_milestone_priority", "eventType": "added",
            "evidenceBoundary": "仅为注册里程碑，不代表疗效结论。",
            "registryRefs": [{"registry": "ClinicalTrials.gov", "registryId": "NCT999", "url": "https://clinicaltrials.gov/study/NCT999"}],
        }],
        "signal_summary": {"total_count": 1, "strength_counts": {"强": 1, "中": 0, "弱": 0}},
    }
    payloads = {
        "literature-recent.js": [],
        "communityAssignmentsRecent.js": {"item_count": 0, "items": []},
        "signals-weekly.js": {
            "window_basis": "trueIngestAddedPmids", "signals": [],
            "source_policy": {"llm_enrichment": True},
        },
        "dashboard-data.js": {"stats": {"recent_articles": 0, "signals": 0}},
        "clinicalTrialsSummary.js": {
            "source_updates": {source: {"revision": "rev"} for source in sources},
            "weekly_changes": {},
        },
        "trial-signals-weekly.js": trial_payload,
    }

    def fake_load(path, global_name):
        if global_name == "MG_LITERATURE_META":
            return {"item_count": 0}
        return payloads[path.name]

    monkeypatch.setattr(validator, "load_js_global", fake_load)
    errors = validator.validateRecentContracts()

    assert "试验信号 T01 突破确定性强度上限" in errors
    assert "试验信号 T01 的官方登记引用与确定性候选不一致" in errors


def test_public_validator_rejects_stale_trial_signal_source_revision(monkeypatch):
    validator = load_validator()
    sources = ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials")
    payloads = {
        "literature-recent.js": [],
        "communityAssignmentsRecent.js": {"item_count": 0, "items": []},
        "signals-weekly.js": {
            "window_basis": "trueIngestAddedPmids", "signals": [],
            "source_policy": {"llm_enrichment": True},
        },
        "dashboard-data.js": {"stats": {"recent_articles": 0, "signals": 0}},
        "clinicalTrialsSummary.js": {
            "source_updates": {source: {"revision": "current"} for source in sources},
            "weekly_changes": {"generated_at": "2026-08-10"},
        },
        "trial-signals-weekly.js": {
            "source_policy": {"llm_enrichment": True},
            "source_windows": {
                source: {
                    "updated_at": "2026-08-10" if source == "ClinicalTrials.gov" else "2026-08-01",
                    "source_revision": "stale" if source == "ChiCTR" else "current",
                }
                for source in sources
            },
            "analysis_cohort": [], "selection_decisions": [], "signals": [],
            "signal_summary": {"total_count": 0, "strength_counts": {"强": 0, "中": 0, "弱": 0}},
        },
    }

    def fake_load(path, global_name):
        if global_name == "MG_LITERATURE_META":
            return {"item_count": 0}
        return payloads[path.name]

    monkeypatch.setattr(validator, "load_js_global", fake_load)
    errors = validator.validateRecentContracts()
    assert "试验信号窗口落后于 ChiCTR 当前缓存 revision" in errors


def test_unchanged_source_windows_preserve_last_good_without_reanalysis(monkeypatch, tmp_path):
    module = load_module()
    output_path = tmp_path / "trial-signals-weekly.js"
    output_path.write_text("window.MG_TRIAL_SIGNALS_DATA = {};", encoding="utf-8")
    monkeypatch.setattr(module, "OUTPUT_PATH", output_path)
    windows = {
        source: {"updated_at": "2026-08-01"}
        for source in ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials")
    }
    previous = {"source_windows": windows, "analysis_cohort": [], "signals": []}
    monkeypatch.setattr(module, "load_js_global", lambda *_args, **_kwargs: previous)
    monkeypatch.setattr(module, "build_candidates", lambda _previous: ([], windows))
    monkeypatch.setattr(
        module, "analyze_candidates",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("窗口未推进时不应重做分析")),
    )
    monkeypatch.setattr(
        module, "atomic_write_js_global",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("窗口未推进时不应改写 last-good")),
    )
    monkeypatch.setattr(sys, "argv", [SCRIPT.name])

    assert module.main() == 0


def test_replay_allows_a_legitimate_empty_frozen_cohort(monkeypatch, tmp_path):
    module = load_module()
    output_path = tmp_path / "trial-signals-weekly.js"
    output_path.write_text("window.MG_TRIAL_SIGNALS_DATA = {};", encoding="utf-8")
    monkeypatch.setattr(module, "OUTPUT_PATH", output_path)
    previous = {
        "source_windows": {
            source: {"updated_at": "2026-08-01"}
            for source in ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials")
        },
        "analysis_cohort": [], "signals": [],
    }
    written = {}
    monkeypatch.setattr(module, "load_js_global", lambda *_args, **_kwargs: previous)
    monkeypatch.setattr(module, "current_source_versions", lambda: {
        source: {"updated_at": "2026-08-01", "source_revision": "rev", "legacy_source_revision": "legacy"}
        for source in ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials")
    })
    monkeypatch.setattr(
        module, "atomic_write_js_global",
        lambda path, name, payload: written.update({"path": path, "name": name, "payload": payload}),
    )
    monkeypatch.setattr(sys, "argv", [SCRIPT.name, "--replay-current-window"])

    assert module.main() == 0
    assert written["payload"]["signals"] == []
    assert written["payload"]["source_policy"]["replay_window_preserved"] is True
    assert all(window["source_revision"] == "rev" for window in written["payload"]["source_windows"].values())


def test_replay_does_not_attach_current_revision_to_an_older_frozen_window(monkeypatch, tmp_path):
    module = load_module()
    output_path = tmp_path / "trial-signals-weekly.js"
    output_path.write_text("window.MG_TRIAL_SIGNALS_DATA = {};", encoding="utf-8")
    monkeypatch.setattr(module, "OUTPUT_PATH", output_path)
    previous = {
        "source_windows": {
            source: {"updated_at": "2026-08-01"}
            for source in ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials")
        },
        "analysis_cohort": [], "signals": [],
    }
    written = {}
    monkeypatch.setattr(module, "load_js_global", lambda *_args, **_kwargs: previous)
    monkeypatch.setattr(module, "current_source_versions", lambda: {
        source: {"updated_at": "2026-08-08", "source_revision": "new-rev", "legacy_source_revision": "legacy"}
        for source in ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials")
    })
    monkeypatch.setattr(
        module, "atomic_write_js_global",
        lambda path, name, payload: written.update({"payload": payload}),
    )
    monkeypatch.setattr(sys, "argv", [SCRIPT.name, "--replay-current-window"])

    assert module.main() == 0
    assert all("source_revision" not in window for window in written["payload"]["source_windows"].values())
