#!/usr/bin/env python3
"""修正专家库（expert-profiles-china.js）中错误的城市/省份标签。

背景
----
旧 infer_china_location 把省份级词映射到单一城市，并用裸子串 "xian" 匹配，
导致华西医院（West China Hospital, Sichuan University）被标成陕西西安、
苏大附一被标成徐州、温医被标成杭州等系统性错误。详情见 chinaLocationRules.py。

策略
----
对每条专家画像，用权威规则（chinaLocationRules）按 affiliation + institution_aliases
重新推断省市：
  * 新推断为明确省市且与原值不同 —— 覆盖（这是要修正的错误）；
  * 新推断为“未识别” —— 保留原值（台湾/香港等大量机构名不含地理词，
    旧标签本来正确，不能因规则未覆盖而清空）。

只改 province/city 两个字段，其余字段（含 generated_at、metrics、timeline）
逐字节保持原值。使用原子写入，遵循 cloud-safe last-good。

用法
----
    python3 scripts/fix-expert-city-labels.py            # 执行修正
    python3 scripts/fix-expert-city-labels.py --dry-run  # 仅预演，不写入
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chinaLocationRules import infer_china_location  # noqa: E402
from common.io import atomic_write_js_global, load_js_global  # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent
CHINA_JS = PROJECT / "data" / "expert-profiles-china.js"
GLOBAL_NAME = "MG_EXPERT_PROFILE_CHINA"


def main() -> int:
    parser = argparse.ArgumentParser(description="修正中国专家库城市标签")
    parser.add_argument("--dry-run", action="store_true", help="仅预演，不写入")
    args = parser.parse_args()

    payload = dict(load_js_global(CHINA_JS, GLOBAL_NAME))
    items = payload.get("items", [])
    if not items:
        print("⚠️  未找到专家画像，退出。")
        return 1

    changed = 0
    kept_unrecognized = 0
    examples: list[str] = []
    for item in items:
        affiliation = item.get("affiliation", "")
        aliases = item.get("institution_aliases", []) or []
        result = infer_china_location(affiliation, aliases)
        old = (item.get("province", ""), item.get("city", ""))
        if result["province"] == "未识别":
            if old[0] != "未识别":
                kept_unrecognized += 1
            continue
        new = (result["province"], result["city"])
        if new != old:
            if len(examples) < 20:
                examples.append(f"  {old[0]}/{old[1]} -> {new[0]}/{new[1]}  {affiliation}")
            item["province"] = new[0]
            item["city"] = new[1]
            changed += 1

    print(f"专家画像总数：{len(items)}")
    print(f"修正城市标签：{changed}")
    print(f"规则未识别、保留原标签：{kept_unrecognized}")
    if examples:
        print("修正示例（前 20 条）：")
        for line in examples:
            print(line)

    if args.dry_run:
        print("--- dry-run：未写入 ---")
        return 0

    atomic_write_js_global(CHINA_JS, GLOBAL_NAME, payload)
    print(f"✅ 已写入 {CHINA_JS.relative_to(PROJECT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
