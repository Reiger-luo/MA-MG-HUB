import re
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def css_rule_bodies(css: str, selector: str):
    pattern = re.compile(re.escape(selector) + r"\s*\{([^}]*)\}", re.S)
    return pattern.findall(css)


def test_msl_expert_detail_uses_page_flow_without_changing_list_scroll_contract():
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    detail_rules = css_rule_bodies(css, ".msl-profile-grid .workspace-detail")
    assert any("height: auto" in body for body in detail_rules)
    assert any("overflow-y: visible" in body for body in detail_rules)
    assert any("align-self: start" in body for body in detail_rules)

    shared_rule = re.search(
        r"\.msl-profile-grid \.sidebar-filters,\s*"
        r"\.msl-profile-grid \.workspace-list,\s*"
        r"\.msl-profile-grid \.workspace-detail\s*\{([^}]*)\}",
        css,
        re.S,
    )
    assert shared_rule is not None
    assert "height: clamp(" in shared_rule.group(1)
    assert "overflow-y: auto" in shared_rule.group(1)


def test_msl_expert_profiles_require_a_search_keyword_before_rendering_results():
    js = (PROJECT / "assets" / "msl.js").read_text(encoding="utf-8")

    assert "function hasProfileSearchQuery(keyword)" in js
    assert "if (!hasProfileSearchQuery(keyword)) return [];" in js
    assert "请输入关键词搜索专家" in js
    assert "请输入关键词后显示匹配结果" in js
    assert "在左侧搜索框输入关键词后查看专家画像。" in js


def test_living_answers_remove_nested_height_caps_only_inside_answer_layout():
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    panel_rules = css_rule_bodies(
        css, ".landscape-answer-layout .landscape-topic-panel"
    )
    assert any("position: static" in body for body in panel_rules)

    for selector in (
        ".landscape-answer-layout .landscape-topic-list",
        ".landscape-answer-layout .landscape-topic-detail",
        ".landscape-answer-layout .landscape-topic-detail .kg-study-list",
    ):
        bodies = css_rule_bodies(css, selector)
        assert any("max-height: none" in body for body in bodies), selector
        assert any("overflow-y: visible" in body for body in bodies), selector

    # 全局知识库组件仍保留原有滚动行为。
    assert re.search(
        r"\.curated-topic-list\s*\{[^}]*max-height:\s*680px;[^}]*overflow-y:\s*auto",
        css,
        re.S,
    )
    assert re.search(
        r"\.kg-study-list\s*\{[^}]*max-height:\s*200px;[^}]*overflow-y:\s*auto",
        css,
        re.S,
    )


def test_conference_rank_rows_are_native_buttons_with_active_state_and_bar_layout():
    js = (PROJECT / "assets" / "conference.js").read_text(encoding="utf-8")
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    assert "function renderRank(target, items, limit, dimension)" in js
    assert "<button type=\"button\" class=\"conference-rank-row" in js
    assert "data-conference-rank-dimension" in js
    assert "data-conference-rank-value" in js
    assert "aria-pressed=\"' + (active ? 'true' : 'false')" in js
    assert "<div class=\"conference-rank-row\">" not in js
    assert "conference-rank-track" in js

    assert "renderRank(el.countryRank, summary.countries, 8, 'country')" in js
    assert "renderRank(el.typeRank, summary.types, 8, 'researchType')" in js

    rank_rules = css_rule_bodies(css, ".conference-rank-row")
    assert any("width: 100%" in body for body in rank_rules)
    assert any("border: 0" in body for body in rank_rules)
    assert any("background: transparent" in body for body in rank_rules)
    assert any("font: inherit" in body for body in rank_rules)
    assert any("cursor: pointer" in body for body in rank_rules)
    assert ".conference-rank-row.active" in css


def test_conference_rank_click_toggles_dimension_filters_and_scrolls_to_results():
    js = (PROJECT / "assets" / "conference.js").read_text(encoding="utf-8")

    assert "state[dimension] = state[dimension] === value ? 'all' : value" in js
    assert "state.page = 0" in js
    assert "applyFilters()" in js
    assert "scrollToResults()" in js
    assert "renderRank(target, items, limit, dimension)" in js


def test_conference_filter_summary_clear_and_module_switch_cover_rank_dimensions():
    js = (PROJECT / "assets" / "conference.js").read_text(encoding="utf-8")

    assert "filters.push('国家/地区：' + state.country)" in js
    assert "filters.push('研究类型：' + state.researchType)" in js

    clear_handler = re.search(
        r"data-conference-clear-filter[^\n]*[\s\S]*?addEventListener\('click', function\(\) \{"
        r"([\s\S]*?)\n\s*\}\);",
        js,
    )
    assert clear_handler is not None
    for reset in (
        "state.country = 'all'",
        "state.researchType = 'all'",
        "state.topic = null",
        "state.keyword = ''",
        "state.page = 0",
    ):
        assert reset in clear_handler.group(1)

    module_handler = re.search(
        r"data-conference-module[\s\S]*?addEventListener\('click', function\(\) \{"
        r"([\s\S]*?)\n\s*\}\);",
        js,
    )
    assert module_handler is not None
    for reset in (
        "state.country = 'all'",
        "state.researchType = 'all'",
        "state.topic = null",
        "state.keyword = ''",
        "state.page = 0",
    ):
        assert reset in module_handler.group(1)
