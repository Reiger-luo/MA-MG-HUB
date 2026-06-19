#!/usr/bin/env python3
"""
backfill-study-classification.py — 证据等级分类回填（任务 B）

遍历 literature-full.json（全量），对每篇文章：
  1. 读取 pub_types（PubMed Publication Type）和 abstract
  2. 调用 pubmed-study-classifier 的 classify_study_type() 分类
  3. 回填到 study_types（数组）和 evidence_level（字符串）

输出：直接更新 literature-full.json
"""

import json, sys, os
from pathlib import Path

# 把 classify.py 所在的路径加入 sys.path
_CLASSIFY_DIR = os.path.expanduser(
    "~/.hermes/skills/research/pubmed-study-classifier/scripts"
)
if _CLASSIFY_DIR not in sys.path:
    sys.path.insert(0, _CLASSIFY_DIR)

from classify import classify_study_type

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"

# 证据等级映射（classifier 输出 → 证据等级数字）
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
    # 其他非证据类
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

# 需要 LLM 二次判断的 Unclassified → 手动标记
# 目前 classifier 已覆盖大部分场景，Unclassified 先保留


def classify_article(article):
    """对一篇文章返回分类结果"""
    pub_types = article.get("pub_types", [])
    abstract = article.get("abstract", "") or ""
    title = article.get("title", "") or ""

    pt_str = "; ".join(pub_types) if pub_types else ""

    # 调用 classifier
    result = classify_study_type(pt_str, abstract, title)

    # 映射证据等级
    level = LEVEL_MAP.get(result, None)

    return {
        "study_types": [result] if result else [],
        "evidence_level": level,
    }


def backfill_file(filepath, label):
    """对单个 JSON 文件执行分类回填"""
    if not filepath.exists():
        print(f"  ⏭ {label}: 文件不存在")
        return 0, 0

    with open(filepath) as f:
        articles = json.load(f)

    classified = 0
    no_change = 0
    for a in articles:
        # 默认跳过已分类条目；但证据等级 III 需要按新标准重跑
        st = a.get("study_types")
        ev = a.get("evidence_level")
        if ev == "III":
            result = classify_article(a)
            a["study_types"] = result["study_types"]
            a["evidence_level"] = result["evidence_level"]
            classified += 1
            continue
        if ev and st and st != ["Unclassified"]:
            no_change += 1
            continue
        result = classify_article(a)
        a["study_types"] = result["study_types"]
        a["evidence_level"] = result["evidence_level"]
        classified += 1

    with open(filepath, "w") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    return classified, len(articles)


def print_stats(articles, label):
    """打印分类统计"""
    from collections import Counter

    types = Counter()
    levels = Counter()
    unclass = 0
    for a in articles:
        for t in a.get("study_types", []):
            types[t] += 1
        lv = a.get("evidence_level")
        if lv:
            levels[lv] += 1
        else:
            # 如果 study_types 非空但 evidence_level 为 None
            if a.get("study_types"):
                unclass += 1

    print(f"\n📊 {label} 分类统计 ({len(articles)} 篇)")
    print(f"  研究类型分布:")
    for t, c in types.most_common():
        print(f"    {t}: {c}")
    print(f"  证据等级分布:")
    for lv in ["I", "II", "III", "IV", "V", "VI"]:
        c = levels.get(lv, 0)
        if c > 0:
            print(f"    L{lv}: {c}")
    if unclass:
        print(f"  非证据类: {unclass}")


def main():
    print("📚 MG-HUB 证据等级分类回填（任务 B）")
    print()

    # 直接分类全量文献（full.json 是唯一数据源，已包含全部记录）
    full_path = DATA_DIR / "literature-full.json"
    classified_full, total_full = backfill_file(full_path, "全量文献")
    print(f"📝 全量: {classified_full} 篇新分类, {total_full} 篇总")

    if classified_full > 0:
        with open(full_path) as f:
            articles = json.load(f)
        print_stats(articles, "全量")


if __name__ == "__main__":
    main()
