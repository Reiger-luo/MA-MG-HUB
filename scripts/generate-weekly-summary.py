#!/usr/bin/env python3
"""
generate-weekly-summary.py — 生成当前通讯渠道可直接使用的 MA-MG-HUB 周报。

定位：状态呈现 + 阅读线索，不是待办清单。
每条文献信号合并呈现「新发现 → KOL → 会前动作」，不再拆成两个 Top 3。
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from common.io import atomic_write_text, load_js_global


PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
SITE_URL = os.environ.get("MG_SITE_URL", "https://reiger-luo.github.io/MA-MG-HUB/").rstrip("/") + "/"


def load_js_data(filename: str, global_name: str):
    return load_js_global(DATA_DIR / filename, global_name)


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


def signal_entry(signal: dict, index: int) -> list[str]:
    """一条信号 = 新发现 + KOL + 会前动作，三行一组。"""
    article = signal.get("article") or {}
    title = signal.get("summary") or article.get("title") or "Untitled"
    pmids = signal.get("related_pmids") or []
    pmid = pmids[0] if pmids else article.get("pmid", "-")
    strength = signal.get("strength") or "-"
    medical = signal.get("medical_affairs") or {}
    action = medical.get("msl_action") or "MSL 后续行动待补充"
    return [
        f"{index}. **[{strength}] {title}**（PMID {pmid}）",
        f"   KOL：{kol_lead_text(signal)}",
        f"   会前：{action}",
    ]


def trial_signal_line(signal: dict, index: int) -> str:
    registry_ids = " / ".join(signal.get("registryIds") or []) or "登记号待核对"
    phase = signal.get("phase") or "阶段未标注"
    change = signal.get("changeSummary") or signal.get("takeaway") or "注册信息更新"
    takeaway = signal.get("takeaway") or "开发意义待复核"
    return (
        f"{index}. [{signal.get('strength') or '-'}] {signal.get('title') or '未命名试验信号'}"
        f"（{registry_ids}；{phase}）｜{change}｜{takeaway}"
    )


def trial_window_line(source: str, window: dict) -> str:
    start = str(window.get("window_start") or "-")[:10]
    end = str(window.get("window_end") or window.get("updated_at") or "-")[:10]
    return f"- {source}：原始变化 {window.get('raw_change_count', 0)}（{start} → {end}）"


def article_line(article: dict, index: int) -> str:
    title = article.get("title") or "Untitled"
    pmid = article.get("pmid", "-")
    journal = article.get("journal") or "-"
    level = article.get("evidence_level") or "未分类"
    return f"{index}. {title}（{journal}；PMID {pmid}；证据 {level}）"


def build_summary() -> str:
    dashboard = load_js_data("dashboard-data.js", "MG_DASHBOARD_DATA")
    signals = load_js_data("signals-weekly.js", "MG_SIGNALS_DATA")
    trial_signals = load_js_data("trial-signals-weekly.js", "MG_TRIAL_SIGNALS_DATA")
    china = load_js_data("china-intelligence.js", "MG_CHINA_DATA")

    stats = dashboard.get("stats") or {}
    signal_items = signals.get("signals") or []
    trial_items = trial_signals.get("signals") or []
    trial_windows = trial_signals.get("source_windows") or {}
    top_signals = (dashboard.get("top_signals") or signal_items)[:3]
    china_articles = (china.get("pubmed_articles") or [])[:3]
    hotspots = (signals.get("topic_hotspots") or [])[:5]

    lines = [
        "# MA-MG-HUB 周更",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"文献窗口：{signals.get('window_start') or '-'} → {signals.get('window_end') or '-'}（口径 {signals.get('window_basis') or '未声明'}）",
        "",
        "## 本周文献信号（新发现 → KOL → 会前动作）",
        "",
    ]
    if top_signals:
        for idx, signal in enumerate(top_signals, 1):
            lines.extend(signal_entry(signal, idx))
    else:
        lines.append("- 本周无文献信号")

    lines.extend(["", "## 临床试验信号", ""])
    if trial_items:
        lines.extend(trial_signal_line(signal, idx) for idx, signal in enumerate(trial_items, 1))
        lines.append("")
        lines.append("强度口径（仅试验组内比较）：强=新增关键试验或关键试验高实质更新；中=关键试验中等更新等；弱=影响有限的早期/一般更新。")
    else:
        lines.append("- 本轮无合格试验信号（允许空组，不补造弱信号）。")
    lines.append("注册/开发信号，不代表疗效证据；完成或上传结果也不等于达到主要终点。")

    lines.extend(["", "三源比较窗口："])
    for source in ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials"):
        lines.append(trial_window_line(source, trial_windows.get(source) or {}))

    lines.extend(["", "## 中国情报 Top 3", ""])
    if china_articles:
        lines.extend(article_line(article, idx) for idx, article in enumerate(china_articles, 1))
    else:
        lines.append("- 暂无")

    lines.extend(["", "## 热点主题", ""])
    if hotspots:
        lines.append(" · ".join(f"{item.get('topic')} {item.get('count')}" for item in hotspots))
    else:
        lines.append("- 暂无")

    lines.extend([
        "", "## 数据库存（状态呈现，非待办）", "",
        f"- 文献：近1年 {stats.get('recent_articles', 0)} · 中国相关 {stats.get('china_articles', 0)}",
        f"- 信号：文献 {len(signal_items)} · 试验 {len(trial_items)}",
        f"- 专家画像：{stats.get('experts', 0)}",
        f"- 内容模块 {stats.get('modules', 0)} · 证据矩阵 {stats.get('landscape_questions', 0)}（均为自动生成草稿，对外使用前核对原文即可，无需逐项处理）",
        "", "## 入口", "", SITE_URL, "",
    ])
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
