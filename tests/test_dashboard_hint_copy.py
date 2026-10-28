"""首页数据面板的说明提示必须与站点当前口径一致。

三类历史漂移，用测试卡住：
1. 指向已下线页面（数据状态）的空态文案；
2. 把内部管线口径（公开滚动 / 语义底座 / full）直接摆给读者；
3. 两块中外差异更新节奏不同，卡片却不标节奏。
"""
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DASHBOARD_JS = PROJECT / "assets" / "dashboard.js"
DASHBOARD_DATA = PROJECT / "data" / "dashboard-data.js"
BUILDER = PROJECT / "scripts" / "build-frontend-data.py"


def loadDashboard():
    text = DASHBOARD_DATA.read_text(encoding="utf-8")
    return json.loads(text[text.index("{"):].rstrip().rstrip(";"))


def test_dashboard_never_points_at_the_removed_data_status_page():
    js = DASHBOARD_JS.read_text(encoding="utf-8")
    assert "data-ops" not in js
    assert "请前往数据状态检查最新构建" not in js
    assert not (PROJECT / "pages" / "data-ops.html").exists()


def test_dashboard_uses_reader_facing_wording_instead_of_pipeline_jargon():
    js = DASHBOARD_JS.read_text(encoding="utf-8")
    assert "语义底座" not in js
    assert "公开滚动" not in js
    assert "近一年文献" in js and "全库文献" in js
    # 数据截止时间与完整发布时间是两件事，页头徽标不得重复发布条
    assert "数据截至" in js


def test_trial_source_window_collapses_degenerate_ranges():
    js = DASHBOARD_JS.read_text(encoding="utf-8")
    assert "startTs < endTs" in js
    # 起止相同或倒挂时不渲染区间，只留更新时间，避免出现"14:53 — 14:53"
    assert "hasRange" in js
    assert "本轮快照" not in js
    assert "本轮比较" not in js


def test_dashboard_artifact_marks_the_two_divergence_cadences():
    data = loadDashboard()
    landscape = [c for c in data["sections"] if c["id"] == "landscape"][0]
    facts = " ".join(landscape["facts"])
    assert "新指南入库后" in facts
    assert "周更滚动" in facts
    assert "近一年主题差异" in facts


def test_dashboard_artifact_speaks_plain_number_units():
    data = loadDashboard()
    recent = [c for c in data["stat_cards"] if c["label"] == "近一年文献"][0]
    assert recent["note"].startswith("全库 ")
    pipeline = [w for w in data["workflows"] if w["label"] == "周更管线"][0]
    assert "主题差异" in pipeline["note"], "周更管线说明未包含新增的中外主题差异分析步骤"


def test_builder_keeps_the_same_wording_so_weekly_rebuild_does_not_revert_it():
    source = BUILDER.read_text(encoding="utf-8")
    assert "条（新指南入库后）" in source
    assert "条（周更滚动）" in source
    assert "近一年中外主题差异分析" in source
    assert 'f"全库 {total_count} 篇"' in source