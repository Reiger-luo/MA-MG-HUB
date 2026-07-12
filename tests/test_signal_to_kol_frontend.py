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


def test_signal_to_kol_is_rendered_on_literature_and_dashboard_pages():
    literature_js = (PROJECT / "assets" / "literature.js").read_text(encoding="utf-8")
    dashboard_js = (PROJECT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    css = (PROJECT / "assets" / "main.css").read_text(encoding="utf-8")

    for token in ["signal_to_kol", "kol_leads", "institution_leads", "medical_affairs"]:
        assert token in literature_js
    assert "renderSignalToKol" in literature_js
    assert "renderDashboardSignalToKol" in dashboard_js
    assert "signal-kol-bridge" in css


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
