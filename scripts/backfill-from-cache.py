#!/usr/bin/env python3
"""
backfill-from-cache.py — 将期刊 cache 映射回文献数据

纯本地操作，不调用任何 API。从 assets/journal_metrics.json 读取 IF/分区，
映射到 data/literature-full.json 中每篇文章。

运行方式：
  python3 scripts/backfill-from-cache.py             # 更新 literature-full.json
  python3 scripts/backfill-from-cache.py --summary   # 只统计不写

数据流：
  assets/journal_metrics.json（期刊字典）
      │
      ▼  逐篇匹配 journal → IF/新锐分区
  data/literature-full.json
      │
      ▼  split-recent-data.py → 前端
"""

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
ASSETS_DIR = PROJECT / "assets"
CACHE_PATH = ASSETS_DIR / "journal_metrics.json"
FULL_PATH = DATA_DIR / "literature-full.json"


def load_cache():
    if not CACHE_PATH.exists():
        print(f"❌ {CACHE_PATH} not found")
        sys.exit(1)
    with open(CACHE_PATH) as f:
        return json.load(f)


def load_articles():
    if not FULL_PATH.exists():
        print(f"❌ {FULL_PATH} not found")
        sys.exit(1)
    with open(FULL_PATH) as f:
        return json.load(f)


def summary(cache, articles):
    """打印覆盖统计。"""
    total = len(articles)
    with_if = sum(1 for a in articles if a.get("journal_if"))
    with_quart = sum(1 for a in articles if a.get("journal_quartile"))
    with_ev = sum(1 for a in articles if a.get("evidence_level"))

    print(f"📚 文章总数: {total}")
    print(f"📦 期刊 cache: {len(cache)} 条")
    print(f"   IF>0: {sum(1 for v in cache.values() if v.get('IF') is not None and v.get('IF', 0) > 0)}")
    print(f"   IF=0: {sum(1 for v in cache.values() if v.get('IF') is None or v.get('IF', 0) == 0)}")
    print()
    print(f"📊 文献覆盖:")
    print(f"   有证据等级: {with_ev} ({with_ev/total*100:.1f}%)")
    print(f"   有 IF: {with_if} ({with_if/total*100:.1f}%)")
    print(f"   有分区: {with_quart} ({with_quart/total*100:.1f}%)")

    # 估算还能再映射多少
    article_journals = set(a["journal"] for a in articles if a.get("journal"))
    cache_journals = set(cache.keys())
    cached = article_journals & cache_journals
    missing = article_journals - cache_journals
    still_missing = sum(
        1 for a in articles
        if a.get("journal") in missing and a.get("evidence_level") and not a.get("journal_if")
    )
    print()
    print(f"🔍 期刊层面:")
    print(f"   文献期刊总数: {len(article_journals)}")
    print(f"   cache 已有: {len(cached)}")
    print(f"   cache 缺失: {len(missing)}")
    print(f"   缺失中有证据等级且缺 IF 的文献: {still_missing} 篇")


def backfill(cache, articles):
    """将 cache 映射到文章。只填充 journal_if/journal_quartile 为空且 cache 中有值的情况。"""
    filled_if = 0
    filled_quart = 0
    overwritten_if = 0
    overwritten_quart = 0

    for a in articles:
        j = a.get("journal", "")
        if not j or j not in cache:
            continue
        entry = cache[j]
        # IF
        if entry.get("IF") is not None and entry["IF"] > 0:
            if a.get("journal_if") is None:
                a["journal_if"] = entry["IF"]
                filled_if += 1
            elif a["journal_if"] != entry["IF"]:
                # IF 有更新（如 EasyScholar 覆盖了旧的 Ablesci IF）
                a["journal_if"] = entry["IF"]
                overwritten_if += 1
        # 分区
        quartile = entry.get("quartile") or entry.get("CAS")
        if quartile:
            if a.get("journal_quartile") is None:
                a["journal_quartile"] = quartile
                filled_quart += 1
            elif a["journal_quartile"] != quartile:
                a["journal_quartile"] = quartile
                overwritten_quart += 1

    return filled_if, filled_quart, overwritten_if, overwritten_quart


def main():
    only_summary = "--summary" in sys.argv

    cache = load_cache()
    articles = load_articles()

    if only_summary:
        summary(cache, articles)
        return

    filled_if, filled_quart, ov_if, ov_quart = backfill(cache, articles)

    with open(FULL_PATH, "w") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"📝 已更新 {FULL_PATH.name}")
    if filled_if or ov_if:
        print(f"   IF: 新增 {filled_if} 篇, 更新 {ov_if} 篇")
    if filled_quart or ov_quart:
        print(f"   分区: 新增 {filled_quart} 篇, 更新 {ov_quart} 篇")
    if not filled_if and not ov_if and not filled_quart and not ov_quart:
        print("   无变化")

    print()
    summary(cache, articles)


if __name__ == "__main__":
    main()
