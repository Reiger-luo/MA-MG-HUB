"""知识库编辑层契约：逐概念策展内容、锚点与每周校对接口。

编辑层是公开产物 data/knowledgeEditorial.js（window.MG_KNOWLEDGE_EDITORIAL），
内容只重述站内已有证据与策展观点，思考项是问题而非结论；所有锚点指向站内确切位置。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common.io import load_js_global  # noqa: E402
from common.publicDataContract import publicDataGlobals  # noqa: E402

DATA = ROOT / "data"
EDITORIAL = DATA / "knowledgeEditorial.js"


def editorial():
    return load_js_global(EDITORIAL, "MG_KNOWLEDGE_EDITORIAL")


def graph_nodes():
    graph = load_js_global(DATA / "knowledge-graph.js", "MG_KNOWLEDGE_GRAPH")
    return {node["id"] for node in graph["nodes"]}


def test_editorial_is_strict_json_public_artifact():
    """发布校验器用 json.loads 解析 window.* 产物，编辑层必须同规格。"""
    payload = editorial()
    assert payload["version"]
    assert "不代表因果" in payload["boundary"]
    assert publicDataGlobals["knowledgeEditorial.js"] == "MG_KNOWLEDGE_EDITORIAL"


def test_every_concept_has_editorial_lead_and_thought():
    payload = editorial()
    nodes = graph_nodes()
    concepts = payload["concepts"]
    assert set(concepts) == nodes, "策展层必须覆盖全部图谱概念"
    for node_id, item in concepts.items():
        for field in ("lead", "point", "caution", "thought", "link"):
            assert item.get(field), f"{node_id} 缺少 {field}"
        assert ("?" in item["thought"] or "？" in item["thought"]), f"{node_id} 的思考项应是问题而非结论"


def test_editorial_links_point_to_real_destinations():
    payload = editorial()
    questions = load_js_global(DATA / "clinicalQuestions.js", "MG_CLINICAL_QUESTIONS")
    question_ids = {q["id"] for group in questions["groups"] for q in group["questions"]}
    chapter_ids = {c["id"] for c in load_js_global(DATA / "treatmentChapters.js", "MG_TREATMENT_CHAPTERS")["chapters"]}
    landscape = load_js_global(DATA / "landscape-data.js", "MG_LANDSCAPE_DATA")
    divergence_ids = {d["id"] for d in landscape["china_landscape"]["guideline_divergence"]["divergences"]}
    topics = load_js_global(DATA / "curated-topics.js", "MG_CURATED_TOPICS")
    topic_ids = {t["id"] for t in topics["topics"]}
    signals = load_js_global(DATA / "signals-weekly.js", "MG_SIGNALS_DATA")
    signal_ids = {s["id"] for s in signals["signals"]}
    pools = {
        "question": question_ids,
        "chapter": chapter_ids,
        "divergence": divergence_ids,
        "topic": topic_ids,
        "signal": signal_ids,
    }
    for node_id, item in payload["concepts"].items():
        kind, _, value = str(item["link"]).partition(":")
        assert kind in pools and value in pools[kind], f"{node_id} 的锚点无效：{item['link']}"


def test_editorial_relations_are_real_pairs_and_avoid_fabricated_pmids():
    payload = editorial()
    nodes = graph_nodes()
    relations = payload["relations"]
    assert len(relations) >= 200, "逐对审阅后应覆盖所有实际显示的关系"
    for key, item in relations.items():
        ids = key.split("::")
        assert len(ids) == 2 and set(ids) <= nodes, f"关系键不是有效概念对：{key}"
        for field in ("read", "evidenceFocus"):
            assert item.get(field), f"{key} 缺少 {field}"
    text = EDITORIAL.read_text(encoding="utf-8")
    assert not re.search(r"PMID\s*\d{6,}", text), "编辑层不得自造 PMID 引用"


def test_landscape_supports_precise_chapter_and_divergence_deep_links():
    source = (ROOT / "assets" / "landscape.js").read_text(encoding="utf-8")
    for token in (
        "function focusChapterCard", "function focusDivergenceCard",
        "getQueryParam('chapter')", "getQueryParam('divergence')",
        'data-chapter-id="', 'data-divergence-id="',
    ):
        assert token in source, f"诊治格局缺少深链实现：{token}"
    css = (ROOT / "assets" / "main.css").read_text(encoding="utf-8")
    assert ".guideline-divergence-card.is-focused" in css
    assert ".chapter-body.is-focused" in css


def test_weekly_llm_review_writes_editorial_directly():
    """用户 2026-11-25 指示：每周 LLM 草稿全自动写入，无人工批准闸门。"""
    script = ROOT / "scripts" / "enrich-knowledge-editorial.py"
    assert script.exists(), "缺少每周 LLM 校对脚本"
    source = script.read_text(encoding="utf-8")
    assert "from llm_client import complete" in source
    assert ".hermes-audit" in source
    assert "atomic_write_js_global" in source, "LLM 校验通过后应自动写公开产物"
    assert "valid_draft" in source, "自动写入前必须严格校验草稿"
    assert not (ROOT / "scripts" / "apply-knowledge-editorial.py").exists(), "人工批准脚本应已移除"
    pipeline = (ROOT / "scripts" / "run-weekly-pipeline.py").read_text(encoding="utf-8")
    assert "review-knowledge-editorial" in pipeline
    assert "args.skip_llm" in pipeline, "LLM 步骤应受 --skip-llm 控制"


def test_topic_whitelist_replaces_bridge_dump():
    payload = editorial()
    whitelist = payload.get("topics", {})
    topics = load_js_global(DATA / "curated-topics.js", "MG_CURATED_TOPICS")
    topic_ids = {t["id"] for t in topics["topics"]}
    graph = load_js_global(DATA / "knowledge-graph.js", "MG_KNOWLEDGE_GRAPH")
    node_ids = {n["id"] for n in graph["nodes"]}
    assert set(whitelist) <= node_ids
    for node_id, ids in whitelist.items():
        assert set(ids) <= topic_ids, f"{node_id} 的专题白名单含无效 id"
    # 用户点名的错误指派已清除
    assert whitelist.get("rozanolixizumab") == []
    assert whitelist.get("nipocalimab") == []
    bridge = topics.get("bridge_by_node", {})
    assert sum(len(v) for v in bridge.values()) > sum(len(v) for v in whitelist.values()) * 3, "白名单应远小于 bridge 原样铺开的条数"


def test_literature_signals_have_cross_week_history():
    """文献信号应有与试验信号同构的跨周沉淀层。"""
    signals = load_js_global(DATA / "signals-weekly.js", "MG_SIGNALS_DATA")
    history = signals.get("signal_history") or []
    assert len(history) >= 5
    assert len(history) <= 10
    captured = [str(item.get("capturedAt") or "") for item in history]
    assert captured == sorted(captured, reverse=True), "历史应按收录批次降序"
    assert len(set(item.get("candidateId") for item in history)) == len(history), "历史按日期+题名去重"
    assert all(item.get("title") and item.get("date") for item in history)
    source = (ROOT / "assets" / "knowledge.js").read_text(encoding="utf-8")
    assert "signalsData.signal_history" in source, "知识库未消费文献信号历史"
    assert "收录批次" in source, "历史信号应显示收录批次"


def test_ravulizumab_name_follows_canonical_drug_dictionary():
    """用户拍板：药名以校订过的临床试验药物词典为准。"""
    from common.drug_tags import public_drug_catalog

    catalog = {drug["id"]: drug for drug in public_drug_catalog()}
    assert catalog["ravulizumab"]["name_zh"] == "瑞利珠单抗"
    network = load_js_global(DATA / "china-author-network.js", "MG_CHINA_AUTHOR_NETWORK")
    catalog_entry = next(d for d in network["drug_catalog"] if d["id"] == "ravulizumab")
    assert catalog_entry["name_zh"] == "瑞利珠单抗"
    assert "拉夫利珠单抗" not in (DATA / "china-author-network.js").read_text(encoding="utf-8")


def test_topic_whitelist_is_quality_gated():
    """收缩标准：中文摘要 + 有 PMID + 非低置信。"""
    import re
    payload = editorial()
    topics = {t["id"]: t for t in load_js_global(DATA / "curated-topics.js", "MG_CURATED_TOPICS")["topics"]}
    for node_id, ids in payload["topics"].items():
        for topic_id in ids:
            topic = topics[topic_id]
            assert len(re.findall(r"[\u4e00-\u9fff]", topic.get("summary") or "")) >= 20, (node_id, topic_id)
            assert topic.get("evidence_pmids"), (node_id, topic_id)
            assert topic.get("confidence") not in ("low", "unknown"), (node_id, topic_id)
    assert payload["topics"]["rozanolixizumab"] == []
    assert len(payload["topics"]["efgartigimod"]) == 4


def test_relation_insight_groups_cover_all_pairs():
    payload = editorial()
    groups = payload["insightGroupRules"]
    assert set(groups) == {"赛道绑定结构", "反常绑定", "证据缺口与行动"}
    for key, item in payload["relations"].items():
        assert item.get("insightGroup") in groups, key
    source = (ROOT / "assets" / "knowledge.js").read_text(encoding="utf-8")
    assert "INSIGHT_ORDER" in source and "kg-insight-banner" in source
    assert "relationSignalSummary" in source, "连接列表应展示近期信号落点"


def test_wiki_curated_topics_sync_is_wired():
    pipeline = (ROOT / "scripts" / "run-weekly-pipeline.py").read_text(encoding="utf-8")
    assert "sync-wiki-curated-topics" in pipeline
    assert "build-curated-topic-data.py" in pipeline
    source = (ROOT / "scripts" / "enrich-knowledge-editorial.py").read_text(encoding="utf-8")
    assert "wiki 新专题纳入白名单" in source
    manual = (ROOT / "report" / "current" / "operationsManual.md").read_text(encoding="utf-8")
    assert "sync-wiki-curated-topics" in manual


def test_relation_insight_groups_cover_all_pairs():
    payload = editorial()
    groups = payload["insightGroupRules"]
    assert set(groups) == {"赛道绑定结构", "反常绑定", "证据缺口与行动"}
    for key, item in payload["relations"].items():
        assert item.get("insightGroup") in groups, key
    source = (ROOT / "assets" / "knowledge.js").read_text(encoding="utf-8")
    assert "INSIGHT_ORDER" in source and "kg-insight-banner" in source
    assert "relationSignalSummary" in source, "连接列表应展示近期信号落点"


def test_wiki_curated_topics_sync_is_wired():
    pipeline = (ROOT / "scripts" / "run-weekly-pipeline.py").read_text(encoding="utf-8")
    assert "sync-wiki-curated-topics" in pipeline
    assert "build-curated-topic-data.py" in pipeline
    source = (ROOT / "scripts" / "enrich-knowledge-editorial.py").read_text(encoding="utf-8")
    assert "wiki 新专题纳入白名单" in source
    manual = (ROOT / "report" / "current" / "operationsManual.md").read_text(encoding="utf-8")
    assert "sync-wiki-curated-topics" in manual
