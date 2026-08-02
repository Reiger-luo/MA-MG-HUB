from datetime import datetime
from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_ingest_manifest_accumulates_only_within_the_same_week():
    module = load_script("merge-weekly-literature.py")
    previous = {
        "window_start": "2026-07-27",
        "added_pmids": ["existing-this-week"],
    }

    same_week = module.buildIngestManifest(
        ["new-this-week"],
        ["updated"],
        generatedAt=datetime(2026, 8, 1, 9, 0),
        previous=previous,
    )
    next_week = module.buildIngestManifest(
        ["new-next-week"],
        [],
        generatedAt=datetime(2026, 8, 3, 3, 15),
        previous=same_week,
    )

    assert same_week["added_pmids"] == ["existing-this-week", "new-this-week"]
    assert same_week["window_start"] == "2026-07-27"
    assert next_week["added_pmids"] == ["new-next-week"]
    assert next_week["window_start"] == "2026-08-03"


def test_community_weekly_uses_only_true_ingest_additions():
    module = load_script("buildCommunityData.py")
    articles = [
        {"pmid": "new", "title": "New MG evidence", "entry_date": "2026/08/01 08:00", "evidence_level": "II"},
        {"pmid": "overlap", "title": "Overlapping old MG evidence", "entry_date": "2026/07/30 08:00", "evidence_level": "I"},
    ]
    assignments = {
        "new": {"primary": "fcrnTargetedTherapy"},
        "overlap": {"primary": "fcrnTargetedTherapy"},
    }
    manifest = {
        "window_start": "2026-07-27",
        "window_end": "2026-08-01",
        "basis": "pmidAbsentFromPreMergeBaseline",
        "added_pmids": ["new"],
    }

    payload = module.buildWeekly(articles, assignments, manifest, "2026-08-01 09:00:00")
    community = next(item for item in payload["communities"] if item["community_id"] == "fcrnTargetedTherapy")

    assert payload["recent_article_count"] == 1
    assert payload["basis"] == "pmidAbsentFromPreMergeBaseline"
    assert community["recent_count"] == 1
    assert [item["pmid"] for item in community["top_refs"]] == ["new"]


def test_topic_impact_ignores_overlap_records_not_added_this_week():
    module = load_script("build-curated-topic-data.py")
    topic = {
        "title": "Efgartigimod Safety Profile",
        "slug": "efgartigimod-safety-profile",
        "anchor_nodes": ["efgartigimod", "safetyOutcome"],
        "evidence_pmids": [],
    }
    articles = [
        {"pmid": "new", "title": "Safety of efgartigimod in generalized myasthenia gravis", "entry_date": "2026/08/01 08:00"},
        {"pmid": "overlap", "title": "Safety of efgartigimod in generalized myasthenia gravis", "entry_date": "2026/07/30 08:00"},
    ]

    hits = module.find_impact_articles(topic, articles, {"new"})

    assert [item["pmid"] for item in hits] == ["new"]


def test_topic_weekly_impact_is_scoped_to_assigned_communities():
    module = load_script("buildWikiTopicCoverage.py")
    topic = {
        "impact": {
            "recent_articles": [{"pmid": "new", "title": "New evidence"}],
        },
    }
    assignments = {
        "new": {
            "primary": "fcrnTargetedTherapy",
            "secondary": [{"community_id": "safetyMedicationManagement", "score": 5}],
        },
    }

    impacts = module.topicCommunityImpacts(topic, assignments)

    assert set(impacts) == {"fcrnTargetedTherapy", "safetyMedicationManagement"}
    assert "guidelineHeorAccess" not in impacts
    assert impacts["fcrnTargetedTherapy"]["recent_article_count"] == 1


def test_frontend_distinguishes_new_evidence_from_long_term_topic_pmids():
    knowledge = (ROOT / "assets" / "knowledge.js").read_text(encoding="utf-8")
    landscape = (ROOT / "assets" / "landscape.js").read_text(encoding="utf-8")

    assert "本周新证据 · " in knowledge
    assert "data-topic-community" in knowledge
    assert "topicImpactForCommunity" in landscape
    assert "专题 PMID（长期知识底座）" in landscape
    assert landscape.index("本周新入库证据") < landscape.index("专题 PMID（长期知识底座）")


def test_capability_docs_define_the_true_weekly_community_baseline():
    operations = (ROOT / "report" / "current" / "operationsManual.md").read_text(encoding="utf-8")
    design = (ROOT / "report" / "current" / "designReview.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "report" / "roadmap" / "decisionIntelligencePlan.md").read_text(encoding="utf-8")

    assert "周更前基线真正新增的 PMID" in operations
    assert "primary/secondary 社区" in operations
    assert "进入相关专题时保留社区筛选参数" in operations
    assert "不等于滚动 14 天" in design
    assert "本周真实新增 PMID" in roadmap
