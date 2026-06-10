#!/usr/bin/env python3
"""
MG-HUB Ablesci Browser Enricher

从 /tmp/mg_hub_browser_remaining.txt 读取需查询的期刊列表，
逐个用 browser_navigate 查 Ablesci，更新 assets/journal_metrics.json。

运行方式：
  python3 scripts/browser-enrich.py        # 交互式，查一个等确认
  python3 scripts/browser-enrich.py --auto  # 自动模式（内部循环）
"""

import json, os, sys, time, re, subprocess, tempfile, random
from pathlib import Path
from datetime import datetime

PROJECT = Path(__file__).resolve().parent.parent
CACHE_PATH = PROJECT / "assets" / "journal_metrics.json"

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
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def parse_ablesci_html(html):
    """从 Ablesci HTML 解析 IF 和分区。"""
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

        if if_raw.startswith("暂无"):
            if_val = 0.0
        else:
            if_m = re.match(r'([\d.]+)', if_raw)
            if_val = float(if_m.group(1)) if if_m else 0.0

        cas_m = re.search(r'([1-4]区)', cas_raw)
        cas_val = cas_m.group(1) if cas_m else None

        if if_val is not None or cas_val is not None:
            return if_val, cas_val

    return None, None


def scrape_curl(journal_name):
    """先用 curl 试一下（部分期刊 curl 能查到）。"""
    cookie_path = tempfile.NamedTemporaryFile(delete=False, suffix="_ablesci.txt").name
    try:
        subprocess.run(
            ["curl", "-c", cookie_path, "-b", cookie_path] + CURL_HEADERS
            + ["https://www.ablesci.com/"],
            capture_output=True, timeout=15
        )
        url = f"https://www.ablesci.com/journal/index?keywords={journal_name.replace(' ', '+')}"
        resp = subprocess.run(
            ["curl", "-c", cookie_path, "-b", cookie_path] + CURL_HEADERS + [url],
            capture_output=True, text=True, timeout=20
        )
        return parse_ablesci_html(resp.stdout)
    except:
        return None, None
    finally:
        os.unlink(cookie_path)


# 以下是供 Hermes execute_code 调用的接口
# 外部通过 browser_navigate 获取页面 HTML 后，调用 process_browser_result()
# 来提取并保存结果


def process_browser_result(journal_name, html):
    """处理 browser_navigate 返回的 HTML，更新 cache。返回 (if_val, quartile, cached)。"""
    if_val, quartile = parse_ablesci_html(html)

    cache = load_cache()
    if if_val is not None:
        cache[journal_name] = {
            "IF": if_val,
            "CAS": quartile,
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "source": "ablesci",
        }
        save_cache(cache)
        return if_val, quartile, True
    return if_val, quartile, False


def get_browser_page_source():
    """从 Hermes browser_console 获取当前页面的 HTML。"""
    # 由调用者通过 browser_console 获取 document.documentElement.outerHTML
    pass


def save_browser_batch(journals):
    """保存需要 browser 查询的期刊列表到文件。"""
    path = Path("/tmp/mg_hub_browser_remaining.txt")
    with open(path, "w") as f:
        json.dump(journals, f)
    return path


if __name__ == "__main__":
    import json as _json
    remaining_path = Path("/tmp/mg_hub_browser_remaining.txt")
    if not remaining_path.exists():
        print("❌ /tmp/mg_hub_browser_remaining.txt not found")
        sys.exit(1)

    with open(remaining_path) as f:
        remaining = _json.load(f)

    if not remaining:
        print("🎉 全部完成！")
        sys.exit(0)

    print(f"📋 剩余 {len(remaining)} 个期刊")
    print(f"下一个: {remaining[0]}")
    print(f"请打开: https://www.ablesci.com/journal/index?keywords={remaining[0].replace(' ', '+')}")
