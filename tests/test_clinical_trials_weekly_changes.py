"""CT.gov 周更变化 diff：快照基线、变化提炼与首页摘要接线。"""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
BUILDER_PATH = PROJECT / "scripts" / "build-clinical-trials-data.py"


def load_builder_module():
    spec = importlib.util.spec_from_file_location("build_clinical_trials_data", BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_study(
    nct_id: str,
    status: str = "RECRUITING",
    first_post: str = "2026-07-01",
    last_update: str = "2026-07-01",
    results_post: str | None = None,
    title: str = "Study",
) -> dict:
    status_module = {
        "overallStatus": status,
        "studyFirstPostDateStruct": {"date": first_post},
        "lastUpdatePostDateStruct": {"date": last_update},
    }
    if results_post:
        status_module["resultsFirstPostDateStruct"] = {"date": results_post}
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id, "officialTitle": title},
            "statusModule": status_module,
        }
    }


def test_snapshot_and_diff_detect_added_status_results_and_removal():
    module = load_builder_module()
    payload = {"studies": [
        make_study("NCT001", first_post="2026-07-25", last_update="2026-07-25", title="New study"),
        make_study("NCT002", status="COMPLETED", first_post="2026-01-01", last_update="2026-07-24"),
        make_study("NCT003", first_post="2026-01-01", last_update="2026-07-23", results_post="2026-07-23"),
        make_study("NCT004", first_post="2026-01-01", last_update="2026-07-22"),
        make_study("NCT005", first_post="2026-01-01", last_update="2026-06-01"),
    ]}
    current = module.build_ct_snapshot(payload)
    baseline = {
        "NCT002": {"registry_id": "NCT002", "status": "RECRUITING", "first_post_date": "2026-01-01",
                   "last_update_date": "2026-07-24", "results_post_date": ""},
        "NCT003": {"registry_id": "NCT003", "status": "RECRUITING", "first_post_date": "2026-01-01",
                   "last_update_date": "2026-07-23", "results_post_date": ""},
        "NCT004": {"registry_id": "NCT004", "status": "RECRUITING", "first_post_date": "2026-01-01",
                   "last_update_date": "2026-07-15", "results_post_date": ""},
        "NCT005": {"registry_id": "NCT005", "status": "RECRUITING", "first_post_date": "2026-01-01",
                   "last_update_date": "2026-06-01", "results_post_date": ""},
        "NCT999": {"registry_id": "NCT999", "status": "RECRUITING", "first_post_date": "2026-01-01",
                   "last_update_date": "2026-01-01", "results_post_date": ""},
    }
    titles = module.ct_titles_from_payload(payload)
    changes = module.diff_ct_weekly_changes(
        current, baseline, date(2026, 7, 27), titles, previous_snapshot_at="2026-07-20"
    )

    assert changes["added_count"] == 1
    assert changes["added"][0]["registry_id"] == "NCT001"
    assert changes["added"][0]["url"] == "https://clinicaltrials.gov/study/NCT001"
    assert changes["status_change_count"] == 1
    assert changes["status_changes"][0]["registry_id"] == "NCT002"
    assert changes["status_changes"][0]["from_label"] == "招募中"
    assert changes["status_changes"][0]["to_label"] == "已完成"
    assert changes["results_posted_count"] == 1
    assert changes["results_posted"][0]["registry_id"] == "NCT003"
    # NCT004 窗口内字段更新计入；NCT005 窗口外不计入
    assert changes["updated_count"] == 1
    assert changes["updated"][0]["registry_id"] == "NCT004"
    assert changes["removed_count"] == 1
    assert changes["removed"] == ["NCT999"]
    assert changes["previous_snapshot_at"] == "2026-07-20"
    assert changes["window_days"] == 7
    assert changes["window_start"] == "2026-07-20"


def test_baseline_loader_prefers_local_file_and_returns_empty_outside_repo(tmp_path):
    module = load_builder_module()
    snapshot_path = tmp_path / "snap.json"
    snapshot_path.write_text(
        json.dumps({"snapshot_date": "2026-07-20", "entries": {"NCT1": {"registry_id": "NCT1"}}}),
        encoding="utf-8",
    )
    entries, snapshot_date = module.load_baseline_ct_snapshot(snapshot_path)
    assert snapshot_date == "2026-07-20"
    assert "NCT1" in entries

    # 项目外缺失路径：既不读文件也无法 git show，安全降级为空基线
    entries, snapshot_date = module.load_baseline_ct_snapshot(tmp_path / "missing.json")
    assert entries == {}
    assert snapshot_date == ""


