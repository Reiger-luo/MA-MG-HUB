from pathlib import Path
import re
import tomllib


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"


def test_report_root_only_contains_the_document_index():
    root_markdown = sorted(path.name for path in REPORT.glob("*.md"))
    assert root_markdown == ["README.md"]


def test_long_lived_documents_use_the_expected_categories():
    expected = (
        REPORT / "current" / "operationsManual.md",
        REPORT / "current" / "designReview.md",
        REPORT / "roadmap" / "decisionIntelligencePlan.md",
        REPORT / "runbooks" / "codeReviewGraph.md",
        REPORT / "runbooks" / "clinicalTrialsMaintenance.md",
        REPORT / "reference" / "evidenceGrading.md",
        REPORT / "decisions" / "communitySemanticLayer.md",
        REPORT / "decisions" / "chinaAuthorNetwork.md",
    )
    assert all(path.is_file() for path in expected)


def test_generators_write_markdown_to_the_audit_area():
    backend = (ROOT / "scripts" / "buildBackendOptions.py").read_text(encoding="utf-8")
    community = (ROOT / "scripts" / "auditCommunityQuality.py").read_text(encoding="utf-8")

    assert '.hermes-audit" / "reports' in backend
    assert "backendOptionsLatest.md" in backend
    assert '.hermes-audit" / "reports' in community
    assert "communityQualityLatest.md" in community
    assert "--snapshot" in community

    for source in (backend, community):
        assert not re.search(r"=\s*\w+\s*/\s*[\"']report[\"']", source)


def test_current_docs_delegate_dynamic_state_to_generated_artifacts():
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "README.md",
            REPORT / "current" / "operationsManual.md",
            REPORT / "current" / "designReview.md",
        )
    )

    assert "data/pipeline-status.js" in docs
    assert "data/release-manifest.js" in docs
    assert "动态数字" in docs or "动态状态" in docs
    assert "快照日期：" not in docs
    assert not re.search(r"public_rolling_count\s*=\s*\d+", docs)
    assert not re.search(r"semantic_full_count\s*=\s*\d+", docs)


def test_sites_build_does_not_publish_internal_reports():
    builder = (ROOT / "scripts" / "build-sites-static.sh").read_text(encoding="utf-8")
    tracked_inputs = re.search(r"git -C .*? ls-files -z -- (.+?)\)", builder)
    assert tracked_inputs is not None
    assert "report" not in tracked_inputs.group(1).split()


def test_current_docs_cover_contextual_briefs_and_publication_boundaries():
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    operations = (REPORT / "current" / "operationsManual.md").read_text(encoding="utf-8")
    design = (REPORT / "current" / "designReview.md").read_text(encoding="utf-8")
    roadmap = (REPORT / "roadmap" / "decisionIntelligencePlan.md").read_text(encoding="utf-8")

    for tab in ("文献", "信号", "中国", "会议", "临床试验"):
        assert tab in operations

    assert "当前标签和筛选状态" in operations
    assert "Markdown 预览" in operations
    assert "简报跟随当前上下文" in design
    assert "buildCurrentBrief()" in roadmap
    assert "MgConferenceBrief.getContext()" in roadmap
    assert "来源层的浏览器内摘要" in roadmap

    assert "GitHub Pages" in operations
    assert "公开主站" in operations
    assert "Sites 受控部署" in operations
    assert "当前上下文简报" in root_readme
    assert "expert-profiles-international.js" in operations
    assert "可通过 GitHub Pages 公开访问" in operations
    assert "仍可通过 GitHub Pages 公开访问" in root_readme


def test_agent_rules_require_capability_docs_to_follow_site_changes():
    rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "修改情报中心标签、筛选、简报导出、发布角色或专家分片公开边界时" in rules
    assert "report/current/operationsManual.md" in rules
    assert "report/current/designReview.md" in rules
    assert "路线图的现有能力基线" in rules


