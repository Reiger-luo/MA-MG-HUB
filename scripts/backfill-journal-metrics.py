#!/usr/bin/env python3
"""
backfill-journal-metrics.py — 期刊 IF/分区回填（EasyScholar API 版）

替代旧的 Ablesci curl+cookie+browser 级联方案。使用 EasyScholar 公开 API：
- JSON 响应，无需反爬处理
- 速率限制：1 req/s（由 easyscholar_api.py 自动控制）
- 支持简称和全称

输出：
  1. assets/journal_metrics.json（cache 增量更新）
  2. 直接回填到 literature-full.json

运行方式：
  python3 scripts/backfill-journal-metrics.py             # 仅近1年期刊
  python3 scripts/backfill-journal-metrics.py --all       # 全库期刊
  python3 scripts/backfill-journal-metrics.py --single "Neurology"  # 查单个期刊
"""

import json, os, sys, time
from pathlib import Path

# 添加 scripts/ 到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from easyscholar_api import EasyScholarAPI

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
ASSETS_DIR = PROJECT / "assets"
CACHE_PATH = ASSETS_DIR / "journal_metrics.json"


def load_cache():
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def load_articles():
    full_path = DATA_DIR / "literature-full.json"
    if not full_path.exists():
        print("❌ literature-full.json not found.")
        sys.exit(1)
    with open(full_path) as f:
        return json.load(f)


def get_journals(articles, mode="recent"):
    """获取需要查的期刊列表。只挑有证据等级的文章期刊。"""
    cache = load_cache()

    needs_fetch_journals = set()
    for a in articles:
        if a.get("evidence_level") and not a.get("journal_if") and a.get("journal"):
            needs_fetch_journals.add(a["journal"])

    all_journals = sorted(set(
        a["journal"] for a in articles if a["journal"]
    ))

    needs_fetch = [
        j for j in all_journals
        if j in needs_fetch_journals
        and (j not in cache or cache[j].get("IF", 0) == 0)
    ]

    if mode != "all":
        from datetime import datetime as dt, timedelta
        cutoff = dt.now() - timedelta(days=365)
        recent_journals = set()
        for a in articles:
            ed = a.get("entry_date", "")
            if ed:
                try:
                    parts = ed.split("/")
                    d = dt(int(parts[0]), int(parts[1]), int(parts[2].split()[0]))
                    if d >= cutoff and a["journal"]:
                        recent_journals.add(a["journal"])
                except:
                    pass
        needs_fetch = [j for j in needs_fetch if j in recent_journals]

    needs_fetch = [
        j for j in needs_fetch
        if not any(kw in j.lower() for kw in ["zhonghua", "zhongguo", "beijing", "shanghai"])
    ]
    covered = [j for j in all_journals if j in cache and cache[j].get("IF", 0) > 0]
    return all_journals, covered, needs_fetch


def backfill_articles(articles, cache):
    """从 cache 回填到文章数据。"""
    filled = 0
    for a in articles:
        j = a.get("journal", "")
        if not j:
            continue
        if j in cache and cache[j].get("IF", 0) > 0:
            if a.get("journal_if") is None:
                a["journal_if"] = cache[j]["IF"]
                a["journal_quartile"] = cache[j].get("CAS")
                filled += 1
    return filled


# ── Main ──

def main():
    mode = "recent"
    if "--all" in sys.argv:
        mode = "all"

    # 单期刊模式
    single_idx = None
    if "--single" in sys.argv:
        try:
            single_idx = sys.argv.index("--single") + 1
        except ValueError:
            pass

    if single_idx:
        journal = sys.argv[single_idx]
        api = EasyScholarAPI()
        res = api.query(journal)
        if res["found"]:
            print(f"✅ {journal}: IF={res['IF']}, 分区={res['sciBase']}")
            cache = load_cache()
            cache[journal] = {
                "IF": res["IF"],
                "CAS": res["sciBase"],
                "updated": time.strftime("%Y-%m-%d"),
                "source": "easyscholar",
            }
            save_cache(cache)
            print("💾 Cache updated.")
        else:
            print(f"⏭️  {journal}: 未查到")
        return

    print("[main] starting…", flush=True)

    articles = load_articles()
    print(f"[main] loaded {len(articles)} articles", flush=True)
    cache = load_cache()
    print(f"[main] cache {len(cache)} entries", flush=True)
    all_journals, covered, needs_fetch = get_journals(articles, mode)

    print(f"📚 全库期刊数: {len(all_journals)}", flush=True)
    print(f"📦 已缓存: {len(cache)}", flush=True)
    print(f"✅ 已覆盖: {len(covered)}", flush=True)
    print(f"⏳ 待查询: {len(needs_fetch)}", flush=True)
    print(flush=True)

    if not needs_fetch:
        print("🎉 全部已覆盖!")
    else:
        print(f"🔍 EasyScholar: 查询 {len(needs_fetch)} 个期刊…", flush=True)
        api = EasyScholarAPI()
        hit = 0

        for i, journal in enumerate(needs_fetch):
            print(f"  [{i+1}/{len(needs_fetch)}] {journal}…", end=" ", flush=True)
            res = api.query(journal)
            if res["found"]:
                cache[journal] = {
                    "IF": res["IF"],
                    "CAS": res["sciBase"],
                    "updated": time.strftime("%Y-%m-%d"),
                    "source": "easyscholar",
                }
                hit += 1
                print(f"IF={res['IF']}, {res['sciBase']}")
            else:
                # 查不到也写入 cache（IF=0），避免下次再查
                cache[journal] = {
                    "IF": 0,
                    "CAS": None,
                    "updated": time.strftime("%Y-%m-%d"),
                    "source": "easyscholar",
                }
                print("未查到")

        save_cache(cache)
        print(f"\n💾 完成: {hit}/{len(needs_fetch)} 命中", flush=True)

    # 回填到文章
    filled = backfill_articles(articles, cache)
    full_path = DATA_DIR / "literature-full.json"
    with open(full_path, "w") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"📝 已更新 {full_path.name} ({filled} 篇回填)", flush=True)

    remaining = [j for j in needs_fetch if j not in cache or cache[j].get("IF", 0) == 0]
    if remaining:
        print(f"⏳ 仍缺 IF: {len(remaining)} 个期刊（下次重试自动跳过）", flush=True)


if __name__ == "__main__":
    main()
