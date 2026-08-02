#!/usr/bin/env python3
"""split-recent-data.py — 从 literature-full.json 截取近1年数据

输出：
  - data/literature-recent.js（近1年公开滚动数据源，前端一次加载）
  - data/literature-recent.json（可选本地调试缓存）

仅在需要从本地 full 快照重建近一年公开库时手动执行。
日常周更使用 merge-weekly-literature.py，不再依赖 full 快照。
"""

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from common.io import atomic_write_json, atomic_write_text
from common.signalStrength import classifySignalStrength

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
DAYS_RECENT = 365


def main():
    parser = argparse.ArgumentParser(description="Rebuild public recent literature data from local full snapshot")
    parser.add_argument("--write-json-cache", action="store_true", help="同时写本地 literature-recent.json 调试缓存")
    args = parser.parse_args()

    full_path = DATA_DIR / "literature-full.json"
    if not full_path.exists():
        print(f"❌ {full_path} not found")
        return

    with open(full_path) as f:
        articles = json.load(f)

    generatedAt = datetime.now()
    cutoffDate = generatedAt.date() - timedelta(days=DAYS_RECENT)

    recent = []
    strengthCounts = Counter()
    for source in articles:
        article = dict(source)
        ed = article.get("entry_date", "")
        if not ed:
            continue
        try:
            parts = ed.split("/")
            dt = datetime(int(parts[0]), int(parts[1]), int(parts[2].split()[0]))
        except (ValueError, IndexError):
            continue
        if dt.date() < cutoffDate:
            continue
        signalStrength = classifySignalStrength(article)
        if signalStrength:
            article["signal_strength"] = signalStrength
            strengthCounts[signalStrength] += 1
        else:
            article.pop("signal_strength", None)
        recent.append(article)
    if args.write_json_cache:
        recent_path = DATA_DIR / "literature-recent.json"
        atomic_write_json(recent_path, recent)
        print(f"✅ literature-recent.json cache ({len(recent)} 篇)")
    else:
        recent_path = DATA_DIR / "literature-recent.json"
        if recent_path.exists():
            recent_path.unlink()
            print("🧹 已清理 literature-recent.json cache")

    recent_js_path = DATA_DIR / "literature-recent.js"
    metadata = {
        "schema_version": "1.0",
        "generated_at": generatedAt.strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": os.environ.get("MG_PIPELINE_RUN_ID", ""),
        "source_mode": "local_full_first",
        "window_days": DAYS_RECENT,
        "window_start": cutoffDate.isoformat(),
        "window_end": generatedAt.strftime("%Y-%m-%d"),
        "item_count": len(recent),
        "semantic_full_count": len(articles),
    }
    content = (
        f"window.MG_PUBLIC_ROLLING_COUNT = {len(recent)};\n"
        f"window.MG_SEMANTIC_FULL_COUNT = {len(articles)};\n"
        f"window.MG_TOTAL_COUNT = {len(articles)};\n"
        "window.MG_LITERATURE_META = "
        + json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
        "window.MG_LITERATURE_DATA = "
        + json.dumps(recent, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    atomic_write_text(recent_js_path, content)
    print(f"✅ literature-recent.js ({len(recent)} 篇)，全库 {len(articles):,}")

    print(f"\n📊 共 {len(recent)} 篇（近 1 年），全库 {len(articles):,} 篇")
    print(
        "🏷️  信号标签：强 {strong} · 中 {medium} · 弱 {weak} · 未标注 {untagged}".format(
            strong=strengthCounts["强"],
            medium=strengthCounts["中"],
            weak=strengthCounts["弱"],
            untagged=len(recent) - sum(strengthCounts.values()),
        )
    )


if __name__ == "__main__":
    main()
