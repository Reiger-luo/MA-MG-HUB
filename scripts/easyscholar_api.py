#!/usr/bin/env python3
"""
EasyScholar API 封装模块。

替代 Ablesci 的 curl+cookie+browser 级联方案。EasyScholar 提供公开 API，
JSON 响应，无需反爬处理。速率限制：每秒最多 1 次请求。

用法：
    from easyscholar_api import EasyScholarAPI
    
    api = EasyScholarAPI()
    result = api.query("Neurology")
    # → {"IF": 8.9, "quartile": "1区", "sci": "Q1", "esi": "神经科学",
    #     "found": True, "journal": "Neurology"}
    
    # 批量查询（自动限速）
    results = api.batch_query(["Neurology", "Front Immunol", "Brain"])
    
    # 直接查 journal_metrics.json 格式的 cache
    api.fill_journal_cache(cache_dict)  # 更新已存在的 cache
    api.backfill_cache(["Neurology", ...], existing_cache)  # 查+返回更新后的 cache
"""

import json
import os
import re
import ssl
import time
import urllib.request
import urllib.parse
import urllib.error

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

# ── 配置 ─────────────────────────────────────────────────────────────

BASE_URL = "https://www.easyscholar.cc/open/getPublicationRank"

# 速率限制：每秒最多 1 次请求（按 API 文档要求）
MIN_INTERVAL = 1.0


def create_ssl_context():
    """
    使用 certifi 的 CA 包创建 SSL 上下文。
    系统 CA 可能无法验证 easyscholar.cc 的证书链，certifi 通常可以。
    若 certifi 不可用，则退回到不验证（仅作最后兜底）。
    """
    if certifi:
        return ssl.create_default_context(cafile=certifi.where())
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def load_secret_key(secret_key=None):
    """从参数或环境变量读取 EasyScholar 密钥，避免代码内硬编码。"""
    key = secret_key or os.environ.get("EASYSCHOLAR_KEY", "")
    if not key:
        raise RuntimeError(
            "EASYSCHOLAR_KEY 未设置。请通过环境变量提供 EasyScholar API 密钥。"
        )
    return key


# ── 核心 API ────────────────────────────────────────────────────────

class RateLimiter:
    """全局速率限制器，保证跨调用不超过 1 req/s。"""
    
    def __init__(self, min_interval=MIN_INTERVAL):
        self._min_interval = min_interval
        self._last_call = 0.0
    
    def wait(self):
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()


