#!/usr/bin/env python3
"""
generate-pipeline-status.py — 生成 MA-MG-HUB 数据管线状态。

只输出可公开的运行状态与数据产物摘要，不写入本地路径、Token 或内部专家信息。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
SITE_URL = "https://reiger-luo.github.io/MA-MG-HUB/"


PUBLIC_ARTIFACTS = [
    ("dashboard-data.js", "Dashboard 数据", "MG_DASHBOARD_DATA"),
    ("literature-recent.js", "近一年文献公开库", "MG_LITERATURE_DATA"),
    ("signals-weekly.js", "候选信号", "MG_SIGNALS_DATA"),
    ("china-intelligence.js", "中国情报", "MG_CHINA_DATA"),
    ("expert-profiles.js", "专家画像", "MG_EXPERT_PROFILES"),
    ("landscape-data.js", "诊治格局", "MG_LANDSCAPE_DATA"),
    ("content-modules.js", "内容模块", "MG_CONTENT_MODULES"),
    ("weekly-summary.md", "当前通讯渠道周报", None),
]


def loadJson(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def loadJs(filename: str, globalName: str):
    path = DATA_DIR / filename
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(globalName)}\s*=\s*(.*);\s*$", text, re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}")
    return json.loads(match.group(1))


def safeLoadJs(filename: str, globalName: str):
    path = DATA_DIR / filename
    if not path.exists():
        return None
    return loadJs(filename, globalName)


def countPayload(payload):
    if payload is None:
        return 0
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("signals", "articles", "pubmed_articles", "experts", "modules", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return None
    return None


def artifactInfo(filename: str, label: str, globalName: str | None):
    path = DATA_DIR / filename
    if not path.exists():
        return {
            "id": filename,
            "label": label,
            "status": "missing",
            "status_label": "缺失",
            "count": None,
            "updated_at": None,
            "size_kb": None,
        }

    count = None
    if globalName:
        count = countPayload(loadJs(filename, globalName))

    updatedAt = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "id": filename,
        "label": label,
        "status": "ok",
        "status_label": "已生成",
        "count": count,
        "updated_at": updatedAt,
        "size_kb": round(path.stat().st_size / 1024, 1),
    }


def buildStatus():
    dashboard = safeLoadJs("dashboard-data.js", "MG_DASHBOARD_DATA") or {}
    literature = safeLoadJs("literature-recent.js", "MG_LITERATURE_DATA") or []
    signals = safeLoadJs("signals-weekly.js", "MG_SIGNALS_DATA") or {}
    modules = safeLoadJs("content-modules.js", "MG_CONTENT_MODULES") or []

    stats = dashboard.get("stats") or {}
    fullPath = DATA_DIR / "literature-full.json"
    weeklyPath = DATA_DIR / "literature-weekly.json"
    fullCount = None
    weeklyCount = None
    if fullPath.exists():
        fullCount = len(loadJson(fullPath))
    if weeklyPath.exists():
        weeklyCount = len(loadJson(weeklyPath))

    recentCount = len(literature)
    signalCount = len(signals.get("signals") or [])
    generatedAt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    storageMode = "local_full_first" if fullPath.exists() else "recent_fallback"

    sources = [
        {
            "id": "pubmed",
            "name": "PubMed 近一年公开库",
            "meta": f"{recentCount} 篇近1年文献 · {stats.get('china_articles', 0)} 篇中国相关 · {signalCount} 条候选信号",
            "status": "ok",
            "status_label": "正常",
        },
        {
            "id": "fullStorage",
            "name": "本地 full 分析底座",
            "meta": (
                f"本地 literature-full.json 已接入 · {fullCount} 篇"
                if fullCount is not None
                else "GitHub Actions 不保存 full；网站使用 recent.js 公开滚动源"
            ),
            "status": "ok" if fullCount is not None else "manual",
            "status_label": "本地可用" if fullCount is not None else "本地专用",
        },
        {
            "id": "conference",
            "name": "会议摘要",
            "meta": "暂不进入自动周更；后续按 AAN / EAN / AANEM 做独立来源",
            "status": "planned",
            "status_label": "规划中",
        },
        {
            "id": "clinicalTrials",
            "name": "ClinicalTrials.gov",
            "meta": "暂不作为自动数据源；需要竞品专题时按需抓取",
            "status": "manual",
            "status_label": "按需",
        },
        {
            "id": "regulatory",
            "name": "监管动态 (FDA/NMPA)",
            "meta": "不与 PubMed 周更混合；后续由公开来源和手动维护补充",
            "status": "manual",
            "status_label": "手动",
        },
        {
            "id": "frontendArtifacts",
            "name": "前端数据产物",
            "meta": f"{stats.get('experts', 0)} 位专家画像 · {stats.get('modules', countPayload(modules) or 0)} 个内容模块 · 更新时间 {dashboard.get('generated_at') or generatedAt}",
            "status": "ok",
            "status_label": "已生成",
        },
    ]

    artifacts = [artifactInfo(filename, label, globalName) for filename, label, globalName in PUBLIC_ARTIFACTS]

    logs = [
        f"[{generatedAt[:10]}] pipeline-status.js 已生成：状态页读取真实数据产物，不再依赖页面硬编码。",
        f"[{generatedAt[:10]}] 存储模式：{storageMode}；recent.js {recentCount} 篇；signals {signalCount} 条。",
    ]
    if weeklyCount is not None:
        logs.append(f"[{generatedAt[:10]}] 当前 weekly 临时输入 {weeklyCount} 篇；默认不入仓库。")
    if fullCount is not None:
        logs.append(f"[{generatedAt[:10]}] 本地 full 分析底座 {fullCount} 篇；周更只 upsert 新增/更新文献。")

    return {
        "generated_at": generatedAt,
        "site_url": SITE_URL,
        "storage": {
            "mode": storageMode,
            "recent_count": recentCount,
            "full_available": fullCount is not None,
            "full_count": fullCount,
            "weekly_temp_count": weeklyCount,
            "recent_json_cache": (DATA_DIR / "literature-recent.json").exists(),
        },
        "pipeline": {
            "local_command": "python3 scripts/run-weekly-pipeline.py",
            "workflow": "MA-MG-HUB Weekly Pipeline",
            "schedule": "每周日 23:00 Asia/Shanghai",
            "policy": "不做全库历史回填；只对 weekly 新增且有摘要、足够判断的文献补充证据等级与 IF/CAS。",
        },
        "sources": sources,
        "artifacts": artifacts,
        "logs": logs,
    }


def main():
    output = DATA_DIR / "pipeline-status.js"
    status = buildStatus()
    with output.open("w", encoding="utf-8") as f:
        f.write("window.MG_PIPELINE_STATUS = ")
        json.dump(status, f, ensure_ascii=False)
        f.write(";\n")
    print(f"✅ pipeline status written: {output.relative_to(PROJECT)}")


if __name__ == "__main__":
    main()
