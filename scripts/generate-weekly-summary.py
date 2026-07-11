#!/usr/bin/env python3
"""
generate-weekly-summary.py — 生成当前通讯渠道可直接使用的 MA-MG-HUB 周报。
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from common.io import atomic_write_text, load_js_global


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
SITE_URL = "https://reiger-luo.github.io/MA-MG-HUB/"


def load_js_data(filename: str, global_name: str):
    return load_js_global(DATA_DIR / filename, global_name)


def signal_line(signal: dict, index: int) -> str:
    article = signal.get("article") or {}
    title = signal.get("summary") or article.get("title") or "Untitled"
    pmids = signal.get("related_pmids") or []
    pmid = pmids[0] if pmids else article.get("pmid", "-")
    strength = signal.get("strength") or "-"
    reason = signal.get("reason") or ""
    return f"{index}. [{strength}] {title}（PMID {pmid}）{(' - ' + reason) if reason else ''}"


def kol_lead_text(signal: dict) -> str:
    leads = signal.get("kol_leads") or []
    if leads:
        lead = leads[0]
        roles = "/".join(lead.get("roles") or [])
        institution = lead.get("institution") or lead.get("country") or "机构待识别"
        return f"{lead.get('name', 'KOL待识别')}（{roles or '作者'}；{institution}）"
    institutions = signal.get("institution_leads") or []
    if institutions:
        inst = institutions[0]
        country = inst.get("country") or "地区待识别"
        return f"机构线索：{inst.get('name', '机构待识别')}（{country}）"
    return "KOL/机构待识别"


def signal_to_kol_line(signal: dict, index: int) -> str:
    article = signal.get("article") or {}
    pmids = signal.get("related_pmids") or []
    pmid = pmids[0] if pmids else article.get("pmid", "-")
    medical = signal.get("medical_affairs") or {}
    implication = medical.get("implication") or signal.get("medical_affairs_implication") or "医学事务含义待补充"
    action = medical.get("msl_action") or "MSL 后续行动待补充"
    return f"{index}. PMID {pmid}｜{implication}｜{kol_lead_text(signal)}｜{action}"


def article_line(article: dict, index: int) -> str:
    title = article.get("title") or "Untitled"
    pmid = article.get("pmid", "-")
    journal = article.get("journal") or "-"
    level = article.get("evidence_level") or "未分类"
    return f"{index}. {title}（{journal}；PMID {pmid}；证据 {level}）"


def build_summary() -> str:
    dashboard = load_js_data("dashboard-data.js", "MG_DASHBOARD_DATA")
    signals = load_js_data("signals-weekly.js", "MG_SIGNALS_DATA")
    china = load_js_data("china-intelligence.js", "MG_CHINA_DATA")

    stats = dashboard.get("stats") or {}
    signal_items = signals.get("signals") or []
    top_signals = (dashboard.get("top_signals") or signal_items)[:3]
    top_signal_to_kol = signal_items[:3]
    china_articles = (china.get("pubmed_articles") or [])[:3]
    work_items = dashboard.get("work_items") or []
    hotspots = (signals.get("topic_hotspots") or [])[:5]

    lines = [
        "# MA-MG-HUB 周更",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 数据状态",
        "",
        f"- 近1年文献：{stats.get('recent_articles', 0)}",
        f"- 中国相关：{stats.get('china_articles', 0)}",
        f"- 候选信号：{stats.get('signals', 0)}",
        f"- 文献级 Signal-to-KOL：{len(signal_items)}（自动审核发布）",
        f"- 专家画像：{stats.get('experts', 0)}",
        f"- 内容模块：{stats.get('modules', 0)}",
        "",
        "## 强信号 Top 3",
        "",
    ]
    lines.extend(signal_line(signal, idx) for idx, signal in enumerate(top_signals, 1))

    lines.extend(["", "## 文献级 Signal-to-KOL Top 3", ""])
    if top_signal_to_kol:
        lines.extend(signal_to_kol_line(signal, idx) for idx, signal in enumerate(top_signal_to_kol, 1))
    else:
        lines.append("- 暂无")

    lines.extend(["", "## 中国情报 Top 3", ""])
    lines.extend(article_line(article, idx) for idx, article in enumerate(china_articles, 1))

    lines.extend(["", "## 热点主题", ""])
    if hotspots:
        lines.extend(f"- {item.get('topic')}: {item.get('count')}" for item in hotspots)
    else:
        lines.append("- 暂无")

    lines.extend(["", "## 待处理", ""])
    if work_items:
        lines.extend(f"- {item.get('label')}: {item.get('count')}" for item in work_items)
    else:
        lines.append("- 暂无")

    lines.extend(["", "## 入口", "", SITE_URL, ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate MA-MG-HUB weekly summary")
    parser.add_argument("--output", default="data/weekly-summary.md", help="输出 Markdown 文件路径")
    args = parser.parse_args()

    summary = build_summary()
    output = PROJECT / args.output
    atomic_write_text(output, summary + "\n")
    print(summary)
    try:
        display_path = output.relative_to(PROJECT)
    except ValueError:
        display_path = output
    print(f"\n✅ weekly summary written: {display_path}")


if __name__ == "__main__":
    main()
