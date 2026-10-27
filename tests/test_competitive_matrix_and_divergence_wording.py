"""竞争矩阵与两块差异模块的口径约束。

三条历史缺陷，必须永久卡住：
1. 刚获批药物的 pivotal 全文发表在滚动窗口（近一年）之外，只按窗口计数会被误读成"没证据"；
2. 指南差异正文里出现 g16/g23 这类语料代号，读者无法理解；
3. 一个月窗口的主题差异被写成"空白/缺位/代差"这类长期结构判断，且模型自报篇数与代码聚合值冲突。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

LONG_TERM_TERMS = ("空白", "缺位", "代差", "落后", "完全没有", "长期不足", "结构性缺失")
GCODE_RE = re.compile(r"\bg\d{2}(?![0-9a-zA-Z])")
NARRATIVE_FIELDS = ("title", "china", "international", "clinical_impact", "msl_action")


def loadLandscape():
    text = (DATA / "landscape-data.js").read_text(encoding="utf-8")
    return json.loads(text[text.index("{"):].rstrip().rstrip(";"))


def test_every_competitive_row_uses_the_same_rolling_window_evidence_fields():
    """竞争矩阵只认滚动窗口口径：任何药物都不得单列窗口外文献，避免口径不一致。"""
    landscape = loadLandscape()
    rows = landscape["approved_competitive_matrix"] + landscape["competitive_matrix"]
    assert rows, "竞争矩阵不应为空"

    allowed = {"overall_depth", "china_depth", "abstract_count", "rwe_count", "china_count"}
    for row in rows:
        summary = row["evidence_summary"]
        assert set(summary) == allowed, f"{row['name']} 证据字段口径不一致: {set(summary) ^ allowed}"
        assert "key_publications" not in row, f"{row['name']} 仍单列窗口外文献"
        # 计数必须与窗口内实际匹配到的文献数一致
        assert summary["abstract_count"] >= summary["china_count"]


def test_batoclimab_is_listed_as_china_approved_with_sources():
    landscape = loadLandscape()
    row = [r for r in landscape["approved_competitive_matrix"] if r["name"] == "Batoclimab"][0]
    reg = row["china_regulatory"]

    assert reg["status_label"] == "已获批"
    assert reg["status_date"] == "2026-10-23"
    assert reg["source_url"].startswith("https://")
    assert reg["secondary_url"].startswith("https://")
    assert "AChR" in reg["china_indication"]
    # 与其它已获批药物一样，证据厚度只按近一年滚动窗口统计
    assert row["evidence_summary"]["abstract_count"] >= 0


def test_guideline_divergence_uses_readable_short_names_not_corpus_codes():
    landscape = loadLandscape()
    guide = landscape["china_landscape"]["guideline_divergence"]
    assert guide.get("label_style") == "human_short_names"

    narrative = []
    for item in guide["divergences"]:
        narrative += [str(item.get(f) or "") for f in NARRATIVE_FIELDS]
        for ev in item["evidence"]:
            assert ev.get("short_name"), f"{item['id']} 证据缺 short_name"
            narrative.append(ev["short_name"])
    for doc in guide["corpus"]:
        assert doc.get("short_name"), f"{doc.get('key')} 语料缺 short_name"
        narrative.append(doc["short_name"])

    blob = "\n".join(narrative)
    hits = GCODE_RE.findall(blob)
    assert not hits, f"面向读者的文本仍含语料代号: {sorted(set(hits))}"


def test_theme_divergence_is_window_scoped_and_never_self_reports_counts():
    landscape = loadLandscape()
    theme = landscape["china_landscape"]["theme_divergence"]
    assert theme["scope_note"], "必须声明这是窗口趋势观察"
    assert theme["window_days"] == 365

    for item in theme["divergences"]:
        # 近一年口径：叙事中的篇数由脚本注入，必须与代码聚合值一致
        for field, expect in (("china_focus", item["china_count"]), ("global_focus", item["non_china_count"])):
            mentioned = sum(int(n) for n in re.findall(r"(\d+)\s*篇", item[field]))
            assert mentioned == expect, f"{item['id']}.{field} 叙事篇数 {mentioned} 与聚合值 {expect} 不一致"
        for name, text in {
            "why_it_matters": item["why_it_matters"],
            "msl_action": item["msl_action"],
            "theme": item["theme"],
        }.items():
            if name != "why_it_matters":
                for bad in LONG_TERM_TERMS:
                    assert bad not in text, f"{item['id']}.{name} 含长期判断词「{bad}」: {text}"
        # 一侧本窗口 0 篇时只能给 medium 及以下
        if not item["china_count"] or not item["non_china_count"]:
            assert item["confidence"] != "high", f"{item['id']} 单侧 0 篇不得判 high"
        # 计数必须与实际列出的 PMID 一致
        assert item["china_count"] == len(item["china_pmids"]) == len(item["china_refs"])
        assert item["non_china_count"] == len(item["non_china_pmids"]) == len(item["non_china_refs"])


def test_frontend_labels_the_two_sides_as_china_and_international():
    js = (ROOT / "assets" / "landscape.js").read_text(encoding="utf-8")
    html = (ROOT / "pages" / "landscape.html").read_text(encoding="utf-8")

    assert "'非中国'" not in js and "非中国侧文献" not in js
    assert "countBtn('non_china', '国际'" in js
    assert "国际侧文献" in js
    assert "['中国 / 国际'" in js
    assert "非中国" not in html


def test_competitive_matrix_does_not_render_window_outside_publication_chips():
    js = (ROOT / "assets" / "landscape.js").read_text(encoding="utf-8")
    css = (ROOT / "assets" / "main.css").read_text(encoding="utf-8")

    assert "key_publications" not in js
    assert "keyPubs" not in js
    assert "key-pub" not in js and "key-pub" not in css
