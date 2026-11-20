"""Contract tests for 情报中心「领域重大事件」标签。

领域重大事件时间线从诊治格局迁移至情报中心，位于「临床试验」标签右侧；
数据源唯一为 source-signals.js（惰性加载），聚合五类事件并按时间降序：
获批/监管 · 指南/共识 · 重点药物 II/III 期文献 · 近12个月新启动III期 · 周更强/中试验信号。
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


def test_literature_js_aggregates_five_event_sources():
    """literature.js 必须聚合五类事件，且周更强/中信号只取强与中。"""
    js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    assert "collectMajorEvents" in js
    assert "renderMajorEvents" in js
    assert "loadMajorEventsModule" in js
    # 惰性加载入口与数据源
    assert "MG_SOURCE_SIGNALS" in js
    assert "data/source-signals.js" in js
    # 五类事件源：获批监管 / 指南共识 / 重点药物 II-III 期文献 / III期 / 周更强中试验信号
    assert "chinaRegulatory" in js
    assert "guidelineConsensus" in js
    assert "keyDrugTrialPublications" in js
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


def test_major_events_layout_readable_layers():
    """时间线三层信息：扫描层/标题整行/来源带标签；标题与来源分属独立区块。"""
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")
    block = css[css.index(".major-events-list"):css.index("/* 诊疗现状章节与临床问题库 */")]
    # 纵向卡片，不再用双列网格挤压标题。
    assert "flex-direction: column" in block
    assert "grid-template-columns" not in block
    assert ".major-event-body" not in block
    # 扫描层：日期右对齐成列；内容层与溯源层分别有样式，且来源有显式标签。
    assert ".major-event-meta" in block and "margin-left: auto" in block
    assert ".major-event-title" in block and "overflow-wrap: anywhere" in block
    assert ".major-event-source-label" in block and ".major-event-source-text" in block
    # 按类型着色的语义类存在。
    for key in ("regulatory", "guideline", "publication", "trial", "signal"):
        assert ".major-event--" + key in block

    js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    assert 'class="major-event-meta"' in js
    assert 'class="major-event-title"' in js
    assert 'class="major-event-source"' in js
    assert 'major-event-source-label">来源<' in js
    assert 'class="major-event-source-text"' in js
    assert 'class="major-event-body"' not in js
    assert "function eventTypeKey" in js
    # 渲染顺序：meta 之后是 title，title 之后才是有标签的 source。
    render = js[js.index("// 三层结构"):js.index("// 三层结构") + 900]
    assert render.index("major-event-meta") < render.index("major-event-title")
    assert render.index("major-event-title") < render.index("major-event-source-label")


def test_global_regulatory_events_merge_without_mislabeling(tmp_path):
    """境外 FDA/EU 获批并入监管频道，逐条标注审批机构，不污染 NMPA 数据文件。"""
    import json
    from scripts.common.source_channels import build_source_signals

    china = tmp_path / "china-regulatory-status.json"
    china.write_text(json.dumps({"drugs": [{
        "name": "Efgartigimod", "status_label": "已获批", "status_date": "2023-06",
        "source_type": "NMPA / company", "source_url": "https://www.nmpa.gov.cn/",
        "last_verified": "2026-06-25",
    }]}), encoding="utf-8")
    glob = tmp_path / "global-regulatory-status.json"
    glob.write_text(json.dumps({"drugs": [
        {
            "generic_name": "cemdisiran", "name": "Cemdisiran（Livsayis）获 FDA 批准上市",
            "status_label": "FDA 批准", "status_date": "2026-11-18",
            "source_type": "FDA · Regeneron 官方新闻稿（2026-11-18）",
            "source_url": "https://investor.regeneron.com/news-releases/x",
            "region": "美国 FDA", "last_verified": "2026-11-21",
        },
        {
            "generic_name": "gefurulimab", "name": "Gefurulimab（Klygefa）获 FDA 与欧盟批准",
            "status_label": "FDA + EU 批准", "status_date": "2026-11-16",
            "source_type": "FDA / EU 委员会 · AstraZeneca 官方新闻稿（2026-11-16）",
            "source_url": "https://www.astrazeneca.com/media-centre/x",
            "region": "美国 FDA + 欧盟委员会", "last_verified": "2026-11-21",
        },
    ]}), encoding="utf-8")

    payload = build_source_signals(
        literature_signals_path=tmp_path / "missing.js",
        guideline_cache_path=tmp_path / "missing.json",
        regulatory_path=china,
        clinicaltrials_path=tmp_path / "missing.json",
        chictr_path=tmp_path / "missing.json",
        china_drug_trials_path=tmp_path / "missing.json",
        conference_path=tmp_path / "missing.json",
        global_regulatory_path=glob,
    )
    channel = {c["id"]: c for c in payload["channels"]}["chinaRegulatory"]
    items = channel["items"]
    assert len(items) == 3
    assert items[0]["source"] == "NMPA / company"
    assert items[0]["date"] == "2026-06-25"
    cemdisiran = [i for i in items if i["id"] == "cemdisiran"][0]
    gefurulimab = [i for i in items if i["id"] == "gefurulimab"][0]
    assert cemdisiran["date"] == "2026-11-18"
    assert "FDA" in cemdisiran["source"] and "NMPA" not in cemdisiran["source"]
    assert gefurulimab["date"] == "2026-11-16"
    assert "FDA" in gefurulimab["source"] and "EU" in gefurulimab["source"]
    assert "NMPA" not in gefurulimab["source"]
    assert set(channel["sources"]) >= {"NMPA", "FDA", "EU Commission"}
    assert "scope_note" in channel
    assert len(json.loads(china.read_text(encoding="utf-8"))["drugs"]) == 1


def test_global_regulatory_optional_without_file(tmp_path):
    """未传境外监管路径时行为与旧版一致，空降级不报错。"""
    from scripts.common.source_channels import build_source_signals
    payload = build_source_signals(
        literature_signals_path=tmp_path / "missing.js",
        guideline_cache_path=tmp_path / "missing.json",
        regulatory_path=tmp_path / "missing-reg.json",
        clinicaltrials_path=tmp_path / "missing.json",
        chictr_path=tmp_path / "missing.json",
        china_drug_trials_path=tmp_path / "missing.json",
        conference_path=tmp_path / "missing.json",
    )
    channel = {c["id"]: c for c in payload["channels"]}["chinaRegulatory"]
    assert channel["items"] == []
