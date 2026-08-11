"""临床试验来源缓存的稳定版本契约。"""

from __future__ import annotations

import hashlib
import json
from typing import Any


VOLATILE_SOURCE_FIELDS = {"generated_at", "scraped_at", "last_verified"}


def source_revision(payload: dict[str, Any]) -> str:
    """只对实质缓存内容生成摘要，纯抓取时间变化不推进分析窗口。"""
    if not payload:
        return ""
    semantic_payload = {
        key: value for key, value in payload.items()
        if key not in VOLATILE_SOURCE_FIELDS
    }
    content = json.dumps(semantic_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "semantic-v1:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def legacy_source_revision(payload: dict[str, Any]) -> str:
    """旧版全缓存摘要，仅用于验证受控迁移。"""
    if not payload:
        return ""
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
