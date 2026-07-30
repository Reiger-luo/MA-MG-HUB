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
