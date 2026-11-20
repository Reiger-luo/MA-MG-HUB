#!/usr/bin/env python3
"""按 OCEBM 2011 v2.1 官方表，用 LLM 复核规则分级，逐轮留痕。

每轮：全局随机采样 10 篇 -> LLM 逐篇复核问题域/等级 -> 与规则结果比对 -> 写审计文件。
本脚本只读 data/literature-full.json，结果只写 .hermes-audit/llmGradingIteration/，
不写 data/**，不改发布产物。规则调整由人工根据分歧报告决定。

用法：
  python3 scripts/llm-grade-iteration.py --round 1
  python3 scripts/llm-grade-iteration.py --round 2 --model reasoner
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path

from llm_client import complete
from studyClassifier import classifyEvidence

PROJECT = Path(__file__).resolve().parent.parent
FULL = PROJECT / "data" / "literature-full.json"
AUDIT = PROJECT / ".hermes-audit" / "llmGradingIteration"
SAMPLE_SIZE = 10

SYSTEM = """你是循证医学方法学专家，精通 Oxford CEBM 2011 Levels of Evidence v2.1 官方表。
任务：只基于给定的文献 title/abstract/pubTypes，判断该研究在官方表中对应的问题域与等级。

官方表（7 域，逐域判定，罗马数字只在域内可比）：
- 治疗获益：L1=RCT系统综述/n-of-1；L2=RCT或戏剧性效应观察；L3=非随机对照队列/随访；L4=病例系列/病例对照/历史对照；L5=机制推理
- 常见伤害/罕见伤害：L1=RCT系统综述/嵌套病例对照综述/n-of-1；L2=RCT或戏剧性效应观察；L3=非随机对照队列（含足量上市后监测）；L4=病例系列/病例对照/历史对照；L5=机制推理
- 预后：L1=inception队列系统综述；L2=inception队列（疾病早期统一时点入组随访）；L3=普通队列或RCT对照臂；L4=病例系列/病例对照/低质量预后队列；无L5
- 诊断准确性：L1=横断面系统综述（一致参考标准+盲法）；L2=单个横断面（一致参考标准+盲法）；L3=非连续入组或参考标准不一致；L4=病例对照或差/非独立参考标准；L5=机制推理
- 患病率：L1=本地当前随机抽样/普查；L2=可匹配本地的抽样系统综述；L3=本地非随机抽样；L4=病例系列；无L5
- 筛查：L1=RCT系统综述；L2=RCT；L3=非随机对照队列/随访；L4=病例系列/病例对照/历史对照；L5=机制推理

关键规则：
1. 官方表没有的研究设计（biomarker关联、预测模型开发与外部验证、GWAS/omics/遗传关联、量表验证、FAERS药物警戒、横断面问卷/DCE、叙述综述、protocol、指南、动物、体外）一律判 level="无等级"，domain="官方表无对应"。
2. 必须为本研究自身设计，不能因摘要提及既往RCT就判RCT。
3. 每个判断必须给出摘要中的原文依据句（quotedEvidence）；摘要无依据时 level 判"无等级"。
4. 只输出 JSON object，不要 Markdown，不要解释。格式：
{"records":[{"pmid":"...","domain":"...","level":"I|II|III|IV|V|无等级","quotedEvidence":"摘要原句","confidence":"high|medium|low","note":"简述理由"}]}"""


def build_prompt(records: list[dict]) -> str:
    payload = []
    for r in records:
        payload.append({
            "pmid": str(r.get("pmid")),
            "title": r.get("title") or "",
            "abstract": r.get("abstract") or "",
            "pubTypes": r.get("pub_types") or [],
        })
    return "请逐篇复核以下文献：\n" + json.dumps(payload, ensure_ascii=False)


def parse_review(text: str) -> dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("LLM 未返回 JSON object")
    return json.loads(text[start:end + 1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--model", default="reasoner", help="reasoner / chat alias")
    ap.add_argument("--seed", type=int, default=20261120)
    args = ap.parse_args()
    from llm_client import DEFAULT as CHAT_MODEL, REASONER as REASONER_MODEL
    modelName = REASONER_MODEL if args.model == "reasoner" else CHAT_MODEL

    articles = json.loads(FULL.read_text(encoding="utf-8"))
    rng = random.Random(args.seed + args.round)
    sample = rng.sample(articles, min(SAMPLE_SIZE, len(articles)))

    # 逐篇调用：reasoner 对超长 prompt 会返回 400，单篇更稳定，也便于逐篇比对。
    # 单篇失败/空回复不中断整轮，记录到 errors 供审计。
    by_pmid = {}
    errors = []
    for a in sample:
        pmid = str(a.get("pmid"))
        prompt = build_prompt([a])
        try:
            reply = complete(
                prompt,
                system=SYSTEM,
                model=modelName,
                temperature=0,
                max_tokens=1000,
                use_cache=False,
            )
            if reply.strip():
                parsed = parse_review(reply)
                for r in parsed.get("records", []):
                    by_pmid[str(r.get("pmid"))] = r
            else:
                errors.append({"pmid": pmid, "reason": "empty_reply"})
        except Exception as exc:  # noqa: BLE001 - 审计脚本需容错，失败只记录不中断
            errors.append({"pmid": pmid, "reason": str(exc)[:200]})

    comparisons = []
    for a in sample:
        pmid = str(a.get("pmid"))
        if pmid not in by_pmid:
            continue
        llm = by_pmid[pmid]
        ruleTypes, ruleLevel = classifyEvidence(a)
        comparisons.append({
            "pmid": pmid,
            "title": a.get("title"),
            "rule_studyType": (ruleTypes or [None])[0],
            "rule_level": ruleLevel,
            "llm_domain": llm.get("domain"),
            "llm_level": llm.get("level"),
            "llm_quotedEvidence": llm.get("quotedEvidence"),
            "llm_confidence": llm.get("confidence"),
            "llm_note": llm.get("note"),
            "agree": (ruleLevel or "无等级") == (llm.get("level") or "无等级"),
        })

    AUDIT.mkdir(parents=True, exist_ok=True)
    out = {
        "round": args.round,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": args.model,
        "seed": args.seed,
        "sample_size": len(sample),
        "reviewed": len(comparisons),
        "errors": errors,
        "agreement": sum(1 for c in comparisons if c["agree"]),
        "disagreement": sum(1 for c in comparisons if not c["agree"]),
        "comparisons": comparisons,
    }
    (AUDIT / f"round-{args.round:02d}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"=== Round {args.round} | model={args.model} | n={len(sample)} ===")
    print(f"agree={out['agreement']}  disagree={out['disagreement']}")
    for c in comparisons:
        if not c["agree"]:
            print(json.dumps(c, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
