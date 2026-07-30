from pathlib import Path
import re


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
