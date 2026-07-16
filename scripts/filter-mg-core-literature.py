#!/usr/bin/env python3
"""审计或清理本地 full 文献库中的非 MG-core 记录。"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from common.io import atomic_write_json
    from common.mg_relevance import filter_mg_core
except ModuleNotFoundError:  # 支持测试按文件导入
    from scripts.common.io import atomic_write_json
    from scripts.common.mg_relevance import filter_mg_core


PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_FULL = PROJECT / "data" / "literature-full.json"
DEFAULT_ARCHIVE = PROJECT / "data" / "archive"


def filter_file(full_path: Path, archive_dir: Path, *, apply: bool = False):
    if not full_path.exists():
        return {"status": "absent", "input_count": 0, "excluded_count": 0, "archive_path": None}
    source_bytes = full_path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    articles = json.loads(source_bytes.decode("utf-8"))
    kept, excluded, counters = filter_mg_core(articles)
    result = {
        "status": "applied" if apply else "dry_run",
        "input_count": len(articles),
        "kept_count": len(kept),
        "excluded_count": len(excluded),
        "reason_counts": dict(sorted(counters.items())),
        "archive_path": None,
    }
    if not apply or not excluded:
        return result

    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_dir / f"literature-full-mg-core-excluded-{timestamp}-{source_hash[:12]}.json"
    archive_payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(full_path),
        "source_sha256": source_hash,
        "input_count": len(articles),
        "excluded_count": len(excluded),
        "reason_counts": dict(Counter(item.get("mg_core_reason") for item in excluded)),
        "records": excluded,
    }
    atomic_write_json(archive_path, archive_payload)
    atomic_write_json(full_path, kept)
    result["archive_path"] = str(archive_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="MG-core full literature audit (dry-run by default)")
    parser.add_argument("--full", type=Path, default=DEFAULT_FULL)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--apply", action="store_true", help="原子写回并归档排除的完整记录")
    args = parser.parse_args()
    result = filter_file(args.full, args.archive_dir, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
