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
import json
import re
from datetime import datetime, timedelta
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
DEFAULT_WEEKLY_PATH = DATA_DIR / "literature-weekly.json"
FULL_PATH = DATA_DIR / "literature-full.json"
RECENT_JSON_CACHE_PATH = DATA_DIR / "literature-recent.json"
RECENT_JS_PATH = DATA_DIR / "literature-recent.js"
DAYS_RECENT = 365

PREFER_EXISTING_FIELDS = {
    "study_types",
    "evidence_level",
    "journal_if",
    "journal_quartile",
    "china_related",
}


def loadJson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def loadRecentFromJs(path: Path):
    text = path.read_text(encoding="utf-8")
    match = re.search(r"window\.MG_LITERATURE_DATA\s*=\s*(.*);\s*$", text, re.S)
    if not match:
        raise ValueError(f"无法解析 {path}")
    return json.loads(match.group(1))


def loadRecent():
    if RECENT_JS_PATH.exists():
        return loadRecentFromJs(RECENT_JS_PATH), "literature-recent.js"
    if RECENT_JSON_CACHE_PATH.exists():
        return loadJson(RECENT_JSON_CACHE_PATH), "literature-recent.json"
    return [], "empty"


def loadBaseArticles():
    if FULL_PATH.exists():
        return loadJson(FULL_PATH), "literature-full.json", True
    recent, source = loadRecent()
    return recent, source, False


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
    RECENT_JSON_CACHE_PATH.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def writeFullJson(articles):
    FULL_PATH.write_text(
        json.dumps(articles, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def writeRecentJs(articles, totalCount=None):
    semanticFullCount = totalCount if totalCount is not None else len(articles)
    with RECENT_JS_PATH.open("w", encoding="utf-8") as f:
        f.write(f"window.MG_PUBLIC_ROLLING_COUNT = {len(articles)};\n")
        f.write(f"window.MG_SEMANTIC_FULL_COUNT = {semanticFullCount};\n")
        f.write(f"window.MG_TOTAL_COUNT = {semanticFullCount};\n")
        f.write("window.MG_LITERATURE_DATA = ")
        json.dump(articles, f, ensure_ascii=False)
        f.write(";\n")


def upsertArticles(base, incoming):
    byPmid = {article.get("pmid"): article for article in base if article.get("pmid")}
    added = 0
    updated = 0
    for article in incoming:
        pmid = article.get("pmid")
        if not pmid:
            continue
        if pmid in byPmid:
            before = byPmid[pmid]
            after = mergeArticle(before, article)
            byPmid[pmid] = after
            updated += int(after != before)
        else:
            byPmid[pmid] = article
            added += 1
    merged = list(byPmid.values())
    merged.sort(key=sortKey, reverse=True)
    return merged, added, updated


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
    parser.add_argument("--write-json-cache", action="store_true", help="同时写本地 literature-recent.json 调试缓存")
    args = parser.parse_args()

    weeklyPath = Path(args.weekly)
    if not weeklyPath.exists():
        raise SystemExit(f"缺少 {weeklyPath}")

    base, source, hasFull = loadBaseArticles()
    weekly = loadJson(weeklyPath)

    mergedBase, added, updated = upsertArticles(base, weekly)
    if hasFull and (added or updated):
        writeFullJson(mergedBase)

    recent, dropped = buildRecentArticles(mergedBase)
    writeRecentJs(recent, totalCount=len(mergedBase))
    if args.write_json_cache:
        writeRecentJson(recent)
    elif RECENT_JSON_CACHE_PATH.exists():
        RECENT_JSON_CACHE_PATH.unlink()

    print(f"✅ weekly 已同步到文献存储并派生 recent.js")
    print(f"   输入基线: {len(base)} 篇（来源 {source}）")
    print(f"   输入 weekly: {len(weekly)} 篇")
    print(f"   新增: {added}")
    print(f"   更新: {updated}")
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
