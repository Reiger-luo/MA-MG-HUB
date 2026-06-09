#!/usr/bin/env python3
"""
split-recent-data.py — 从 literature-full.json 截取近1年数据并按月拆分

输出：
  - data/literature-recent.json（近1年全量，供 backfill 回填）
  - data/literature-YYYY-MM.json（按月拆分，供前端按需加载）

每周增量后执行一次即可。
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"

DAYS_RECENT = 365


def main():
    full_path = DATA_DIR / "literature-full.json"
    if not full_path.exists():
        print(f"❌ {full_path} not found")
        return

    with open(full_path) as f:
        articles = json.load(f)

    cutoff = datetime.now() - timedelta(days=DAYS_RECENT)

    # 筛选近1年
    recent = []
    by_month = defaultdict(list)

    for a in articles:
        ed = a.get("entry_date", "")
        if not ed:
            continue
        try:
            parts = ed.split("/")
            dt = datetime(int(parts[0]), int(parts[1]), int(parts[2].split()[0]))
        except (ValueError, IndexError):
            continue
        if dt < cutoff:
            continue
        recent.append(a)
        ym = f"{parts[0]}-{parts[1]}"
        by_month[ym].append(a)

    # 写 recent.json（回填用）
    recent_path = DATA_DIR / "literature-recent.json"
    with open(recent_path, "w") as f:
        json.dump(recent, f, ensure_ascii=False, indent=2)
    print(f"✅ literature-recent.json ({len(recent)} 篇)")

    # 写按月文件（前端用）
    for ym in sorted(by_month.keys(), reverse=True):
        fp = DATA_DIR / f"literature-{ym}.json"
        with open(fp, "w") as f:
            json.dump(by_month[ym], f, ensure_ascii=False, indent=2)
        print(f"   literature-{ym}.json ({len(by_month[ym])} 篇)")

    print(f"\n📊 共 {len(recent)} 篇，{len(by_month)} 个月")

    # 更新文献总量硬编码到 literature.js
    js_path = PROJECT / "assets" / "literature.js"
    if js_path.exists():
        js = js_path.read_text("utf-8")
        import re
        new_js = re.sub(
            r"document\.getElementById\('statTotal'\)\.textContent = '[0-9,]+'",
            f"document.getElementById('statTotal').textContent = '{len(articles):,}'",
            js
        )
        if new_js != js:
            js_path.write_text(new_js, "utf-8")
            print(f"✅ 已更新 literature.js 总量为 {len(articles):,}")
        else:
            print(f"ℹ️  literature.js 总量未变（{len(articles):,}）")


if __name__ == "__main__":
    main()
