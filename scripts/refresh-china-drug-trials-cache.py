#!/usr/bin/env python3
"""导入 ChinaDrugTrials 月度官方文件、输出差异并重建网站数据。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common.china_drug_trials_import import import_china_drug_trials_exports


PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE = PROJECT / "data" / "china-drug-trials-cache.json"
DEFAULT_CHANGES = PROJECT / "data" / "china-drug-trials-changes.json"


def display_path(path: Path) -> str:
    """优先显示项目相对路径，外部交接文件保留绝对路径。"""
    try:
        return str(path.resolve().relative_to(PROJECT.resolve()))
    except ValueError:
        return str(path.resolve())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import official ChinaDrugTrials JSON/CSV/XLS/XLSX exports"
    )
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        required=True,
        help="官方导出文件；如分成多个文件可重复传入",
    )
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--changes", type=Path, default=DEFAULT_CHANGES)
    parser.add_argument("--dry-run", action="store_true", help="只比较，不写缓存或重建网站")
    parser.add_argument(
        "--allow-large-drop",
        action="store_true",
        help="允许新导出数量低于旧缓存的 60%%；仅确认是完整导出时使用",
    )
    parser.add_argument("--no-build", action="store_true", help="更新缓存但不重建临床试验前端数据")
    args = parser.parse_args()

    try:
        payload, changes = import_china_drug_trials_exports(
            args.cache,
            args.input,
            changes_path=args.changes,
            allow_large_drop=args.allow_large_drop,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"❌ ChinaDrugTrials 导入失败，旧缓存未改动: {exc}", file=sys.stderr)
        return 1

    print(
        "ChinaDrugTrials 对比完成 · "
        f"旧 {changes['old_count']} → 新 {changes['new_count']} · "
        f"新增 {changes['added_count']} · 更新 {changes['updated_count']} · "
        f"移除 {changes['removed_count']}"
    )
    if args.dry_run:
        print("ℹ️ dry-run：未写缓存，未重建网站")
        return 0

    print(f"✅ 已更新 {display_path(args.cache)}（{payload['total']} 条）")
    print(f"✅ 已写入差异报告 {display_path(args.changes)}")
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
