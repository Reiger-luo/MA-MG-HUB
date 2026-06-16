#!/usr/bin/env python3
"""
llm_client.py — MG-HUB 统一 LLM 调用客户端

所有需要 LLM 的脚本（信号提取、证据矩阵、模块组装、拜访归类等）
都应通过本模块调用，而非各自处理 API 细节。

特性：
  - 统一接口：complete(prompt, system, model, temperature, max_tokens, use_cache)
  - 密钥加载：环境变量 DEEPSEEK_API_KEY → ~/.config/mg-hub/.env
  - 本地缓存：prompt+model 的 sha256 → data/.llm_cache/{hash}.json（省钱+可复现）
  - 重试：指数退避（429/5xx），最多 3 次
  - 成本日志：data/.llm_cost.log（时间/模型/token 数/费用）
  - DeepSeek 官方 API（OpenAI 兼容协议）

用法：
    from llm_client import complete
    reply = complete("用一句话介绍重症肌无力", temperature=0.3)
    print(reply)

    # 需要推理时换更强的模型
    from llm_client import complete, REASONER
    reply = complete("...", model=REASONER)
"""

import os
import sys
import json
import time
import hashlib
import logging
from pathlib import Path

import requests

# ── 配置 ──────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / ".llm_cache"
COST_LOG = PROJECT_ROOT / "data" / ".llm_cost.log"
ENV_FILE = Path.home() / ".config" / "mg-hub" / ".env"

# DeepSeek 官方 API（OpenAI 兼容）
API_BASE = "https://api.deepseek.com"
CHAT_ENDPOINT = f"{API_BASE}/chat/completions"

# 模型常量
DEFAULT = "deepseek-chat"        # DeepSeek-V3，日常提取/分类
REASONER = "deepseek-reasoner"   # 需要推理的任务（证据矩阵、复杂判断）

# DeepSeek 定价（人民币元 / 百万 token，cache miss）
# 来源：https://api-docs.deepseek.com/zh-cn/quick_start/pricing
# deepseek-chat: input ¥1/M（cache miss），output ¥2/M
# deepseek-reasoner: input ¥4/M，output ¥16/M
PRICE_PER_M = {
    DEFAULT: {"input": 1.0, "output": 2.0},
    REASONER: {"input": 4.0, "output": 16.0},
}

# 日志
logger = logging.getLogger("llm_client")
if not logger.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)


# ── 密钥加载 ──────────────────────────────────────────

def _load_env_file(path: Path):
    """从 .env 文件加载环境变量（不覆盖已存在的）。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def get_api_key() -> str:
    """获取 DeepSeek API key。优先环境变量，其次 ~/.config/mg-hub/.env。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        _load_env_file(ENV_FILE)
        key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        raise RuntimeError(
            f"DEEPSEEK_API_KEY 未设置。\n"
            f"  方式 1: export DEEPSEEK_API_KEY=sk-...\n"
            f"  方式 2: 写入 {ENV_FILE}（内容: DEEPSEEK_API_KEY=sk-...）"
        )
    return key


# ── 缓存 ──────────────────────────────────────────────

def _cache_key(prompt: str, system, model: str, temperature: float, max_tokens: int) -> str:
    """生成缓存 key（基于完整请求参数的 sha256）。"""
    payload = json.dumps(
        {"prompt": prompt, "system": system, "model": model,
         "temperature": temperature, "max_tokens": max_tokens},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str):
    p = CACHE_DIR / f"{key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _cache_put(key: str, entry: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = CACHE_DIR / f"{key}.json"
    p.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 成本日志 ──────────────────────────────────────────

def _log_cost(model: str, prompt_tokens: int, completion_tokens: int, cached: bool):
    """追加一条成本记录。"""
    price = PRICE_PER_M.get(model, PRICE_PER_M[DEFAULT])
    cost = (prompt_tokens * price["input"] + completion_tokens * price["output"]) / 1_000_000
    line = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_cny": round(cost, 6),
        "cached": cached,
    }
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(COST_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return cost


def total_cost() -> float:
    """读取累计花费（人民币元）。"""
    if not COST_LOG.exists():
        return 0.0
    total = 0.0
    for line in COST_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            total += json.loads(line).get("cost_cny", 0)
        except Exception:
            pass
    return round(total, 4)


# ── 核心调用 ──────────────────────────────────────────

def complete(
    prompt: str,
    system: str | None = None,
    model: str = DEFAULT,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    use_cache: bool = True,
) -> str:
    """调用 LLM 返回文本回复。

    参数：
        prompt: 用户提示词
        system: 系统提示词（可选）
        model: DEFAULT / REASONER
        temperature: 0-2，默认 0.3（提取类任务偏低更稳定）
        max_tokens: 最大输出 token 数
        use_cache: 是否启用本地缓存（相同请求直接返回缓存，不调 API）

    返回：
        LLM 回复文本
    """
    key = _cache_key(prompt, system, model, temperature, max_tokens)

    # 缓存命中
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            logger.info(f"cache hit [{model}] (hash {key[:8]}...)")
            _log_cost(model, cached.get("prompt_tokens", 0),
                      cached.get("completion_tokens", 0), cached=True)
            return cached["content"]

    # 实际调用
    content, usage = _call_api(prompt, system, model, temperature, max_tokens)
    _log_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), cached=False)

    if use_cache:
        _cache_put(key, {
            "content": content,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return content


def _call_api(prompt, system, model, temperature, max_tokens):
    """实际 HTTP 调用，带重试。返回 (content, usage)。"""
    api_key = get_api_key()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(CHAT_ENDPOINT, headers=headers, json=payload, timeout=120)
            # 429 / 5xx → 退避重试
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = 2 ** attempt
                logger.warning(f"HTTP {resp.status_code}, 重试 {attempt+1}/3，等待 {wait}s")
                time.sleep(wait)
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return content, usage
        except (requests.RequestException, KeyError, ValueError) as e:
            wait = 2 ** attempt
            logger.warning(f"调用失败 {attempt+1}/3: {e}，等待 {wait}s")
            last_err = str(e)
            time.sleep(wait)

    raise RuntimeError(f"DeepSeek API 调用 3 次均失败: {last_err}")


# ── 批量调用辅助 ──────────────────────────────────────

def complete_batch(items, prompt_builder, model=DEFAULT, temperature=0.3, use_cache=True):
    """批量调用。prompt_builder(item) -> (prompt, system)。

    适用于逐篇文献提取信号等场景。已缓存的自动跳过。
    返回 [(item, reply), ...]，顺序与输入一致。
    """
    results = []
    for i, item in enumerate(items):
        prompt, system = prompt_builder(item)
        try:
            reply = complete(prompt, system=system, model=model,
                             temperature=temperature, use_cache=use_cache)
            results.append((item, reply))
        except Exception as e:
            logger.error(f"第 {i+1} 项失败: {e}")
            results.append((item, None))
        # 批量场景打印进度
        if (i + 1) % 10 == 0:
            logger.info(f"进度 {i+1}/{len(items)}")
    return results


if __name__ == "__main__":
    # 直接运行时做一次自检
    print("=== llm_client.py 自检 ===")
    try:
        api_key = get_api_key()
        print(f"✅ API key 已加载（{api_key[:6]}...{api_key[-4:]}）")
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"缓存目录: {CACHE_DIR}")
    print(f"成本日志: {COST_LOG}")
    print(f"累计花费: ¥{total_cost()}")
