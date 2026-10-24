#!/usr/bin/env python3
"""按月抓取 ChiCTR 官方 XML，或从运营人员提供的官方导出刷新缓存。"""

from __future__ import annotations

import argparse
import json
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
        default=7,
        help="无 --input 时，距离上次成功刷新达到该天数才运行官方抓取（默认 7，与 CT.gov 同频）",
    )
    parser.add_argument("--force-live", action="store_true", help="忽略间隔并立即运行官方抓取")
    parser.add_argument(
        "--detail-budget",
        type=int,
        default=0,
        help=(
            "本轮允许回退详情页的项目数（用于把缓存分批迁移到 XML 直连，0 表示不限）。"
            "未迁移的项目保留旧记录并计入 records_deferred，不推进 last_verified"
        ),
    )
    args = parser.parse_args()

    if args.interval_days < 0:
        parser.error("--interval-days 不能小于 0")

    if args.input:
        payload = refresh_chictr_cache(args.cache, input_path=args.input)
        refresh_status = "updated" if not payload.get("warning") else "failed"
    else:
        force = args.force_live
        if args.detail_budget and not force:
            # 迁移未完成时不受 7 天闸门限制：否则「今天刚核对过」会让第一次
            # 迁移白白跳过一周，把一次性迁移拖成好几周。
            pending = 0
            if args.cache.exists():
                try:
                    cached = json.loads(args.cache.read_text(encoding="utf-8"))
                    pending = sum(
                        1 for record in cached.get("records") or [] if not record.get("xml_url")
                    )
                except (OSError, json.JSONDecodeError):
                    pending = 0
            if pending:
                force = True
                print(f"ℹ️ 有 {pending} 条记录尚未迁移到 XML 直连，本轮忽略间隔继续迁移")
        payload = refresh_chictr_live(
            args.cache,
            interval_days=args.interval_days,
            force=force,
            detail_budget=args.detail_budget or None,
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
        reused = payload.get("records_xml_reused")
        detail = payload.get("records_detail_fetched")
        deferred = payload.get("records_deferred")
        deferred_note = f"，分批迁移待办 {deferred} 条" if deferred else ""
        extra = (
            f"（复用 XML 链接 {reused} 条，回退详情页 {detail} 条{deferred_note}）"
            if reused is not None
            else ""
        )
        print(f"✅ ChiCTR mode={payload.get('mode')}，刷新并缓存 {count} 条{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
