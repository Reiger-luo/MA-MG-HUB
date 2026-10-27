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


def test_landscape_chapters_and_questions_replace_living_answers():
    html = (PROJECT / "pages" / "landscape.html").read_text(encoding="utf-8")
    assert 'data-landscape-tab="chapters"' in html
    assert 'data-landscape-tab="questions"' in html
    assert 'data-landscape-tab="answers"' not in html
    assert "treatmentChapters.js" in html
    assert "clinicalQuestions.js" in html


def _load_js_global(path: Path, name: str):
    text = path.read_text(encoding="utf-8")
    prefix = f"window.{name} = "
    assert prefix in text, path
    payload = text[text.index(prefix) + len(prefix):].strip().rstrip(";")
    import json

    return json.loads(payload)


def test_chapter_and_question_references_are_resolvable():
    chapters_data = _load_js_global(PROJECT / "data" / "treatmentChapters.js", "MG_TREATMENT_CHAPTERS")
    questions_data = _load_js_global(PROJECT / "data" / "clinicalQuestions.js", "MG_CLINICAL_QUESTIONS")

    def check_item(item, statements_key):
        ref_map = item["ref_map"]
        refs = item["refs"]
        assert refs, item.get("id")
        numbers = {ref["n"] for ref in refs}
        assert set(ref_map.values()) == numbers
        for statement in item[statements_key]:
            assert statement["text"].strip()
            for ref in statement.get("refs", []):
                key = ref.get("pmid") or ref.get("key")
                assert key in ref_map, (item.get("id"), key)
        for branch in item.get("branches", []):
            for side in branch["sides"]:
                for ref in side.get("refs", []):
                    key = ref.get("pmid") or ref.get("key")
                    assert key in ref_map, (item.get("id"), key)
        for ref in refs:
            if ref["kind"] == "article":
                assert ref.get("pmid") and ref.get("url")
            else:
                assert ref.get("text")

    for chapter in chapters_data["chapters"]:
        check_item(chapter, "statements")
    for group in questions_data["groups"]:
        for question in group["questions"]:
            check_item(question, "answer")


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
