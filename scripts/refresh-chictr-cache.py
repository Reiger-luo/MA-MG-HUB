#!/usr/bin/env python3
"""按月抓取 ChiCTR 官方 XML，或从运营人员提供的官方导出刷新缓存。"""

from __future__ import annotations

import argparse
from pathlib import Path

from common.chictr_live import refresh_chictr_live
from common.clinical_registry import refresh_chictr_cache


PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = PROJECT / "data" / "chictr-trials-cache.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh ChiCTR cache from official XML or JSON/CSV export")
    parser.add_argument("--input", type=Path, help="运营人员提供的 ChiCTR 官方 JSON/CSV 导出")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--interval-days",
        type=int,
        default=28,
        help="无 --input 时，距离上次成功刷新达到该天数才运行官方抓取（默认 28）",
    )
    parser.add_argument("--force-live", action="store_true", help="忽略间隔并立即运行官方抓取")
    args = parser.parse_args()

    if args.interval_days < 0:
        parser.error("--interval-days 不能小于 0")

    if args.input:
        payload = refresh_chictr_cache(args.cache, input_path=args.input)
        refresh_status = "updated" if not payload.get("warning") else "failed"
    else:
        payload = refresh_chictr_live(
            args.cache,
            interval_days=args.interval_days,
            force=args.force_live,
        )
        refresh_status = payload.get("refresh_status")

    count = len(payload.get("records") or [])
    if payload.get("warning"):
        print(f"⚠️ ChiCTR 刷新不可用，保留最后良好缓存（{count} 条）: {payload['warning']}")
        return 1
    if refresh_status == "not_due":
        print(
            f"ℹ️ ChiCTR 月更未到期，继续使用 {count} 条缓存；"
            f"上次核对 {payload.get('last_verified') or payload.get('scraped_at') or '未知'}"
        )
    else:
        print(f"✅ ChiCTR mode={payload.get('mode')}，刷新并缓存 {count} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
