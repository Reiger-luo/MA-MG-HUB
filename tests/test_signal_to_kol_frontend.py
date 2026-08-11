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

    assert payload["source_policy"]["scope"] == "literature_only"
    assert payload["source_policy"]["auto_publish"] is True
    assert payload["source_policy"]["review_required"] is False
    assert payload["source_policy"]["signal_count_unlimited"] is True
    if not signals:
        # 零信号周（无新增 MG-core 文献）为合法发布；校验"合法空"契约，防止真错误混入。
        _assert_legitimate_empty_signals_payload(payload)
        return
    assert all(signal.get("signal_to_kol") for signal in signals)
    assert all("kol_leads" in signal for signal in signals)
    assert all("institution_leads" in signal for signal in signals)
    assert all("medical_affairs" in signal for signal in signals)


def _assert_legitimate_empty_signals_payload(payload):
    """零信号周必须走 no_new_mg_core_signals 跳过分支，且满足发布契约。"""
    policy = payload.get("source_policy") or {}
    assert policy.get("llm_enrichment") is True
    assert policy.get("llm_skip_reason") == "no_new_mg_core_signals"
    assert payload.get("window_basis") == "trueIngestAddedPmids"
    assert policy.get("analysis_model") == "literature-signal-to-kol-v4"
    assert policy.get("llm_reference_coverage") == 0.0
    assert policy.get("published_reference_coverage") == 0.0


def test_signal_to_kol_is_rendered_on_literature_page():
    literature_js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    for token in ["signal_to_kol", "kol_leads", "institution_leads", "medical_affairs"]:
        assert token in literature_js
    assert "renderSignalToKol" in literature_js
    assert "signal-kol-bridge" in css
    assert "strategicNoveltyScore" in literature_js
    assert "signal-novelty" in literature_js and ".signal-novelty" in css


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
    assert summary["overview"].startswith("本周共形成 4 条信号")
    assert "治疗证据" in summary["overview"]
    assert "主题乙" in summary["overview"]
    assert "疗效" in summary["overview"]


def test_enrich_skips_llm_and_publishes_empty_payload_when_no_new_mg_core_signals(tmp_path, monkeypatch):
    """无新增 MG-core 信号时，enrich 应优雅跳过 LLM、发布合法空 payload（exit 0）。"""
    module = load_enrichment_module()

    # 用空 requireIngest 窗口构造"本周无新增"的确定性 payload。
    empty_payload = {
        "signals": [],
        "window_basis": "trueIngestAddedPmids",
        "window_start": "2026-08-03",
        "window_end": "2026-08-10",
        "source_policy": {
            "scope": "literature_only",
            "auto_publish": True,
            "review_required": False,
            "signal_count_unlimited": True,
        },
    }

    class EmptyBuilder:
        @staticmethod
        def load_weekly_ingest_manifest():
            return {"window_start": "2026-08-03", "window_end": "2026-08-10", "added_pmids": []}

        @staticmethod
        def build_signals(_literature, _manifest, requireIngest=False):
            assert requireIngest is True
            return dict(empty_payload)

    written = {}

    signals_out = tmp_path / "signals-weekly.js"
    monkeypatch.setattr(module, "SIGNALS_PATH", signals_out)
    monkeypatch.setattr(module, "LITERATURE_PATH", tmp_path / "literature-recent.js")
    monkeypatch.setattr(module, "DASHBOARD_PATH", tmp_path / "dashboard-data.js")
    monkeypatch.setattr(module, "load_js_global", lambda _path, _name: [] if "literature" in str(_path) else {})
    monkeypatch.setattr(module, "load_builder_module", lambda: EmptyBuilder)
    # main() 用 argparse 读取 sys.argv；注入干净 argv 避免把 pytest 参数误当 --force。
    monkeypatch.setattr(sys, "argv", ["enrich-literature-narrative.py"])
    monkeypatch.setattr(
        module,
        "atomic_write_js_global",
        lambda path, name, payload: written.update({"path": path, "name": name, "payload": payload}),
    )
    # 防御：空记录路径绝不应触发 LLM 调用。
    monkeypatch.setattr(
        module,
        "collect_llm_signals",
        lambda _records: (_ for _ in ()).throw(AssertionError("空记录路径不应调用 LLM")),
    )

    module.main()

    assert written["path"] == signals_out
    payload = written["payload"]
    assert payload["signals"] == []
    assert payload["window_basis"] == "trueIngestAddedPmids"
    _assert_legitimate_empty_signals_payload(payload)


