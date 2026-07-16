#!/usr/bin/env python3
"""使用运营人员提供的 ChiCTR 官方 JSON/CSV 导出刷新静态缓存。"""

from __future__ import annotations

import argparse
from pathlib import Path

from common.clinical_registry import refresh_chictr_cache


PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = PROJECT / "data" / "chictr-trials-cache.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh cache from an official ChiCTR JSON/CSV export")
    parser.add_argument("--input", type=Path, help="运营人员提供的 ChiCTR 官方 JSON/CSV 导出")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args()
    payload = refresh_chictr_cache(args.cache, input_path=args.input)
    count = len(payload.get("records") or [])
    if payload.get("warning"):
        print(f"⚠️ ChiCTR 刷新不可用，保留最后良好缓存（{count} 条）: {payload['warning']}")
    else:
        print(f"✅ ChiCTR mode={payload.get('mode')}，缓存 {count} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
