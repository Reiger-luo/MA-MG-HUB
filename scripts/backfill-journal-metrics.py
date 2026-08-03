#!/usr/bin/env python3
"""
backfill-journal-metrics.py — 期刊 IF/分区更新（EasyScholar API 版）

只更新 assets/journal_metrics.json（期刊 cache），不碰文献数据。
跑完这个后，运行 backfill-from-cache.py 将 cache 映射到文献。

运行方式：
  python3 scripts/backfill-journal-metrics.py             # 近1年期刊（默认）
  python3 scripts/backfill-journal-metrics.py --all       # 全库期刊
  python3 scripts/backfill-journal-metrics.py --single "Neurology"  # 查单个期刊

数据流：
  EasyScholar API → assets/journal_metrics.json（独立期刊字典）
                         ↓
                 backfill-from-cache.py（映射到文献）
                         ↓
                 data/literature-full.json → split-recent-data.py → 前端
"""

import json, os, sys, time
from pathlib import Path

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
    """
    收集文献中出现的所有期刊，对比 cache 找出需要查询的。

    EasyScholar 提供统一的 JSON 响应，对所有期刊一视同仁。
    不再区分 evidence_level——每个期刊名都值得录入 cache。
    """
    cache = load_cache()

    # 所有期刊（去重排序）
    all_journals = sorted(set(
        a["journal"] for a in articles if a["journal"]
    ))

    # 按期刊名查全库：cache 中没有的 + cache 中 IF=0 的
    needs_fetch = [
        j for j in all_journals
        if j not in cache or cache[j].get("IF") is None or cache[j].get("IF", 0) == 0
    ]

    # 近 1 年过滤
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

    # 过滤中文期刊名（EasyScholar 查不了）
    needs_fetch = [
        j for j in needs_fetch
        if not any(kw in j.lower() for kw in ["zhonghua", "zhongguo", "beijing", "shanghai"])
    ]

    covered = [j for j in all_journals if j in cache and cache[j].get("IF") is not None and cache[j].get("IF", 0) > 0]
    return all_journals, covered, needs_fetch


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
            print(f"✅ {journal}: IF={res['IF']}, 新锐分区={res['quartile']}")
            cache = load_cache()
            cache[journal] = {
                "IF": res["IF"],
                "quartile": res["quartile"],
                "updated": time.strftime("%Y-%m-%d"),
                "source": "easyscholar",
            }
            save_cache(cache)
            print("💾 Cache updated.")
        else:
            print(f"⏭️  {journal}: 未查到")
        return

    print("[main] 开始…", flush=True)

    articles = load_articles()
    print(f"[main] 已加载 {len(articles)} 篇文章", flush=True)
    cache = load_cache()
    print(f"[main] 期刊 cache {len(cache)} 条", flush=True)

    all_journals, covered, needs_fetch = get_journals(articles, mode)

    print(f"📚 文献中出现的期刊数: {len(all_journals)}", flush=True)
    print(f"📦 已有 cache: {len(cache)}", flush=True)
    print(f"✅ 已覆盖 (IF>0): {len(covered)}", flush=True)
    print(f"⏳ 待查询: {len(needs_fetch)}", flush=True)
    print(flush=True)

    if not needs_fetch:
        print("🎉 全部已覆盖！")
        save_cache(cache)
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
                    "quartile": res["quartile"],
                    "updated": time.strftime("%Y-%m-%d"),
                    "source": "easyscholar",
                }
                hit += 1
                print(f"IF={res['IF']}, 新锐分区={res['quartile']}")
            else:
                # 未查到也写入 cache（IF=0），避免下次再查
                cache[journal] = {
                    "IF": 0,
                    "quartile": None,
                    "updated": time.strftime("%Y-%m-%d"),
                    "source": "easyscholar",
                }
                print("未查到")

        save_cache(cache)
        print(f"\n💾 Cache 更新完成: {hit}/{len(needs_fetch)} 命中，总 {len(cache)} 条", flush=True)

    remaining = [j for j in needs_fetch if j not in cache or cache[j].get("IF", 0) == 0]
    if remaining:
        print(f"⏳ 仍缺 IF: {len(remaining)} 个期刊", flush=True)

    print(f"\n📝 期刊 cache 已更新。")
    print(f"   运行 scripts/backfill-from-cache.py 将 cache 映射到文献数据。", flush=True)


if __name__ == "__main__":
    main()
