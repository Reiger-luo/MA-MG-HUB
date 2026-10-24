#!/usr/bin/env python3
"""按周抓取 CDE 全量 MG 登记、生成差异并重建临床试验前端数据。

平台提供 RSS，但 RSS 只有全站最近 20 条新登记，MG 试验命中率极低，
因此更新来源仍是全量检索（3 页左右），RSS 只用于输出新登记早报。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common.cde_live import CdeClient, CdeLiveError, collect_mg_trials, is_mg_trial, rss_watch
from common.china_drug_trials_import import import_china_drug_trials_exports
from common.io import atomic_write_json


PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = PROJECT / "data" / "china-drug-trials-cache.json"
DEFAULT_CHANGES = PROJECT / "data" / "china-drug-trials-changes.json"
# RSS 早报属于运行状态，不进入公开数据目录，避免未跟踪文件阻塞周更自动提交
DEFAULT_RSS = PROJECT / ".hermes-audit" / "cde-rss-snapshot.json"


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT.resolve()))
    except ValueError:
        return str(path.resolve())


def is_due(cache_path: Path, interval_days: int, now: datetime | None = None) -> tuple[bool, str]:
    """距离上次成功抓取不足 interval_days 时跳过，避免周更重复打站点。"""
    if interval_days <= 0 or not cache_path.exists():
        return True, ""
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, ""
    generated_at = str(payload.get("generated_at") or "").strip()
    if not generated_at:
        return True, ""
    try:
        last = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        return True, ""
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    elapsed = current - last
    if elapsed < timedelta(days=interval_days):
        return False, last.isoformat()
    return True, last.isoformat()


def run_rss_watch(snapshot_path: Path, *, client: CdeClient, keyword: str, cache_ids: set[str]) -> dict:
    """抓 RSS 主题早报并对比上次快照；失败不影响主流程。

    同时核对 RSS 已知的最近登记是否都已在缓存中——若 RSS 出现缓存里没有的
    登记号，说明全量检索漏抓（分页或门控异常），会显式打印告警。
    """
    try:
        current = rss_watch(client, keyword=keyword)
    except Exception as exc:
        print(f"⚠️ CDE RSS 早报不可用（不影响缓存更新）: {exc}", file=sys.stderr)
        return {}
    previous: dict = {}
    if snapshot_path.exists():
        try:
            previous = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    previous_ids = {item.get("registry_id") for item in previous.get("items") or []}
    new_items = [item for item in current["items"] if item["registry_id"] not in previous_ids]
    current["new_since_last_check"] = new_items
    current["new_count"] = len(new_items)
    # 平台的 keywords 检索是模糊匹配，会带出无关疾病（如肿瘤试验）的登记，
    # 因此只对通过 MG 门控的条目做覆盖度核对。
    current["missing_from_cache"] = sorted(
        item["registry_id"]
        for item in current["items"]
        if item["registry_id"] not in cache_ids and is_mg_trial(item["title"])
    )
    atomic_write_json(snapshot_path, current)
    print(
        f"📡 CDE RSS 早报（{keyword}）：最近 {len(current['items'])} 条登记，"
        f"较上次快照新增 {len(new_items)} 条"
    )
    for item in new_items[:5]:
        print(f"   · {item['registry_id']} {item['published_date']} {item['title'][:56]}")
    if current["missing_from_cache"]:
        print(
            "⚠️ RSS 中出现缓存未收录的登记号（请检查分页/门控）："
            + ", ".join(current["missing_from_cache"][:10])
        )
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh ChinaDrugTrials MG cache from the official registry")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--changes", type=Path, default=DEFAULT_CHANGES)
    parser.add_argument("--rss-snapshot", type=Path, default=DEFAULT_RSS)
    parser.add_argument("--keyword", default="重症肌无力")
    parser.add_argument(
        "--interval-days",
        type=int,
        default=7,
        help="距离上次成功抓取达到该天数才重新检索（默认 7；0 表示每次都抓）",
    )
    parser.add_argument("--force-live", action="store_true", help="忽略间隔立即抓取")
    parser.add_argument("--rss-only", action="store_true", help="只抓 RSS 早报，不更新缓存")
    parser.add_argument("--dry-run", action="store_true", help="抓取并比较，但不写缓存、不重建网站")
    parser.add_argument(
        "--allow-large-drop",
        action="store_true",
        help="允许新抓取数量低于旧缓存的 60%%；仅在确认平台确实大幅删减时使用",
    )
    parser.add_argument("--no-build", action="store_true", help="更新缓存但不重建前端数据")
    args = parser.parse_args()

    if args.interval_days < 0:
        parser.error("--interval-days 不能小于 0")

    client = CdeClient()

    def cached_ids() -> set[str]:
        """读取当前缓存里的登记号，供 RSS 早报核对覆盖度。"""
        if not args.cache.exists():
            return set()
        try:
            payload = json.loads(args.cache.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        return {
            str(item.get("registry_id") or "")
            for item in payload.get("records") or []
            if item.get("registry_id")
        }

    if args.rss_only:
        run_rss_watch(
            args.rss_snapshot,
            client=client,
            keyword=args.keyword,
            cache_ids=cached_ids(),
        )
        return 0

    due, last_seen = is_due(args.cache, args.interval_days)
    if not args.force_live and not due:
        print(f"ℹ️ CDE 周更未到期（上次 {last_seen}），继续使用 {len(cached_ids())} 条缓存")
        run_rss_watch(
            args.rss_snapshot,
            client=client,
            keyword=args.keyword,
            cache_ids=cached_ids(),
        )
        return 0

    try:
        records, meta = collect_mg_trials(client, keyword=args.keyword)
    except CdeLiveError as exc:
        print(f"⚠️ CDE 抓取不可用，保留最后良好缓存: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # 网络异常同样不能改写缓存
        print(f"⚠️ CDE 抓取失败，保留最后良好缓存: {exc}", file=sys.stderr)
        return 1

    print(
        f"CDE 抓取完成 · 检索 {meta['scanned_rows']} 条（平台声明 "
        f"{meta['declared_total']}，{meta['total_pages']} 页）· MG 命中 {meta['mg_rows']} 条"
    )
    if meta["detail_failures"]:
        print(f"⚠️ 详情页失败 {len(meta['detail_failures'])} 条：{meta['detail_failures'][:5]}")

    try:
        payload, changes = import_china_drug_trials_exports(
            args.cache,
            records=records,
            changes_path=args.changes,
            allow_large_drop=args.allow_large_drop,
            dry_run=args.dry_run,
            mode="live_crawl",
            query=args.keyword,
            inputs=[{"name": "cde-live-crawl", "sha256": ""}],
        )
    except Exception as exc:
        print(f"❌ CDE 导入失败，旧缓存未改动: {exc}", file=sys.stderr)
        return 1

    print(
        "ChinaDrugTrials 对比完成 · "
        f"旧 {changes['old_count']} → 新 {changes['new_count']} · "
        f"新增 {changes['added_count']} · 更新 {changes['updated_count']} · "
        f"移除 {changes['removed_count']} · 基线补全 {changes.get('enriched_count', 0)}"
    )
    if args.dry_run:
        print("ℹ️ dry-run：未写缓存，未重建网站")
        return 0

    print(f"✅ 已更新 {display_path(args.cache)}（{payload['total']} 条）")
    print(f"✅ 已写入差异报告 {display_path(args.changes)}")
    run_rss_watch(
        args.rss_snapshot,
        client=client,
        keyword=args.keyword,
        cache_ids={
            str(item.get("registry_id") or "")
            for item in payload.get("records") or []
            if item.get("registry_id")
        },
    )

    if not args.no_build:
        for script, label in (
            ("build-clinical-trials-data.py", "临床试验页面与首页摘要"),
            ("generate-pipeline-status.py", "数据状态页"),
        ):
            result = subprocess.run([sys.executable, f"scripts/{script}"], cwd=PROJECT)
            if result.returncode != 0:
                print(f"❌ 缓存已更新，但{label}重建失败", file=sys.stderr)
                return result.returncode
            print(f"✅ 已重建{label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())