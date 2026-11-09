"""Contract tests for 情报中心「领域重大事件」标签。

领域重大事件时间线从诊治格局迁移至情报中心，位于「临床试验」标签右侧；
数据源唯一为 source-signals.js（惰性加载），聚合四类事件并按时间降序：
获批/监管 · 指南/共识 · 近12个月新启动III期 · 周更强/中试验信号。
"""
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def test_literature_html_has_events_tab_after_trials():
    """领域重大事件标签必须位于临床试验右侧，且与前一组标签有分隔符。"""
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    tab_order = re.findall(r'data-tab="(\w+)"', html)
    assert tab_order.index("events") == tab_order.index("trials") + 1, (
        f"events tab must sit right after trials: {tab_order}"
    )
    # 临床试验与领域重大事件之间保留视觉分隔栏
    trials_pos = html.index('data-tab="trials"')
    events_pos = html.index('data-tab="events"')
    between = html[trials_pos:events_pos]
    assert 'intel-tab-separator' in between, (
        "trials 与 events 之间必须有 intel-tab-separator 分隔栏"
    )


def test_literature_html_events_panel_structure():
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    panel_match = re.search(
        r'id="tab-events".*?(?=<section class="intel-tab-panel"|</main>)',
        html, re.S,
    )
    assert panel_match, "tab-events panel not found"
    panel = panel_match.group(0)
    assert 'id="majorEventsList"' in panel, "事件列表容器缺失"
    assert 'id="majorEventsMeta"' in panel, "事件条数徽标缺失"
    assert 'id="eventsBadge"' in panel, "事件页眉徽标缺失"
    assert "领域重大事件" in panel, "面板标题缺失"


def test_literature_html_does_not_statically_load_source_signals():
    """source-signals.js 只能由 literature.js 首次进入标签时惰性加载。"""
    html = (PROJECT / "pages" / "literature.html").read_text(encoding="utf-8")
    assert re.search(r'<script src="[^"]*source-signals\.js', html) is None, (
        "source-signals.js 不得静态引入 literature.html（必须惰性加载保护首屏）"
    )


def test_landscape_no_longer_hosts_major_events():
    """诊治格局不再承载领域重大事件面板与渲染代码。"""
    html = (PROJECT / "pages" / "landscape.html").read_text(encoding="utf-8")
    assert "领域重大事件" not in html
    assert "majorEventsList" not in html
    assert "majorEventsMeta" not in html
    # 数据消费方已迁移，landscape 不再静态加载 source-signals.js
    assert re.search(r'<script src="[^"]*source-signals\.js', html) is None

    js = (PROJECT / "assets" / "landscape.js").read_text(encoding="utf-8")
    assert "renderMajorEvents" not in js
    assert "collectMajorEvents" not in js


def test_literature_js_aggregates_four_event_sources():
    """literature.js 必须聚合四类事件，且周更强/中信号只取强与中。"""
    js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    assert "collectMajorEvents" in js
    assert "renderMajorEvents" in js
    assert "loadMajorEventsModule" in js
    # 惰性加载入口与数据源
    assert "MG_SOURCE_SIGNALS" in js
    assert "data/source-signals.js" in js
    # 四类事件源：获批监管 / 指南共识 / III期 / 周更强中试验信号
    assert "chinaRegulatory" in js
    assert "guidelineConsensus" in js
    assert "weekly_signals" in js
    assert "trialRegistry" in js
    # 只收强/中试验信号
    strength_block = js[js.index("weekly_signals"):]
    assert "强" in strength_block and "中" in strength_block


def test_major_events_css_tokens_present():
    """时间线样式与强/中信号徽标样式存在。"""
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")
    assert ".major-events-list" in css
    assert ".major-event-item" in css
    assert ".major-event-strength-strong" in css
    assert ".major-event-strength-medium" in css
