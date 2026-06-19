#!/usr/bin/env python3
"""
backfill-study-classification.py — 证据等级分类回填（任务 B）

遍历 literature-full.json（全量），对每篇文章：
  1. 读取 pub_types（PubMed Publication Type）和 abstract
  2. 调用本项目 studyClassifier 统一分类
  3. 回填到 study_types（数组）和 evidence_level（字符串）

输出：直接更新 literature-full.json
"""

import json
from pathlib import Path

from studyClassifier import classifyEvidence

PROJECT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT / "data"

def classify_article(article):
    """对一篇文章返回分类结果"""
    studyTypes, evidenceLevel = classifyEvidence(article)
    return {
        "study_types": studyTypes,
        "evidence_level": evidenceLevel,
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
        # 默认跳过已分类条目；但证据等级 II/III/VI 需要按新标准重跑
        st = a.get("study_types")
        ev = a.get("evidence_level")
        if ev in {"II", "III", "VI"}:
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
