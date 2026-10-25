"""三个注册源统一周更：节奏标签与时间窗必须反映真实管线。

历史缺陷：
- ChiCTR 标 28_days、ChinaDrugTrials 标 monthly_manual，但两者都在周一任务内刷新；
- 基线来自 git HEAD，当前值来自工作区，两者相等或倒挂时会渲染出「14:53 — 14:53」这种无意义区间。
"""
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
ENRICH = PROJECT / "scripts" / "enrich-clinical-trial-signals.py"
PIPELINE = PROJECT / "scripts" / "run-weekly-pipeline.py"
RUNBOOK = PROJECT / "report" / "runbooks" / "clinicalTrialsMaintenance.md"

SOURCES = ("ClinicalTrials.gov", "ChiCTR", "ChinaDrugTrials")


def loadSignals():
    text = (DATA / "trial-signals-weekly.js").read_text(encoding="utf-8")
    return json.loads(text[text.index("{"):].rstrip().rstrip(";"))


def test_all_three_registries_are_labelled_weekly():
    windows = loadSignals()["source_windows"]
    assert set(windows) == set(SOURCES)
    for source in SOURCES:
        assert windows[source]["cadence"] == "weekly", f"{source} 节奏标签仍是 {windows[source]['cadence']}"


def test_generator_no_longer_emits_low_frequency_cadences():
    source = ENRICH.read_text(encoding="utf-8")
    assert '"28_days"' not in source
    assert '"monthly_manual"' not in source
    assert source.count('"cadence": "weekly"') == 3, "三个来源都应声明 weekly"


def test_window_start_is_blank_when_baseline_is_not_earlier():
    windows = loadSignals()["source_windows"]
    for source in SOURCES:
        start = str(windows[source].get("window_start") or "")
        end = str(windows[source].get("window_end") or "")
        if start and end:
            assert start < end, f"{source} 时间窗倒挂或相等: {start} .. {end}"


def test_generator_guards_the_window_order():
    source = ENRICH.read_text(encoding="utf-8")
    assert "ordered_window_start" in source
    # 起止相等或基线更晚时返回空串，交给界面按单点快照呈现
    assert "return baseline if baseline_epoch < current_epoch else \"\"" in source


def test_pipeline_refreshes_all_three_sources_in_one_weekly_run():
    source = PIPELINE.read_text(encoding="utf-8")
    for step in ("refresh-chictr-cache", "refresh-china-drug-trials-cache"):
        assert step in source, f"周更管线缺少 {step}"
    assert '"--interval-days", "7"' in source
    # 注释不得再把 ChiCTR 描述成低频节奏
    assert "28 天节奏" not in source


def test_frontend_maps_every_cadence_to_weekly():
    js = (PROJECT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    matched = re.search(r"var cadence = \(\{[^}]*\}\)", js)
    assert matched, "未找到节奏文案映射"
    mapping = matched.group(0)
    assert "'28_days': '每周'" in mapping
    assert "monthly_manual: '每周'" in mapping
    assert "按来源节奏" not in js.split("function trialWindowLabel")[1][:600]


def test_runbook_states_weekly_for_every_registry():
    runbook = RUNBOOK.read_text(encoding="utf-8")
    section = runbook[runbook.index("## 更新节奏"):runbook.index("## 周更调度")]
    for source in SOURCES:
        row = next(line for line in section.splitlines() if line.startswith(f"| {source} "))
        assert "每周" in row, f"runbook 的 {source} 行仍不是每周"
    assert "每 28 天" not in section