#!/usr/bin/env python3
"""
merge-weekly-literature.py — 把每周 PubMed 增量合入本地 full，并派生网站 recent。

输出：
  - data/literature-full.json：本地分析底座（如果存在则 upsert 更新，仍然 gitignore）
  - data/literature-recent.js：GitHub Pages 前端公开滚动数据源
  - data/literature-recent.json：可选本地调试缓存（默认不写）

运行策略：
  - 本地工作站有 literature-full.json：weekly → full → recent.js
  - GitHub Actions 没有 literature-full.json：weekly → recent.js 轻量兜底
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path

from common.guideline_consensus import isGuidelineConsensus, updateGuidelineCache
from common.io import atomic_write_json, atomic_write_text, load_json
from common.mg_relevance import assess_mg_core
from common.signalStrength import classifySignalStrength


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
DEFAULT_WEEKLY_PATH = DATA_DIR / "literature-weekly.json"
FULL_PATH = DATA_DIR / "literature-full.json"
RECENT_JSON_CACHE_PATH = DATA_DIR / "literature-recent.json"
RECENT_JS_PATH = DATA_DIR / "literature-recent.js"
INGEST_MANIFEST_PATH = DATA_DIR / "literature-ingest-latest.json"
GUIDELINE_CACHE_PATH = DATA_DIR / "guideline-consensus-cache.json"
DAYS_RECENT = 365
EVIDENCE_LEVELS = {"I", "II", "III", "IV", "V"}

PREFER_EXISTING_FIELDS = {
    "study_types",
    "evidence_level",
    "journal_if",
    "journal_quartile",
    "china_related",
}


def loadJson(path: Path):
    return load_json(path)


def loadRecentFromJs(path: Path):
    text = path.read_text(encoding="utf-8")
    match = re.search(r"window\.MG_LITERATURE_DATA\s*=\s*(.*);\s*$", text, re.S)
    if not match:
        raise ValueError(f"无法解析 {path}")
    import json
    return json.loads(match.group(1))


def loadDeclaredSemanticFullCount(path: Path):
    text = path.read_text(encoding="utf-8")
    for name in ("MG_SEMANTIC_FULL_COUNT", "MG_TOTAL_COUNT"):
        match = re.search(rf"window\.{name}\s*=\s*(\d+)\s*;", text)
        if match:
            return int(match.group(1))
    return None


def loadRecent():
    if RECENT_JS_PATH.exists():
        articles = loadRecentFromJs(RECENT_JS_PATH)
        semanticCount = loadDeclaredSemanticFullCount(RECENT_JS_PATH) or len(articles)
        return articles, "literature-recent.js", semanticCount
    if RECENT_JSON_CACHE_PATH.exists():
        articles = loadJson(RECENT_JSON_CACHE_PATH)
        return articles, "literature-recent.json", len(articles)
    return [], "empty", 0


def loadBaseArticles():
    if FULL_PATH.exists():
        articles = loadJson(FULL_PATH)
        return articles, "literature-full.json", True, len(articles)
    recent, source, semanticCount = loadRecent()
    return recent, source, False, semanticCount


def parseDate(value: str | None):
    if not value:
        return None
    value = value.strip()
    for pattern in ("%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    match = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}):(\d{1,2}))?", value)
    if match:
        year, month, day, hour, minute = match.groups()
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
        )
    match = re.match(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", value)
    if match:
        year, month, day = match.groups()
        return datetime(int(year), int(month), int(day or 1))
    match = re.match(r"(\d{4})", value)
    if match:
        return datetime(int(match.group(1)), 1, 1)
    return None


def hasValue(value):
    if value is None:
        return False
    if value == "":
        return False
    if value == []:
        return False
    return True


def mergeArticle(existing, incoming):
    merged = dict(existing)
    for key, value in incoming.items():
        if key in PREFER_EXISTING_FIELDS and hasValue(existing.get(key)):
            continue
        if hasValue(value) or key not in merged:
            merged[key] = value
    return merged


def sortKey(article):
    dt = parseDate(article.get("entry_date")) or parseDate(article.get("pub_date")) or datetime.min
    pmid = article.get("pmid") or ""
    return (dt, pmid)


def writeRecentJson(articles):
    atomic_write_json(RECENT_JSON_CACHE_PATH, articles)


def writeFullJson(articles):
    atomic_write_json(FULL_PATH, articles)


def writeRecentJs(articles, totalCount=None):
    import json
    semanticFullCount = totalCount if totalCount is not None else len(articles)
    content = (
        f"window.MG_PUBLIC_ROLLING_COUNT = {len(articles)};\n"
        f"window.MG_SEMANTIC_FULL_COUNT = {semanticFullCount};\n"
        f"window.MG_TOTAL_COUNT = {semanticFullCount};\n"
        "window.MG_LITERATURE_DATA = "
        + json.dumps(articles, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    atomic_write_text(RECENT_JS_PATH, content)


def filterEligibleIncoming(articles):
    """合并前防御性复核 MG-core 与 Oxford I–V 门控。"""
    eligible = []
    counters = {"not_mg_core": 0, "missing_evidence_level": 0}
    for source in articles:
        article = dict(source)
        assessment = assess_mg_core(article)
        if not assessment.is_core:
            counters["not_mg_core"] += 1
            continue
        if article.get("evidence_level") not in EVIDENCE_LEVELS:
            counters["missing_evidence_level"] += 1
            continue
        article["mg_core"] = True
        article["mg_core_reason"] = assessment.reason_code
        eligible.append(article)
    return eligible, counters


def derivePublicArticles(
    articles,
    guidelineCachePath=None,
    replaceGuidelineCache=False,
):
    """对完整候选流执行 MG-core、指南分流和 I–V 公开门控。"""
    eligible = []
    guidelines = []
    counters = {
        "kept": 0,
        "not_mg_core": 0,
        "guideline_consensus": 0,
        "missing_evidence_level": 0,
        "mg_core_reason_codes": {},
        "signal_strength_counts": {"强": 0, "中": 0, "弱": 0},
    }
    for source in articles:
        article = dict(source)
        assessment = assess_mg_core(article)
        reasons = counters["mg_core_reason_codes"]
        reasons[assessment.reason_code] = reasons.get(assessment.reason_code, 0) + 1
        if not assessment.is_core:
            counters["not_mg_core"] += 1
            continue
        article["mg_core"] = True
        article["mg_core_reason"] = assessment.reason_code
        if isGuidelineConsensus(article):
            guidelines.append(article)
            counters["guideline_consensus"] += 1
            continue
        if article.get("evidence_level") not in EVIDENCE_LEVELS:
            counters["missing_evidence_level"] += 1
            continue
        signalStrength = classifySignalStrength(article)
        article["signal_strength"] = signalStrength
        counters["signal_strength_counts"][signalStrength] += 1
        eligible.append(article)
        counters["kept"] += 1
    if guidelineCachePath is not None:
        updateGuidelineCache(
            guidelineCachePath,
            guidelines,
            replace=replaceGuidelineCache,
        )
    return eligible, counters


def upsertArticles(base, incoming):
    merged, addedPmids, updatedPmids = upsertArticlesWithChanges(base, incoming)
    return merged, len(addedPmids), len(updatedPmids)


def upsertArticlesWithChanges(base, incoming):
    """合并文献并返回本次真正新增/更新的 PMID。"""
    byPmid = {article.get("pmid"): article for article in base if article.get("pmid")}
    addedPmids = []
    updatedPmids = []
    for article in incoming:
        pmid = article.get("pmid")
        if not pmid:
            continue
        if pmid in byPmid:
            before = byPmid[pmid]
            after = mergeArticle(before, article)
            byPmid[pmid] = after
            if after != before:
                updatedPmids.append(str(pmid))
        else:
            byPmid[pmid] = article
            addedPmids.append(str(pmid))
    merged = list(byPmid.values())
    merged.sort(key=sortKey, reverse=True)
    return merged, addedPmids, updatedPmids


def weekStart(value: datetime) -> datetime:
    """使用周一作为本地周更周期起点。"""
    return value.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=value.weekday())


def loadPreviousIngestManifest(path: Path):
    if not path.exists():
        return {}
    try:
        payload = loadJson(path)
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def buildIngestManifest(addedPmids, updatedPmids, generatedAt=None, previous=None, sourceFile="data/literature-weekly.json"):
    """生成本周真实入库清单；同周重跑时累积新增 PMID。"""
    generatedAt = generatedAt or datetime.now()
    currentWeekStart = weekStart(generatedAt)
    previous = previous or {}
    previousAdded = previous.get("added_pmids") or []
    if previous.get("window_start") != currentWeekStart.strftime("%Y-%m-%d"):
        previousAdded = []
    cumulativeAdded = list(dict.fromkeys([str(item) for item in previousAdded + list(addedPmids) if item]))
    return {
        "schema_version": "1.0",
        "generated_at": generatedAt.strftime("%Y-%m-%d %H:%M:%S"),
        "window_start": currentWeekStart.strftime("%Y-%m-%d"),
        "window_end": generatedAt.strftime("%Y-%m-%d"),
        "basis": "pmidAbsentFromPreMergeBaseline",
        "source_file": sourceFile,
        "added_count": len(cumulativeAdded),
        "updated_count": len(updatedPmids),
        "added_pmids": cumulativeAdded,
        "updated_pmids": list(dict.fromkeys(str(item) for item in updatedPmids if item)),
    }


def writeIngestManifest(path: Path, payload) -> None:
    atomic_write_json(path, payload)


def buildRecentArticles(articles):
    cutoff = datetime.now() - timedelta(days=DAYS_RECENT)
    recent = []
    dropped = 0
    for article in articles:
        dt = parseDate(article.get("entry_date")) or parseDate(article.get("pub_date"))
        if dt and dt < cutoff:
            dropped += 1
            continue
        recent.append(article)
    recent.sort(key=sortKey, reverse=True)
    return recent, dropped


def main():
    parser = argparse.ArgumentParser(description="Merge weekly PubMed data into public rolling recent.js")
    parser.add_argument("--weekly", default=str(DEFAULT_WEEKLY_PATH), help="weekly JSON input path")
    parser.add_argument(
        "--derive-only",
        action="store_true",
        help="只从现有 full（或 recent fallback）重建严格公开 recent，不合并 weekly、不写 full",
    )
    parser.add_argument("--write-json-cache", action="store_true", help="同时写本地 literature-recent.json 调试缓存")
    args = parser.parse_args()

    base, source, hasFull, declaredSemanticCount = loadBaseArticles()
    weekly = []
    gateCounters = {"not_mg_core": 0, "missing_evidence_level": 0}
    added = 0
    updated = 0
    addedPmids = []
    updatedPmids = []
    mergedBase = base
    if not args.derive_only:
        weeklyPath = Path(args.weekly)
        if not weeklyPath.exists():
            raise SystemExit(f"缺少 {weeklyPath}")
        weekly, gateCounters = filterEligibleIncoming(loadJson(weeklyPath))
        mergedBase, addedPmids, updatedPmids = upsertArticlesWithChanges(base, weekly)
        added = len(addedPmids)
        updated = len(updatedPmids)
        if hasFull and (added or updated):
            writeFullJson(mergedBase)
        previousIngest = loadPreviousIngestManifest(INGEST_MANIFEST_PATH)
        ingestManifest = buildIngestManifest(
            addedPmids,
            updatedPmids,
            previous=previousIngest,
            sourceFile=str(weeklyPath),
        )
        writeIngestManifest(INGEST_MANIFEST_PATH, ingestManifest)

    publicBase, publicGateCounters = derivePublicArticles(
        mergedBase,
        guidelineCachePath=GUIDELINE_CACHE_PATH,
        replaceGuidelineCache=hasFull,
    )
    recent, dropped = buildRecentArticles(publicBase)
    semanticCount = len(mergedBase) if hasFull else declaredSemanticCount
    writeRecentJs(recent, totalCount=semanticCount)
    if args.write_json_cache:
        writeRecentJson(recent)
    elif RECENT_JSON_CACHE_PATH.exists():
        RECENT_JSON_CACHE_PATH.unlink()

    if args.derive_only:
        print("✅ derive-only 已从现有基线重建严格公开 recent.js（未合并 weekly、未写 full）")
    else:
        print("✅ weekly 已同步到文献存储并派生 recent.js")
    print(f"   输入基线: {len(base)} 篇（来源 {source}）")
    print(f"   输入 weekly: {len(weekly)} 篇")
    print(f"   合并前防御门控: {gateCounters}")
    print(f"   完整公开流门控: {publicGateCounters}")
    print(f"   新增: {added}")
    print(f"   更新: {updated}")
    if not args.derive_only:
        print(f"   本周累计新增 PMID: {len(ingestManifest['added_pmids'])}")
    if hasFull:
        print(f"   full 本地分析底座: {len(mergedBase)} 篇")
    else:
        print("   full 本地分析底座: 不存在，已使用 recent.js 兜底")
    print(f"   滚动窗口剔除: {dropped}")
    print(f"   输出 recent.js: {len(recent)} 篇")
    if args.write_json_cache:
        print("   本地 JSON cache: 已写入")
    else:
        print("   本地 JSON cache: 默认不保留")


if __name__ == "__main__":
    main()
