#!/usr/bin/env python3
"""
backfill-journal-metrics.py — 期刊 IF/分区回填（Tier 2 curl → Tier 3 browser）

两层级联：
  Tier 2: curl + cookie 爬 Ablesci（3-6s 随机延迟）
  Tier 3: Hermes browser_navigate（curl 查不到的降级）

输出：
  1. assets/journal_metrics.json（cache 增量更新）
  2. 直接回填到 literature-full.json

运行方式：
  python3 scripts/backfill-journal-metrics.py              # 仅 curl（默认）
  python3 scripts/backfill-journal-metrics.py --browser    # curl + browser 兜底
  python3 scripts/backfill-journal-metrics.py --all        # 全库期刊（默认仅近1年）
"""

import json, os, sys, time, re, subprocess, tempfile, random
from pathlib import Path
from datetime import datetime

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
ASSETS_DIR = PROJECT / "assets"
CACHE_PATH = ASSETS_DIR / "journal_metrics.json"

RATE_RANGE = (3, 6)

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


def get_journals(articles, mode="recent"):
    """获取需要查的期刊列表。只挑有证据等级的文章期刊。"""
    all_journals = sorted(set(
        a["journal"] for a in articles if a["journal"]
    ))
    cache = load_cache()
    # 只找有证据等级且缺IF的期刊
    needs_fetch_journals = set()
    for a in articles:
        if a.get("evidence_level") and not a.get("journal_if") and a.get("journal"):
            needs_fetch_journals.add(a["journal"])
    
    needs_fetch = [j for j in all_journals if j in needs_fetch_journals and (j not in cache or cache[j].get("IF", 0) == 0)]

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


# ── Tier 2: curl + cookie ─────────────────────────────────────────────

def init_cookie():
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


def parse_ablesci_html(html):
    """从 Ablesci HTML 解析第一条结果中的 IF 和分区。

    td[2] 格式示例：
      '45.5↓ 1'       → IF=45.5
      '0.3↓ 0'        → IF=0.3
      '暂无↓ 0.5'      → IF=None（暂无表示无 IF）
      '暂无↓ 0'        → IF=None

    td[3] 格式示例：
      '1区 医学'       → '1区'
      '暂无'           → None
    """
    count_m = re.search(r'总计查询到\s*<span[^>]*>\s*(\d+)\s*</span>', html)
    if not count_m or int(count_m.group(1)) == 0:
        return None, None

    trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for tr in trs:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
        if len(tds) < 6:
            continue

        def _clean(t):
            return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip()

        if_raw = _clean(tds[2])
        cas_raw = _clean(tds[3])

        # IF: 提取第一个数字，但排除"暂无"开头
        if if_raw.startswith("暂无"):
            if_val = 0.0
        else:
            if_m = re.match(r'([\d.]+)', if_raw)
            if_val = float(if_m.group(1)) if if_m else 0.0

        # 分区
        cas_m = re.search(r'([1-4]区)', cas_raw)
        cas_val = cas_m.group(1) if cas_m else None

        # 只返回第一行有效数据（最匹配的结果）
        if if_val is not None or cas_val is not None:
            return if_val, cas_val

    return None, None


def scrape_curl(journal_name, cookie_path):
    """Tier 2: curl + cookie 查 Ablesci。返回 (if_val, quartile) 或 (None, None)。"""
    url = f"https://www.ablesci.com/journal/index?keywords={journal_name.replace(' ', '+')}"
    try:
        resp = subprocess.run(
            ["curl", "-c", cookie_path, "-b", cookie_path] + CURL_HEADERS + [url],
            capture_output=True, text=True, timeout=20
        )
        return parse_ablesci_html(resp.stdout)
    except Exception as e:
        print(f"    ⚠️ curl error: {e}")
        return None, None


def cache_journal(cache, journal, if_val, quartile):
    """写入一条到 cache。"""
    cache[journal] = {
        "IF": if_val,
        "CAS": quartile,
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "source": "ablesci",
    }


# ── Tier 3: browser（Hermes 外部调用） ─────────────────────────────────

# browser_navigate 在 Hermes 工具中调用，此函数输出指令供 Machine 执行
BROWSER_BATCH_FILE = "/tmp/mg_hub_browser_batch.json"


def save_browser_batch(journals):
    """保存需要 browser 查询的期刊列表到文件。"""
    with open(BROWSER_BATCH_FILE, "w") as f:
        json.dump(journals, f)
    print(f"\n📋 已保存 {len(journals)} 个需 browser 查询的期刊到 {BROWSER_BATCH_FILE}")
    print("   执行: 用 browser_navigate 逐个访问 Ablesci，调用 parse_browser_result() 提取")


def parse_browser_result(html_source):
    """从 browser 的 page source 中提取 IF/分区（和 parse_ablesci_html 相同逻辑）。"""
    return parse_ablesci_html(html_source)


# ── 回填 ──────────────────────────────────────────────────────────────

def backfill_articles(articles, cache):
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


# ── Main ──────────────────────────────────────────────────────────────

def main():
    print("[main] starting…", flush=True)
    mode = "recent"
    if "--all" in sys.argv:
        mode = "all"
    use_browser = "--browser" in sys.argv

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
        print("🎉 全部已覆盖，直接回填。")
    else:
        # ── Tier 2: curl ──
        print(f"🔍 Tier 2 — curl: 查询 {len(needs_fetch)} 个期刊…")
        cookie_path = init_cookie()
        if not cookie_path:
            print("❌ 无法初始化 cookie。")
            sys.exit(1)

        curl_hit = 0
        need_browser = []

        try:
            for i, journal in enumerate(needs_fetch):
                print(f"  [{i+1}/{len(needs_fetch)}] {journal}")
                if_val, quartile = scrape_curl(journal, cookie_path)
                if if_val is not None:
                    cache_journal(cache, journal, if_val, quartile)
                    curl_hit += 1
                    print(f"    → IF={if_val}, 分区={quartile}")
                else:
                    need_browser.append(journal)
                    print(f"    → curl 未查到")

                if i < len(needs_fetch) - 1:
                    delay = random.uniform(*RATE_RANGE)
                    print(f"    ⏳ 等待 {delay:.0f}s…")
                    time.sleep(delay)
        finally:
            os.unlink(cookie_path)

        save_cache(cache)
        print(f"\n💾 Tier 2 完成: {curl_hit} 命中, {len(need_browser)} 待 browser")

        # ── Tier 3: browser ──
        if need_browser and use_browser:
            print(f"\n🔍 Tier 3 — browser: {len(need_browser)} 个期刊待查")
            save_browser_batch(need_browser)
            print("请用 Hermes browser_navigate 工具逐个查询，结果通过 add_to_cache.py 写入。")
        elif need_browser and not use_browser:
            print(f"\n⏳ {len(need_browser)} 个期刊 curl 未查到。加 --browser 启用 browser 兜底。")
            save_browser_batch(need_browser)

    # 回填
    filled = backfill_articles(articles, cache)
    full_path = DATA_DIR / "literature-full.json"
    with open(full_path, "w") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"📝 已更新 {full_path.name} ({filled} 篇回填)")

    remaining = [j for j in needs_fetch if j not in cache or cache[j].get("IF", 0) == 0]
    if remaining:
        print(f"⏳ 仍缺 IF: {len(remaining)} 个期刊（需 browser 或下次重试）")


if __name__ == "__main__":
    main()
