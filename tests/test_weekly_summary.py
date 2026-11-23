"""周报必须分别消费文献与临床试验信号，不跨来源混排；文献信号合并呈现 新发现→KOL→会前动作。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "scripts" / "generate-weekly-summary.py"


def load_module():
    scripts = str(PROJECT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("generate_weekly_summary", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_payloads(trial_items):
    return {
        "dashboard-data.js": {"stats": {"recent_articles": 1, "china_articles": 0, "experts": 0, "modules": 0, "landscape_questions": 0}},
        "signals-weekly.js": {
            "window_start": "2026-08-03", "window_end": "2026-08-10",
            "window_basis": "trueIngestAddedPmids",
            "signals": [{
                "strength": "强", "summary": "一条文献信号", "related_pmids": ["1"],
                "kol_leads": [{"name": "张三", "roles": ["第一作者"], "institution": "某医院"}],
                "medical_affairs": {"msl_action": "会前核查主要终点定义。"},
            }],
        },
        "trial-signals-weekly.js": {
            "signals": trial_items,
            "source_windows": {
                "ClinicalTrials.gov": {"raw_change_count": 3, "window_start": "2026-08-03", "window_end": "2026-08-10", "updated_at": "2026-08-10"},
                "ChiCTR": {"raw_change_count": 0, "updated_at": "2026-07-27"},
                "ChinaDrugTrials": {"raw_change_count": 0, "updated_at": "2026-07-27"},
            },
        },
        "china-intelligence.js": {"pubmed_articles": []},
    }


def test_weekly_summary_has_independent_literature_and_trial_sections(monkeypatch):
    module = load_module()
    payloads = fixture_payloads([{
        "strength": "强", "title": "关键Ⅲ期试验进入招募", "registryIds": ["NCT00000001"],
        "phase": "Phase 3", "changeSummary": "尚未招募 → 招募中",
        "takeaway": "关键开发节点已更新", "evidenceBoundary": "不代表疗效证据。",
    }])
    monkeypatch.setattr(module, "load_js_data", lambda filename, _global_name: payloads[filename])

    summary = module.build_summary()

    assert "## 本周文献信号（新发现 → KOL → 会前动作）" in summary
    assert "## 临床试验信号" in summary
    assert "文献 1 · 试验 1" in summary
    assert "NCT00000001" in summary
    assert "注册/开发信号，不代表疗效证据" in summary
    assert "ClinicalTrials.gov：原始变化 3" in summary


def test_literature_signal_merges_finding_kol_and_action(monkeypatch):
    module = load_module()
    payloads = fixture_payloads([])
    monkeypatch.setattr(module, "load_js_data", lambda filename, _global_name: payloads[filename])

    summary = module.build_summary()

    assert "**[强] 一条文献信号**（PMID 1）" in summary
    assert "KOL：张三（第一作者；某医院）" in summary
    assert "会前：会前核查主要终点定义。" in summary
    # 不再存在拆分的两个 Top 3 区块
    assert "Signal-to-KOL Top 3" not in summary
    assert "优先文献信号 Top 3" not in summary


def test_weekly_summary_publishes_legitimate_empty_trial_group(monkeypatch):
    module = load_module()
    payloads = fixture_payloads([])
    monkeypatch.setattr(module, "load_js_data", lambda filename, _global_name: payloads[filename])

    summary = module.build_summary()

    assert "文献 1 · 试验 0" in summary
    assert "本轮无合格试验信号（允许空组，不补造弱信号）" in summary


def test_inventory_section_is_status_not_todo(monkeypatch):
    module = load_module()
    payloads = fixture_payloads([])
    monkeypatch.setattr(module, "load_js_data", lambda filename, _global_name: payloads[filename])

    summary = module.build_summary()

    assert "## 数据库存（状态呈现，非待办）" in summary
    assert "## 待处理" not in summary
