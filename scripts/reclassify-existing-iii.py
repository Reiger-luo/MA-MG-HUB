#!/usr/bin/env python3
"""Reclassify all records in selected evidence buckets after classifier updates.

Targets:
- data/literature-full.json

Modes:
- ALL: recheck all records matched by the optional date window
- II: recheck existing evidence_level == 'II'
- III: recheck existing evidence_level == 'III'
- IV: recheck existing evidence_level == 'IV'
- VI: recheck existing evidence_level == 'VI'
- NONE: recheck records with empty/None evidence_level

Other records are left untouched unless matched by the selected mode(s).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from studyClassifier import classifyEvidence

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
TARGETS = [DATA_DIR / "literature-full.json"]


def parse_date(value: str | None):
    if not value:
        return None
    value = value.strip()
    for pattern in ("%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    return None


def classify_article(article: dict) -> tuple[str | None, str | None]:
    studyTypes, evidenceLevel = classifyEvidence(article)
    studyType = studyTypes[0] if studyTypes else None
    return studyType, evidenceLevel


def should_recheck(article: dict, modes: set[str]) -> bool:
    if "ALL" in modes:
        return True
    level = article.get("evidence_level")
    if "II" in modes and level == "II":
        return True
    if "III" in modes and level == "III":
        return True
    if "IV" in modes and level == "IV":
        return True
    if "VI" in modes and level == "VI":
        return True
    if "NONE" in modes and not level:
        return True
    return False


def process_file(path: Path, modes: set[str], recent_days: int | None = None) -> dict:
    with open(path) as f:
        articles = json.load(f)

    stats = Counter()
    changed_examples = []
    cutoff = datetime.now() - timedelta(days=recent_days) if recent_days else None

    for article in articles:
        if cutoff:
            dt = parse_date(article.get("entry_date")) or parse_date(article.get("pub_date"))
            if not dt or dt < cutoff:
                stats["skipped_outside_window"] += 1
                continue
        if not should_recheck(article, modes):
            continue
        stats["rechecked"] += 1
        old_type = ", ".join(article.get("study_types") or []) or None
        old_level = article.get("evidence_level")
        new_type, new_level = classify_article(article)

        if new_type != old_type or new_level != old_level:
            article["study_types"] = [new_type] if new_type else []
            article["evidence_level"] = new_level
            stats["changed"] += 1
            stats[f"to_{new_level or 'none'}"] += 1
            if len(changed_examples) < 20:
                changed_examples.append({
                    "pmid": article.get("pmid"),
                    "title": article.get("title", "")[:120],
                    "old_type": old_type,
                    "old_level": old_level,
                    "new_type": new_type,
                    "new_level": new_level,
                })
        else:
            stats["unchanged"] += 1

    with open(path, "w") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    return {
        "path": str(path),
        "stats": dict(stats),
        "examples": changed_examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reclassify selected evidence buckets")
    parser.add_argument(
        "--modes",
        default="II,III,IV,VI,NONE",
        help="Comma-separated buckets to recheck: ALL,II,III,IV,VI,NONE",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=None,
        help="Only recheck records whose entry_date/pub_date falls within this many days",
    )
    args = parser.parse_args()
    modes = {m.strip().upper() for m in args.modes.split(",") if m.strip()}

    reports = []
    for path in TARGETS:
        if path.exists():
            reports.append(process_file(path, modes, args.recent_days))

    print("=== Reclassify selected evidence buckets ===")
    print(f"modes={sorted(modes)}")
    if args.recent_days:
        print(f"recent_days={args.recent_days}")
    for report in reports:
        print(report["path"])
        print(json.dumps(report["stats"], ensure_ascii=False, indent=2))
        if report["examples"]:
            print("examples:")
            print(json.dumps(report["examples"], ensure_ascii=False, indent=2))

    subprocess.run([sys.executable, "scripts/split-recent-data.py"], cwd=PROJECT, check=True)
    subprocess.run([sys.executable, "scripts/build-frontend-data.py"], cwd=PROJECT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
