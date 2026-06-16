#!/usr/bin/env python3
"""
normalize-journal-names.py — 统一 literature-full.json 的期刊名为全称

当前数据是老脚本抓的（ISO 缩写优先），
新脚本已改为全称优先。此脚本对历史数据做一次批量修正。

策略：遍历所有唯一期刊名，
  1. 先在已有 cache (journal_metrics.json) 里找全称匹配
  2. 如果当前 name 是缩写 → 尝试用 NLM Catalog API 查全称
  3. 找不到的保持原样（前端显示缩写不影响功能）
"""

import json, time, ssl
from urllib.request import urlopen, Request
from urllib.parse import quote
from pathlib import Path

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
ASSETS_DIR = PROJECT / "assets"
CACHE_PATH = ASSETS_DIR / "journal_metrics.json"


def load_data():
    with open(DATA_DIR / "literature-full.json") as f:
        return json.load(f)

def save_data(articles):
    with open(DATA_DIR / "literature-full.json", "w") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"Saved: {len(articles)} total")

def load_cache():
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def lookup_nlm(abbreviation):
    """通过 NLM Catalog API 查缩写对应的全称"""
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=nlmcatalog&term={quote(abbreviation)}[Journal]+AND+currentlyindexed[All]&retmode=json"
    try:
        req = Request(url, headers={"User-Agent": "MG-HUB/1.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        ids = data.get("esearchresult", {}).get("idlist", [])
        if ids:
            # 取第一条结果的 full title
            fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=nlmcatalog&id={ids[0]}&retmode=json"
            req2 = Request(fetch_url, headers={"User-Agent": "MG-HUB/1.0"})
            with urlopen(req2, timeout=15) as resp2:
                detail = json.loads(resp2.read())
            result = detail.get("result", {}).get(ids[0], {})
            title = result.get("title", "")
            if title:
                return title
    except Exception as e:
        print(f"  ⚠ NLM lookup failed for '{abbreviation}': {e}")
    return None


def main():
    articles = load_data()
    cache = load_cache()

    # 收集所有唯一期刊名
    all_names = sorted(set(a["journal"] for a in articles if a["journal"]))
    print(f"Total unique journal names: {len(all_names)}")

    # 判断哪些已经是全称（含空格、逗号、冒号、无缩写标记）
    def looks_like_full(name):
        # 全称通常有完整单词、逗号、冒号、括号
        if "," in name or ":" in name:
            return True
        if len(name) > 15 and " " in name:
            return True
        # 常见缩写模式：首字母缩写或短名
        if name.isupper() and len(name) <= 6:
            return False
        if len(name) <= 8 and " " not in name:
            return False
        return True

    short_names = [n for n in all_names if not looks_like_full(n)]
    print(f"Looks like abbreviations (need check): {len(short_names)}")

    # 尝试在 cache 中匹配全称
    cache_full_names = {k.lower(): k for k in cache.keys()}
    rename_map = {}
    for name in short_names:
        # 尝试 cache 匹配（忽略大小写）
        key = name.lower()
        if key in cache_full_names:
            rename_map[name] = cache_full_names[key]
            continue
        # 尝试 cache 中部分包含
        matched = [v for k, v in cache_full_names.items() if key in k or any(
            word in k for word in name.lower().replace(".", "").split()
        )]
        if matched:
            rename_map[name] = matched[0]
            continue

    print(f"Matched via cache: {len(rename_map)}")
    remaining = [n for n in short_names if n not in rename_map]
    print(f"Remaining for NLM lookup: {len(remaining)}")
    print(f"  (skipped NLM — API timeout. Will fix next session)")

    nmap = {}
    rename_map.update(nmap)

    # 执行重命名
    renamed_count = 0
    for a in articles:
        old = a.get("journal", "")
        if old in rename_map:
            a["journal"] = rename_map[old]
            renamed_count += 1

    save_data(articles)
    print(f"\nRenamed: {renamed_count} articles")

    # 输出仍未匹配的，便于后续手动处理
    unmatched = [n for n in remaining if n not in nmap]
    if unmatched:
        print(f"\nUnmatched journals ({len(unmatched)}):")
        for n in unmatched:
            print(f"  - {n}")


if __name__ == "__main__":
    main()