def test_replay_current_window_freezes_published_cohort_without_using_empty_ingest(tmp_path, monkeypatch):
    module = load_enrichment_module()
    published = {
        "signals": [
            {"id": "L01", "title": "候选一", "related_pmids": ["5101"], "source_policy": {}},
            {"id": "L02", "title": "候选二", "related_pmids": ["5102"], "source_policy": {}},
        ],
        "window_basis": "trueIngestAddedPmids",
        "window_start": "2026-08-03",
        "window_end": "2026-08-08",
        "source_policy": {"weekly_selection": "literature-ingest-latest.json added_pmids"},
    }
    literature = [sample_article("5101", "II"), sample_article("5102", "IV")]

    class ReplayBuilder(FakeBuilder):
        @staticmethod
        def load_weekly_ingest_manifest():
            raise AssertionError("重放不得读取当前的空 ingest manifest")

        @staticmethod
        def build_signals(*_args, **_kwargs):
            raise AssertionError("重放不得重建或推进周更窗口")

    captured = {}
    signals_out = tmp_path / "signals-weekly.js"
    monkeypatch.setattr(module, "SIGNALS_PATH", signals_out)
    monkeypatch.setattr(module, "LITERATURE_PATH", tmp_path / "literature-recent.js")
    monkeypatch.setattr(module, "DASHBOARD_PATH", tmp_path / "missing-dashboard.js")
    monkeypatch.setattr(
        module,
        "load_js_global",
        lambda _path, name: published if name == "MG_SIGNALS_DATA" else literature,
    )
    monkeypatch.setattr(module, "load_builder_module", lambda: ReplayBuilder)
    monkeypatch.setattr(sys, "argv", ["enrich-literature-narrative.py", "--replay-current-window"])

    def fake_analysis(records, batch_size):
        captured["recordPmids"] = [record["pmid"] for record in records]
        captured["candidateIds"] = [record["candidateSignalId"] for record in records]
        captured["batchSize"] = batch_size
        return {
            "signals": [{"title": "重放后的信号", "refPmids": ["5101"]}],
            "decisions": {
                "5101": {"pmid": "5101", "decision": "include", "valueScore": 4},
                "5102": {"pmid": "5102", "decision": "background", "valueScore": 2},
            },
        }

    monkeypatch.setattr(module, "collect_llm_analysis", fake_analysis)
    monkeypatch.setattr(
        module,
        "merge_llm_signals",
        lambda *_args, **_kwargs: ([{"id": "L01", "related_pmids": ["5101"]}], 1.0),
    )
    monkeypatch.setattr(
        module,
        "atomic_write_js_global",
        lambda path, name, payload: captured.update({"path": path, "name": name, "payload": payload}),
    )

    module.main()

    assert captured["recordPmids"] == ["5101", "5102"]
    assert captured["candidateIds"] == ["", ""]
    assert captured["batchSize"] == 2
    assert captured["payload"]["window_start"] == "2026-08-03"
    assert captured["payload"]["window_end"] == "2026-08-08"
    assert captured["payload"]["analysis_cohort_pmids"] == ["5101", "5102"]
    assert captured["payload"]["source_policy"]["weekly_selection"] == "replay_current_published_window"
    assert captured["payload"]["source_policy"]["replay_window_preserved"] is True


