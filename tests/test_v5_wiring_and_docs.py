from pathlib import Path
from types import SimpleNamespace

import importlib.util


ROOT = Path(__file__).resolve().parents[1]


def load_pipeline_module():
    path = ROOT / "scripts" / "run-weekly-pipeline.py"
    spec = importlib.util.spec_from_file_location("run_weekly_pipeline", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def pipeline_args():
    return SimpleNamespace(
        mode="authoritative-full",
        skip_fetch=True,
        local_full=False,
        reuse_ingest=True,
        skip_downstream=False,
        skip_llm=True,
        skip_status=False,
    )


def test_pipeline_step_selection_is_read_only_when_full_is_absent():
    module = load_pipeline_module()
    args = pipeline_args()
    args.mode = "validate-only"
    steps = module.pipeline_steps(args, full_available=False)
    ids = [step.id for step in steps]

    assert ids == ["validate-current-release"]
    assert "--source-only" in steps[0].command
    assert "--require-release" in steps[0].command


def test_pipeline_without_an_explicit_mode_defaults_to_read_only_validation():
    module = load_pipeline_module()
    args = pipeline_args()
    args.mode = None
    args.local_full = False

    steps = module.pipeline_steps(args, full_available=True)

    assert [step.id for step in steps] == ["validate-current-release"]


def test_pipeline_step_selection_keeps_full_dependent_builds_when_full_exists():
    module = load_pipeline_module()
    steps = module.pipeline_steps(pipeline_args(), full_available=True)
    ids = [step.id for step in steps]
    frontend = next(step for step in steps if step.id == "build-frontend")

    assert "--rebuild-experts-from-full" in frontend.command

    for step_id in (
        "build-full-index",
        "build-community",
        "build-knowledge",
        "build-china-author-network",
        "build-curated-topics",
        "build-wiki-coverage",
    ):
        assert step_id in ids


def test_literature_narrative_enrichment_is_a_required_publish_step():
    args = pipeline_args()
    args.skip_llm = False
    steps = load_pipeline_module().pipeline_steps(args, full_available=True)
    enrichment = next(step for step in steps if step.id == "enrich-literature-narrative")

    assert enrichment.optional is False


def test_merge_step_declares_the_true_weekly_ingest_manifest():
    module = load_pipeline_module()
    args = pipeline_args()
    args.skip_fetch = False
    steps = module.pipeline_steps(args, full_available=True)
    merge = next(step for step in steps if step.id == "merge-weekly")

    assert ROOT / "data" / "literature-ingest-latest.json" in merge.outputs


def test_pipeline_and_ci_wire_new_artifacts_and_local_full_gate():
    runner = (ROOT / "scripts" / "run-weekly-pipeline.py").read_text(encoding="utf-8")
    local = (ROOT / "scripts" / "run-local-weekly-sync.sh").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "weekly-pipeline.yml").read_text(encoding="utf-8")
    status = (ROOT / "scripts" / "generate-pipeline-status.py").read_text(encoding="utf-8")

    assert "filter-mg-core-literature.py" in runner
    assert "refresh-chictr-cache.py" in runner
    assert "build-clinical-trials-data.py" in runner
    assert "clinicalTrialsSummary.js" in runner
    assert "build-source-signals.py" in runner
    assert "release-manifest.js" in runner
    assert runner.count("generate_release_manifest(") == 2
    assert "Hermes 主机本地时间" in status
    assert "--mode authoritative-full" in local
    assert "DRY_RUN_INGEST_BACKUP" in local
    assert "data/literature-ingest-latest.json" in local
    assert "--mode validate-only" in workflow
    assert "contents: read" in workflow
    assert "git push" not in workflow
    assert "CHICTR_COOKIE" not in workflow
    assert "source-signals.js" in status
    assert "release-manifest.js" in status


def test_clinical_trial_maintenance_runbook_defines_monthly_workflows():
    runbook = (ROOT / "report" / "runbooks" / "clinicalTrialsMaintenance.md").read_text(encoding="utf-8")
    china_importer = (ROOT / "scripts" / "refresh-china-drug-trials-cache.py").read_text(encoding="utf-8")
    chictr_refresh = (ROOT / "scripts" / "refresh-chictr-cache.py").read_text(encoding="utf-8")

    for phrase in (
        "每 28 天",
        "CHICTR_COOKIE",
        "DownloadXml",
        "ChinaDrugTrials",
        "--dry-run",
        "--allow-large-drop",
        "china-drug-trials-changes.json",
    ):
        assert phrase in runbook
    assert "build-clinical-trials-data.py" in china_importer
    assert "--interval-days" in chictr_refresh


def test_current_docs_define_public_msl_non_recording_scope_and_v5_operations():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    manual = (ROOT / "report" / "current" / "operationsManual.md").read_text(encoding="utf-8")
    combined = readme + "\n" + manual

    for phrase in (
        "不记录拜访", "China-only", "expert-profiles-china.js",
        "expert-profiles-international.js", "MG-core", "证据等级 I–V",
        "source-signals.js", "ChiCTR", "--resume", "--from-step", "release-manifest.js",
    ):
        assert phrase in combined
    future = manual.split("## 14. 后续建设方向", 1)[1]
    assert "follow-up" not in future.lower()
    assert "拜访记录" not in future
    assert "持久记录" not in future


def test_five_minute_review_entry_point_is_linked_and_defines_product_boundary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    manual = (ROOT / "report" / "current" / "operationsManual.md").read_text(encoding="utf-8")
    review = (ROOT / "report" / "current" / "designReview.md").read_text(encoding="utf-8")

    assert "report/current/designReview.md" in readme
    assert "designReview.md" in manual
    for phrase in (
        "公开证据决策支持和拜访准备来源",
        "不是拜访记录、CRM、follow-up、互动历史或私有数据存储",
        "设计原则",
        "页面任务",
        "证据与来源频道层级",
        "MSL 建议工作流",
        "非目标",
        "权威产物",
        "5 分钟审查顺序",
        "验证命令",
        "已知限制",
    ):
        assert phrase in review


def test_current_docs_have_balanced_fences_and_no_retired_count_claims():
    paths = [
        ROOT / "README.md",
        ROOT / "report" / "current" / "operationsManual.md",
        ROOT / "report" / "current" / "designReview.md",
    ]
    retired = ("1,151", "1,154", "1,165", "10,635", "10,656")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert sum(line.lstrip().startswith("```") for line in text.splitlines()) % 2 == 0
        assert not any(value in text for value in retired)


def test_github_actions_and_docs_describe_manual_only_trigger():
    workflow = (ROOT / ".github" / "workflows" / "weekly-pipeline.yml").read_text(encoding="utf-8")
    manual = (ROOT / "report" / "current" / "operationsManual.md").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "仅手动 `workflow_dispatch`" in manual


def test_msl_has_no_visit_recording_or_browser_persistence_surface():
    html = (ROOT / "pages" / "msl.html").read_text(encoding="utf-8")
    js = (ROOT / "assets" / "msl.js").read_text(encoding="utf-8")
    combined = (html + js).lower()
    assert "localstorage" not in combined
    assert "follow-up" not in combined
    assert "visit notes" not in combined
    assert "拜访记录" not in combined
