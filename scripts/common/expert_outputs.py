"""专家 manifest 与区域分片输出。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import atomic_write_js_global


def build_expert_manifest(experts: dict[str, Any]) -> dict[str, Any]:
    """构建轻量 manifest；前端默认只加载中国分片。"""
    china_index = experts.get("china_expert_index") or []
    international_index = experts.get("international_expert_index") or []
    generated_at = experts.get("generated_at") or datetime.now(timezone.utc).isoformat()
    summary = dict(experts.get("summary") or {})
    summary.update({"frontend_load_mode": "china_only", "initial_shard": "china"})
    return {
        "generated_at": generated_at,
        "summary": summary,
        "experts": [],
        "quick_expert_ids": experts.get("quick_expert_ids") or {},
        "shards": [
            {
                "id": "china",
                "label": "中国作者-机构索引",
                "path": "data/expert-profiles-china.js",
                "global": "MG_EXPERT_PROFILE_CHINA",
                "count": len(china_index),
                "loaded_by_default": True,
            },
            {
                "id": "international",
                "label": "国际作者-机构索引（仅离线分析）",
                "path": "data/expert-profiles-international.js",
                "global": "MG_EXPERT_PROFILE_INTERNATIONAL",
                "count": len(international_index),
                "loaded_by_default": False,
            },
        ],
    }


def write_expert_outputs(experts: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    """每次完整专家重建固定写出 manifest 与两个分片，包括空分片。"""
    manifest = build_expert_manifest(experts)
    china_index = experts.get("china_expert_index") or []
    international_index = experts.get("international_expert_index") or []
    atomic_write_js_global(data_dir / "expert-profiles.js", "MG_EXPERT_PROFILES", manifest)
    atomic_write_js_global(
        data_dir / "expert-profiles-china.js",
        "MG_EXPERT_PROFILE_CHINA",
        {
            "generated_at": manifest["generated_at"],
            "region": "china",
            "count": len(china_index),
            "items": china_index,
        },
    )
    atomic_write_js_global(
        data_dir / "expert-profiles-international.js",
        "MG_EXPERT_PROFILE_INTERNATIONAL",
        {
            "generated_at": manifest["generated_at"],
            "region": "international",
            "count": len(international_index),
            "items": international_index,
        },
    )
    return manifest