def test_code_review_graph_contract_is_project_scoped_and_advisory():
    rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    runbook = (REPORT / "runbooks" / "codeReviewGraph.md").read_text(encoding="utf-8")
    workflow = (
        ROOT / ".github" / "workflows" / "code-review-graph.yml"
    ).read_text(encoding="utf-8")
    refresh_workflow = (
        ROOT / ".github" / "workflows" / "code-review-graph-refresh.yml"
    ).read_text(encoding="utf-8")
    skill_root = ROOT / ".agents" / "skills" / "refresh-review-graph"
    skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    skill_metadata = (skill_root / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )
    refresh_script_path = ROOT / "scripts" / "refreshReviewGraphAfterPush.sh"
    refresh_script = refresh_script_path.read_text(encoding="utf-8")
    weekly_sync = (ROOT / "scripts" / "run-local-weekly-sync.sh").read_text(
        encoding="utf-8"
    )
    ignore = (ROOT / ".code-review-graphignore").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    config = tomllib.loads((ROOT / ".codex" / "config.toml").read_text(encoding="utf-8"))
    server = config["mcp_servers"]["code-review-graph"]

    assert server["command"] == "uvx"
    assert "code-review-graph==2.3.7" in server["args"]
    assert server["required"] is False
    assert "detect_changes_tool" in server["enabled_tools"]
    assert "get_review_context_tool" in server["enabled_tools"]
    assert all("refactor" not in tool for tool in server["enabled_tools"])

    assert "/data/**" in ignore
    assert ".code-review-graph/" in gitignore
    assert "pull_request:" in workflow
    assert 'fail-on-risk: "none"' in workflow
    assert "6a1ee1c7063cc35cfa5ff12b8198c29360f3e4ad" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert '"data/**"' not in workflow

    assert "push:" in refresh_workflow
    assert "- main" in refresh_workflow
    assert "workflow_dispatch:" in refresh_workflow
    assert '"code-review-graph==2.3.7"' in refresh_workflow
    assert "ece7cb06caefa5fff74198d8649806c4678c61a1" in refresh_workflow
    assert "code-review-graph build" in refresh_workflow
    assert "GITHUB_STEP_SUMMARY" in refresh_workflow
    assert "pull-requests: write" not in refresh_workflow
    assert '"data/**"' not in refresh_workflow

    assert "name: refresh-review-graph" in skill
    assert "after user-approved code changes are pushed or deployed" in skill
    assert "Never infer push or deployment permission" in skill
    assert "scripts/refreshReviewGraphAfterPush.sh" in skill
    assert not (skill_root / "scripts" / "refreshGraphAfterPush.sh").exists()
    assert "allow_implicit_invocation: true" in skill_metadata
    assert 'default_prompt: "Use $refresh-review-graph' in skill_metadata
    assert 'currentHead" != "$upstreamHead' in refresh_script
    assert "graph-covered paths contain uncommitted changes" in refresh_script
    assert "build --repo" in refresh_script
    assert "detect-changes --repo" in refresh_script
    assert "update --repo" not in refresh_script

    assert "data/*|pages/*|index.html" in weekly_sync
    assert "git add -u -- data pages index.html" in weekly_sync
    assert "git add -u -- data assets pages index.html" not in weekly_sync
    assert 'pushBase=$(git rev-parse origin/main)' in weekly_sync
    assert 'bash scripts/refreshReviewGraphAfterPush.sh --base "$pushBase"' in weekly_sync
    assert weekly_sync.index("git push origin main") < weekly_sync.index(
        'bash scripts/refreshReviewGraphAfterPush.sh --base "$pushBase"'
    )

    for phrase in (
        "只提供辅助信号",
        "findings 为先",
        "不得阻塞审查",
        "不开放自动重构写入",
        "$refresh-review-graph",
        "Skill 触发本身不构成 push 或部署授权",
    ):
        assert phrase in rules

    for phrase in (
        "Review 顺序",
        "findings-first",
        "不因风险分数阻断合并",
        "CRG 不得成为审查单点故障",
        "修改与上线后的闭环",
        "完整重建 Graph",
    ):
        assert phrase in runbook


def test_current_docs_do_not_restore_obsolete_agent_workflow_instructions():
    roadmap = (REPORT / "roadmap" / "decisionIntelligencePlan.md").read_text(encoding="utf-8")

    obsolete_phrases = (
        "software-development:mg-hub-website",
        "software-development:test-driven-development",
        "software-development:requesting-code-review",
        "交由 Codex CLI",
        "Machine 负责",
        "预计工具调用",
        "background coding run",
    )
    assert all(phrase not in roadmap for phrase in obsolete_phrases)


def test_china_network_docs_name_the_real_parse_rate_source():
    operations = (REPORT / "current" / "operationsManual.md").read_text(encoding="utf-8")
    decision = (REPORT / "decisions" / "chinaAuthorNetwork.md").read_text(encoding="utf-8")

    for source in (operations, decision):
        assert "summary.graph_author_hospital_parse_rate" in source


def test_evidence_reference_uses_named_official_links():
    evidence = (REPORT / "reference" / "evidenceGrading.md").read_text(encoding="utf-8")

    assert "[官方说明与下载页](https://www.cebm.ox.ac.uk/" in evidence
    assert "[v2.1 表格 PDF](https://www.cebm.ox.ac.uk/" in evidence
    assert "官方页面：https://" not in evidence
    assert "PDF：https://" not in evidence
