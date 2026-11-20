#!/usr/bin/env python3
"""汇总 15 轮 LLM 分级复核的分歧，按规则 studyType 归类，供逐条改规则。"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / ".hermes-audit" / "llmGradingIteration"


def main() -> int:
    by_type = defaultdict(list)
    total_agree = total_dis = total_reviewed = total_err = 0
    for path in sorted(AUDIT.glob("round-*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        total_agree += d["agreement"]
        total_dis += d["disagreement"]
        total_reviewed += d["reviewed"]
        total_err += len(d.get("errors", []))
        for c in d["comparisons"]:
            if not c["agree"]:
                by_type[c["rule_studyType"] or "None"].append({
                    "round": d["round"],
                    "pmid": c["pmid"],
                    "rule_level": c["rule_level"],
                    "llm_level": c["llm_level"],
                    "llm_domain": c["llm_domain"],
                    "title": (c["title"] or "")[:70],
                    "quoted": (c["llm_quotedEvidence"] or "")[:120],
                })

    print(f"rounds=15 reviewed={total_reviewed} agree={total_agree} disagree={total_dis} errors={total_err}")
    print(f"agreement rate = {total_agree}/{total_reviewed} = {total_agree/max(1,total_reviewed):.1%}")
    print("\n=== 分歧按规则 studyType 归类 ===")
    for st, items in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        print(f"\n[{st}] {len(items)} 处")
        for it in items[:6]:
            print(f"  R{it['round']:02d} {it['pmid']}: rule={it['rule_level']} llm={it['llm_level']} ({it['llm_domain']})")
            print(f"      {it['title']}")
            print(f"      quote: {it['quoted']}")


if __name__ == "__main__":
    raise SystemExit(main())