def test_signal_builder_uses_one_week_window():
    builder = load_enrichment_module().load_builder_module()
    fetch_source = (PROJECT / "scripts" / "fetch-pubmed-weekly.py").read_text(encoding="utf-8")
    current = sample_article("current", level="II")
    current.update({
        "title": "Randomized trial of efgartigimod in myasthenia gravis",
        "abstract": "Results: Efgartigimod improved efficacy outcomes in myasthenia gravis.",
        "entry_date": "2026-07-20",
    })
    older = sample_article("older", level="II")
    older.update({
        "title": "Randomized trial of efgartigimod in myasthenia gravis",
        "abstract": "Results: Efgartigimod improved efficacy outcomes in myasthenia gravis.",
        "entry_date": "2026-07-12",
    })

    payload = builder.build_signals([current, older])
    included_pmids = {
        pmid
        for signal in payload["signals"]
        for pmid in signal.get("related_pmids", [])
    }

    assert builder.SIGNAL_WINDOW_DAYS == 7
    assert payload["window_days"] == 7
    assert included_pmids == {"current"}
    assert "WINDOW_DAYS = 7" in fetch_source
    assert "WINDOW_DAYS = 14" not in fetch_source


def test_signal_builder_uses_only_true_ingest_pmids_when_manifest_is_present():
    builder = load_enrichment_module().load_builder_module()
    included = sample_article("included", level="II")
    excluded = sample_article("excluded", level="II")
    for article in (included, excluded):
        article.update({
            "title": "Randomized trial of efgartigimod in myasthenia gravis",
            "abstract": "Results: Efgartigimod improved efficacy outcomes in myasthenia gravis.",
            "entry_date": "2026-07-31",
        })
    manifest = {
        "window_start": "2026-07-27",
        "window_end": "2026-08-01",
        "added_pmids": ["included"],
    }

    payload = builder.build_signals([included, excluded], manifest, requireIngest=True)
    relatedPmids = {
        pmid
        for signal in payload["signals"]
        for pmid in signal.get("related_pmids", [])
    }

    assert relatedPmids == {"included"}
    assert payload["window_basis"] == "trueIngestAddedPmids"
    assert payload["window_start"] == manifest["window_start"]
    assert payload["window_end"] == manifest["window_end"]


def test_signal_strength_uses_evidence_baseline_without_product_or_if_floor():
    builder = load_enrichment_module().load_builder_module()

    for alias in ["efgartigimod", "Vyvgart", "ARGX-113", "艾加莫德"]:
        article = {
            "title": f"{alias} in myasthenia gravis",
            "abstract": "",
            "evidence_level": "V",
            "journal_if": 0,
        }
        assert builder.literature_cluster_key(
            article,
            ["FcRn"],
            ["efgartigimod"],
        ) == "efgar"
        assert builder.classifySignalStrength(article) == "弱"
    assert builder.classifySignalStrength({
        "title": "Efgartigimod randomized trial",
        "evidence_level": "II",
        "journal_if": 0,
    }) == "强"
    assert builder.classifySignalStrength({
        "title": "Efgartigimod narrative review",
        "evidence_level": None,
        "journal_if": 2,
    }) == "弱"
    assert builder.classifySignalStrength({
        "title": "General myasthenia gravis narrative review",
        "evidence_level": None,
        "journal_if": 2,
    }) == "弱"
    assert builder.classifySignalStrength({
        "title": "High-impact myasthenia gravis review",
        "evidence_level": None,
        "journal_if": 12,
    }) == "弱"
    assert builder.cluster_strength(
        [{"level": "II", "strength": "强", "score": 5}],
        "efgar",
    ) == "强"
    assert builder.cluster_strength(
        [{"level": "V", "strength": "弱", "score": 5}],
        "efgar",
    ) == "弱"
    assert builder.cluster_strength(
        [{"level": "V", "strength": "弱", "score": 5}],
        "mechanism_biomarker",
    ) == "弱"


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
    if not signals:
        # 零信号周：汇总为空属合法，仅校验与 payload 的"合法空"契约一致。
        _assert_legitimate_empty_signals_payload(signal_payload)
        return
    assert summary["leading_types"]
    assert summary["top_topics"]
    assert summary["overview"]


