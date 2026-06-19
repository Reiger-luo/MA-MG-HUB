#!/usr/bin/env python3
"""split-recent-data.py — 从 literature-full.json 截取近1年数据

输出：
  - data/literature-recent.js（近1年公开滚动数据源，前端一次加载）
  - data/literature-recent.json（可选本地调试缓存）

仅在需要从本地 full 快照重建近一年公开库时手动执行。
日常周更使用 merge-weekly-literature.py，不再依赖 full 快照。
"""

import argparse
import json, re
from datetime import datetime, timedelta
from pathlib import Path

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
    if args.write_json_cache:
        recent_path = DATA_DIR / "literature-recent.json"
        with open(recent_path, "w") as f:
            json.dump(recent, f, ensure_ascii=False, indent=2)
        print(f"✅ literature-recent.json cache ({len(recent)} 篇)")
    else:
        recent_path = DATA_DIR / "literature-recent.json"
        if recent_path.exists():
            recent_path.unlink()
            print("🧹 已清理 literature-recent.json cache")

    recent_js_path = DATA_DIR / "literature-recent.js"
    with open(recent_js_path, "w") as f:
        f.write("window.MG_LITERATURE_DATA = ")
        json.dump(recent, f, ensure_ascii=False)
        f.write(";\n")
    print(f"✅ literature-recent.js ({len(recent)} 篇)")

    # 更新文献总量硬编码到 literature.js
    js_path = PROJECT / "assets" / "literature.js"
    if js_path.exists():
        js = js_path.read_text("utf-8")
        new_js = re.sub(
            r"document\.getElementById\('statTotal'\)\.textContent = '[0-9,]+'.*",
            f"document.getElementById('statTotal').textContent = '{len(articles):,}';  // 全库文献总量（由 split-recent-data.py 更新）",
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
