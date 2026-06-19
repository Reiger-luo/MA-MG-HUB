#!/usr/bin/env python3
"""Reclassify all records in selected evidence buckets after classifier updates.

Targets:
- data/literature-full.json

Modes:
- III: recheck existing evidence_level == 'III'
- IV: recheck existing evidence_level == 'IV'
- NONE: recheck records with empty/None evidence_level

Other records are left untouched unless matched by the selected mode(s).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

_CLASSIFY_DIR = os.path.expanduser(
    "~/.hermes/skills/research/pubmed-study-classifier/scripts"
)
if _CLASSIFY_DIR not in sys.path:
    sys.path.insert(0, _CLASSIFY_DIR)

from classify import classify_study_type

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"
TARGETS = [DATA_DIR / "literature-full.json"]

LEVEL_MAP = {
    "ITC": "I",
    "Systematic Review": "I",
    "RCT": "II",
    "Non-randomized controlled cohort": "III",
    "Case-Control": "IV",
    "Historical Control": "IV",
    "Single Arm": "IV",
    "Case Report": "V",
    "Review": "VI",
    "Protocol": None,
    "HEOR": None,
    "Guideline/Consensus": None,
    "Animal Study": None,
    "In Vitro": None,
    "Comment": None,
    "Letter": None,
    "Editorial": None,
    "Unclassified": None,
    "Historical Article": None,
    "Biography": None,
    "News": None,
    "Lecture": None,
    "Patient Education": None,
    "Technical Report": None,
    "Conference Abstract": None,
    "Introductory Editorial": None,
    "Practice Guideline": None,
    "Consensus Statement": None,
    "Government Document": None,
    "Personal Narrative": None,
    "Fictional Work": None,
    "Webcast": None,
    "Portrait": None,
}


def classify_article(article: dict) -> tuple[str | None, str | None]:
    pub_types = article.get("pub_types", []) or []
    abstract = article.get("abstract", "") or ""
    title = article.get("title", "") or ""
    pt_str = "; ".join(pub_types)
    study_type = classify_study_type(pt_str, abstract, title)
    return study_type, LEVEL_MAP.get(study_type)


def should_recheck(article: dict, modes: set[str]) -> bool:
    level = article.get("evidence_level")
    if "III" in modes and level == "III":
        return True
    if "IV" in modes and level == "IV":
        return True
    if "NONE" in modes and not level:
        return True
    return False


def process_file(path: Path, modes: set[str]) -> dict:
    with open(path) as f:
        articles = json.load(f)

    stats = Counter()
    changed_examples = []

    for article in articles:
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
        default="III,IV,NONE",
        help="Comma-separated buckets to recheck: III,IV,NONE",
    )
    args = parser.parse_args()
    modes = {m.strip().upper() for m in args.modes.split(",") if m.strip()}

    reports = []
    for path in TARGETS:
        if path.exists():
            reports.append(process_file(path, modes))

    print("=== Reclassify selected evidence buckets ===")
    print(f"modes={sorted(modes)}")
    for report in reports:
        print(report["path"])
        print(json.dumps(report["stats"], ensure_ascii=False, indent=2))
        if report["examples"]:
            print("examples:")
            print(json.dumps(report["examples"], ensure_ascii=False, indent=2))

    subprocess.run([sys.executable, "scripts/build-frontend-data.py"], cwd=PROJECT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
