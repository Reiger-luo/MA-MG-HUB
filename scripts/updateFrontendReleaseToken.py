#!/usr/bin/env python3
"""把同一 run id 写入活动页面的本地脚本和样式 URL。"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from common.io import atomic_write_text


projectPath = Path(__file__).resolve().parent.parent
activePages = (
    projectPath / "index.html",
    projectPath / "pages" / "literature.html",
    projectPath / "pages" / "landscape.html",
    projectPath / "pages" / "knowledge.html",
    projectPath / "pages" / "msl.html",
    projectPath / "pages" / "data-ops.html",
)


def versionLocalAssets(text: str, releaseId: str) -> str:
    """只改 script src 与 stylesheet href，不改页面导航或数据查看链接。"""
    version = f"v={releaseId}"

    def replaceScript(match: re.Match) -> str:
        prefix, path, suffix = match.groups()
        cleanPath = path.split("?", 1)[0]
        return f'{prefix}{cleanPath}?{version}{suffix}'

    text = re.sub(
        r'(<script\b[^>]*\bsrc=")((?:\.\./)?(?:assets|data)/[^"?]+(?:\?[^" ]*)?)("[^>]*>)',
        replaceScript,
        text,
    )
    text = re.sub(
        r'(<link\b[^>]*\brel="stylesheet"[^>]*\bhref=")((?:\.\./)?assets/[^"?]+(?:\?[^" ]*)?)("[^>]*>)',
        replaceScript,
        text,
    )
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=os.environ.get("MG_PIPELINE_RUN_ID", ""))
    args = parser.parse_args()
    releaseId = str(args.release_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", releaseId):
        parser.error("release id 仅允许字母、数字、点、下划线和连字符")

    changed = 0
    for path in activePages:
        before = path.read_text(encoding="utf-8")
        after = versionLocalAssets(before, releaseId)
        if after != before:
            atomic_write_text(path, after)
            changed += 1
    print(f"✅ frontend release token={releaseId} · 更新 {changed}/{len(activePages)} 个页面")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
