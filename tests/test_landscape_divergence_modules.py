"""诊治格局两块中外差异必须保持独立模块与不同更新轨道。

历史问题：文献主题差异（周更滚动）与指南差异（新指南后更新）被塞进同一个
「中外证据与诊治差异」容器，导致周更只动一半内容时整块看起来"没有更新"，
也让读者误以为指南结论每周都在变。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_landscape_page_has_two_independent_divergence_panels():
    html = (ROOT / "pages" / "landscape.html").read_text(encoding="utf-8")

    assert html.count('class="workspace-panel landscape-divergence-panel') == 2
    assert "rolling-panel" in html and "stable-panel" in html
    # 不能再有把两块合在一起的容器标题
    assert "中外证据与诊治差异" not in html
    assert 'id="themeDivergenceMeta"' in html
    assert 'id="guidelineDivergenceMeta"' in html


def test_each_panel_declares_its_own_update_mode():
    html = (ROOT / "pages" / "landscape.html").read_text(encoding="utf-8")

    assert re.search(r'update-mode-chip rolling[^>]*>\s*周更滚动', html)
    assert re.search(r'update-mode-chip event[^>]*>\s*新指南入库后更新', html)


def test_landscape_js_renders_panels_separately():
    js = (ROOT / "assets" / "landscape.js").read_text(encoding="utf-8")

    assert "function renderThemeDivergence()" in js
    assert "function renderGuidelineDivergence()" in js
    # 旧的合并渲染入口必须消失，否则两块状态会重新耦合
    assert "renderChinaLandscape" not in js
    assert "chinaLandscapePrinciple" not in js
    init_block = js[js.index("function init() {"):]
    assert init_block.index("renderThemeDivergence()") < init_block.index("renderGuidelineDivergence()")


def test_rolling_panel_exposes_staleness_warning():
    js = (ROOT / "assets" / "landscape.js").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "main.css").read_text(encoding="utf-8")

    assert "function themeStaleness(" in js
    assert "窗口已 " in js
    assert ".update-badge.is-stale" in css
    # 指南模块不参与过期判断
    guide = js[js.index("function renderGuidelineDivergence() {"):js.index("function stanceClass(")]
    assert "themeStaleness" not in guide


def test_weekly_pipeline_rolls_theme_analysis_before_frontend_build():
    pipeline = (ROOT / "scripts" / "run-weekly-pipeline.py").read_text(encoding="utf-8")

    assert '"analyze-china-foreign-themes"' in pipeline
    assert '"--skip-if-current"' in pipeline
    # 必须先于 build-frontend，否则前端读到上一周窗口
    assert pipeline.index('"analyze-china-foreign-themes"') < pipeline.index('"build-frontend"')
    # 受 --skip-llm 保护
    guard = pipeline[:pipeline.index('"analyze-china-foreign-themes"')]
    assert "if not args.skip_llm:" in guard.rsplit("\n    steps.append", 1)[-1]
    # 指南差异属事件驱动，不得进入周更
    assert "analyze-guideline-divergence" not in pipeline


def test_theme_analysis_supports_idempotent_weekly_run():
    script = (ROOT / "scripts" / "analyze-china-foreign-themes.py").read_text(encoding="utf-8")

    assert "--skip-if-current" in script
    assert "窗口与语料未变化" in script
