#!/usr/bin/env python3
"""
generate-pipeline-status.py — 生成 MA-MG-HUB 数据管线状态。

只输出可公开的运行状态与数据产物摘要，不写入本地路径、Token 或内部专家信息。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from common.io import atomic_write_js_global, load_js_global, load_json


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
SITE_URL = "https://reiger-luo.github.io/MA-MG-HUB/"
PUBLIC_PATH_PREFIX = "/MA-MG-HUB/"


PUBLIC_ARTIFACTS = [
    ("dashboard-data.js", "Dashboard 数据", "MG_DASHBOARD_DATA"),
    ("literature-recent.js", "近一年文献公开库", "MG_LITERATURE_DATA"),
    ("literature-full-index.js", "全库文献轻索引", "MG_LITERATURE_FULL_INDEX"),
    ("signals-weekly.js", "候选信号", "MG_SIGNALS_DATA"),
    ("source-signals.js", "独立来源信号频道", "MG_SOURCE_SIGNALS"),
    ("clinical-trials-data.js", "三源临床试验数据", "MG_CLINICAL_TRIALS_DATA"),
    ("clinicalTrialsSummary.js", "首页临床试验摘要", "MG_CLINICAL_TRIALS_SUMMARY"),
    ("release-manifest.js", "一致性发布清单", "MG_RELEASE_MANIFEST"),
    ("china-intelligence.js", "中国情报", "MG_CHINA_DATA"),
    ("expert-profiles.js", "专家画像", "MG_EXPERT_PROFILES"),
    ("landscape-data.js", "诊治格局", "MG_LANDSCAPE_DATA"),
    ("landscapeInsights.js", "动态诊治格局洞察", "MG_LANDSCAPE_INSIGHTS"),
    ("knowledge-graph.js", "知识库图谱", "MG_KNOWLEDGE_GRAPH"),
    ("graphHealth.js", "图谱健康", "MG_GRAPH_HEALTH"),
    ("china-author-network.js", "中国作者医院联络图", "MG_CHINA_AUTHOR_NETWORK"),
    ("curated-topics.js", "专题层", "MG_CURATED_TOPICS"),
    ("wikiTopicCoverage.js", "专题社区覆盖", "MG_WIKI_TOPIC_COVERAGE"),
    ("communityTaxonomy.js", "社区 Taxonomy", "MG_COMMUNITY_TAXONOMY"),
    ("communityAssignmentIndex.js", "社区归类索引", "MG_COMMUNITY_ASSIGNMENT_INDEX"),
    ("communityAssignmentsRecent.js", "近一年社区归类", "MG_COMMUNITY_RECENT_ASSIGNMENTS"),
    ("communityCards.js", "社区卡片", "MG_COMMUNITY_CARDS"),
    ("communityWeekly.js", "社区周更", "MG_COMMUNITY_WEEKLY"),
    ("communityAudit.js", "社区 Audit", "MG_COMMUNITY_AUDIT"),
    ("backendOptions.js", "Phase 6 后端选项评估", "MG_BACKEND_OPTIONS"),
    ("content-modules.js", "内容模块", "MG_CONTENT_MODULES"),
    ("weekly-summary.md", "当前通讯渠道周报", None),
]


def loadJson(path: Path):
    return load_json(path)


def loadJs(filename: str, globalName: str):
    return load_js_global(DATA_DIR / filename, globalName)


def safeLoadJs(filename: str, globalName: str):
    path = DATA_DIR / filename
    if not path.exists():
        return None
    return loadJs(filename, globalName)


def numberValue(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def firstNumber(payload: dict, keys: tuple[str, ...]):
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = numberValue(payload.get(key))
        if value is not None:
            return value
    return None


def readWindowNumber(path: Path, globalName: str):
    if not path.exists():
        return None
    match = re.search(rf"window\.{re.escape(globalName)}\s*=\s*(\d+)\s*;", path.read_text(encoding="utf-8"))
    if not match:
        return None
    return int(match.group(1))


def generatedAtFromPayload(payload):
    if not isinstance(payload, dict):
        return None
    for key in ("generated_at", "generatedAt", "updated_at", "last_updated"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def fileUpdatedAt(path: Path):
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def fileUpdatedEpoch(path: Path):
    return path.stat().st_mtime if path.exists() else None


def shardDeclaredTotal(shards):
    if not isinstance(shards, list) or not shards:
        return None
    total = 0
    seen = False
    for shard in shards:
        count = firstNumber(shard, ("count", "item_count", "items_count"))
        if count is None:
            continue
        total += count
        seen = True
    return total if seen else None


def countPayload(payload):
    if payload is None:
        return 0
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        direct = firstNumber(payload, ("item_count", "total_count", "count"))
        if direct is not None:
            return direct
        summary = payload.get("summary") or {}
        summaryCount = firstNumber(summary, ("indexed_experts", "total_experts", "total_articles", "article_count"))
        if summaryCount is not None:
            return summaryCount
        shardTotal = shardDeclaredTotal(payload.get("shards"))
        if shardTotal is not None:
            return shardTotal
        for key in ("signals", "insights", "options", "triggers", "articles", "pubmed_articles", "experts", "modules", "topics", "topic_coverage", "nodes", "items", "communities", "cards", "shards"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return None
    return None


def resolvePublicDataPath(pathValue: str | None):
    if not pathValue:
        return None
    value = str(pathValue).split("?", 1)[0].strip()
    if value.startswith(PUBLIC_PATH_PREFIX):
        value = value[len(PUBLIC_PATH_PREFIX):]
    value = value.lstrip("/")
    if value.startswith("data/"):
        return PROJECT / value
    if value:
        return DATA_DIR / Path(value).name
    return None


def loadCommunityShard(path: Path):
    text = path.read_text(encoding="utf-8")
    match = re.search(r"window\.MG_COMMUNITY_ASSIGNMENT_SHARDS\[[^\]]+\]\s*=\s*", text)
    if not match:
        raise ValueError(f"Cannot find community assignment shard payload in {path}")
    decoder = json.JSONDecoder()
    payload, _ = decoder.raw_decode(text[match.end():].lstrip())
    return payload


def shardInfo(payload: dict, kind: str):
    shards = payload.get("shards") if isinstance(payload, dict) else []
    if not isinstance(shards, list) or not shards:
        return None

    items = []
    declaredTotal = 0
    actualTotal = 0
    hasDeclared = False
    hasActual = False
    checks = []
    for shard in shards:
        path = resolvePublicDataPath(shard.get("path") or shard.get("file"))
        declaredCount = firstNumber(shard, ("count", "item_count", "items_count"))
        actualCount = None
        shardGeneratedAt = None
        exists = bool(path and path.exists())
        if declaredCount is not None:
            declaredTotal += declaredCount
            hasDeclared = True
        if exists:
            try:
                if kind == "expert":
                    shardPayload = load_js_global(path, shard.get("global") or "")
                else:
                    shardPayload = loadCommunityShard(path)
                actualCount = countPayload(shardPayload)
                shardGeneratedAt = generatedAtFromPayload(shardPayload)
            except Exception as exc:
                checks.append({
                    "id": shard.get("id") or shard.get("community_id") or path.name,
                    "status": "warning",
                    "message": f"分片读取失败：{exc}",
                })
        if actualCount is not None:
            actualTotal += actualCount
            hasActual = True
        if declaredCount is not None and actualCount is not None and declaredCount != actualCount:
            checks.append({
                "id": shard.get("id") or shard.get("community_id") or path.name,
                "status": "warning",
                "message": f"分片声明 {declaredCount} 与实际 {actualCount} 不一致",
            })
        items.append({
            "id": shard.get("id") or shard.get("community_id") or (path.stem if path else ""),
            "label": shard.get("label") or shard.get("community_id") or shard.get("id") or "",
            "path": str(path.relative_to(PROJECT)) if path and path.exists() else (shard.get("path") or shard.get("file") or ""),
            "declared_count": declaredCount,
            "actual_count": actualCount,
            "generated_at": shardGeneratedAt,
            "exists": exists,
            "loaded_by_default": shard.get("loaded_by_default"),
        })

    if hasDeclared and hasActual and declaredTotal != actualTotal:
        checks.append({
            "id": f"{kind}ShardTotal",
            "status": "warning",
            "message": f"分片声明合计 {declaredTotal} 与实际合计 {actualTotal} 不一致",
        })

    return {
        "items": items,
        "declared_total": declaredTotal if hasDeclared else None,
        "actual_total": actualTotal if hasActual else None,
        "checks": checks,
    }


def artifactInfo(filename: str, label: str, globalName: str | None):
    path = DATA_DIR / filename
    if not path.exists():
        return {
            "id": filename,
            "label": label,
            "status": "missing",
            "status_label": "缺失",
            "count": None,
            "updated_at": None,
            "generated_at": None,
            "file_updated_at": None,
            "size_kb": None,
        }

    count = None
    payload = None
    checks = []
    if globalName:
        payload = loadJs(filename, globalName)
        count = countPayload(payload)

    shards = None
    if filename == "expert-profiles.js" and isinstance(payload, dict):
        shards = shardInfo(payload, "expert")
    elif filename == "communityAssignmentIndex.js" and isinstance(payload, dict):
        shards = shardInfo(payload, "community")

    if shards:
        checks.extend(shards["checks"])
        if filename == "expert-profiles.js":
            count = shards["actual_total"] or shards["declared_total"] or count
        if count is not None and shards["declared_total"] is not None and count != shards["declared_total"]:
            checks.append({
                "id": f"{filename}:shardCount",
                "status": "warning",
                "message": f"主计数 {count} 与分片声明合计 {shards['declared_total']} 不一致",
            })

    if isinstance(payload, dict):
        itemCount = firstNumber(payload, ("item_count", "count"))
        items = payload.get("items")
        if itemCount is not None and isinstance(items, list) and itemCount != len(items):
            checks.append({
                "id": f"{filename}:itemCount",
                "status": "warning",
                "message": f"item_count {itemCount} 与 items {len(items)} 不一致",
            })

    generatedAt = generatedAtFromPayload(payload)
    updatedAt = generatedAt or fileUpdatedAt(path)
    info = {
        "id": filename,
        "label": label,
        "status": "warning" if checks else "ok",
        "status_label": "需核对" if checks else "已生成",
        "count": count,
        "updated_at": updatedAt,
        "generated_at": generatedAt,
        "file_updated_at": fileUpdatedAt(path),
        "size_kb": round(path.stat().st_size / 1024, 1),
    }
    if shards:
        info["shard_count"] = len(shards["items"])
        info["shard_total_count"] = shards["actual_total"] or shards["declared_total"]
        info["shards"] = shards["items"]
    if checks:
        info["checks"] = checks
    return info


def semanticFullCounts(fullPath: Path, fullIndex: dict, communityIndex: dict, communityAudit: dict):
    counts = []
    if fullPath.exists():
        counts.append({"source": "literature-full.json", "count": len(loadJson(fullPath))})
    if isinstance(fullIndex, dict):
        count = countPayload(fullIndex)
        if count is not None:
            counts.append({"source": "literature-full-index.js", "count": count})
    if isinstance(communityIndex, dict):
        count = countPayload(communityIndex)
        if count is not None:
            counts.append({"source": "communityAssignmentIndex.js", "count": count})
    if isinstance(communityAudit, dict):
        count = firstNumber(communityAudit.get("summary") or {}, ("total_articles",))
        if count is not None:
            counts.append({"source": "communityAudit.js", "count": count})
    return counts


def recentSourceRows(literature: list, communityRecent: dict):
    rows = []
    literaturePath = DATA_DIR / "literature-recent.js"
    if literaturePath.exists():
        rows.append({
            "id": "literature-recent.js",
            "label": "公开文献 recent",
            "count": len(literature),
            "updated_at": fileUpdatedAt(literaturePath),
            "updated_epoch": fileUpdatedEpoch(literaturePath),
            "role": "literature",
        })

    communityRecentPath = DATA_DIR / "communityAssignmentsRecent.js"
    if communityRecentPath.exists() and isinstance(communityRecent, dict):
        rows.append({
            "id": "communityAssignmentsRecent.js",
            "label": "社区归类 recent",
            "count": countPayload(communityRecent),
            "updated_at": fileUpdatedAt(communityRecentPath),
            "generated_at": generatedAtFromPayload(communityRecent),
            "updated_epoch": fileUpdatedEpoch(communityRecentPath),
            "role": "community_assignments",
        })
    rows.sort(key=lambda item: (item.get("updated_epoch") or 0, item["id"]), reverse=True)
    return rows


def activeRecentSource(recentRows):
    if not recentRows:
        return None
    return recentRows[0]


def buildCountChecks(publicRollingCount, declaredPublicRollingCount, legacyTotalCount, declaredSemanticFullCount, semanticCountRows, recentRows):
    checks = []
    activeRecent = activeRecentSource(recentRows)
    recentAssignmentRow = next((row for row in recentRows if row["id"] == "communityAssignmentsRecent.js"), None)
    recentAssignmentCount = recentAssignmentRow.get("count") if recentAssignmentRow else None
    semanticValues = {row["count"] for row in semanticCountRows}
    semanticFullCount = semanticCountRows[0]["count"] if semanticCountRows else None
    if len(semanticValues) == 1:
        checks.append({
            "id": "semanticFullConsistency",
            "label": "semantic full count",
            "status": "ok",
            "message": f"full-index/community/raw full 均为 {semanticFullCount} 篇",
        })
    elif semanticCountRows:
        checks.append({
            "id": "semanticFullConsistency",
            "label": "semantic full count",
            "status": "warning",
            "message": "semantic full 候选计数不一致：" + "；".join(f"{row['source']}={row['count']}" for row in semanticCountRows),
        })
    else:
        checks.append({
            "id": "semanticFullConsistency",
            "label": "semantic full count",
            "status": "missing",
            "message": "未找到 semantic full 计数来源",
        })

    if declaredPublicRollingCount is None:
        checks.append({
            "id": "publicRollingDeclaredCount",
            "label": "public rolling count",
            "status": "manual",
            "message": "literature-recent.js 尚未写入 MG_PUBLIC_ROLLING_COUNT；使用 MG_LITERATURE_DATA 长度兜底",
        })
    elif declaredPublicRollingCount == publicRollingCount:
        checks.append({
            "id": "publicRollingDeclaredCount",
            "label": "public rolling count",
            "status": "ok",
            "message": f"MG_PUBLIC_ROLLING_COUNT 与公开数组长度均为 {publicRollingCount} 篇",
        })
    else:
        checks.append({
            "id": "publicRollingDeclaredCount",
            "label": "public rolling count",
            "status": "warning",
            "message": f"MG_PUBLIC_ROLLING_COUNT={declaredPublicRollingCount}，公开数组长度={publicRollingCount}",
        })

    if declaredSemanticFullCount is not None and semanticFullCount is not None:
        checks.append({
            "id": "semanticFullDeclaredCount",
            "label": "semantic full declared count",
            "status": "ok" if declaredSemanticFullCount == semanticFullCount else "warning",
            "message": (
                f"MG_SEMANTIC_FULL_COUNT 与 semantic full 均为 {semanticFullCount} 篇"
                if declaredSemanticFullCount == semanticFullCount
                else f"MG_SEMANTIC_FULL_COUNT={declaredSemanticFullCount}，semantic full={semanticFullCount}"
            ),
        })

    if legacyTotalCount is not None and semanticFullCount is not None and legacyTotalCount != semanticFullCount:
        checks.append({
            "id": "legacyTotalCount",
            "label": "legacy MG_TOTAL_COUNT",
            "status": "warning",
            "message": f"MG_TOTAL_COUNT={legacyTotalCount}，semantic full={semanticFullCount}；该字段仅保留兼容",
        })

    if activeRecent:
        checks.append({
            "id": "activeRecentSource",
            "label": "active recent source",
            "status": "ok",
            "message": f"当前采用最新 recent 文件 {activeRecent['id']}={activeRecent['count']} 条；更新时间 {activeRecent.get('updated_at') or '-'}",
        })

    if recentAssignmentCount is not None and recentAssignmentCount != publicRollingCount:
        if activeRecent:
            staleRows = [row for row in recentRows if row["id"] != activeRecent["id"]]
            staleText = "；".join(f"{row['id']}={row['count']} ({row.get('updated_at') or '-'})" for row in staleRows) or "无"
            checks.append({
                "id": "recentSourceDivergence",
                "label": "recent source divergence",
                "status": "ok",
                "message": f"recent 文件计数不同，按最新文件 {activeRecent['id']}={activeRecent['count']} 条生效；较旧文件：{staleText}",
            })
            return checks
        checks.append({
            "id": "recentAssignmentWindow",
            "label": "recent assignment window",
            "status": "warning",
            "message": f"近一年社区归类 {recentAssignmentCount} 条，公开 rolling {publicRollingCount} 篇；需确认 cutoff 口径",
        })

    return checks


def buildStatus():
    dashboard = safeLoadJs("dashboard-data.js", "MG_DASHBOARD_DATA") or {}
    literature = safeLoadJs("literature-recent.js", "MG_LITERATURE_DATA") or []
    fullIndex = safeLoadJs("literature-full-index.js", "MG_LITERATURE_FULL_INDEX") or {}
    signals = safeLoadJs("signals-weekly.js", "MG_SIGNALS_DATA") or {}
    modules = safeLoadJs("content-modules.js", "MG_CONTENT_MODULES") or []
    backendOptions = safeLoadJs("backendOptions.js", "MG_BACKEND_OPTIONS") or {}
    communityIndex = safeLoadJs("communityAssignmentIndex.js", "MG_COMMUNITY_ASSIGNMENT_INDEX") or {}
    communityRecent = safeLoadJs("communityAssignmentsRecent.js", "MG_COMMUNITY_RECENT_ASSIGNMENTS") or {}
    communityAudit = safeLoadJs("communityAudit.js", "MG_COMMUNITY_AUDIT") or {}

    stats = dashboard.get("stats") or {}
    fullPath = DATA_DIR / "literature-full.json"
    weeklyPath = DATA_DIR / "literature-weekly.json"
    regulatoryPath = DATA_DIR / "china-regulatory-status.json"
    clinicalTrialsPath = DATA_DIR / "clinicaltrials-pipeline-cache.json"
    chictrPath = DATA_DIR / "chictr-trials-cache.json"
    chinaDrugTrialsPath = DATA_DIR / "china-drug-trials-cache.json"
    chinaDrugTrialsChangesPath = DATA_DIR / "china-drug-trials-changes.json"
    localFullCount = None
    weeklyCount = None
    regulatoryPayload = {}
    clinicalTrialsPayload = {}
    chictrPayload = {}
    chinaDrugTrialsPayload = {}
    chinaDrugTrialsChanges = {}
    if fullPath.exists():
        localFullCount = len(loadJson(fullPath))
    if weeklyPath.exists():
        weeklyCount = len(loadJson(weeklyPath))
    if regulatoryPath.exists():
        regulatoryPayload = loadJson(regulatoryPath)
    if clinicalTrialsPath.exists():
        clinicalTrialsPayload = loadJson(clinicalTrialsPath)
    if chictrPath.exists():
        chictrPayload = loadJson(chictrPath)
    if chinaDrugTrialsPath.exists():
        chinaDrugTrialsPayload = loadJson(chinaDrugTrialsPath)
    if chinaDrugTrialsChangesPath.exists():
        chinaDrugTrialsChanges = loadJson(chinaDrugTrialsChangesPath)

    recentCount = len(literature)
    declaredRollingCount = readWindowNumber(DATA_DIR / "literature-recent.js", "MG_PUBLIC_ROLLING_COUNT")
    declaredSemanticFullCount = readWindowNumber(DATA_DIR / "literature-recent.js", "MG_SEMANTIC_FULL_COUNT")
    legacyTotalCount = readWindowNumber(DATA_DIR / "literature-recent.js", "MG_TOTAL_COUNT")
    semanticCountRows = semanticFullCounts(fullPath, fullIndex, communityIndex, communityAudit)
    semanticFullCount = semanticCountRows[0]["count"] if semanticCountRows and len({row["count"] for row in semanticCountRows}) == 1 else (
        localFullCount or countPayload(fullIndex) or countPayload(communityIndex)
    )
    recentRows = recentSourceRows(literature, communityRecent)
    activeRecent = activeRecentSource(recentRows)
    activeRecentCount = activeRecent.get("count") if activeRecent else recentCount
    recentAssignmentCount = next((row.get("count") for row in recentRows if row["id"] == "communityAssignmentsRecent.js"), None)
    countChecks = buildCountChecks(
        recentCount,
        declaredRollingCount,
        legacyTotalCount,
        declaredSemanticFullCount,
        semanticCountRows,
        recentRows,
    )
    signalCount = len(signals.get("signals") or [])
    generatedAt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    storageMode = "local_full_first" if fullPath.exists() else ("semantic_full_index" if semanticFullCount else "recent_fallback")
    countWarningCount = sum(1 for check in countChecks if check.get("status") == "warning")

    sources = [
        {
            "id": "pubmed",
            "name": "PubMed 公开 rolling 源",
            "meta": f"{recentCount} 篇近1年公开文献 · {stats.get('china_articles', 0)} 篇中国相关 · {signalCount} 条候选信号",
            "status": "warning" if any(check.get("id") == "publicRollingDeclaredCount" and check.get("status") == "warning" for check in countChecks) else "ok",
            "status_label": "需核对" if any(check.get("id") == "publicRollingDeclaredCount" and check.get("status") == "warning" for check in countChecks) else "正常",
        },
        {
            "id": "fullStorage",
            "name": "semantic full 语义底座",
            "meta": (
                f"full-index / community 层 {semanticFullCount} 篇 · raw full {'本地可用' if localFullCount is not None else '未入公开仓库'}"
                if semanticFullCount is not None
                else "等待 literature-full-index.js 或 communityAssignmentIndex.js"
            ),
            "status": "warning" if any(check.get("id") == "semanticFullConsistency" and check.get("status") == "warning" for check in countChecks) else ("ok" if semanticFullCount is not None else "manual"),
            "status_label": "需核对" if any(check.get("id") == "semanticFullConsistency" and check.get("status") == "warning" for check in countChecks) else ("已接入" if semanticFullCount is not None else "待接入"),
        },
        {
            "id": "conference",
            "name": "会议摘要",
            "meta": "暂不进入自动周更；后续按 AAN / EAN / AANEM 做独立来源",
            "status": "planned",
            "status_label": "规划中",
        },
        {
            "id": "clinicalTrials",
            "name": "ClinicalTrials.gov",
            "meta": (
                f"MG 研究缓存 {len(clinicalTrialsPayload.get('studies') or [])} 项 · 更新时间 {clinicalTrialsPayload.get('generated_at') or '待更新'}"
                if clinicalTrialsPayload
                else "等待 ClinicalTrials.gov 缓存"
            ),
            "status": "ok" if clinicalTrialsPayload else "manual",
            "status_label": "已接入" if clinicalTrialsPayload else "待接入",
        },
        {
            "id": "chictr",
            "name": "ChiCTR 官方注册缓存",
            "meta": (
                f"MG 注册记录 {len(chictrPayload.get('records') or [])} 项 · mode={chictrPayload.get('mode', 'cache')} · 核对 {chictrPayload.get('last_verified') or '待更新'}"
                if chictrPayload
                else "等待 ChiCTR 官方 JSON/CSV 缓存"
            ),
            "status": "ok" if chictrPayload else "manual",
            "status_label": "缓存可用" if chictrPayload else "待接入",
        },
        {
            "id": "chinaDrugTrials",
            "name": "ChinaDrugTrials 人工月更",
            "meta": (
                f"MG 登记记录 {len(chinaDrugTrialsPayload.get('records') or [])} 项 · "
                f"mode={chinaDrugTrialsPayload.get('mode', 'cache')} · "
                f"更新 {chinaDrugTrialsPayload.get('generated_at') or '待提交'} · "
                f"最近差异 +{chinaDrugTrialsChanges.get('added_count', 0)} "
                f"~{chinaDrugTrialsChanges.get('updated_count', 0)} "
                f"-{chinaDrugTrialsChanges.get('removed_count', 0)}"
                if chinaDrugTrialsPayload
                else "等待 ChinaDrugTrials 官方月度导出"
            ),
            "status": "ok" if chinaDrugTrialsPayload else "manual",
            "status_label": "缓存可用" if chinaDrugTrialsPayload else "待提交",
        },
        {
            "id": "regulatory",
            "name": "中国监管状态 (NMPA/CDE)",
            "meta": (
                f"{len(regulatoryPayload.get('drugs') or [])} 个 MG 相关治疗对象 · 核对 {regulatoryPayload.get('generated_at') or '待核对'}"
                if regulatoryPayload
                else "等待 data/china-regulatory-status.json"
            ),
            "status": "ok" if regulatoryPayload else "manual",
            "status_label": "已接入" if regulatoryPayload else "待接入",
        },
        {
            "id": "frontendArtifacts",
            "name": "前端数据产物",
            "meta": f"{stats.get('experts', 0)} 位专家画像 · {stats.get('modules', countPayload(modules) or 0)} 个内容模块 · 更新时间 {dashboard.get('generated_at') or generatedAt}",
            "status": "ok",
            "status_label": "已生成",
        },
        {
            "id": "backendOptions",
            "name": "Phase 6 后端选项",
            "meta": (
                f"{(backendOptions.get('summary') or {}).get('decision', '等待 backendOptions.js')} · "
                f"{(backendOptions.get('summary') or {}).get('triggered_count', 0)}/"
                f"{(backendOptions.get('summary') or {}).get('total_triggers', 5)} 个触发条件"
            ),
            "status": (backendOptions.get("summary") or {}).get("status") or "manual",
            "status_label": (backendOptions.get("summary") or {}).get("status_label") or "待评估",
        },
    ]

    artifacts = [artifactInfo(filename, label, globalName) for filename, label, globalName in PUBLIC_ARTIFACTS]
    expertArtifact = next((item for item in artifacts if item["id"] == "expert-profiles.js"), {})
    frontendSource = next((item for item in sources if item["id"] == "frontendArtifacts"), None)
    if frontendSource and expertArtifact.get("count"):
        frontendSource["meta"] = (
            f"{expertArtifact['count']} 位专家画像"
            f" · {stats.get('modules', countPayload(modules) or 0)} 个内容模块"
            f" · 更新时间 {dashboard.get('generated_at') or generatedAt}"
        )
        if expertArtifact.get("status") == "warning":
            frontendSource["status"] = "warning"
            frontendSource["status_label"] = "需核对"

    logs = [
        f"[{generatedAt[:10]}] pipeline-status.js 已生成：状态页读取真实数据产物，不再依赖页面硬编码。",
        f"[{generatedAt[:10]}] 计数口径：active recent {activeRecentCount} 条（{activeRecent.get('id') if activeRecent else 'literature-recent.js'}）；semantic full {semanticFullCount or '待识别'} 篇；signals {signalCount} 条。",
    ]
    if weeklyCount is not None:
        logs.append(f"[{generatedAt[:10]}] 当前 weekly 临时输入 {weeklyCount} 篇；默认不入仓库。")
    if localFullCount is not None:
        logs.append(f"[{generatedAt[:10]}] 本地 raw full 分析底座 {localFullCount} 篇；周更只 upsert 新增/更新文献。")
    if countWarningCount:
        logs.append(f"[{generatedAt[:10]}] 计数校验存在 {countWarningCount} 个 warning；详见 storage.count_checks。")

    return {
        "generated_at": generatedAt,
        "site_url": SITE_URL,
        "storage": {
            "mode": storageMode,
            "recent_count": recentCount,
            "public_rolling_count": recentCount,
            "active_recent_count": activeRecentCount,
            "active_recent_source": activeRecent.get("id") if activeRecent else "literature-recent.js",
            "public_rolling_declared_count": declaredRollingCount,
            "semantic_full_count": semanticFullCount,
            "semantic_full_declared_count": declaredSemanticFullCount,
            "legacy_total_count": legacyTotalCount,
            "full_available": semanticFullCount is not None,
            "full_count": semanticFullCount,
            "local_full_available": localFullCount is not None,
            "local_full_count": localFullCount,
            "weekly_temp_count": weeklyCount,
            "recent_assignment_count": recentAssignmentCount,
            "recent_sources": recentRows,
            "recent_json_cache": (DATA_DIR / "literature-recent.json").exists(),
            "semantic_full_sources": semanticCountRows,
            "count_checks": countChecks,
        },
        "pipeline": {
            "local_command": "bash scripts/run-local-weekly-sync.sh",
            "workflow": "Hermes 本地周更主流程；GitHub Actions 仅手动兜底",
            "schedule": "每周一 03:15 Asia/Shanghai；排在 efgar-wiki 周更/社区摘要之后读取本地 vault",
            "policy": "以本地 full 为源头；weekly 先 upsert full/recent，再重扫 full 的近一年窗口，读取 efgar-wiki 策展层，最后一次性生成 full-derived 公开产物并 push。",
            "upstream_sync": [
                {
                    "id": "efgar-wiki",
                    "label": "efgar-wiki 本地策展源",
                    "mode": "read_local_vault",
                    "path": "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/efgartigimod-wiki",
                    "handoff": "build-curated-topic-data.py → curated-topics.js；buildWikiTopicCoverage.py → wikiTopicCoverage.js",
                    "note": "wiki cron 先更新本地 vault；MG-HUB 周更随后读取，不让 wiki 任务直接阻断网站部署。"
                },
                {
                    "id": "mg-hub-publish",
                    "label": "MA-MG-HUB 发布链路",
                    "mode": "commit_and_push",
                    "handoff": "git commit → git push origin main → GitHub Pages",
                    "note": "非 dry-run 且工作区干净时自动执行；若无公开产物变更则不提交。"
                }
            ],
        },
        "sources": sources,
        "artifacts": artifacts,
        "logs": logs,
    }


def main():
    output = DATA_DIR / "pipeline-status.js"
    status = buildStatus()
    atomic_write_js_global(output, "MG_PIPELINE_STATUS", status)
    print(f"✅ pipeline status written: {output.relative_to(PROJECT)}")


if __name__ == "__main__":
    main()
