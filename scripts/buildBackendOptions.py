#!/usr/bin/env python3
"""
buildBackendOptions.py — 生成 Phase 6 后端选项评估产物。

Phase 6 当前不是启动真实后端，而是把“什么时候需要后端、选哪类后端、
当前为什么暂缓”沉淀成公开、可审计的数据和报告。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
REPORT_DIR = PROJECT / "report"


def load_js(filename: str, global_name: str) -> Any:
    path = DATA_DIR / filename
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(global_name)}\s*=\s*(.*);\s*$", text, re.S)
    if not match:
        raise ValueError(f"Cannot parse {path}")
    return json.loads(match.group(1))


def maybe_load_js(filename: str, global_name: str) -> Any:
    path = DATA_DIR / filename
    if not path.exists():
        return None
    return load_js(filename, global_name)


def bool_label(value: bool) -> str:
    return "已触发" if value else "未触发"


def build_payload() -> dict[str, Any]:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pipeline = maybe_load_js("pipeline-status.js", "MG_PIPELINE_STATUS") or {}
    storage = pipeline.get("storage") or {}
    artifact_ids = {path.name for path in DATA_DIR.glob("*") if path.is_file()}

    # Phase 6 的关键是触发条件。当前静态站没有登录、私有笔记、实时问答或后端密钥。
    triggers = [
        {
            "id": "realtimeLlmQa",
            "label": "实时 LLM 问答",
            "triggered": False,
            "evidence": "动态诊治格局已由离线脚本生成，前端不调用 LLM。",
            "backend_need": "需要隐藏模型 key、限流、日志和引用校验时再启动。",
        },
        {
            "id": "realtimeSemanticSearch",
            "label": "实时语义搜索",
            "triggered": False,
            "evidence": "当前使用 full-index、社区分片和静态图谱检索，未接入向量服务。",
            "backend_need": "需要跨全文、自然语言问答或 embedding 排序时再启动。",
        },
        {
            "id": "privateNotes",
            "label": "用户私有笔记",
            "triggered": False,
            "evidence": "公开站只展示公开数据产物；拜访记录和内部标签不进入仓库。",
            "backend_need": "需要多人私有记录、跟进任务或专家标签时再启动。",
        },
        {
            "id": "collaboration",
            "label": "多人协作",
            "triggered": False,
            "evidence": "当前协作仍以 Git/Hermes/Codex 工作流为主。",
            "backend_need": "需要浏览器内多人编辑、审阅队列或通知时再启动。",
        },
        {
            "id": "permission",
            "label": "权限管理",
            "triggered": False,
            "evidence": "GitHub Pages 为公开展示层，无登录和权限分层。",
            "backend_need": "需要区分公开、内部、个人笔记和管理员操作时再启动。",
        },
    ]

    options = [
        {
            "id": "staticGithubPages",
            "name": "继续 GitHub Pages + 本地/Hermes 周更",
            "fit": "current",
            "recommendation": "当前主路径",
            "best_for": ["公开展示", "静态数据产物", "可追溯知识库", "低运维成本"],
            "tradeoffs": ["不支持私有用户数据", "不适合实时 LLM key", "交互智能依赖离线生成"],
            "score": {"security": 5, "cost": 5, "complexity": 5, "data_fit": 4, "future_flex": 3},
        },
        {
            "id": "cloudflareWorker",
            "name": "Cloudflare Worker + KV/D1",
            "fit": "candidate",
            "recommendation": "优先轻后端候选",
            "best_for": ["LLM API 代理", "轻量权限", "速率限制", "公开缓存"],
            "tradeoffs": ["复杂查询能力有限", "D1 数据模型需提前设计", "本地 full 仍不应直接搬上云"],
            "score": {"security": 4, "cost": 4, "complexity": 4, "data_fit": 3, "future_flex": 4},
        },
        {
            "id": "vercelFunction",
            "name": "Vercel Function",
            "fit": "candidate",
            "recommendation": "适合作原型",
            "best_for": ["快速 API 原型", "LLM 代理", "小规模服务端逻辑"],
            "tradeoffs": ["与 GitHub Pages 部署面分离", "持久化仍需外部数据库", "长期运行任务不合适"],
            "score": {"security": 4, "cost": 3, "complexity": 3, "data_fit": 2, "future_flex": 3},
        },
        {
            "id": "supabaseEdge",
            "name": "Supabase Edge Function + Postgres/Auth",
            "fit": "future",
            "recommendation": "私有数据触发后再评估",
            "best_for": ["用户登录", "私有笔记", "多人协作", "审阅队列"],
            "tradeoffs": ["数据治理复杂度最高", "需要权限模型", "公开站阶段过早引入会增加负担"],
            "score": {"security": 4, "cost": 3, "complexity": 2, "data_fit": 5, "future_flex": 5},
        },
        {
            "id": "localHermesApi",
            "name": "本地 Hermes API",
            "fit": "operator",
            "recommendation": "本地完整分析和自动化主控",
            "best_for": ["访问 full 本地库", "长任务", "定时周更", "本地 LLM/embedding 实验"],
            "tradeoffs": ["不适合作公开多人访问", "需要本机在线", "浏览器外部访问需额外安全边界"],
            "score": {"security": 5, "cost": 4, "complexity": 3, "data_fit": 5, "future_flex": 4},
        },
    ]

    readiness = {
        "status": "defer",
        "status_label": "暂缓后端",
        "decision": "当前继续采用离线智能 + 静态发布；Phase 6 不启动生产后端。",
        "reason": "核心能力已经能通过公开静态产物运行，触发后端的 5 类需求均未成为当前阻塞。",
        "triggered_count": sum(1 for item in triggers if item["triggered"]),
        "total_triggers": len(triggers),
        "recommended_now": "staticGithubPages",
        "first_backend_candidate": "cloudflareWorker",
        "operator_backend": "localHermesApi",
    }

    return {
        "generated_at": generated_at,
        "version": "2026.07-phase6-backend-options",
        "method": "staticArchitectureDecisionRecord",
        "summary": readiness,
        "triggers": triggers,
        "options": options,
        "decision_rules": [
            "只要没有实时 LLM key、私有用户数据或多人协作，GitHub Pages 继续作为主展示层。",
            "所有 LLM/embedding 能离线生成的结果优先离线生成，并以静态 JS 产物发布。",
            "第一个轻后端只承担窄职责：LLM 代理、限流、日志或私有笔记之一，不一次性承载全站。",
            "本地 full 数据库仍留在本地/Hermes，不直接上传到公开后端。",
        ],
        "next_steps": [
            {
                "stage": "现在",
                "action": "维持 GitHub Pages + 本地/Hermes 周更；数据状态页展示后端暂缓原因。",
            },
            {
                "stage": "触发后",
                "action": "若需要实时 LLM 问答，先做 Cloudflare Worker API 代理和 PMID schema 校验。",
            },
            {
                "stage": "私有数据触发后",
                "action": "若需要拜访记录、个人笔记或多人协作，再评估 Supabase Auth/Postgres。",
            },
        ],
        "current_site_evidence": {
            "storage_mode": storage.get("mode") or ("local_full_first" if (DATA_DIR / "literature-full.json").exists() else "recent_fallback"),
            "full_available_on_site": bool(storage.get("full_available")),
            "public_artifact_count": len([name for name in artifact_ids if name.endswith((".js", ".md", ".json"))]),
            "has_landscape_insights": "landscapeInsights.js" in artifact_ids,
            "has_community_layer": "communityTaxonomy.js" in artifact_ids and "communityCards.js" in artifact_ids,
            "has_graph_layer": "knowledge-graph.js" in artifact_ids,
            "trigger_labels": [f"{item['label']}：{bool_label(item['triggered'])}" for item in triggers],
        },
        "guardrails": [
            "不得把 API key 放进 GitHub Pages 前端或公开仓库。",
            "不得把本地 full abstract、私有拜访记录、专家内部标签直接推到公开后端。",
            "后端生成的医学洞察必须保留 PMID、证据等级、社区、图谱节点和限制说明。",
            "任何实时问答都必须区分 abstract-level 线索和正式医学结论。",
        ],
    }


def option_score(option: dict[str, Any]) -> float:
    score = option.get("score") or {}
    return round(sum(score.values()) / max(len(score), 1), 1)


def write_report(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / "backendOptionsPhase6-2026-07-01.md"
    summary = payload["summary"]
    lines = [
        "# MA-MG-HUB Phase 6 后端选项评估",
        "",
        f"生成时间：{payload['generated_at']}",
        f"版本：`{payload['version']}`",
        "",
        "## 1. 结论",
        "",
        f"**{summary['status_label']}**。{summary['decision']}",
        "",
        summary["reason"],
        "",
        "当前建议：继续 `GitHub Pages + 本地/Hermes 周更 + 静态公开产物`。",
        "",
        "## 2. 后端触发条件",
        "",
        "| 条件 | 当前状态 | 证据 | 什么时候需要后端 |",
        "| --- | --- | --- | --- |",
    ]
    for item in payload["triggers"]:
        lines.append(
            f"| {item['label']} | {bool_label(item['triggered'])} | "
            f"{item['evidence']} | {item['backend_need']} |"
        )

    lines.extend([
        "",
        "## 3. 选项比较",
        "",
        "| 选项 | 推荐级别 | 适合场景 | 主要代价 | 平均分 |",
        "| --- | --- | --- | --- | ---: |",
    ])
    for option in payload["options"]:
        lines.append(
            f"| {option['name']} | {option['recommendation']} | "
            f"{'；'.join(option['best_for'])} | {'；'.join(option['tradeoffs'])} | {option_score(option)} |"
        )

    lines.extend([
        "",
        "## 4. 决策规则",
        "",
    ])
    lines.extend(f"- {item}" for item in payload["decision_rules"])
    lines.extend([
        "",
        "## 5. 后续路径",
        "",
    ])
    lines.extend(f"- **{item['stage']}**：{item['action']}" for item in payload["next_steps"])
    lines.extend([
        "",
        "## 6. 护栏",
        "",
    ])
    lines.extend(f"- {item}" for item in payload["guardrails"])
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    payload = build_payload()
    output = DATA_DIR / "backendOptions.js"
    output.write_text(
        "window.MG_BACKEND_OPTIONS = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    write_report(payload)
    print(
        "✅ backend options written:",
        output.relative_to(PROJECT),
        f"({payload['summary']['status_label']})",
    )


if __name__ == "__main__":
    main()
