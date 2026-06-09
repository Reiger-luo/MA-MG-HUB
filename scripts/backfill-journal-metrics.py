#!/usr/bin/env python3
"""
backfill-journal-metrics.py — 期刊 IF/分区回填

用途：遍历 literature-full.json 中所有唯一期刊名，
      从 local cache (journal_metrics.json) 匹配，
      未覆盖的 → curl + cookie 爬 Ablesci（利用 pubmed-search skill 验证过的模式）。

输出：
  1. assets/journal_metrics.json（cache 增量更新）
  2. 直接回填到 literature-full.json

运行方式：
  python3 scripts/backfill-journal-metrics.py          # 一次跑一批(30)
  python3 scripts/backfill-journal-metrics.py --all    # 全部
  python3 scripts/backfill-journal-metrics.py --recent # 仅近1年缺IF的期刊
"""

import json, os, sys, time, re, subprocess, tempfile, random
from pathlib import Path
from datetime import datetime

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
ASSETS_DIR = PROJECT / "assets"
CACHE_PATH = ASSETS_DIR / "journal_metrics.json"

BATCH_SIZE = 30
RATE_RANGE = (3, 6)  # 随机延迟秒数

# Ablesci curl headers（与 pubmed-search skill 一致）
CURL_HEADERS = [
    "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "-H", "Accept: text/html,application/xhtml+xml,application/xml;"
          "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "-H", "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8",
    "-H", "Referer: https://www.ablesci.com/journal/index",
    "--compressed", "-s",
]


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


def get_journals(articles, mode="all"):
    """获取需要查的期刊列表。mode='recent' 仅近1年缺IF的。"""
    all_journals = sorted(set(
        a["journal"] for a in articles if a["journal"]
    ))
    cache = load_cache()
    needs_fetch = [j for j in all_journals if j not in cache or cache[j].get("IF", 0) == 0]

    if mode == "recent":
        # 仅近1年缺IF的
        from datetime import datetime as dt, timedelta
        cutoff = dt.now() - timedelta(days=365)
        recent_journals = set()
        for a in articles:
            ed = a.get("entry_date", "")
            if ed:
                try:
                    parts = ed.split("/")
                    d = dt(int(parts[0]), int(parts[1]), int(parts[2].split()[0]))
                    if d >= cutoff:
                        if a["journal"]:
                            recent_journals.add(a["journal"])
                except:
                    pass
        needs_fetch = [j for j in needs_fetch if j in recent_journals]

    # 过滤中文期刊
    needs_fetch = [
        j for j in needs_fetch
        if not any(kw in j.lower() for kw in ["zhonghua", "zhongguo", "beijing", "shanghai"])
    ]

    covered = [j for j in all_journals if j in cache and cache[j].get("IF", 0) > 0]
    return all_journals, covered, needs_fetch


def init_cookie():
    """访问 Ablesci 首页获取 security_session_verify cookie。"""
    cookie_path = tempfile.NamedTemporaryFile(delete=False, suffix="_ablesci.txt").name
    try:
        subprocess.run(
            ["curl", "-c", cookie_path, "-b", cookie_path] + CURL_HEADERS
            + ["https://www.ablesci.com/"],
            capture_output=True, timeout=15
        )
        return cookie_path
    except Exception as e:
        print(f"  ⚠️ Cookie init failed: {e}")
        return None


def scrape_ablesci(journal_name, cookie_path):
    """从 Ablesci 查期刊 IF/分区。返回 (if_val, quartile_str) 或 (None, None)。"""
    url = f"https://www.ablesci.com/journal/index?keywords={journal_name.replace(' ', '+')}"
    try:
        resp = subprocess.run(
            ["curl", "-c", cookie_path, "-b", cookie_path] + CURL_HEADERS + [url],
            capture_output=True, text=True, timeout=20
        )
        html = resp.stdout
    except Exception as e:
        print(f"    ⚠️ curl error: {e}")
        return None, None

    # 检查是否有搜索结果
    count_m = re.search(r'总计查询到\s*<span[^>]*>\s*(\d+)\s*</span>', html)
    if not count_m or int(count_m.group(1)) == 0:
        return None, None

    # 解析表格
    trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for tr in trs:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
        if len(tds) < 6:
            continue

        def _clean(t):
            return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip()

        if_raw = _clean(tds[2])
        if_m = re.search(r'([\d.]+)', if_raw)
        cas_raw = _clean(tds[3])
        cas_m = re.search(r'([1-4]区)', cas_raw)

        if if_m:
            return float(if_m.group(1)), cas_m.group(1) if cas_m else None

    return None, None


def backfill_articles(articles, cache):
    """将 cache 里的 IF/分区回填到文章数据"""
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


def main():
    mode = "all"
    if "--all" in sys.argv:
        mode = "all"
    elif "--recent" in sys.argv:
        mode = "recent"

    articles = load_articles()
    cache = load_cache()
    all_journals, covered, needs_fetch = get_journals(articles, mode)

    print(f"📚 全库期刊数: {len(all_journals)}")
    print(f"📦 已缓存: {len(cache)}")
    print(f"✅ 已覆盖: {len(covered)}")
    print(f"⏳ 待查询: {len(needs_fetch)}")
    print()

    if not needs_fetch:
        print("🎉 全部已覆盖，直接回填。")
    else:
        batch = needs_fetch[:BATCH_SIZE] if mode != "all" else needs_fetch
        print(f"🔍 本批查询: {len(batch)} 个期刊")

        cookie_path = init_cookie()
        if not cookie_path:
            print("❌ 无法初始化 cookie，退出。")
            sys.exit(1)

        try:
            for i, journal in enumerate(batch):
                print(f"  [{i+1}/{len(batch)}] {journal}")
                if_val, quartile = scrape_ablesci(journal, cookie_path)
                if if_val is not None:
                    cache[journal] = {
                        "IF": if_val,
                        "CAS": quartile,
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

                if i < len(batch) - 1:
                    delay = random.uniform(*RATE_RANGE)
                    print(f"    ⏳ 等待 {delay:.0f}s…")
                    time.sleep(delay)
        finally:
            os.unlink(cookie_path)

        save_cache(cache)
        print(f"\n💾 Cache 已保存 ({len(cache)} 条)")

    # 回填到文章
    filled = backfill_articles(articles, cache)

    full_path = DATA_DIR / "literature-full.json"
    with open(full_path, "w") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"📝 已更新 {full_path.name}")

    print(f"\n📊 本轮回填: {filled} 篇文章")
    remaining = [j for j in needs_fetch if j not in cache or cache[j].get("IF", 0) == 0]
    if remaining:
        print(f"⏳ 剩余未查询期刊: {len(remaining)}")


if __name__ == "__main__":
    main()
