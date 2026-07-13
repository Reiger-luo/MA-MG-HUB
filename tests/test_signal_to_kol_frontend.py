from __future__ import annotations

import json
import importlib.util
import re
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def load_js_global(path: Path, global_name: str):
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{re.escape(global_name)}\s*=\s*(.*);\s*$", text, re.S)
    assert match, f"{global_name} not found in {path}"
    return json.loads(match.group(1))


def load_enrichment_module():
    sys.path.insert(0, str(PROJECT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "enrich_literature_narrative",
        PROJECT / "scripts" / "enrich-literature-narrative.py",
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeBuilder:
    @staticmethod
    def evidence_score(level):
        return {"I": 3, "II": 2, "III": 1}.get(level, 0)

    @staticmethod
    def infer_topics(article):
        return article.get("keywords") or ["其他"]

    @staticmethod
    def aggregate_kol_leads(_articles):
        return []

    @staticmethod
    def aggregate_institution_leads(_articles, _kol_leads):
        return []


def sample_article(pmid: str, level: str = "III"):
    return {
        "pmid": pmid,
        "title": f"English MG study {pmid}",
        "abstract": "Results: This English abstract reports an exploratory association.",
        "evidence_level": level,
        "study_types": ["observational"],
        "journal": "Test Journal",
        "entry_date": "2026-07-12",
        "pub_date": "2026-07-11",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "keywords": ["疾病负担"],
    }


def test_signals_data_contains_literature_signal_to_kol_schema():
    payload = load_js_global(PROJECT / "data" / "signals-weekly.js", "MG_SIGNALS_DATA")
    signals = payload.get("signals") or []

    assert signals
    assert payload["source_policy"]["scope"] == "literature_only"
    assert payload["source_policy"]["auto_publish"] is True
    assert payload["source_policy"]["review_required"] is False
    assert payload["source_policy"]["signal_count_unlimited"] is True
    assert all(signal.get("signal_to_kol") for signal in signals)
    assert all("kol_leads" in signal for signal in signals)
    assert all("institution_leads" in signal for signal in signals)
    assert all("medical_affairs" in signal for signal in signals)


def test_signal_to_kol_is_rendered_on_literature_page():
    literature_js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    for token in ["signal_to_kol", "kol_leads", "institution_leads", "medical_affairs"]:
        assert token in literature_js
    assert "renderSignalToKol" in literature_js
    assert "signal-kol-bridge" in css


def test_signal_summary_helper_aggregates_all_normalized_signals_deterministically():
    builder = load_enrichment_module().load_builder_module()
    signals = [
        {"strength": "强", "type": "治疗证据", "title": "主题乙", "keywords": ["FcRn", "疗效"]},
        {"strength": "强", "type": "治疗证据", "title": "主题甲", "keywords": ["疗效", "FcRn"]},
        {"strength": "中", "type": "安全性", "title": "安全观察", "keywords": ["安全性", "疗效"]},
        {"strength": "弱", "type": "安全性", "title": "机制观察", "keywords": ["机制", "安全性", "安全性"]},
    ]

    summary = builder.build_signal_summary(signals)

    assert summary["total_count"] == 4
    assert summary["strength_counts"] == {"strong": 2, "medium": 1, "weak": 1}
    assert summary["leading_types"] == [
        {"label": "治疗证据", "count": 2},
        {"label": "安全性", "count": 2},
    ]
    assert summary["strong_themes"] == ["主题乙", "主题甲"]
    assert summary["top_topics"] == [
        {"label": "疗效", "count": 3},
        {"label": "FcRn", "count": 2},
        {"label": "安全性", "count": 2},
    ]
    assert summary["overview"].startswith("近 14 天共形成 4 条信号")
    assert "治疗证据" in summary["overview"]
    assert "主题乙" in summary["overview"]
    assert "疗效" in summary["overview"]


def test_dashboard_build_and_enrichment_both_refresh_signal_summary():
    builder_source = (PROJECT / "scripts" / "build-frontend-data.py").read_text(encoding="utf-8")
    enrichment_source = (PROJECT / "scripts" / "enrich-literature-narrative.py").read_text(encoding="utf-8")

    assert '"signal_summary": build_signal_summary(signals["signals"])' in builder_source
    assert 'dashboard["signal_summary"] = builder.build_signal_summary(normalized)' in enrichment_source


def test_generated_dashboard_signal_summary_matches_all_final_signals():
    signal_payload = load_js_global(PROJECT / "data" / "signals-weekly.js", "MG_SIGNALS_DATA")
    dashboard = load_js_global(PROJECT / "data" / "dashboard-data.js", "MG_DASHBOARD_DATA")
    signals = signal_payload.get("signals") or []
    summary = dashboard["signal_summary"]

    assert summary["total_count"] == len(signals) == dashboard["stats"]["signals"]
    assert sum(summary["strength_counts"].values()) == len(signals)
    assert summary["strength_counts"] == {
        "strong": sum(signal.get("strength") == "强" for signal in signals),
        "medium": sum(signal.get("strength") == "中" for signal in signals),
        "weak": sum(signal.get("strength") == "弱" for signal in signals),
    }
    assert summary["leading_types"]
    assert summary["top_topics"]
    assert summary["overview"]


def test_dashboard_renders_one_aggregate_signal_summary_with_legacy_fallback():
    dashboard_js = (PROJECT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    assert "data.signal_summary" in dashboard_js
    assert "buildSignalSummaryFallback" in dashboard_js
    assert "data.top_signals" in dashboard_js
    assert "data.stats" in dashboard_js
    assert "dashboard-signal-summary" in dashboard_js
    assert "dashboard-signal-facts" in dashboard_js
    assert "renderDashboardSignalToKol" not in dashboard_js
    assert "PMID" not in dashboard_js
    assert "KOL lead" not in dashboard_js
    assert "signal-card" not in dashboard_js
    assert ".dashboard-signal-summary" in css
    assert ".dashboard-signal-facts" in css


def test_literature_signal_card_renders_each_pmid_only_once():
    literature_js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")

    assert "function renderSignalReferenceLinks(refs, renderedPmids)" in literature_js
    assert "renderSignalReferenceLinks(point.refs || [], renderedPmids)" in literature_js
    assert "renderSignalReferenceLinks(item.refs || [], renderedPmids)" in literature_js
    assert "if (pmidValue && renderedPmids[pmidValue]) continue" in literature_js
    assert "var parentRefsHtml = renderSignalReferenceLinks(item.refs || [], renderedPmids)" in literature_js
    assert "(parentRefsHtml ? '<div class=\"literature-signal-refs\"" in literature_js


def test_enrichment_prompt_requires_chinese_and_separates_narrative_roles():
    module = load_enrichment_module()
    prompt = module.SYSTEM + "\n" + module.build_prompt([])

    assert "所有面向用户的叙事字段必须使用中文" in prompt
    assert "takeaway=研究实际发现及其解释" in prompt
    assert "whySignal=该发现为何改变现有判断或开启可持续追踪的问题" in prompt
    assert "evidenceBoundary=研究设计与可推广性限制" in prompt
    assert "keyMessages" in prompt and "必须使用中文" in prompt


def test_llm_records_are_split_into_bounded_unique_batches():
    module = load_enrichment_module()
    records = [{"pmid": str(1000 + index)} for index in range(26)]

    batches = module.batch_records(records, batch_size=8)

    assert [len(batch) for batch in batches] == [8, 8, 8, 2]
    batched_pmids = [record["pmid"] for batch in batches for record in batch]
    assert batched_pmids == [record["pmid"] for record in records]
    assert len(batched_pmids) == len(set(batched_pmids))


def test_llm_batcher_rejects_duplicate_pmids_before_any_request():
    module = load_enrichment_module()

    try:
        module.batch_records([{"pmid": "1000"}, {"pmid": "1000"}], batch_size=8)
    except ValueError as exc:
        assert "Duplicate PMID" in str(exc)
    else:
        raise AssertionError("Duplicate PMIDs must not cross LLM batch boundaries")


def test_all_batched_llm_results_cover_all_26_pmids_exactly_once():
    module = load_enrichment_module()
    records = [{"pmid": str(2000 + index), "title": f"Study {index}"} for index in range(26)]
    requested_batches = []

    def fake_complete(prompt, **_kwargs):
        prompt_records = json.loads(prompt.split("records = ", 1)[1])
        requested_batches.append(prompt_records)
        return json.dumps({
            "signals": [
                {
                    "title": f"新增证据 {record['pmid']}",
                    "refPmids": [record["pmid"]],
                    "talkingPoints": [],
                }
                for record in prompt_records
            ]
        }, ensure_ascii=False)

    raw_signals = module.collect_llm_signals(
        records,
        complete_fn=fake_complete,
        batch_size=8,
        max_attempts=2,
    )

    assert [len(batch) for batch in requested_batches] == [8, 8, 8, 2]
    assert all("本批每个 PMID 必须恰好分配一次" in module.build_prompt(batch) for batch in requested_batches)
    result_pmids = [pmid for signal in raw_signals for pmid in signal["refPmids"]]
    assert sorted(result_pmids) == sorted(record["pmid"] for record in records)
    assert len(result_pmids) == len(set(result_pmids))


def test_llm_batch_retries_only_omitted_pmids_with_a_bounded_attempt_count():
    module = load_enrichment_module()
    records = [{"pmid": str(3000 + index), "title": f"Study {index}"} for index in range(3)]
    requested_pmids = []

    def fake_complete(prompt, **_kwargs):
        prompt_records = json.loads(prompt.split("records = ", 1)[1])
        pmids = [record["pmid"] for record in prompt_records]
        requested_pmids.append(pmids)
        returned_pmids = pmids[:-1] if len(requested_pmids) == 1 else pmids
        return json.dumps({
            "signals": [
                {"title": f"新增证据 {pmid}", "refPmids": [pmid], "talkingPoints": []}
                for pmid in returned_pmids
            ]
        }, ensure_ascii=False)

    raw_signals = module.collect_llm_signals(
        records,
        complete_fn=fake_complete,
        batch_size=8,
        max_attempts=2,
    )

    assert requested_pmids == [["3000", "3001", "3002"], ["3002"]]
    result_pmids = [pmid for signal in raw_signals for pmid in signal["refPmids"]]
    assert result_pmids == ["3000", "3001", "3002"]


def test_partial_llm_coverage_keeps_valid_clusters_and_falls_back_without_pmid_loss():
    module = load_enrichment_module()
    by_pmid = {pmid: sample_article(pmid) for pmid in ("101", "102", "103")}
    payload = {
        "signals": [
            {"id": "old-1", "related_pmids": ["101", "102"], "score": 8, "keywords": []},
            {"id": "old-2", "related_pmids": ["103"], "score": 7, "keywords": []},
        ]
    }
    raw_signals = [
        {
            "title": "患者负担出现新的可追踪证据",
            "takeaway": "近期研究观察到患者负担相关的新结果。",
            "whySignal": "该结果开启了患者报告结局能否影响管理决策的追踪问题。",
            "evidenceBoundary": "该证据来自观察性设计，外推到其他人群时仍需谨慎。",
            "maUse": "用于设计患者负担相关的专家交流问题。",
            "refPmids": ["101"],
            "talkingPoints": [
                {
                    "title": "讨论患者报告结局的临床意义",
                    "whyKol": "可询问该结局是否足以影响随访策略。",
                    "keyMessages": ["研究报告了患者负担相关结果，具体效应需全文核查。"],
                    "refPmids": ["101"],
                }
            ],
        }
    ]

    signals, coverage = module.merge_llm_signals(raw_signals, payload, by_pmid, FakeBuilder())

    assert coverage == 1 / 3
    assert any(signal["takeaway"] == raw_signals[0]["takeaway"] for signal in signals)
    published_pmids = [pmid for signal in signals for pmid in signal["related_pmids"]]
    assert sorted(published_pmids) == ["101", "102", "103"]
    assert len(published_pmids) == len(set(published_pmids))
    assert all(
        {ref["pmid"] for ref in signal["refs"]} == set(signal["related_pmids"])
        for signal in signals
    )
    assert any(signal["signal_to_kol"]["analysis_model"].endswith("-fallback") for signal in signals)


def test_invalid_english_narrative_fields_fall_back_individually_to_chinese():
    module = load_enrichment_module()
    article = sample_article("201", "II")
    raw = {
        "title": "新的治疗路径证据",
        "takeaway": "This field leaked an English abstract excerpt.",
        "whySignal": "该结果使治疗节点选择成为可持续追踪的问题。",
        "evidenceBoundary": "该结果使治疗节点选择成为可持续追踪的问题。",
        "maUse": "Use this for an English briefing.",
        "refPmids": ["201"],
        "talkingPoints": [
            {
                "dimension": "outcomes",
                "title": "Discuss the efficacy result",
                "whyKol": "可讨论终点是否具有临床意义。",
                "keyMessages": [
                    "Results: response improved in the exploratory analysis.",
                    "该结果仍需结合完整研究设计解读。",
                ],
                "refPmids": ["201"],
            }
        ],
    }

    signal = module.normalize_signal(raw, 1, {"201": article}, {}, FakeBuilder())

    assert signal is not None
    narrative = [
        signal["title"],
        signal["takeaway"],
        signal["whySignal"],
        signal["evidenceBoundary"],
        signal["maUse"],
        signal["talkingPoints"][0]["dimension"],
        signal["talkingPoints"][0]["title"],
        signal["talkingPoints"][0]["whyKol"],
        *signal["talkingPoints"][0]["keyMessages"],
    ]
    assert all(module.is_predominantly_chinese(value) for value in narrative)
    assert signal["whySignal"] == raw["whySignal"]
    assert signal["evidenceBoundary"] != signal["whySignal"]
    assert signal["talkingPoints"][0]["keyMessages"] == ["该结果仍需结合完整研究设计解读。"]


def test_invalid_talking_points_container_falls_back_without_aborting_signal():
    module = load_enrichment_module()
    article = sample_article("301")
    raw = {
        "title": "新增疾病负担证据",
        "takeaway": "近期研究提供了疾病负担方面的新结果。",
        "whySignal": "该结果开启了患者负担是否影响管理决策的追踪问题。",
        "evidenceBoundary": "该研究为观察性设计，其他人群中的可推广性仍需验证。",
        "maUse": "用于准备疾病负担相关的专家交流。",
        "refPmids": ["301"],
        "talkingPoints": 42,
    }

    signal = module.normalize_signal(raw, 1, {"301": article}, {}, FakeBuilder())

    assert signal is not None
    assert len(signal["talkingPoints"]) == 1
    assert all(module.is_predominantly_chinese(message) for message in signal["talkingPoints"][0]["keyMessages"])


def test_literature_signals_use_parent_child_evidence_chain_without_duplicate_pmids():
    payload = load_js_global(PROJECT / "data" / "signals-weekly.js", "MG_SIGNALS_DATA")
    signals = payload.get("signals") or []
    policy = payload.get("source_policy") or {}
    pmids = [str(pmid) for signal in signals for pmid in signal.get("related_pmids", [])]

    assert len(signals) < len(pmids)
    assert len(pmids) == len(set(pmids))
    assert sum(signal.get("article_count", 0) for signal in signals) == len(pmids)
    assert policy["analysis_model"].startswith("literature-signal-to-kol-")
    assert policy["aggregation"].startswith("mg_core_topic_cluster")
    if policy.get("llm_enrichment"):
        assert policy["published_reference_coverage"] == 1.0
    assert policy["excluded_non_mg_core"] >= 1

    for signal in signals:
        assert signal.get("title")
        assert signal.get("whySignal")
        assert signal.get("evidenceBoundary")
        assert signal.get("refs")
        assert signal.get("talkingPoints")
        for point in signal["talkingPoints"]:
            assert point["parentSignalId"] == signal["id"]
            assert point["parentSignalTitle"] == signal["title"]
            assert point["priorityTier"] in {"efgar", "competitor_response", "disease_progress"}
            assert point.get("whyKol")
            assert point.get("keyMessages")
            assert point.get("refs")


def test_mg_core_guard_rejects_secondary_disease_comparator():
    sys.path.insert(0, str(PROJECT / "scripts"))
    spec = importlib.util.spec_from_file_location("build_frontend_data", PROJECT / "scripts" / "build-frontend-data.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    excluded, reason = module.mg_core_relevance({
        "title": "Serum inflammatory proteomic signatures define chronic inflammatory demyelinating polyneuropathy",
        "abstract": "We compared chronic inflammatory demyelinating polyneuropathy with IG-treated myasthenia gravis and healthy controls.",
    })
    included, included_reason = module.mg_core_relevance({
        "title": "Clinical Characteristics and Treatment Management of Seronegative Myasthenia Gravis",
        "abstract": "Seronegative myasthenia gravis presents diagnostic and treatment challenges.",
    })

    assert excluded is False
    assert reason == "secondary_disease_in_title"
    assert included is True
    assert included_reason == "title_explicit_mg"
