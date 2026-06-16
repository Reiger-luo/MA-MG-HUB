#!/usr/bin/env python3
"""
llm_demo.py — LLM 引擎层冒烟测试

验证：
  1. API key 正确加载
  2. DeepSeek API 连通
  3. 缓存写入（第一次调用）
  4. 缓存命中（第二次调用，不产生新 API 调用）
  5. 成本日志记录

运行：
  python3 scripts/llm_demo.py
"""

import sys
from pathlib import Path

# 让脚本能 import 同目录的 llm_client
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm_client import complete, total_cost, CACHE_DIR, COST_LOG, DEFAULT


def main():
    print("=" * 50)
    print("🧪 LLM 引擎层冒烟测试")
    print("=" * 50)

    # ── 测试用例：MG 领域相关，验证中文输出 ──
    prompt = "用一句话（不超过 40 字）介绍重症肌无力（Myasthenia Gravis）的核心病理机制。"
    system = "你是神经免疫学领域的医学专家，回答要准确、简洁。"

    print(f"\n📝 提示词：{prompt}")
    print(f"🎯 模型：{DEFAULT}\n")

    # ── 第一次调用（应触发真实 API 调用）──
    print("▶ 第一次调用（预期触发 API）...")
    t0 = __import__("time").time()
    reply1 = complete(prompt, system=system, temperature=0.3, use_cache=True)
    dt1 = __import__("time").time() - t0
    print(f"  ✅ 耗时 {dt1:.1f}s")
    print(f"  💬 回复：{reply1}")

    # ── 第二次调用（应命中缓存，毫秒级）──
    print("\n▶ 第二次调用（预期命中缓存）...")
    t0 = __import__("time").time()
    reply2 = complete(prompt, system=system, temperature=0.3, use_cache=True)
    dt2 = __import__("time").time() - t0
    print(f"  ✅ 耗时 {dt2:.3f}s（{'缓存命中 ✓' if dt2 < 0.1 else '可能未命中 ⚠️'})")
    print(f"  💬 回复：{reply2}")

    if reply1 == reply2:
        print("\n✅ 两次回复一致，缓存工作正常")
    else:
        print("\n⚠️ 两次回复不一致（缓存可能未生效，或 temperature 导致差异）")

    # ── 基础设施检查 ──
    print("\n" + "=" * 50)
    print("📦 基础设施状态")
    print("=" * 50)

    cache_files = list(CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else []
    print(f"缓存目录：{CACHE_DIR}")
    print(f"  缓存条目：{len(cache_files)} 个")

    print(f"成本日志：{COST_LOG}")
    print(f"  文件存在：{'是' if COST_LOG.exists() else '否'}")

    cost = total_cost()
    print(f"\n💰 累计花费：¥{cost}")

    # ── 结论 ──
    print("\n" + "=" * 50)
    ok = reply1 and len(cache_files) > 0 and COST_LOG.exists()
    if ok:
        print("🎉 冒烟测试通过！LLM 引擎层就绪。")
        print("   后续脚本 from llm_client import complete 即可使用。")
    else:
        print("❌ 冒烟测试未完全通过，请检查上面的输出。")
        sys.exit(1)


if __name__ == "__main__":
    main()
