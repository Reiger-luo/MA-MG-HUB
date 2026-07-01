#!/usr/bin/env python3
"""
run-weekly-pipeline.py — MA-MG-HUB 每周管线调度器。

默认执行 PubMed 14 天增量抓取、weekly 证据等级筛选、IF/CAS 补充、full/recent
存储同步、前端数据构建、周报与管线状态生成。
周更管线不做历史全库回填；每周新增文献先补证据等级，无证据等级则不进入后续周更。
涉及敏感的拜访记录、专家内部标签不在本管线中处理，也不会写入公开仓库。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
def run_step(label: str, command: list[str], optional: bool = False):
    print(f"\n== {label} ==")
    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=PROJECT)
    if result.returncode != 0:
      if optional:
          print(f"⚠️  {label} 失败，已跳过")
          return
      raise SystemExit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Run MA-MG-HUB weekly data pipeline")
    parser.add_argument("--skip-fetch", action="store_true", help="跳过 PubMed 增量抓取")
    parser.add_argument("--skip-llm", action="store_true", help="跳过未来 LLM 提取步骤")
    parser.add_argument("--skip-status", action="store_true", help="跳过管线状态生成，供本地总入口最后统一刷新")
    parser.add_argument("--skip-downstream", action="store_true", help="只执行抓取/富集/存储同步，跳过公开前端产物生成")
    args = parser.parse_args()

    print("MA-MG-HUB weekly pipeline")
    print("Started:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    if not args.skip_fetch:
        run_step("PubMed 增量抓取", [sys.executable, "scripts/fetch-pubmed-weekly.py"])
        run_step("每周文献轻量富集", [sys.executable, "scripts/enrich-weekly-literature.py"])
        run_step("文献存储同步与 recent 派生", [sys.executable, "scripts/merge-weekly-literature.py"])

    print("\nℹ️  周更管线不执行历史全库回填。")
    print("   历史数据保持现状；weekly 新增先补证据等级，无证据等级则剔除；有等级后再补 IF/CAS。")
    print("   本地有 data/literature-full.json 时会 upsert 到 full；静态站使用 data/literature-recent.js。")

    if args.skip_downstream:
        print("\n✅ 已完成抓取、富集和存储同步；跳过下游公开产物生成。")
        return

    run_step("前端数据产物生成", [sys.executable, "scripts/build-frontend-data.py"])
    run_step("全库文献轻索引生成", [sys.executable, "scripts/buildFullLiteratureIndex.py"])
    run_step("医学事务社区语义层生成", [sys.executable, "scripts/buildCommunityData.py"])
    run_step("知识库图谱与证据矩阵生成", [sys.executable, "scripts/build-knowledge-data.py"])
    run_step("本地 wiki 专题层生成", [sys.executable, "scripts/build-curated-topic-data.py"])
    run_step("wiki 专题社区覆盖生成", [sys.executable, "scripts/buildWikiTopicCoverage.py"])
    run_step("动态诊治格局洞察生成", [sys.executable, "scripts/buildLandscapeInsights.py"])
    run_step("后端选项评估生成", [sys.executable, "scripts/buildBackendOptions.py"])
    run_step("当前通讯渠道周报生成", [sys.executable, "scripts/generate-weekly-summary.py"])
    if not args.skip_status:
        run_step("管线状态生成", [sys.executable, "scripts/generate-pipeline-status.py"])

    print("\n✅ Pipeline finished:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main()
