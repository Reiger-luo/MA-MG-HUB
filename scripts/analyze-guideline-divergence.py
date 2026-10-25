#!/usr/bin/env python3
"""中外指南/共识差异归纳（10 点）。

输入：{scratch}/stances/*.json（由 guideline-stance-extract.py 生成）
流程：
  1. 按维度把中国侧与国际侧立场卡分别喂给 reasoner，抽取该维度上的实质差异；
  2. 汇总所有维度差异，reasoner 排序合并为最重要的 10 点；
  3. 代码回验：doc key 是否存在、region 是否与所述阵营一致、quote 是否能在原文中逐字命中；
  4. 写 data/guideline-divergence.json。
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'common'))
from llm_client import complete, DEFAULT, REASONER  # noqa: E402
from guidelineLabels import short_name  # noqa: E402

# g01–gNN 是语料内部代号，页面上必须换成「中国 2025 MG 指南」这类可读短名。
# 只替换前面是非词字符、后面不是字母数字的形态，避免误伤 gMG / MgG23 之类。
GCODE_RE = re.compile(r'\bg(\d{2})(?![0-9a-zA-Z])')


def humanize_codes(text, key_short):
    """把正文里的 gNN 代号替换成可读短名；未知代号原样保留以便排查。"""

    def sub(match):
        key = 'g' + match.group(1)
        return key_short.get(key, key)

    return GCODE_RE.sub(sub, str(text or ''))

DEFAULT_SCRATCH = os.environ.get(
    'MG_GUIDELINE_SCRATCH', '/Users/ruiluo/.hermes/cache/scratch/guidelines')

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

DIM_SYSTEM = """你是重症肌无力循证医学与指南方法学专家。给定同一维度上「中国指南/共识」与「国际指南/共识」的结构化立场卡，
请找出**实质性差异**（推荐强度、具体方案、剂量、指征边界、是否覆盖、本土化条款的不同），忽略措辞差异。
要求：
1) 只依据给定立场卡，不得引入外部知识；没有实质差异就输出空数组；
2) 每条差异的 china_docs / intl_docs 只能使用给定的 doc key；
3) 输出简体中文，最多 4 条，按重要性排序；
4) 严格输出 JSON，不要代码块：
{"differences":[{"aspect":"≤16字差异点","china":"≤110字：中国侧怎么说","international":"≤110字：国际侧怎么说","impact":"≤100字：对临床/医学事务的影响","confidence":"high|medium|low","china_docs":["g23"],"intl_docs":["g27"]}]}"""

TOP_SYSTEM = """你是医学事务战略分析专家。给定一批按维度抽取的「中国 vs 国际」指南差异条目，
请合并同类项并选出**对上市后医学部最重要的 10 点**，用于医学信息答疑、KOL 沟通和证据生成规划。
要求：
1) 10 条互不重复；优先选择会改变临床路径、影响产品定位/使用条件、或涉及可及性与安全性的差异；
2) 每条必须给出可追溯证据：evidence 数组只能引用给定条目里出现过的 doc key 与原文 quote（quote 原样复制，不得改写）；
3) china / international 字段写清双方立场，含剂量、推荐级别等硬信息；
4) 输出简体中文；严格输出 JSON，不要代码块：
{"top":[{"dimension":"维度名","title":"≤18字标题","china":"≤150字","international":"≤150字","clinical_impact":"≤130字：为什么重要","msl_action":"≤90字：医学部可执行动作","confidence":"high|medium|low","evidence":[{"doc":"g23","quote":"..."}]}]}
恰好 10 条，按重要性从高到低。"""


def robust_json(prompt, system, max_tokens=3000, tag=''):
    """按 chat → reasoner 顺序尝试，直到拿到可解析 JSON。

    reasoner 的 reasoning token 计入 max_tokens，输出预算不足时会返回空 content，
    因此这里显式升级预算并在全部失败时报错，而不是静默返回空结果。
    """
    attempts = [(DEFAULT, max_tokens), (REASONER, max_tokens * 4)]
    last = ''
    for model, mt in attempts:
        try:
            reply = complete(prompt, system=system, model=model, temperature=0.2, max_tokens=mt)
        except Exception as exc:  # noqa: BLE001
            last = f'{model} 调用异常: {exc}'
            print(f'  [retry] {tag} {last}', flush=True)
            continue
        obj = parse_json(reply)
        if obj is not None:
            return obj
        last = f'{model} 输出无法解析（len={len(reply or "")}）'
        print(f'  [retry] {tag} {last}', flush=True)
    raise RuntimeError(f'{tag} JSON 提取失败：{last}')


def load_stances(scratch):
    out = {}
    d = os.path.join(scratch, 'stances')
    for f in sorted(os.listdir(d)):
        if f.endswith('.json'):
            rec = json.load(open(os.path.join(d, f), encoding='utf-8'))
            rec.setdefault('short_name', short_name(rec.get('name', ''), rec.get('region', ''), rec.get('year', '')))
            out[rec['key']] = rec
    return out


def canon(s):
    """引文核对用规范化：NFKC + 去软连字符 + 只保留字母数字与汉字。

    PDF 抽取常见换行连字、en-dash/连字符混用、全角标点，直接字符串比对会误判为造假引文。
    """
    s = unicodedata.normalize('NFKC', s or '')
    s = s.replace('\u00ad', '').replace('\u2010', '').replace('\u2011', '')
    return re.sub(r'[^0-9a-z\u4e00-\u9fff]+', '', s.lower())


def verify_quote(quote, text_canon):
    """返回 ('exact'|'partial'|None)。

    exact   = 规范化后整段连续命中；
    partial = 要么前 70% 连续命中（PDF 跨页/换行连字导致尾部缺失），
              要么剔除数字后命中（PDF 上标引文序号被抽成正文数字）。
    """
    q = canon(quote)
    if not q:
        return None
    if q in text_canon:
        return 'exact'
    head = q[:max(24, int(len(q) * 0.7))]
    if head in text_canon:
        return 'partial'
    if len(q) >= 40:
        qd = re.sub(r'\d+', '', q)
        if qd and qd in re.sub(r'\d+', '', text_canon):
            return 'partial'
    return None


def norm(s):
    return re.sub(r'\s+', '', s or '')


def load_text(scratch, key):
    p = os.path.join(scratch, 'texts', key + '.txt')
    if not os.path.exists(p):
        return ''
    return norm(open(p, encoding='utf-8').read())


def dim_prompt(dim_key, dim_name, china_cards, intl_cards):
    def fmt(cards):
        return "\n".join(
            f"- {c['short_name']}（代号 {c['key']}）\n  立场：{c['stance']}\n  原文：{c['quote']}"
            for c in cards) or "（本侧无相关立场）"
    return (f"【维度】{dim_name} ({dim_key})\n\n"
            f"【中国指南/共识】\n{fmt(china_cards)}\n\n"
            f"【国际指南/共识】\n{fmt(intl_cards)}\n\n"
            f"请输出该维度上的实质差异（最多 4 条）。\n"
            f"描述里引用文献一律用上面的中文短名（如「中国 2025 MG 指南」），"
            f"不要写 g01/g23 这类代号；代号只放进 china_docs / intl_docs 字段。")


def top_prompt(all_diffs):
    lines = []
    for d in all_diffs:
        lines.append(f"- [{d['dimension']}] {d['aspect']}\n"
                     f"  中国：{d['china']}\n  国际：{d['international']}\n"
                     f"  影响：{d['impact']}\n"
                     f"  可用 doc key：中国 {d['china_docs']} / 国际 {d['intl_docs']}\n"
                     f"  可用原文 quote：{json.dumps(d['quotes'], ensure_ascii=False)}")
    return ("以下是按维度抽取的差异条目，请合并选出最重要的 10 点。\n"
            "china / international / clinical_impact / msl_action 里引用文献一律用中文短名，"
            "不要出现 g01、g23 这类代号；代号只写进 evidence[].doc。\n\n" + "\n".join(lines))


def parse_json(reply):
    if not reply:
        return None
    s = re.sub(r'^```(?:json)?\s*', '', reply.strip())
    s = re.sub(r'\s*```$', '', s).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r'[\{\[][\s\S]*[\}\]]', s)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def humanize_payload(payload, key_short, stances=None):
    """把产物里的 gNN 代号换成可读短名，并给语料/证据补 short_name。

    与 LLM 重跑解耦：命名规则调整后可以直接 --relabel-only 就地修正，不必再花钱归纳一遍。
    """
    texts = {}
    if stances:
        texts = {k: v.get('short_name', '') for k, v in stances.items()}

    for item in payload.get('divergences') or []:
        for field in ('title', 'china', 'international', 'clinical_impact', 'msl_action', 'dimension'):
            if item.get(field):
                item[field] = humanize_codes(item[field], key_short)
        for ev in item.get('evidence') or []:
            key = ev.get('doc')
            label = texts.get(key) or key_short.get(key) or ''
            if label:
                ev['short_name'] = label
            if ev.get('name'):
                ev['name'] = humanize_codes(ev['name'], key_short)

    for doc in payload.get('corpus') or []:
        label = texts.get(doc.get('key')) or key_short.get(doc.get('key')) or ''
        if label:
            doc['short_name'] = label
        if doc.get('name'):
            doc['name'] = humanize_codes(doc['name'], key_short)

    # 只统计面向读者的叙述字段；evidence[].doc 与 corpus[].key 是刻意保留的溯源代号
    narrative = []
    for item in payload.get('divergences') or []:
        narrative += [str(item.get(f) or '') for f in
                      ('title', 'china', 'international', 'clinical_impact', 'msl_action')]
        narrative += [str((ev or {}).get('short_name') or '') for ev in item.get('evidence') or []]
    narrative += [str(d.get('short_name') or '') for d in payload.get('corpus') or []]
    remaining = sum(len(GCODE_RE.findall(t)) for t in narrative)
    payload['label_style'] = 'human_short_names'
    return remaining


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scratch', default=DEFAULT_SCRATCH)
    ap.add_argument('--out', default=os.path.join(PROJECT_ROOT, 'data', 'guideline-divergence.json'))
    ap.add_argument('--reverify-only', action='store_true',
                    help='只对已有产物重跑引文回验（不调用 LLM），用于核对规则调整后的命中率')
    ap.add_argument('--relabel-only', action='store_true',
                    help='只把已有产物里的 gNN 代号换成可读短名（不调用 LLM）')
    args = ap.parse_args()

    stances = load_stances(args.scratch)
    print(f'载入立场卡 {len(stances)} 份', flush=True)
    key_short = {k: v.get('short_name') or short_name(v.get('name', ''), v.get('region', ''), v.get('year', ''))
                 for k, v in stances.items()}
    texts = {k: canon(load_text(args.scratch, k)) for k in stances}

    if args.relabel_only:
        payload = json.loads(open(args.out, encoding='utf-8').read())
        remaining = humanize_payload(payload, key_short, stances)
        payload['relabeled_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tmp = args.out + '.tmp'
        json.dump(payload, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(tmp, args.out)
        print(f'短名替换完成，残留代号 {remaining} 处')
        if remaining:
            for item in payload.get('divergences') or []:
                for ev in item.get('evidence') or []:
                    if GCODE_RE.search(ev.get('quote', '')):
                        print(f"  [注意] {item.get('id')} 引文内含代号形态：{ev.get('quote','')[:60]}")
        return

    if args.reverify_only:
        payload = json.loads(open(args.out, encoding='utf-8').read())
        total = verified = 0
        misses = []
        for item in payload.get('divergences') or []:
            for ev in item.get('evidence') or []:
                key = ev.get('doc')
                if key not in texts:
                    ev['quote_verified'] = False
                    ev['quote_match'] = 'none'
                    misses.append((key, ev.get('quote', '')))
                    total += 1
                    continue
                total += 1
                hit = verify_quote(ev.get('quote', ''), texts[key])
                ev['quote_verified'] = bool(hit)
                ev['quote_match'] = hit or 'none'
                if hit:
                    verified += 1
                else:
                    misses.append((key, ev.get('quote', '')))
        payload['quote_check'] = {'total': total, 'verified': verified,
                                  'rate': round(verified / total * 100, 1) if total else None}
        payload['reverified_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tmp = args.out + '.tmp'
        json.dump(payload, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(tmp, args.out)
        print(f'引文回验 {verified}/{total} ({payload["quote_check"]["rate"]}%)')
        for key, quote in misses:
            print(f'  [miss] {key}: {quote[:100]}')
        return

    def cards(dim):
        cn, it = [], []
        for k, rec in stances.items():
            st = (rec.get('stance') or {}).get(dim)
            if not st:
                continue
            row = {'key': k, 'name': rec['name'], 'stance': st.get('stance', ''),
                   'quote': st.get('quote', ''), 'section': st.get('section', '')}
            (cn if rec['region'] == 'china' else it).append(row)
        return cn, it

    # Phase 1：维度级差异
    all_diffs = []
    t0 = time.time()
    for dim, dim_name in DIMENSIONS.items():
        cn, it = cards(dim)
        if not cn or not it:
            print(f'  [skip] {dim}: 中国 {len(cn)} / 国际 {len(it)}（一侧为空）', flush=True)
            continue
        obj = robust_json(dim_prompt(dim, dim_name, cn, it), DIM_SYSTEM,
                          max_tokens=3000, tag=dim)
        diffs = (obj or {}).get('differences') or []
        for d in diffs:
            cn_keys = [k for k in (d.get('china_docs') or []) if k in stances]
            it_keys = [k for k in (d.get('intl_docs') or []) if k in stances]
            quotes = []
            for k in cn_keys + it_keys:
                st = (stances[k].get('stance') or {}).get(dim) or {}
                if st.get('quote'):
                    quotes.append({'doc': k, 'quote': st['quote'], 'section': st.get('section', '')})
            all_diffs.append({
                'dimension': dim_name, 'dimension_key': dim,
                'aspect': d.get('aspect', ''), 'china': d.get('china', ''),
                'international': d.get('international', ''), 'impact': d.get('impact', ''),
                'confidence': d.get('confidence', 'medium'),
                'china_docs': cn_keys, 'intl_docs': it_keys, 'quotes': quotes,
            })
        print(f'  [ok] {dim}: {len(diffs)} 条差异 ({time.time()-t0:.0f}s)', flush=True)

    print(f'\n维度级差异合计 {len(all_diffs)} 条，开始 Top10 归纳', flush=True)
    if not all_diffs:
        raise SystemExit('维度级差异为 0，说明提取或比对失败， refusing to synthesize')
    obj = robust_json(top_prompt(all_diffs), TOP_SYSTEM, max_tokens=6000, tag='top10')
    top = (obj or {}).get('top') or []
    if len(top) < 5:
        raise SystemExit(f'Top10 归纳失败，仅 {len(top)} 条')

    # Phase 2：回验
    verified_items = []
    quote_total = quote_ok = 0
    for i, t in enumerate(top[:10], 1):
        ev = []
        for e in (t.get('evidence') or [])[:6]:
            key = e.get('doc')
            quote = (e.get('quote') or '').strip()
            if key not in stances or not quote:
                continue
            quote_total += 1
            hit = verify_quote(quote, texts[key])
            if hit:
                quote_ok += 1
            else:
                print(f"  [quote-miss] {key}: {quote[:80]}", flush=True)
            ev.append({
                'doc': key,
                'short_name': key_short.get(key, ''),
                'name': re.sub(r'\.(pdf|docx)$', '', stances[key]['name']),
                'year': stances[key]['year'],
                'region': stances[key]['region'],
                'quote': quote,
                'quote_verified': bool(hit),
                'quote_match': hit or 'none',
            })
        verified_items.append({
            'id': f'gd{i:02d}',
            'dimension': t.get('dimension', ''),
            'title': t.get('title', '')[:24],
            'china': t.get('china', ''),
            'international': t.get('international', ''),
            'clinical_impact': t.get('clinical_impact', ''),
            'msl_action': t.get('msl_action', ''),
            'confidence': t.get('confidence') if t.get('confidence') in ('high', 'medium', 'low') else 'medium',
            'evidence': ev,
        })

    corpus = [{'key': k, 'short_name': key_short.get(k, ''),
               'name': re.sub(r'\.(pdf|docx)$', '', v['name']), 'year': v['year'],
               'region': v['region'], 'lang': v['lang'], 'dims': len(v.get('stance') or {})}
              for k, v in sorted(stances.items())]
    out = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'analysis_model': 'guideline-divergence-llm',
        'method': 'LLM 逐份指南结构化立场提取（16 维度）→ 维度级中外差异 → LLM 归纳 Top10；'
                  '引文按 NFKC 规范化后回验原文（exact/partial），未命中者标记 quote_verified=false',
        'quote_check': {'total': quote_total, 'verified': quote_ok,
                        'rate': round(quote_ok / quote_total * 100, 1) if quote_total else None},
        'corpus_count': {'total': len(corpus),
                         'china': sum(1 for c in corpus if c['region'] == 'china'),
                         'international': sum(1 for c in corpus if c['region'] == 'international'),
                         'taiwan': sum(1 for c in corpus if c['region'] == 'taiwan')},
        'dimension_diff_count': len(all_diffs),
        'corpus': corpus,
        'divergences': verified_items,
    }
    remaining = humanize_payload(out, key_short, stances)
    print(f'短名替换后残留代号 {remaining} 处', flush=True)
    tmp = args.out + '.tmp'
    json.dump(out, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, args.out)
    print(f"\n写入 {args.out}")
    print(f"引文回验 {quote_ok}/{quote_total} ({out['quote_check']['rate']}%)")
    for it in verified_items:
        print(f"  [{it['id']}] {it['title']}  证据 {len(it['evidence'])} 条 ({it['confidence']})")


if __name__ == '__main__':
    main()
