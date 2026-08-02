"""结构化数据读写工具。"""

from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, TextIO


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


@contextmanager
def atomic_text_writer(path: Path, *, fsync: bool = False) -> Iterator[TextIO]:
    """提供同目录临时文本流，成功后原子替换目标，异常时保留 last-good。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yield handle
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        os.replace(tmp, path)
        if fsync:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


def atomic_write_text(path: Path, content: str, *, fsync: bool = False) -> None:
    """使用同目录唯一临时文件写入，失败时保留旧目标并清理临时文件。"""
    with atomic_text_writer(path, fsync=fsync) as handle:
        handle.write(content)


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
