#!/usr/bin/env python3
"""指南立场结构化提取：逐份指南 → 分块提取 → 合并为一份维度立场。

输出：{out_dir}/stances/{key}.json  （可断点续跑，已存在则跳过）
"""
import argparse
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from llm_client import complete  # noqa: E402

DEFAULT_SCRATCH = os.environ.get(
    'MG_GUIDELINE_SCRATCH', '/Users/ruiluo/.hermes/cache/scratch/guidelines')
SCRATCH = DEFAULT_SCRATCH
TEXTS = os.path.join(SCRATCH, 'texts')

# 16 个比较维度（中英双语 key，输出中文）
DIMENSIONS = {
    "scope": "适用范围与人群",
    "diagnosis": "诊断标准与自身抗体/分型",
    "treatment_goal": "治疗目标与达标定义",
    "first_line": "一线治疗（溴吡斯的明/激素/免疫抑制剂选择）",
    "steroid": "糖皮质激素方案与减量、并发症管理",
    "ist": "免疫抑制剂推荐（AZA/TAC/MMF/CsA 等）",
    "rescue": "IVIG/PLEX/免疫吸附 指征与时机",
    "biologics": "FcRn 拮抗剂与补体抑制剂定位",
    "thymectomy": "胸腺切除与胸腺瘤处理",
    "crisis": "危象/危象前状态与呼吸管理",
    "ocular": "眼肌型 MG 处理",
    "special": "特殊人群（儿童/妊娠/老年/合并症）",
    "monitoring": "随访、结局量表与患者报告结局",
    "access": "医保、可及性与成本相关表述",
    "methodology": "证据分级与制定方法（GRADE/Delphi 等）",
    "other_local": "地域特有内容（本土化条款/登记/多学科）",
}

SYSTEM = """你是重症肌无力（MG）领域的循证医学专家，擅长把指南原文转成结构化立场卡。
要求：
1) 只依据给定文本，不要引入外部知识或推测；文本没写的维度直接省略该 key。
2) stance 用简体中文，≤110 字，写清"推荐什么/剂量/条件/推荐强度"，能具体就具体（数字、剂量、级别）。
3) quote 必须是原文的连续摘录（≤70 字），可含原文语言（中/英/德/日），用于人工核对，不得改写。
4) section 写该立场所在的小节标题或页码线索（若原文可见），≤30 字。
5) 严格输出 JSON，不要 markdown 代码块，不要任何解释文字。"""

DIM_LIST = "\n".join(f"- {k}: {v}" for k, v in DIMENSIONS.items())


def build_prompt(doc, chunk_idx, chunk_total, text):
    return f"""以下是一份指南/共识的第 {chunk_idx}/{chunk_total} 段原文。

【文献】{doc['name']}
【年份】{doc['year']}
【地区归类】{doc['region']}
【语言】{doc['lang']}

【维度清单】
{DIM_LIST}

请对**本段中确实出现**的维度输出立场卡。输出格式（严格 JSON）：
{{"scope": {{"stance": "...", "quote": "...", "section": "..."}}, ...}}

【原文】
{text}
"""


def parse_json(reply):
    if not reply:
        return None
    s = reply.strip()
    s = re.sub(r'^```(?:json)?\s*', '', s)
    s = re.sub(r'\s*```$', '', s).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r'\{[\s\S]*\}', s)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def chunk_text(text, size=13000, overlap=250):
    if len(text) <= size:
        return [text]
    out = []
    i = 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return out


MERGE_SYSTEM = """你是重症肌无力循证医学专家。给定同一份指南不同段落的立场卡，请合并成该指南的最终立场卡。
要求：
- 同一维度出现多条时，合并为一条最完整、最具体的 stance（≤140 字），保留剂量、条件、推荐强度等硬信息。
- quote 只能从输入的 quote 里**原样选一条**最有代表性的（不得改写、不得拼接新句）。
- section 从输入中选一条。
- 维度没有内容就省略该 key。
- 严格输出 JSON，不要代码块。"""


def merge_prompt(doc, parts):
    return f"""【文献】{doc['name']}（{doc['year']}，{doc['region']}）

以下是分段提取结果：
{json.dumps(parts, ensure_ascii=False, indent=1)}

请合并为该指南的最终立场卡，输出格式：
{{"scope": {{"stance": "...", "quote": "...", "section": "..."}}, ...}}
"""


def extract_mg_section(text):
    """从中国罕见病诊疗指南（多病种合集）里切出 MG 章节。"""
    idx = [m.start() for m in re.finditer('重症肌无力', text)]
    if not idx:
        return text[:60000]
    # 找最后一个"重症肌无力"独立标题行附近，取该标题到下一个疾病标题之间的内容
    head = idx[0]
    return text[max(0, head - 200):head + 60000]


def load_docs(scratch=None):
    scratch = scratch or SCRATCH
    docs = json.load(open(os.path.join(scratch, 'docs.json')))
    overrides = {'g31': 'china'}  # 中国药房/中国专家共识
    for d in docs:
        if d['key'] in overrides:
            d['region'] = overrides[d['key']]
    return docs


def main():
    global SCRATCH, TEXTS
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(SCRATCH, 'stances'))
    ap.add_argument('--docs', default='', help='只处理指定 key，逗号分隔')
    ap.add_argument('--scratch', default=DEFAULT_SCRATCH, help='语料与中间产物目录')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()
    SCRATCH = args.scratch
    TEXTS = os.path.join(SCRATCH, 'texts')
    os.makedirs(args.out, exist_ok=True)
    docs = load_docs(SCRATCH)
    if args.docs:
        want = set(args.docs.split(','))
        docs = [d for d in docs if d['key'] in want]

    t0 = time.time()
    for d in docs:
        out = os.path.join(args.out, d['key'] + '.json')
        if os.path.exists(out) and not args.force:
            print(f"[skip] {d['key']} 已有", flush=True)
            continue
        path = os.path.join(TEXTS, d['key'] + '.txt')
        text = open(path, encoding='utf-8').read()
        if d['key'] == 'g06':
            text = extract_mg_section(text)
        text = re.sub(r'[ \t]+', ' ', text).strip()
        chunks = chunk_text(text)[:8]
        parts = []
        for i, c in enumerate(chunks, 1):
            reply = complete(build_prompt(d, i, len(chunks), c), system=SYSTEM,
                             temperature=0.1, max_tokens=3500)
            obj = parse_json(reply)
            if obj is None:
                print(f"  [warn] {d['key']} chunk {i} JSON 解析失败", flush=True)
                continue
            parts.append(obj)
        if not parts:
            print(f"  [fail] {d['key']} 无任何有效提取", flush=True)
            continue
        if len(parts) == 1:
            stance = parts[0]
        else:
            merged = complete(merge_prompt(d, parts), system=MERGE_SYSTEM,
                              temperature=0.1, max_tokens=4000)
            stance = parse_json(merged) or parts[0]
        rec = {'key': d['key'], 'name': d['name'], 'year': d['year'],
               'region': d['region'], 'lang': d['lang'], 'stance': stance,
               'chunks': len(chunks), 'extracted_chars': len(text)}
        json.dump(rec, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"[ok] {d['key']} dims={len(stance)} chunks={len(chunks)} "
              f"({time.time()-t0:.0f}s)", flush=True)


if __name__ == '__main__':
    main()
