from __future__ import annotations

import json
import re
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