class EasyScholarAPI:
    """
    EasyScholar 期刊指标查询 API。
    
    >>> api = EasyScholarAPI()
    >>> result = api.query("Neurology")
    >>> result["found"]
    True
    >>> result["IF"] > 0
    True
    """
    
    def __init__(self, secret_key=None, min_interval=MIN_INTERVAL):
        self.secret_key = load_secret_key(secret_key)
        self._limiter = RateLimiter(min_interval)
        self._cache = {}  # journal_name → parsed result (in-memory dedup)
    
    def query(self, journal_name):
        """
        查询单个期刊。
        
        返回 dict:
            journal: str      — 查询的期刊名
            IF: float|None    — SCI 影响因子（sciif）。None 表示无数据
            sciif5: float|None— 5年影响因子
            quartile: str|None— 新锐分区（从 API 的 xr 字段提取纯 X 区，如"1区"）
            sci: str|None     — SCI JCR 分区（Q1/Q2/Q3/Q4）
            esi: str|None     — ESI 学科分类
            jci: float|None   — 期刊引文指标
            found: bool       — 是否查到有效数据
            raw: dict         — 原始 API 响应数据
        """
        # 内存缓存
        if journal_name in self._cache:
            r = self._cache[journal_name].copy()
            r["_cached"] = True
            return r
        
        self._limiter.wait()
        
        params = urllib.parse.urlencode({
            'secretKey': self.secret_key,
            'publicationName': journal_name,
        })
        url = f"{BASE_URL}?{params}"
        
        try:
            req = urllib.request.Request(url)
            ctx = create_ssl_context()
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                body = resp.read().decode("utf-8")
            data = json.loads(body)
        except Exception as e:
            print(f"  ⚠️  EasyScholar API error ({journal_name}): {e}")
            result = self._make_fallback(journal_name)
            self._cache[journal_name] = result
            return result
        
        if data.get("code") != 200:
            print(f"  ⚠️  EasyScholar API returned code={data.get('code')} for {journal_name}")
            result = self._make_fallback(journal_name)
            self._cache[journal_name] = result
            return result
        
        all_data = data.get("data", {})
        official = all_data.get("officialRank", {})
        rank_all = official.get("all")
        
        if not rank_all or not isinstance(rank_all, dict):
            # 无数据（期刊不存在）
            result = self._make_fallback(journal_name)
            self._cache[journal_name] = result
            return result
        
        # 提取字段
        sciif_raw = rank_all.get("sciif")
        sciif5_raw = rank_all.get("sciif5")
        jci_raw = rank_all.get("jci")
        quartile_raw = rank_all.get("xr", "")  # 新锐分区，取代旧 sciBase
        sci = rank_all.get("sci", "")            # e.g. "Q1"
        esi = rank_all.get("esi", "")            # e.g. "神经科学与行为"
        
        result = {
            "journal": journal_name,
            "IF": self._parse_float(sciif_raw),
            "sciif5": self._parse_float(sciif5_raw),
            "jci": self._parse_float(jci_raw),
            "quartile": self._extract_zone(quartile_raw),
            "sci": sci.strip() if sci else None,
            "esi": esi.strip() if esi else None,
            "found": True,
            "raw": rank_all,
        }
        
        self._cache[journal_name] = result
        return result
    
    def batch_query(self, journal_names):
        """
        批量查询多个期刊（自动限速 1 req/s）。
        返回 {journal_name: result_dict, ...}
        """
        results = {}
        total = len(journal_names)
        for i, j in enumerate(journal_names):
            results[j] = self.query(j)
            if i < total - 1:
                self._limiter.wait()  # extra wait between queries
        return results
    
    def fill_journal_cache(self, cache_dict, journal_names=None):
        """
        用 EasyScholar 数据填充 journal_metrics.json 格式的 cache。
        
        Args:
            cache_dict: 现有 cache dict（会被原地更新）
            journal_names: 要查询的期刊列表。默认查所有 IF<=0 且不在 cache 中的期刊。
        
        返回更新的 cache_dict（也会修改入参）。
        """
        if journal_names is None:
            # 自动挑选需要查询的期刊
            journal_names = []
            for j, entry in cache_dict.items():
                if entry.get("IF", 0) == 0 or entry.get("IF") is None:
                    journal_names.append(j)
        
        for j in journal_names:
            res = self.query(j)
            if res["IF"] is not None:
                cache_dict[j] = {
                    "IF": res["IF"],
                    "quartile": res["quartile"],
                    "updated": time.strftime("%Y-%m-%d"),
                    "source": "easyscholar",
                }
            elif not res["found"] and j not in cache_dict:
                # 查不到但也是有效结果——标记 IF=0 避免反复查
                cache_dict[j] = {
                    "IF": 0,
                    "quartile": None,
                    "updated": time.strftime("%Y-%m-%d"),
                    "source": "easyscholar",
                }
            else:
                # 已存在 cache，但 IF=0 且 EasyScholar 也没查到
                pass
        
        return cache_dict
    
    def backfill_cache(self, journal_names, existing_cache):
        """
        查新期刊并合并到已有 cache 中。
        
        Args:
            journal_names: 待查的期刊名列表（确保不在 existing_cache 中）
            existing_cache: 已有 cache dict
        
        返回更新后的 cache dict
        """
        cache = dict(existing_cache)
        for j in journal_names:
            res = self.query(j)
            if res["IF"] is not None:
                cache[j] = {
                    "IF": res["IF"],
                    "quartile": res["quartile"],
                    "updated": time.strftime("%Y-%m-%d"),
                    "source": "easyscholar",
                }
                print(f"  ✅ ({j}): IF={res['IF']}, {res['quartile']}")
            else:
                # 未查到，但仍写入 cache 避免下次再查
                cache[j] = {
                    "IF": 0,
                    "quartile": None,
                    "updated": time.strftime("%Y-%m-%d"),
                    "source": "easyscholar",
                }
                print(f"  ⏭️  ({j}): 未查到")
        return cache
    
    def query_mg_hub_format(self, journal_name):
        """
        查询单个期刊，返回 MG-HUB backfill 兼容格式。
        (if_val: float|None, quartile: str|None)
        """
        res = self.query(journal_name)
        if not res["found"] or res["IF"] is None:
            return None, None
        return res["IF"], res["quartile"]
    
    @staticmethod
    def _parse_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _extract_zone(raw):
        """
        从分区字符串中提取纯 X 区（兼容旧 sciBase 与新 xr 字段）。

        '医学1区' → '1区'
        '新锐1区' → '1区'
        '1区'      → '1区'
        '暂无'     → None
        ''         → None
        """
        if not raw or not isinstance(raw, str):
            return None
        raw = raw.strip()
        m = re.search(r'([1-4]区)', raw)
        if m:
            return m.group(1)
        return None
    
    @staticmethod
    def _make_fallback(journal_name):
        return {
            "journal": journal_name,
            "IF": None,
            "sciif5": None,
            "jci": None,
            "quartile": None,
            "sci": None,
            "esi": None,
            "found": False,
            "raw": None,
        }


# ── CLI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    api = EasyScholarAPI()
    
    if len(sys.argv) < 2:
        print("Usage: python easyscholar_api.py <journal_name1> [journal_name2 ...]")
        print("  or:   python easyscholar_api.py --stdin   # read from stdin, one per line")
        sys.exit(1)
    
    if sys.argv[1] == "--stdin":
        journals = [line.strip() for line in sys.stdin if line.strip()]
    else:
        journals = sys.argv[1:]
    
    results = api.batch_query(journals)
    
    for j, r in results.items():
        if r["found"]:
            print(f"✅ {j}: IF={r['IF']}, 新锐分区={r['quartile']}, JCR={r['sci']}, ESI={r['esi']}")
        else:
            print(f"⏭️  {j}: 未查到")
