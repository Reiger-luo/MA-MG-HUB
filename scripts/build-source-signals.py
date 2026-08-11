#!/usr/bin/env python3
"""生成互不混用的公开来源信号频道。"""

from __future__ import annotations

from pathlib import Path

from common.io import atomic_write_js_global
from common.source_channels import build_source_signals


PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"


def main() -> int:
    payload = build_source_signals(
        literature_signals_path=DATA / "signals-weekly.js",
        guideline_cache_path=DATA / "guideline-consensus-cache.json",
        regulatory_path=DATA / "china-regulatory-status.json",
        clinicaltrials_path=DATA / "clinicaltrials-pipeline-cache.json",
        chictr_path=DATA / "chictr-trials-cache.json",
        china_drug_trials_path=DATA / "china-drug-trials-cache.json",
        conference_path=DATA / "conference-data.json",
        trial_signals_path=DATA / "trial-signals-weekly.js",
    )
    target = DATA / "source-signals.js"
    atomic_write_js_global(target, "MG_SOURCE_SIGNALS", payload)
    print(f"✅ {target.relative_to(PROJECT)}: {sum(len(item['items']) for item in payload['channels'])} signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