def test_dashboard_renders_three_actionable_priority_signals():
    dashboard_js = (PROJECT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    assert "data.signal_summary" in dashboard_js
    assert "data.top_signals" in dashboard_js
    assert "data.stats" in dashboard_js
    assert "signals.slice(0, 3)" in dashboard_js
    assert "signal.medical_affairs" in dashboard_js
    assert "'&signal=' + encodeURIComponent(signal.id)" in dashboard_js
    assert "dashboard-priority-link" in dashboard_js
    assert "查看详细信号" in dashboard_js
    assert "dashboard-priority-card" in dashboard_js
    assert "准备 KOL 讨论" in dashboard_js
    assert "renderDashboardSignalToKol" not in dashboard_js
    assert "PMID" not in dashboard_js
    assert "KOL lead" not in dashboard_js
    assert "signal-card" not in dashboard_js
    assert ".dashboard-priority-card" in css
    assert ".dashboard-priority-link" in css
    assert ".dashboard-priority-actions" in css


def test_literature_signal_deep_link_targets_the_matching_card():
    literature_js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    assert "id: signal.id || ''" in literature_js
    assert "params.get('signal')" in literature_js
    assert "data-signal-id" in literature_js
    assert "document.getElementById('signal-' + safeIdToken(requestedSignal))" in literature_js
    assert "target.scrollIntoView({ block: 'start' })" in literature_js
    assert "target.classList.add('is-targeted')" in literature_js
    assert ".signal-card.is-targeted" in css
    assert ".signal-card[id]" in css


def test_literature_signal_card_renders_each_pmid_only_once():
    literature_js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")

    assert "function renderSignalReferenceLinks(refs, renderedPmids)" in literature_js
    assert "function renderSignalEvidence(item, renderedPmids)" in literature_js
    assert "if (!pmid || renderedPmids[pmid]) return ''" in literature_js
    assert "renderedPmids[pmid] = true" in literature_js
    assert "literature-evidence-item" in literature_js
    assert "这篇补了什么 gap" in literature_js
    assert "renderSignalReferenceLinks(point.refs || [], renderedPmids)" not in literature_js
    assert "var parentRefsHtml" not in literature_js


def test_generated_signal_narratives_do_not_repeat_pmid_labels():
    payload = load_js_global(PROJECT / "data" / "signals-weekly.js", "MG_SIGNALS_DATA")

    for signal in payload.get("signals") or []:
        narrative = {
            "title": signal.get("title"),
            "takeaway": signal.get("takeaway"),
            "gapBefore": signal.get("gapBefore"),
            "gapFilled": signal.get("gapFilled"),
            "remainingGap": signal.get("remainingGap"),
            "evidenceItems": [
                {key: item.get(key) for key in ("finding", "gapContribution", "boundary")}
                for item in signal.get("evidenceItems") or []
            ],
            "talkingPoints": [
                {key: point.get(key) for key in ("title", "whyKol", "keyMessages")}
                for point in signal.get("talkingPoints") or []
            ],
        }
        assert "PMID" not in json.dumps(narrative, ensure_ascii=False).upper()


def test_homepage_signal_board_keeps_the_approved_display_contract():
    dashboard_js = (PROJECT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    index_html = (PROJECT / "index.html").read_text(encoding="utf-8")
    signal_card_renderer = dashboard_js.split("function renderSignalCard", 1)[1].split(
        "function renderSignals", 1
    )[0]

    assert "function renderSignalEvidence(item, renderedPmids)" in dashboard_js
    assert "signal-takeaway" in signal_card_renderer
    assert "为什么构成信号" in dashboard_js
    assert "证据怎么支持" in dashboard_js
    assert "signal-topic-row" not in signal_card_renderer
    assert "准备 KOL 讨论" not in signal_card_renderer
    assert "查看文献" not in signal_card_renderer
    assert "function buildSignalBrief()" in dashboard_js
    assert "getFilteredSignalItems().slice()" in dashboard_js
    assert 'id="btnExportSignalBrief"' in index_html


def test_enrichment_prompt_requires_chinese_and_separates_narrative_roles():
    module = load_enrichment_module()
    prompt = module.SYSTEM + "\n" + module.build_prompt([{
        "pmid": "prompt-test",
        "candidateSignalId": "candidate-1",
        "candidateSignalTitle": "候选主题",
    }])

    assert "所有面向用户的叙事字段必须使用中文" in prompt
    assert "takeaway=MG 专家临床结论" in prompt
    assert "gapBefore=此前不知道什么" in prompt
    assert "gapFilled=本期证据补了什么" in prompt
    assert "remainingGap=限制应用的关键缺口" in prompt
    assert "recordDecisions" in prompt
    assert "strategicNoveltyScore" in prompt
    assert "concept_reframing" in prompt and "pharmacology_threshold" in prompt
    assert "新术语”本身不等于新概念" in prompt
    assert "补体介导疾病" in prompt and "C5 抑制浓度阈值" in prompt
    assert "background" in prompt and "exclude" in prompt
    assert "数量由证据自然决定，可以为 0" in prompt
    assert "candidateSignalId 只用于组织批次，不是最终医学分类" in prompt
    assert "普通病例/小病例系列" in prompt
    assert "不同工具、不同治疗、不同暴露或不同决策节点必须拆开" in prompt
    assert "evidenceItems 必须逐篇覆盖 refPmids" in prompt
    assert "PMID 只放结构化的 refPmids/evidenceItems.pmid" in prompt
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
    assert all("本批每个 PMID 必须在 recordDecisions 中恰好裁决一次" in module.build_prompt(batch) for batch in requested_batches)
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


def test_llm_analysis_resolves_background_without_publishing_it_as_a_signal():
    module = load_enrichment_module()
    records = [{"pmid": "4101", "title": "Incremental MG trial"}, {"pmid": "4102", "title": "Background MG case"}]
    requests = []

    def fake_complete(prompt, **_kwargs):
        prompt_records = json.loads(prompt.split("records = ", 1)[1])
        requests.append([record["pmid"] for record in prompt_records])
        return json.dumps({
            "recordDecisions": [
                {"pmid": "4101", "decision": "include", "category": "治疗疗效与定位", "valueScore": 4, "reason": "提供新的比较性临床结果。"},
                {"pmid": "4102", "decision": "background", "category": "病例级警示", "valueScore": 1, "reason": "病例级证据未形成新的安全警示。"},
            ],
            "signals": [{
                "type": "治疗证据",
                "strength": "强",
                "signalScore": 4,
                "title": "治疗证据推进临床判断",
                "refPmids": ["4101"],
                "talkingPoints": [],
            }],
        }, ensure_ascii=False)

    analysis = module.collect_llm_analysis(records, complete_fn=fake_complete, batch_size=8, max_attempts=2)

    assert requests == [["4101", "4102"]]
    assert [signal["refPmids"] for signal in analysis["signals"]] == [["4101"]]
    assert analysis["decisions"]["4101"]["decision"] == "include"
    assert analysis["decisions"]["4102"]["decision"] == "background"


def test_mixed_include_and_background_narrative_is_retried_without_contamination():
    module = load_enrichment_module()
    records = [{"pmid": "4151", "title": "Included trial"}, {"pmid": "4152", "title": "Background case"}]
    requests = []

    def fake_complete(prompt, **_kwargs):
        batch = json.loads(prompt.split("records = ", 1)[1])
        pmids = [record["pmid"] for record in batch]
        requests.append(pmids)
        if len(pmids) == 2:
            return json.dumps({
                "recordDecisions": [
                    {"pmid": "4151", "decision": "include", "valueScore": 4},
                    {"pmid": "4152", "decision": "background", "valueScore": 2},
                ],
                "signals": [{"title": "被背景文献污染的合并叙事", "refPmids": ["4151", "4152"]}],
            }, ensure_ascii=False)
        return json.dumps({
            "recordDecisions": [{"pmid": "4151", "decision": "include", "valueScore": 4}],
            "signals": [{"title": "干净的单篇试验信号", "refPmids": ["4151"], "talkingPoints": []}],
        }, ensure_ascii=False)

    analysis = module.collect_llm_analysis(records, complete_fn=fake_complete, max_attempts=2)

    assert requests == [["4151", "4152"], ["4151"]]
    assert [signal["title"] for signal in analysis["signals"]] == ["干净的单篇试验信号"]
    assert analysis["decisions"]["4152"]["decision"] == "background"


def test_merge_does_not_fallback_explicit_background_or_excluded_pmids():
    module = load_enrichment_module()
    by_pmid = {pmid: sample_article(pmid) for pmid in ("4201", "4202", "4203")}
    payload = {
        "signals": [
            {"id": "old-1", "related_pmids": ["4201", "4202", "4203"], "score": 8, "keywords": []},
        ]
    }
    raw_signals = [{
        "type": "预后与流行病学",
        "strength": "中",
        "signalScore": 4,
        "title": "队列结果推进风险判断",
        "takeaway": "队列结果补充了风险判断。",
        "whySignal": "该结果推进了风险人群识别。",
        "refPmids": ["4201"],
        "talkingPoints": [],
    }]
    decisions = {
        "4201": {"pmid": "4201", "decision": "include", "valueScore": 4},
        "4202": {"pmid": "4202", "decision": "background", "valueScore": 2},
        "4203": {"pmid": "4203", "decision": "exclude", "valueScore": 1},
    }

    signals, coverage = module.merge_llm_signals(raw_signals, payload, by_pmid, FakeBuilder(), decisions=decisions)

    assert coverage == 1.0
    assert [pmid for signal in signals for pmid in signal["related_pmids"]] == ["4201"]
    assert not any(signal["signal_to_kol"]["analysis_model"].endswith("-fallback") for signal in signals)


def test_mg_expert_strength_and_type_are_bounded_by_evidence_design():
    module = load_enrichment_module()
    case_article = sample_article("4301", "V")
    case_article.update({"title": "A case report in myasthenia gravis", "study_types": ["Case Report"]})
    cohort_article = sample_article("4302", "IV")
    rct_article = sample_article("4303", "II")
    rct_article.update({"title": "Randomized trial in generalized myasthenia gravis", "study_types": ["RCT"]})

    assert module.normalize_signal_strength("强", [case_article], 5) == "弱"
    assert module.normalize_signal_strength("强", [cohort_article], 4) == "中"
    assert module.normalize_signal_strength("强", [rct_article], 5) == "强"
    assert module.normalize_signal_strength("中", [cohort_article], 3) == "弱"
    assert module.normalize_signal_type("诊断与监测", [cohort_article], "真实世界") == "诊断与监测"

    case_decision = module.apply_decision_evidence_ceiling(
        {"decision": "include", "category": "病例级警示", "valueScore": 4, "reason": "病例有趣。"},
        module.records_for_prompt([case_article])[0],
    )
    assert case_decision["decision"] == "background"
    assert case_decision["valueScore"] == 2

    animal_record = module.records_for_prompt([{
        **case_article,
        "pmid": "4304",
        "title": "Feline myasthenia gravis case report",
    }])[0]
    animal_decision = module.apply_decision_evidence_ceiling(
        {"decision": "include", "category": "病例级警示", "valueScore": 3, "reason": "动物病例。"},
        animal_record,
    )
    assert animal_decision["decision"] == "exclude"

    exploratory_exclusion = module.apply_decision_evidence_ceiling(
        {"decision": "exclude", "category": "机制与转化", "valueScore": 1, "reason": "纯计算探索，无临床数据。"},
        module.records_for_prompt([{
            **cohort_article,
            "pmid": "4306",
            "title": "Computational study in myasthenia gravis",
        }])[0],
    )
    assert exploratory_exclusion["decision"] == "background"

    concept_record = module.records_for_prompt([{
        **cohort_article,
        "pmid": "4307",
        "title": "Machine learning model refines an effective-concentration threshold",
        "abstract": "The model pooled generalized myasthenia gravis and other diseases to estimate a pharmacodynamic concentration threshold.",
        "study_types": ["Prediction Model Development"],
    }])[0]
    concept_decision = module.apply_decision_evidence_ceiling(
        {
            "decision": "background",
            "category": "机制与转化",
            "valueScore": 2,
            "strategicNoveltyScore": 5,
            "noveltyType": "pharmacology_threshold",
            "conceptAdvance": "跨适应证模型对既有完全抑制浓度阈值提出了可验证挑战。",
            "clinicalImplication": "若前瞻性验证，可能影响重症肌无力的药物监测和无应答解释。",
            "reason": "目前仅为模型研究。",
        },
        concept_record,
    )
    assert concept_decision["decision"] == "include"
    assert concept_decision["valueScore"] == 3

    concept_signal = module.normalize_signal(
        {
            "type": "机制与转化",
            "strength": "中",
            "signalScore": 4,
            "strategicNoveltyScore": 5,
            "noveltyType": "pharmacology_threshold",
            "conceptAdvance": concept_decision["conceptAdvance"],
            "clinicalImplication": concept_decision["clinicalImplication"],
            "title": "模型挑战完全补体抑制的传统浓度阈值",
            "refPmids": ["4307"],
            "talkingPoints": [],
        },
        1,
        {"4307": {**cohort_article, "pmid": "4307", "study_types": ["Prediction Model Development"]}},
        {},
        FakeBuilder(),
    )
    assert concept_signal["strength"] == "弱"
    assert concept_signal["signalScore"] == 3
    assert concept_signal["strategicNoveltyScore"] == 5
    assert concept_signal["noveltyLabel"] == "高战略新颖性"

    national_matched = {
        **cohort_article,
        "pmid": "4308",
        "title": "Propensity-matched national database cohort in myasthenia gravis",
        "study_types": ["Prognostic Cohort"],
        "evidence_level": "IV",
    }
    prospective_unmet = {
        **cohort_article,
        "pmid": "4309",
        "title": "Prospective study in severe exacerbation requiring ventilatory support",
        "abstract": "Clinical efficacy was assessed with MG-ADL and QMG after enteral support.",
        "study_types": ["Single Arm"],
        "evidence_level": "IV",
    }
    assert module.expert_signal_score_floor([national_matched]) == 4
    assert module.expert_signal_score_floor([prospective_unmet]) == 4
    prospective_diagnostic = {
        **cohort_article,
        "pmid": "4310",
        "title": "Prospective diagnostic study to distinguish myasthenia gravis",
        "abstract": "Diagnostic performance included AUC, sensitivity, and specificity.",
        "study_types": ["Cross-Sectional"],
        "evidence_level": "IV",
    }
    assert module.expert_signal_score_floor([prospective_diagnostic]) == 4
    direct_signal = module.normalize_signal(
        {
            "type": "预后与流行病学",
            "strength": "弱",
            "signalScore": 3,
            "title": "全国匹配队列量化围手术期风险",
            "refPmids": ["4308"],
            "talkingPoints": [],
        },
        1,
        {"4308": national_matched},
        {},
        FakeBuilder(),
    )
    assert direct_signal["strength"] == "中"
    assert direct_signal["signalScore"] == 4

    descriptive_record = module.records_for_prompt([{
        **cohort_article,
        "pmid": "4305",
        "title": "MG outcomes at a tertiary center - A retrospective cohort study",
        "abstract": "Methods: We conducted a retrospective single-center cohort without a comparator.",
        "study_types": ["Single Arm"],
    }])[0]
    descriptive_decision = module.apply_decision_evidence_ceiling(
        {"decision": "include", "category": "预后与流行病学", "valueScore": 4, "reason": "描述本地负担。"},
        descriptive_record,
    )
    assert descriptive_decision["decision"] == "background"


def test_noncomparative_language_cannot_imply_standard_rescue_replacement_or_screening_policy():
    module = load_enrichment_module()
    single_arm = sample_article("4351", "IV")
    single_arm["study_types"] = ["Single Arm"]
    cohort = sample_article("4352", "IV")
    cohort["study_types"] = ["Cross-Sectional"]

    rescue_claim = module.apply_evidence_language(
        "该结果可能改变当前急性期治疗路径中对PLEX/IVIG的依赖，但证据级别低。",
        [single_arm],
    )
    screening_claim = module.apply_evidence_language(
        "临床可考虑在MG诊断前两年加强自身免疫病筛查，但需前瞻性验证。",
        [cohort],
    )
    precursor_claim = module.apply_evidence_language(
        "这些疾病可能作为MG前驱标志。",
        [cohort],
    )
    monitoring_claim = module.apply_evidence_language(
        "临床实践中应考虑在MG诊断时及前后监测这些共病。",
        [cohort],
    )

    assert "尚不能据此替代或减少 PLEX/IVIG" in rescue_claim
    assert "仅提示值得在标准救援治疗背景下进一步验证" in module.apply_evidence_language(
        "该结果提示FcRn阻断可能成为急性期治疗的替代选择。",
        [single_arm],
    )
    assert "不足以直接支持扩大筛查" in screening_claim
    assert "不能据此认定为前驱标志" in precursor_claim
    assert "不足以直接支持新增常规筛查或监测策略" in monitoring_claim
    assert "不足以直接支持改变筛查策略" in module.apply_evidence_language(
        "该结果提示临床医生应关注既往自身免疫疾病，可能影响早期筛查策略。",
        [cohort],
    )


def test_cross_candidate_cluster_merge_requires_explicit_clinical_coherence():
    module = load_enrichment_module()
    records = {
        "4401": {"candidateSignalId": "candidate-a"},
        "4402": {"candidateSignalId": "candidate-b"},
    }
    rejected = module._accepted_batch_signals(
        [{"title": "过宽聚合", "refPmids": ["4401", "4402"], "talkingPoints": []}],
        {"4401", "4402"},
        set(),
        {"4401", "4402"},
        records,
    )
    accepted = module._accepted_batch_signals(
        [{
            "title": "同一临床问题的合并证据",
            "clinicalQuestion": "该治疗能否改善同类全身型重症肌无力患者的疾病控制？",
            "aggregationRationale": "两篇研究针对相同疾病阶段和治疗节点，结局均用于判断疾病控制，因此可共同支持这一临床问题。",
            "refPmids": ["4401", "4402"],
            "talkingPoints": [],
        }],
        {"4401", "4402"},
        set(),
        {"4401", "4402"},
        records,
    )

    assert rejected == []
    assert [signal["refPmids"] for signal in accepted] == [["4401", "4402"]]


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

    assert policy["analysis_model"].startswith("literature-signal-to-kol-")
    assert policy["aggregation"].startswith("mg_core_topic_cluster")
    if not signals:
        # 零信号周：无 parent-child 链可查，仅校验"合法空"契约。
        _assert_legitimate_empty_signals_payload(payload)
        return
    # 多篇可以归为同一信号，但聚合不是配额要求；本周也可能每条高价值证据恰好回答不同问题。
    assert len(signals) <= len(pmids)
    assert len(pmids) == len(set(pmids))
    assert sum(signal.get("article_count", 0) for signal in signals) == len(pmids)
    if policy.get("llm_enrichment"):
        assert 0.0 < policy["published_reference_coverage"] <= policy["llm_reference_coverage"] <= 1.0
    # 严格 recent 上游已可能排除全部 non-core；构建器的混合输入防御另有单测覆盖。
    assert policy["excluded_non_mg_core"] >= 0

    for signal in signals:
        assert signal.get("title")
        assert signal.get("whySignal")
        assert signal.get("evidenceBoundary")
        assert signal.get("gapBefore")
        assert signal.get("gapFilled")
        assert signal.get("remainingGap")
        assert signal.get("refs")
        assert signal.get("evidenceItems")
        assert signal.get("talkingPoints")
        evidence_pmids = [str(item["pmid"]) for item in signal["evidenceItems"]]
        assert len(evidence_pmids) == len(set(evidence_pmids))
        assert set(evidence_pmids) == set(signal["related_pmids"])
        assert all(item.get("finding") and item.get("gapContribution") and item.get("boundary") for item in signal["evidenceItems"])
        for point in signal["talkingPoints"]:
            assert point["parentSignalId"] == signal["id"]
            assert point["parentSignalTitle"] == signal["title"]
            assert point["priorityTier"] in {"efgar", "competitor_response", "disease_progress"}
            assert point.get("whyKol")
            assert point.get("keyMessages")
            assert point.get("refs")

    concept_signals = [
        signal for signal in signals
        if signal.get("strategicNoveltyScore", 0) >= 4
        and signal.get("noveltyType") in {"concept_reframing", "pharmacology_threshold"}
    ]
    for signal in concept_signals:
        assert signal["strength"] == "弱"
        assert signal["signalScore"] <= 3
        assert signal["noveltyLabel"] == "高战略新颖性"
        assert signal.get("conceptAdvance")
        assert signal.get("clinicalImplication")
        assert "当前" in signal["whySignal"] or "验证" in signal["whySignal"]


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
