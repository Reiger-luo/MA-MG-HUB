#!/usr/bin/env python3
"""上线后核对：把 release-manifest.js 的 sha256 与线上同名产物逐一比对。

GitHub Pages 部署可能瞬时失败或 CDN 延迟，单看 push 成功不能证明站点已切换。
本脚本把人工核对固化为可复用的发布校验：任一产物哈希不符或读取失败即返回非零。

用法：
  python3 scripts/verifyOnlineRelease.py
  python3 scripts/verifyOnlineRelease.py --only data/landscape-data.js,data/treatmentChapters.js
  python3 scripts/verifyOnlineRelease.py --base-url https://reiger-luo.github.io/MA-MG-HUB/
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from common.io import load_js_global  # noqa: E402

DEFAULT_BASE_URL = "https://reiger-luo.github.io/MA-MG-HUB/"
# data/*.js 用清单哈希核对；assets/*.js 不在清单内，改由活动页面的 ?v= 缓存版本核对。
ACTIVE_PAGES = (
    "index.html",
    "pages/literature.html",
    "pages/landscape.html",
    "pages/knowledge.html",
    "pages/msl.html",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="线上站点根地址")
    parser.add_argument("--only", default="", help="逗号分隔的产物路径，仅核对指定项")
    parser.add_argument("--timeout", type=float, default=25.0, help="单个请求超时秒数")
    parser.add_argument("--skip-pages", action="store_true", help="跳过活动页面资源版本号核对")
    args = parser.parse_args()

    manifest = load_js_global(PROJECT / "data" / "release-manifest.js", "MG_RELEASE_MANIFEST")
    artifacts = [item for item in manifest.get("artifacts") or [] if item.get("sha256")]
    if args.only.strip():
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        artifacts = [item for item in artifacts if item.get("path") in wanted]
        missing = wanted - {item.get("path") for item in artifacts}
        if missing:
            print(f"❌ 发布清单中没有这些产物：{', '.join(sorted(missing))}")
            print("   说明：清单只记录公开数据产物（不含 release-manifest.js 自身与 assets/*.js）；后者由活动页面 ?v= 版本号核对。")
            return 2
    if not artifacts:
        print("❌ 发布清单无可用产物")
        return 2

    base = args.base_url.rstrip("/")
    failures = 0
    for item in artifacts:
        rel = item["path"]
        url = f"{base}/{rel}"
        try:
            with urllib.request.urlopen(url, timeout=args.timeout) as response:
                body = response.read()
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            print(f"❌ {rel}: 读取失败 {exc}")
            failures += 1
            continue
        digest = hashlib.sha256(body).hexdigest()
        same = digest == item["sha256"]
        if not same:
            failures += 1
        print(f"{'✅' if same else '❌'} {rel}: {'一致' if same else '哈希漂移'} ({len(body)} bytes)")

    page_checks = 0
    if not args.skip_pages:
        run_id = str(manifest.get("run_id") or "")
        for page in ACTIVE_PAGES:
            url = f"{base}/{page}"
            try:
                with urllib.request.urlopen(url, timeout=args.timeout) as response:
                    html = response.read().decode("utf-8", "ignore")
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                print(f"❌ {page}: 读取失败 {exc}")
                failures += 1
                continue
            tokens = set(re.findall(r"\?v=([A-Za-z0-9._-]+)", html))
            same = bool(tokens) and tokens == {run_id} and bool(run_id)
            if not same:
                failures += 1
            page_checks += 1
            print(f"{'✅' if same else '❌'} {page}: 资源版本 "
                  f"{'与 run_id 一致' if same else '漂移 ' + ','.join(sorted(tokens))} ({run_id})")

    total = len(artifacts) + page_checks
    print(
        f"\n{'✅ 线上产物与发布清单完全一致' if failures == 0 else '❌ 存在漂移或读取失败'}："
        f"{total - failures}/{total} 项通过 · run_id={manifest.get('run_id', '')}"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
