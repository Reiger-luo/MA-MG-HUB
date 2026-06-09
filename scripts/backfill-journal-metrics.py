#!/usr/bin/env python3
"""
backfill-journal-metrics.py — 期刊 IF/分区回填

用途：遍历 literature-full.json 中所有唯一的期刊名，
      从 local cache (journal_metrics.json) 匹配，
      未覆盖的 → 爬 Ablesci 补充（有限速）。

输出：
  1. assets/journal_metrics.json（cache 增量更新）
  2. 直接回填到 literature-full.json + literature-2026.json

运行方式：
  python3 backfill-journal-metrics.py          # 一次跑一批
  python3 backfill-journal-metrics.py --all    # 一次跑全部（会花很久）
"""

import json, os, sys, time, re, ssl
from urllib.request import urlopen, Request
from urllib.parse import quote
from pathlib import Path
from datetime import datetime

# macOS SSL
try:
    _create_unverified = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
ASSETS_DIR = PROJECT / "assets"
CACHE_PATH = ASSETS_DIR / "journal_metrics.json"

BATCH_SIZE = 30           # 每轮最多爬多少个新期刊
ABLESCI_DELAY = (3, 6)    # 每次爬之间的随机延迟（秒）


def load_cache():
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}

def save_cache(cache):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def load_data():
    """加载 literature-full.json，返回 articles + 所有唯一期刊"""
    full_path = DATA_DIR / "literature-full.json"
    if not full_path.exists():
        print("❌ literature-full.json not found. Run fetch-pubmed-full.py first.")
        sys.exit(1)
    with open(full_path) as f:
        articles = json.load(f)
    journals = sorted(set(
        a["journal"] for a in articles if a["journal"]
    ))
    return articles, journals


def scrape_ablesci(journal_name):
    """从 Ablesci 查期刊 IF 和分区。返回 (if_val, quartile) 或 (None, None)。"""
    url = f"https://www.ablesci.com/journal/index?keywords={quote(journal_name)}"
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    try:
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    ⚠ HTTP error: {e}")
        return None, None

    # 尝试从 HTML 中提取 IF 和分区
    # 常见格式: "2025年影响因子: 5.9" 或 "IF: 5.9"
    if_val = None
    quartile = None

    # 匹配 IF
    if_match = re.search(r'(?:影响因子|IF)[：:]\s*([\d.]+)', html)
    if if_match:
        if_val = float(if_match.group(1))

    # 匹配分区（大类）
    q_match = re.search(r'大类[：:]\s*(\d)区', html)
    if q_match:
        quartile = int(q_match.group(1))

    # 如果没有匹配，检查是否搜索到具体期刊页
    if not if_val:
        # 可能跳转到详情页了
        if_match2 = re.search(r'class=["\']journal-impact["\'][^>]*>([\d.]+)', html)
        if if_match2:
            if_val = float(if_match2.group(1))
    if not quartile:
        q_match2 = re.search(r'class=["\']journal-cas["\'][^>]*>(\d)区', html)
        if q_match2:
            quartile = int(q_match2.group(1))

    # 如果期刊名包含 "Zhonghua" 或 "Chinese"，可能是中文期刊，查不到是正常的
    if not if_val:
        return None, None

    return if_val, quartile


def backfill_articles(articles, cache, journal_map):
    """将 cache 里的 IF/分区回填到文章数据"""
    filled = 0
    for a in articles:
        j = a.get("journal", "")
        if not j:
            continue
        if j in cache:
            if a.get("journal_if") is None:
                a["journal_if"] = cache[j].get("IF")
                a["journal_quartile"] = cache[j].get("CAS")
                filled += 1
        elif j in journal_map:
            # journal_map 是已匹配但不在 cache 中的缩写→原名映射
            pass
    return filled


def main():
    articles, all_journals = load_data()
    cache = load_cache()
    print(f"📚 总期刊数: {len(all_journals)}")
    print(f"📦 已缓存: {len(cache)}")

    # --all 模式
    run_all = "--all" in sys.argv

    # 统计已覆盖和未覆盖
    covered = [j for j in all_journals if j in cache and cache[j].get("IF", 0) > 0]
    needs_fetch = [j for j in all_journals if j not in cache or cache[j].get("IF", 0) == 0]
    # 过滤掉明显是中文期刊的全名（Ablesci 可能查不到）
    needs_fetch = [
        j for j in needs_fetch
        if not any(kw in j.lower() for kw in ["zhonghua", "zhongguo", "beijing", "shanghai"])
    ]

    print(f"✅ 已覆盖: {len(covered)}")
    print(f"⏳ 待查询: {len(needs_fetch)}")
    print()

    if not needs_fetch:
        print("🎉 全部已覆盖，直接回填。")
    else:
        batch = needs_fetch[:BATCH_SIZE] if not run_all else needs_fetch
        print(f"🔍 本批查询: {len(batch)} 个期刊")
        for i, journal in enumerate(batch):
            print(f"  [{i+1}/{len(batch)}] {journal}")
            if_val, quartile = scrape_ablesci(journal)
            if if_val is not None:
                cache[journal] = {
                    "IF": if_val,
                    "CAS": str(quartile) + "区" if quartile else None,
                    "updated": datetime.now().strftime("%Y-%m-%d"),
                    "source": "ablesci",
                }
                print(f"    → IF={if_val}, 分区={quartile}")
            else:
                cache[journal] = {
                    "IF": 0.0,
                    "CAS": None,
                    "updated": datetime.now().strftime("%Y-%m-%d"),
                    "source": "ablesci",
                }
                print(f"    → 未查到（标记为 null）")
            # 限速
            if i < len(batch) - 1:
                delay = ABLESCI_DELAY[0] + (ABLESCI_DELAY[1] - ABLESCI_DELAY[0]) * 0.5
                print(f"    ⏳ 等待 {delay:.0f}s…")
                time.sleep(delay)

        save_cache(cache)
        print(f"\n💾 Cache 已保存 ({len(cache)} 条)")

    # 回填到文章
    journals_matched = {}
    filled = backfill_articles(articles, cache, journals_matched)

    # 写回 literature-full.json
    full_path = DATA_DIR / "literature-full.json"
    with open(full_path, "w") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"📝 已更新 {full_path.name}")

    # 也回填到 literature-2026.json
    yearly_path = DATA_DIR / "literature-2026.json"
    if yearly_path.exists():
        with open(yearly_path) as f:
            yearly = json.load(f)
        filled_yearly = backfill_articles(yearly, cache, journals_matched)
        with open(yearly_path, "w") as f:
            json.dump(yearly, f, ensure_ascii=False, indent=2)
        print(f"📝 已更新 {yearly_path.name} ({filled_yearly} 篇)")

    print(f"\n📊 本轮回填: {filled} 篇文章")
    remaining = [j for j in needs_fetch if j not in cache or cache[j].get("IF", 0) == 0]
    if remaining:
        print(f"⏳ 剩余未查询期刊: {len(remaining)}（运行 --all 或下次再跑）")


if __name__ == "__main__":
    main()
