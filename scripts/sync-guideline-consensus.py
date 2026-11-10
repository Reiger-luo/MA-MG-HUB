#!/usr/bin/env python3
"""周更 link 步骤：把公开文献流里的指南/共识同步到权威缓存。

网站涉及指南共识的三处（中外指南共识差异、诊疗现状、领域重大事件）都从
``data/guideline-consensus-cache.json`` 派生，因此本步骤是缓存的唯一写入点：
每轮周更对公开文献层做一次全量重扫并幂等合并，不依赖当周抓取窗口。

识别到新指南后由后续的 ``refresh-guideline-views.py`` 联动刷新三个板块；
结论改动必须有全文与逐字回验引文，本步骤只写摘要级缓存，不臆造诊疗结论。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from common.guideline_consensus import syncGuidelineCacheFromLiterature
from common.io import load_js_global

PROJECT = Path(__file__).resolve().parent.parent
# MG_DATA_DIR 供测试把数据根指向临时目录，避免写已发布产物。
DATA = Path(os.environ.get("MG_DATA_DIR") or PROJECT / "data")
RECENT_PATH = DATA / "literature-recent.js"
WEEKLY_PATH = DATA / "literature-weekly.json"
CACHE_PATH = DATA / "guideline-consensus-cache.json"


def loadRecentArticles() -> list[dict[str, Any]]:
    """读取已发布的公开文献层；解析失败返回空列表，由调用方保留 last-good。"""
    if not RECENT_PATH.is_file():
        return []
    try:
        value = load_js_global(RECENT_PATH, "MG_LITERATURE_DATA")
    except (OSError, ValueError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def loadWeeklyArticles() -> list[dict[str, Any]]:
    """合并当周抓取层，兼容 list 与 {articles:[]} 两种结构。"""
    if not WEEKLY_PATH.is_file():
        return []
    try:
        value = json.loads(WEEKLY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = value if isinstance(value, list) else (value.get("articles") or [])
    return [item for item in items if isinstance(item, dict)]


def main() -> int:
    recent = loadRecentArticles()
    if not recent:
        # 公开文献层不可用时不得清空或重写缓存：直接保留上一版 last-good。
        print("⚠️ 公开文献层不可用，保留上一版指南/共识缓存（last-good），本次不写入。")
        return 0

    merged: dict[str, dict[str, Any]] = {}
    for article in [*recent, *loadWeeklyArticles()]:
        pmid = str(article.get("pmid") or "").strip()
        if pmid and pmid not in merged:
            merged[pmid] = article

    _, counters = syncGuidelineCacheFromLiterature(CACHE_PATH, list(merged.values()))
    print(
        "✅ 指南/共识同步："
        f"扫描 {counters['scanned']} 篇 · 命中 {counters['matched']} 篇 · "
        f"缓存共 {counters['cache_total']} 条"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
