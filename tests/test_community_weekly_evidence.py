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


def test_frontend_marks_curated_topics_as_static_snapshot():
    knowledge = (ROOT / "assets" / "knowledge.js").read_text(encoding="utf-8")
    contract = (ROOT / "scripts" / "common" / "publicDataContract.py").read_text(encoding="utf-8")

    # 策展专题就地展开，明确标注为静态快照、非实时证据。
    # curated-topics.js 已于 2026-10-26 停止周更，旧的"本周新证据"角标是事实错误，已移除。
    assert "topicSnapshotDate" in knowledge
    assert "静态策展快照" in knowledge
    assert "本周新证据" not in knowledge
    assert "topicsById" in knowledge
    assert "renderTopicCuration" in knowledge
    # 社区视图/证据矩阵下线后，周更社区数据仍作为公开产物保留（诊疗现状滚动层数据源）
    assert "communityWeekly.js" in contract
    assert "communityAudit.js" in contract
    # wiki 覆盖层已退役
    assert "wikiTopicCoverage.js" not in contract


def test_related_topic_opens_inline_and_deep_link_is_consumed():
    """专题在工作台右栏展开、深链 ?topic= 有接收端、三层工作台结构就位。"""
    knowledge = (ROOT / "assets" / "knowledge.js").read_text(encoding="utf-8")
    landscape = (ROOT / "assets" / "landscape.js").read_text(encoding="utf-8")
    html = (ROOT / "pages" / "knowledge.html").read_text(encoding="utf-8")

    # 整个知识图谱模块无任何页面跳转（唯一外链是 PMID 的 target=_blank）
    # 旧问题：专题曾无条件外跳诊治格局第一章节并丢掉 topicId；现在只允许带 chapter id 的精确深链
    assert "landscape.html?tab=chapters'" not in knowledge
    assert "pages/landscape.html?tab=chapters&chapter=" in knowledge
    assert "location.href" not in knowledge
    # 深链接收端
    assert "getInitialKnowledgeTopicId" in knowledge
    assert "selectNode(anchorNodeId, { topicId: initialTopicId })" in knowledge
    assert "function renderTopicCuration" in knowledge
    # 三段式工作台渲染函数
    assert "function renderWorkbench" in knowledge
    assert "function renderCuration" in knowledge
    assert "function renderCrossEvidence" in knowledge
    assert "function hideEvidencePane" in knowledge
    # 旧的外跳函数与三 tab 死代码已清理
    assert "function topicHref" not in knowledge
    assert "function topicHref" not in landscape
    assert "function renderCommunityProfileBlock" not in knowledge
    assert "switchWorkbenchTab" not in knowledge
    # 数据层仍叫 community，前端显示名已简化为"主题 / 医学主题"
    assert "全部主题" in html
    assert "医学主题" in html
    assert "全部医学社区" not in html
    # 三段式工作台结构：左关系 / 右策展 / 下文献
    assert 'id="kgRelationList"' in html
    assert 'id="kgCurationPanel"' in html
    assert 'id="kgEvidencePane"' in html
    assert 'id="kgEvidenceClose"' in html
    assert 'data-workbench-tab' not in html


def test_capability_docs_define_the_true_weekly_community_baseline():
    operations = (ROOT / "report" / "current" / "operationsManual.md").read_text(encoding="utf-8")
    design = (ROOT / "report" / "current" / "designReview.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "report" / "roadmap" / "decisionIntelligencePlan.md").read_text(encoding="utf-8")

    assert "周更前基线真正新增的 PMID" in operations
    assert "primary/secondary 社区" in operations
    # 相关专题已改为就地展开静态策展快照，不再有"社区→专题"的周更过滤流程
    assert "静态策展知识底座" in operations
    assert "?topic=<id>" in operations
    assert "不等于滚动 14 天" in design
    assert "本周真实新增 PMID" in roadmap
