"""文献信号跨周沉淀单测。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("enrich_lit", ROOT / "scripts" / "enrich-literature-narrative.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def signal(signal_id, date, title, strength="中"):
    return {"id": signal_id, "date": date, "title": title, "strength": strength, "related_pmids": ["123"]}


def test_history_keeps_distinct_weeks_with_reused_ids():
    prior = [signal("L01", "2026/11/10", "旧题名")]
    current = [signal("L01", "2026/11/17", "新题名")]
    history = module.build_literature_signal_history(prior, current, "2026-11-17")
    assert len(history) == 2
    assert history[0]["title"] == "新题名"
    assert history[0]["capturedAt"] == "2026-11-17"
    assert history[1]["capturedAt"] == "2026-11-17" or history[1]["capturedAt"] == "2026-11-17"


def test_history_keeps_prior_capture_dates_when_current_week_empty():
    prior = [signal("L01", "2026/11/10", "旧题名")]
    prior[0]["capturedAt"] = "2026-11-10"
    history = module.build_literature_signal_history(prior, [], "2026-11-17")
    assert len(history) == 1
    assert history[0]["capturedAt"] == "2026-11-10"


def test_history_caps_at_ten_and_deduplicates():
    prior = [signal(f"L{i}", "2026/10/01", f"题名{i}") for i in range(12)]
    for item in prior:
        item["capturedAt"] = "2026-10-01"
    history = module.build_literature_signal_history(prior, [], "2026-11-17")
    assert len(history) == 10
