"""公开站点数据产物契约。

这里集中维护浏览器会直接或按需加载的 data/*.js 文件。发布清单、管线输出
声明和发布前校验必须复用同一份契约，避免通配符把缺失文件误判为完整发布。
"""

from __future__ import annotations

from pathlib import Path


publicDataGlobals = {
    "backendOptions.js": "MG_BACKEND_OPTIONS",
    "china-author-network.js": "MG_CHINA_AUTHOR_NETWORK",
    "china-intelligence.js": "MG_CHINA_DATA",
    "clinical-trials-data.js": "MG_CLINICAL_TRIALS_DATA",
    "clinicalTrialsSummary.js": "MG_CLINICAL_TRIALS_SUMMARY",
    "communityAssignmentIndex.js": "MG_COMMUNITY_ASSIGNMENT_INDEX",
    "communityAssignmentsRecent.js": "MG_COMMUNITY_RECENT_ASSIGNMENTS",
    "communityAudit.js": "MG_COMMUNITY_AUDIT",
    "communityCards.js": "MG_COMMUNITY_CARDS",
    "communityTaxonomy.js": "MG_COMMUNITY_TAXONOMY",
    "communityWeekly.js": "MG_COMMUNITY_WEEKLY",
    "conference-data.js": "MG_CONFERENCE_DATA",
    "content-modules.js": "MG_CONTENT_MODULES",
    "curated-topics.js": "MG_CURATED_TOPICS",
    "dashboard-data.js": "MG_DASHBOARD_DATA",
    "expert-profiles-china.js": "MG_EXPERT_PROFILE_CHINA",
    "expert-profiles-international.js": "MG_EXPERT_PROFILE_INTERNATIONAL",
    "expert-profiles.js": "MG_EXPERT_PROFILES",
    "graphHealth.js": "MG_GRAPH_HEALTH",
    "knowledge-graph.js": "MG_KNOWLEDGE_GRAPH",
    "landscape-data.js": "MG_LANDSCAPE_DATA",
    "landscapeInsights.js": "MG_LANDSCAPE_INSIGHTS",
    "literature-full-index.js": "MG_LITERATURE_FULL_INDEX",
    "literature-recent.js": "MG_LITERATURE_DATA",
    "pipeline-status.js": "MG_PIPELINE_STATUS",
    "signals-weekly.js": "MG_SIGNALS_DATA",
    "source-signals.js": "MG_SOURCE_SIGNALS",
    "wikiTopicCoverage.js": "MG_WIKI_TOPIC_COVERAGE",
}


communityShardNames = (
    "communityAssignments-clinicalSubtypesStratification.js",
    "communityAssignments-competitiveLandscapeIndirectComparison.js",
    "communityAssignments-complementAndNovelTargets.js",
    "communityAssignments-diagnosisMonitoringPrediction.js",
    "communityAssignments-efficacyBurdenOutcomes.js",
    "communityAssignments-fcrnTargetedTherapy.js",
    "communityAssignments-guidelineHeorAccess.js",
    "communityAssignments-mechanismTranslationalMedicine.js",
    "communityAssignments-rweClinicalPathway.js",
    "communityAssignments-safetyMedicationManagement.js",
    "communityAssignments-unassigned.js",
)


def publicArtifactNames() -> tuple[str, ...]:
    """返回必须进入一次完整静态发布的 JS 文件名。"""
    return tuple(sorted((*publicDataGlobals.keys(), *communityShardNames)))


def publicArtifactPaths(dataDir: Path) -> list[Path]:
    """把公开产物契约解析为指定 data 目录下的路径。"""
    return [Path(dataDir) / name for name in publicArtifactNames()]


def communityArtifactPaths(dataDir: Path) -> list[Path]:
    """返回 buildCommunityData.py 必须完整生成的公开文件。"""
    names = (
        "communityTaxonomy.js",
        "communityAssignmentIndex.js",
        "communityAssignmentsRecent.js",
        *communityShardNames,
        "communityCards.js",
        "communityWeekly.js",
        "communityAudit.js",
    )
    return [Path(dataDir) / name for name in names]
