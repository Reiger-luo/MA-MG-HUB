#!/usr/bin/env python3
"""split-recent-data.py — 从 literature-full.json 截取近1年数据

输出：
  - data/literature-recent.json（近1年全量，前端一次加载）

每周增量后执行一次即可。同时自动更新 literature.js 中的文献总量数字。
"""

import json, re
from datetime import datetime, timedelta
from pathlib import Path

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

    recent = []
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

    recent_path = DATA_DIR / "literature-recent.json"
    with open(recent_path, "w") as f:
        json.dump(recent, f, ensure_ascii=False, indent=2)
    print(f"✅ literature-recent.json ({len(recent)} 篇)")

    # 更新文献总量硬编码到 literature.js
    js_path = PROJECT / "assets" / "literature.js"
    if js_path.exists():
        js = js_path.read_text("utf-8")
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

    print(f"\n📊 共 {len(recent)} 篇（近 1 年），全库 {len(articles):,} 篇")


if __name__ == "__main__":
    main()
