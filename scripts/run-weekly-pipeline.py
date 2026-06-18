#!/usr/bin/env python3
"""
run-weekly-pipeline.py — MA-MG-HUB 每周管线调度器。

默认执行公开数据更新、前端数据构建与周报生成。周更管线不再做历史全库回填；
证据等级、IF/CAS 等补充只面向每周新增且有摘要、足够判断的文献。
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
    args = parser.parse_args()

    print("MA-MG-HUB weekly pipeline")
    print("Started:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    if not args.skip_fetch:
        run_step("PubMed 增量抓取", [sys.executable, "scripts/fetch-pubmed-weekly.py"])

    print("\nℹ️  周更管线不执行历史全库回填。")
    print("   历史数据保持现状；后续仅对每周新增且有摘要、足够判断的文献补充证据等级与 IF/CAS。")
    print("   当前静态站将使用已提交的公开 literature-recent.js 构建前端数据。")

    run_step("前端数据产物生成", [sys.executable, "scripts/build-frontend-data.py"])
    run_step("当前通讯渠道周报生成", [sys.executable, "scripts/generate-weekly-summary.py"])

    print("\n✅ Pipeline finished:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main()