def test_build_weekly_changes_writes_baseline_and_reports_first_run(tmp_path, monkeypatch):
    module = load_builder_module()
    snapshot_path = tmp_path / "snapshot.json"
    monkeypatch.setattr(module, "WEEKLY_CHANGES_SNAPSHOT_PATH", snapshot_path)
    monkeypatch.setattr(module, "load_baseline_ct_snapshot", lambda snapshot_path=None: ({}, ""))
    payload = {
        "generated_at": "2026-07-27T08:00:00+00:00",
        "studies": [
            make_study("NCT010", first_post="2026-07-26", last_update="2026-07-26", title="Fresh"),
            make_study("NCT011", first_post="2026-05-01", last_update="2026-07-21", title="Updated only"),
        ],
    }
    changes = module.build_weekly_changes(payload, "2026-07-27")
    assert changes["previous_snapshot_at"] == ""
    assert changes["comparison_available"] is False
    assert changes["added_count"] == 0
    assert changes["added"] == []
    assert changes["updated_count"] == 0
    assert changes["updated"] == []

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["entry_count"] == 2
    assert "NCT010" in snapshot["entries"]
    assert snapshot["entries"]["NCT010"]["status"] == "RECRUITING"


def test_identical_snapshot_is_idempotent():
    module = load_builder_module()
    payload = {"studies": [
        make_study("NCT020", first_post="2026-07-20", last_update="2026-07-25", title="Stable"),
    ]}
    current = module.build_ct_snapshot(payload)
    changes = module.diff_ct_weekly_changes(
        current, current, date(2026, 7, 27), module.ct_titles_from_payload(payload),
        previous_snapshot_at="2026-07-20",
    )

    assert changes["comparison_available"] is True
    for key in ("added_count", "status_change_count", "results_posted_count", "updated_count", "removed_count"):
        assert changes[key] == 0


def test_summary_payload_includes_weekly_changes():
    module = load_builder_module()
    payload = {"meta": {"generated_at": "2026-07-27"}, "sources": [], "pipeline_matrix": [], "decision_signals": []}
    changes = {"added_count": 2, "status_change_count": 0}
    summary = module.buildSummaryPayload(payload, changes)
    assert summary["weekly_changes"] == changes
    # 未提供时降级为空对象，前端按占位提示渲染
    assert module.buildSummaryPayload(payload)["weekly_changes"] == {}
    # trial_insights 同理降级
    assert module.buildSummaryPayload(payload)["trial_insights"] == {}


def test_trial_insights_extract_population_phase_and_recent_trend():
    module = load_builder_module()
    ct_payload = {"studies": [
        {"protocolSection": {
            "identificationModule": {"nctId": "NCT001"},
            "designModule": {"phases": ["PHASE3"]},
            "eligibilityModule": {"stdAges": ["ADULT", "OLDER_ADULT"]},
            "statusModule": {"studyFirstPostDateStruct": {"date": "2026-06-15"}},
        }},
        {"protocolSection": {
            "identificationModule": {"nctId": "NCT002"},
            "designModule": {"phases": ["PHASE1"]},
            "eligibilityModule": {"stdAges": ["CHILD"]},
            "statusModule": {"studyFirstPostDateStruct": {"date": "2026-01-01"}},
        }},
    ]}
    records = [
        {"phase_label": "Phase 3", "registered_date": "2026-06-15", "drug_name": "Efgartigimod"},
        {"phase_label": "Phase 1", "registered_date": "2026-01-01", "drug_name": "Ravulizumab"},
        {"phase_label": "N/A", "registered_date": "2026-05-01"},
        {"phase_label": "0", "registered_date": "2026-04-01"},
    ]
    insights = module.build_trial_insights(ct_payload, records, date(2026, 7, 27))
    assert {"label": "含成人", "count": 1} in insights["population_distribution"]
    assert {"label": "含儿童/青少年", "count": 1} in insights["population_distribution"]
    phase_labels = [p["label"] for p in insights["phase_concentration"]]
    assert "Phase 3" in phase_labels
    assert "未标注" in phase_labels  # N/A 合并到未标注
    assert "N/A" not in phase_labels
    assert "0" not in phase_labels
    assert next(p["count"] for p in insights["phase_concentration"] if p["label"] == "未标注") == 2
    assert insights["recent_registrations"]["count"] == 3
    recent_phases = insights["recent_registrations"]["top_phases"]
    assert {"label": "未标注", "count": 2} in recent_phases
    recent_drugs = [d["label"] for d in insights["recent_registrations"]["top_drugs"]]
    assert "Efgartigimod" in recent_drugs


def test_public_outputs_use_atomic_text_writes():
    source = BUILDER_PATH.read_text(encoding="utf-8")
    assert "atomic_write_text(OUTPUT_PATH, output)" in source
    assert "atomic_write_text(summaryOutputPath, summaryOutput)" in source
    assert "OUTPUT_PATH.write_text" not in source


def test_pipeline_and_publish_chain_wires_weekly_changes_snapshot():
    runner = (PROJECT / "scripts" / "run-weekly-pipeline.py").read_text(encoding="utf-8")
    local = (PROJECT / "scripts" / "run-local-weekly-sync.sh").read_text(encoding="utf-8")
    workflow = (PROJECT / ".github" / "workflows" / "weekly-pipeline.yml").read_text(encoding="utf-8")
    status = (PROJECT / "scripts" / "generate-pipeline-status.py").read_text(encoding="utf-8")
    for text in (runner, status):
        assert "clinicaltrials-weekly-changes-snapshot.json" in text
    assert "git add -u -- data pages index.html" in local
    assert "git add -u -- data assets pages index.html" not in local
    assert "--mode validate-only" in workflow
    assert "git push" not in workflow
