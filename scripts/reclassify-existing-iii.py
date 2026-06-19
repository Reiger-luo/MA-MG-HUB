#!/usr/bin/env python3
"""Reclassify only records currently marked evidence_level == 'III'.

Targets:
- data/literature-full.json
- data/literature-weekly.json

Uses the current pubmed-study-classifier and updates only existing III-level
records. Other records are left untouched.
"""

from __future__ import annotations

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
TARGETS = [
    DATA_DIR / "literature-full.json",
]

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


def process_file(path: Path) -> dict:
    with open(path) as f:
        articles = json.load(f)

    stats = Counter()
    changed_examples = []

    for article in articles:
        if article.get("evidence_level") != "III":
            continue
        stats["rechecked"] += 1
        old_type = ", ".join(article.get("study_types") or []) or None
        old_level = article.get("evidence_level")
        new_type, new_level = classify_article(article)

        if new_type != old_type or new_level != old_level:
            article["study_types"] = [new_type] if new_type else []
            article["evidence_level"] = new_level
            stats["changed"] += 1
            if new_level == "IV":
                stats["to_iv"] += 1
            elif new_level == "III":
                stats["stay_iii_changed_label"] += 1
            else:
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
    reports = []
    for path in TARGETS:
        if path.exists():
            reports.append(process_file(path))

    print("=== Reclassify existing III only ===")
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
