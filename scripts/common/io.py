"""结构化数据读写工具。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    """读取 JSON 文件。"""
    return json.loads(path.read_text(encoding="utf-8"))


def load_js_global(path: Path, global_name: str) -> Any:
    """从 window.GLOBAL = <json>; 格式的公开 JS 产物中解析 JSON。"""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(global_name)}\s*=\s*", text)
    if not match:
        raise ValueError(f"Cannot find window.{global_name} assignment in {path}")
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(text[match.end():].lstrip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cannot parse window.{global_name} JSON in {path}: {exc}") from exc
    return payload


def atomic_write_text(path: Path, content: str) -> None:
    """先写临时文件，再原子替换目标文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, payload: Any, *, indent: int | None = 2) -> None:
    """原子写入 JSON。"""
    text = json.dumps(payload, ensure_ascii=False, indent=indent)
    atomic_write_text(path, text + "\n")


def atomic_write_js_global(path: Path, global_name: str, payload: Any, header: str = "") -> None:
    """原子写入 window.GLOBAL = <json>; 公开 JS 产物。"""
    text = header + f"window.{global_name} = " + json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ) + ";\n"
    atomic_write_text(path, text)
