#!/usr/bin/env python3
"""中外证据主题差异分析（近 N 天新增文献）。

流程：
  1. 从 data/literature-recent.js 取窗口内新增文献，按 china_related 分中外两组；
  2. LLM 逐篇标注主题（受控词表）+ 子主题 + 研究角度；
  3. 代码聚合主题 × 中外计数（不采信 LLM 自报数字）；
  4. reasoner 输出最大 5 点主题差异，PMID 必须来自语料；
  5. 代码回验 PMID 归属与计数，写 data/china-foreign-themes.json。
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
from llm_client import complete, DEFAULT, REASONER  # noqa: E402

# 受控主题词表（医学事务可解读口径）
TOPICS = {
    "diagnosis_typing": "诊断与自身抗体分型",
    "prognosis_activity": "疾病活动度与预后预测",
    "first_line_steroid": "一线治疗与激素管理",
    "ist_sequential": "免疫抑制剂与序贯/联合方案",
    "fcrn": "FcRn 拮抗剂",
    "complement": "补体抑制剂",
    "novel_cellular": "新型细胞/靶向疗法（CAR-T、双抗等）",
    "thymectomy_surgery": "胸腺切除与外科处理",
    "crisis_respiratory": "危象与呼吸管理",
    "safety_drug": "安全性与用药管理",
    "rwe_registry": "真实世界研究与登记",
    "pro_qol": "患者报告结局与生活质量",
    "heor_access": "卫生经济与可及性",
    "mechanism": "机制与转化医学",
    "special_population": "特殊人群（儿童/妊娠/老年/合并症）",
    "guideline_method": "指南共识与方法学",
    "burden_epidemiology": "疾病负担与流行病学",
    "other": "其他",
}
TOPIC_LIST = "\n".join(f"- {k}: {v}" for k, v in TOPICS.items())

LABEL_SYSTEM = """你是重症肌无力（MG）文献分类专家。给定若干篇文献的标题与摘要，为每篇分配：
1) topic：从受控词表中选**最贴切的一个** key（只能用给定 key）；
2) subtopic：中文短标签（≤8 字），描述这篇的具体切入点；
3) angle：研究角度，只能是以下之一：疗效 / 安全性 / 机制 / 诊断 / 真实世界 / 卫生经济 / 患者结局 / 管理流程 / 方法学 / 综述述评。
只依据标题与摘要判断。严格输出 JSON 数组，不要代码块，不要解释：
[{"pmid": "...", "topic": "...", "subtopic": "...", "angle": "..."}]"""


def label_prompt(items):
    lines = []
    for it in items:
        lines.append(f"[{it['pmid']}] ({'中国' if it['china'] else '国际'} | {it['study_type']} | {it['journal']})\n"
                     f"标题：{it['title']}\n摘要：{it['abstract']}")
    return (f"【受控主题词表】\n{TOPIC_LIST}\n\n"
            f"请为下列 {len(items)} 篇文献打标：\n\n" + "\n\n".join(lines))


# 一个月窗口不足以支撑长期结构判断；这些词一旦出现就替换成窗口限定表述。
# 只靠 prompt 约束不可靠，因此在落盘前由代码强制改写。
LONG_TERM_TERMS = {
    '结构性缺失': '本窗口未见',
    '结构性差异': '本窗口差异',
    '长期不足': '本月未见新增',
    '完全缺位': '本月未见新增',
    '证据缺位': '本月未见新增',
    '证据空白': '本月未见相关发表',
    '安全空白': '本月未见相关发表',
    '完全空白': '本月未见相关发表',
    '空白': '本月未见相关发表',
    '缺位': '本月未见新增',
    '代差': '本窗口差异',
    '落后': '本月滞后',
    '完全没有': '本月未见',
}
NARRATIVE_FIELDS = ('theme', 'china_focus', 'global_focus', 'why_it_matters', 'msl_action')
# 篇数只由代码聚合后经界面展示；模型在叙述里再写一遍必然与聚合值冲突
COUNT_CLAIM_RE = re.compile(r'(?:仅|共|计)?\s*\d+\s*篇')


def strip_count_claims(text):
    """删掉叙述里模型自报的篇数，返回（文本, 删除处数）。"""
    value = str(text or '')
    hits = len(COUNT_CLAIM_RE.findall(value))
    if not hits:
        return value, 0
    value = COUNT_CLAIM_RE.sub('', value)
    value = re.sub(r'\s{2,}', ' ', value)
    value = re.sub(r'侧(?=[（(])', '侧', value)
    return value.strip(), hits


def soften_narrative(text):
    """把长期性判断词改写为窗口限定表述，返回（改写后文本, 命中次数）。"""
    value = str(text or '')
    hits = 0
    for bad, good in LONG_TERM_TERMS.items():
        if bad in value:
            hits += value.count(bad)
            value = value.replace(bad, good)
    return value, hits


def normalize_narrative(dv, field):
    """统一叙述口径：去长期判断词 + 去模型自报篇数。"""
    value, tone_hits = soften_narrative(dv.get(field))
    value, count_hits = strip_count_claims(value)
    return value, tone_hits, count_hits


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
    m = re.search(r'[\[\{][\s\S]*[\]\}]', s)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def load_recent(path):
    s = open(path, encoding='utf-8').read()
    return json.loads(s[s.index('['):].rstrip().rstrip(';'))


def parse_entry_date(v):
    if not v:
        return None
    m = re.match(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', v.strip())
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def build_corpus(recent, days):
    dated = [(parse_entry_date(a.get('entry_date')), a) for a in recent]
    dated = [(dt, a) for dt, a in dated if dt]
    if not dated:
        raise SystemExit('无可用 entry_date')
    latest = max(dt for dt, _ in dated)
    cutoff = latest - timedelta(days=days)
    corpus = []
    for dt, a in dated:
        if dt < cutoff:
            continue
        abstract = re.sub(r'\s+', ' ', a.get('abstract') or '').strip()
        corpus.append({
            'pmid': str(a.get('pmid') or ''),
            'title': re.sub(r'\s+', ' ', a.get('title') or '').strip(),
            'abstract': abstract[:1100],
            'journal': a.get('journal') or '',
            'study_type': (a.get('study_types') or ['-'])[0],
            'evidence_level': a.get('evidence_level') or '',
            'china': bool(a.get('china_related')),
            'entry_date': dt.strftime('%Y-%m-%d'),
            'url': a.get('url') or f"https://pubmed.ncbi.nlm.nih.gov/{a.get('pmid')}/",
        })
    corpus = [c for c in corpus if c['pmid']]
    return corpus, cutoff, latest


def label_corpus(corpus, batch=6, log=print):
    labels = {}
    for i in range(0, len(corpus), batch):
        items = corpus[i:i + batch]
        reply = complete(label_prompt(items), system=LABEL_SYSTEM, temperature=0.1, max_tokens=2000)
        arr = parse_json(reply)
        got = 0
        if isinstance(arr, list):
            for row in arr:
                pmid = str(row.get('pmid') or '')
                if pmid not in {it['pmid'] for it in items}:
                    continue
                topic = row.get('topic') if row.get('topic') in TOPICS else 'other'
                labels[pmid] = {
                    'topic': topic,
                    'subtopic': re.sub(r'\s+', ' ', str(row.get('subtopic') or ''))[:12],
                    'angle': str(row.get('angle') or '')[:8],
                }
                got += 1
        if got < len(items):
            log(f'  [warn] 批次 {i//batch+1} 只标出 {got}/{len(items)}')
        for it in items:
            labels.setdefault(it['pmid'], {'topic': 'other', 'subtopic': '', 'angle': ''})
    return labels


SYNTH_SYSTEM = """你是重症肌无力领域的医学事务战略分析专家。给定**近一个月**中外新增文献的主题分布与标题清单，
你要归纳中外在这个窗口内**发表重心上的 5 点不同**，用于上市后医学部（MSL/医学信息/证据生成）判断"这个月中国和国际各在发什么"。

【最关键约束：这是一个月窗口的趋势观察，不是长期结构判断】
一个月的文献量很小（几十篇），某侧本月没有发表某个主题，**不代表该国在该主题上长期空白或落后**。
因此：
- 禁用"空白""缺位""代差""落后""完全没有""长期不足""结构性缺失"这类长期性判断词；
- 一律用窗口限定表述："本月未见新增""本窗口内未检索到""本月集中在""本月尚未见"；
- 某侧篇数为 0 时，要写成"本月该侧无相关发表"，并明确这只能说明发表节奏，不能推断研究能力或证据储备；
- why_it_matters 只说这个窗口对医学部工作节奏的影响（例如"若连续数月如此，值得启动本地证据生成"），
  不要说成已经存在的证据缺口；
- confidence 只在两侧都有足够篇数支撑对比时给 high；一侧为 0 篇时最高只能给 medium。

【其他要求】
1) 差异要落在研究重心、方法学取向、人群覆盖、终点选择、可及性视角或证据成熟度上，不是"某侧多 2 篇"这种噪声；
2) 每条必须能落到具体文献：china_pmids 与 non_china_pmids 只能从给定清单里挑选；某侧本月确实没有文献时用空数组，并在对应 focus 里写明"本月无相关发表"；
3) 不得编造 PMID；不得引用清单外的文献；不得把个案报告写成有代表性的研究趋势；
3b) **叙述里不要写篇数**（如"4篇""仅1篇"）：篇数由界面按代码聚合值展示，你写的数字会与聚合值冲突并被删除。
    需要表达数量对比时用"集中""以…为主""仅见""尚无"这类定性表述；
4) 输出简体中文，立场克制，只写清单支持的内容；
5) 严格输出 JSON，不要代码块：
{"divergences":[{"id":"cd1","theme":"≤14字主题名","china_focus":"≤90字：本月中国侧在发什么（或本月无相关发表）","global_focus":"≤90字：本月国际侧在发什么（或本月无相关发表）","divergence_type":"本月关注点|本月方法学取向|本月人群覆盖|本月终点取向|本月可及性视角|本月证据成熟度","why_it_matters":"≤120字：对本月工作节奏意味着什么，含窗口限定","msl_action":"≤80字：可执行动作","confidence":"high|medium|low","china_pmids":["..."],"non_china_pmids":["..."]}]}
恰好 5 条，按本月重要性从高到低排序。"""


def synth_prompt(agg, corpus):
    by_pmid = {c['pmid']: c for c in corpus}
    lines = []
    lines.append("【主题 × 中外 计数】（代码统计，权威）")
    for topic, row in sorted(agg.items(), key=lambda kv: -(kv[1]['china'] + kv[1]['non_china'])):
        lines.append(f"- {TOPICS[topic]}: 中国 {row['china']} 篇 / 非中国 {row['non_china']} 篇")
    lines.append("\n【各主题代表文献（标题 + 角度）】")
    for topic, row in sorted(agg.items(), key=lambda kv: -(kv[1]['china'] + kv[1]['non_china'])):
        lines.append(f"\n## {TOPICS[topic]} ({topic})")
        for camp in ('china_pmids', 'non_china_pmids'):
            tag = '中国' if camp == 'china_pmids' else '非中国'
            pmids = row[camp][:14]
            if not pmids:
                lines.append(f"  [{tag}] 本窗口无文献")
                continue
            lines.append(f"  [{tag}] {len(row[camp])} 篇：")
            for p in pmids:
                c = by_pmid.get(p, {})
                ang = (c.get('label') or {}).get('angle', '')
                sub = (c.get('label') or {}).get('subtopic', '')
                lines.append(f"    - {p} | {ang}/{sub} | {c.get('title','')[:150]} ({c.get('journal','')}, {c.get('study_type','')})")
    return "请据此产出中外主题差异 Top 5。\n\n" + "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=30)
    ap.add_argument('--in', dest='src', default=os.path.join(PROJECT_ROOT, 'data', 'literature-recent.js'))
    ap.add_argument('--out', default=os.path.join(PROJECT_ROOT, 'data', 'china-foreign-themes.json'))
    ap.add_argument('--batch', type=int, default=6)
    ap.add_argument('--skip-if-current', action='store_true',
                    help='窗口与语料未变化时直接退出（周更调用，避免重复计费）')
    args = ap.parse_args()

    recent = load_recent(args.src)
    corpus, cutoff, latest = build_corpus(recent, args.days)
    print(f"窗口 {cutoff:%Y-%m-%d} ~ {latest:%Y-%m-%d}  文献 {len(corpus)} 篇 "
          f"(中国 {sum(1 for c in corpus if c['china'])} / 国际 {sum(1 for c in corpus if not c['china'])})", flush=True)

    if args.skip_if_current and os.path.exists(args.out):
        try:
            previous = json.loads(open(args.out, encoding='utf-8').read())
        except Exception:
            previous = {}
        if (previous.get('window_end') == latest.strftime('%Y-%m-%d')
                and previous.get('total_count') == len(corpus)):
            print('窗口与语料未变化，跳过重算（--skip-if-current）', flush=True)
            return

    t0 = time.time()
    labels = label_corpus(corpus, batch=args.batch)
    print(f"标注完成 {len(labels)} 篇，用时 {time.time()-t0:.0f}s", flush=True)
    for c in corpus:
        c['label'] = labels.get(c['pmid'], {'topic': 'other', 'subtopic': '', 'angle': ''})

    # 代码聚合
    agg = {}
    for c in corpus:
        t = c['label']['topic']
        row = agg.setdefault(t, {'china': 0, 'non_china': 0, 'china_pmids': [], 'non_china_pmids': []})
        if c['china']:
            row['china'] += 1
            row['china_pmids'].append(c['pmid'])
        else:
            row['non_china'] += 1
            row['non_china_pmids'].append(c['pmid'])

    # reasoner 的 reasoning token 计入 max_tokens，预算不足会返回空 content；
    # 因此按 chat → reasoner（4x 预算）依次尝试，全部失败才报错。
    obj = None
    prompt = synth_prompt(agg, corpus)
    for model, mt in ((DEFAULT, 4000), (REASONER, 16000)):
        reply = complete(prompt, system=SYNTH_SYSTEM, model=model,
                         temperature=0.3, max_tokens=mt)
        obj = parse_json(reply)
        if obj and obj.get('divergences'):
            print(f'差异归纳模型：{model}', flush=True)
            break
        print(f'  [retry] {model} 输出不可用（len={len(reply or "")}）', flush=True)
    if not obj or not obj.get('divergences'):
        raise SystemExit('synthesis 失败：模型未返回可用 divergences')

    valid = {c['pmid']: c for c in corpus}
    counters = {'tone': 0, 'counts': 0}
    divergences = []
    for i, dv in enumerate(obj['divergences'][:5], 1):
        cn = [p for p in dv.get('china_pmids') or [] if p in valid and valid[p]['china']]
        nc = [p for p in dv.get('non_china_pmids') or [] if p in valid and not valid[p]['china']]
        tone_hits = count_hits = 0
        softened = {}
        for field in NARRATIVE_FIELDS:
            value, t_hits, c_hits = normalize_narrative(dv, field)
            softened[field] = value
            tone_hits += t_hits
            count_hits += c_hits
        if tone_hits or count_hits:
            print(f"  [叙述校正] cd{i} 长期措辞 {tone_hits} 处 / 自报篇数 {count_hits} 处", flush=True)
        counters['tone'] += tone_hits
        counters['counts'] += count_hits
        divergences.append({
            'id': f'cd{i}',
            'theme': (softened['theme'] or '')[:20],
            'china_focus': softened['china_focus'],
            'global_focus': softened['global_focus'],
            'divergence_type': str(dv.get('divergence_type') or '本月关注点'),
            'why_it_matters': softened['why_it_matters'],
            'msl_action': softened['msl_action'],
            # 一侧本窗口 0 篇时，只能得出"本月未见"，不得给 high
            'confidence': ('medium'
                           if not cn or not nc
                           else (dv.get('confidence')
                                 if dv.get('confidence') in ('high', 'medium', 'low') else 'medium')),
            'china_count': len(cn),
            'non_china_count': len(nc),
            'china_pmids': cn,
            'non_china_pmids': nc,
            'china_refs': [{'pmid': p, 'title': valid[p]['title'], 'journal': valid[p]['journal'],
                            'url': valid[p]['url'], 'topic': valid[p]['label']['topic'],
                            'angle': valid[p]['label']['angle']} for p in cn],
            'non_china_refs': [{'pmid': p, 'title': valid[p]['title'], 'journal': valid[p]['journal'],
                                'url': valid[p]['url'], 'topic': valid[p]['label']['topic'],
                                'angle': valid[p]['label']['angle']} for p in nc],
        })

    out = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'window_start': cutoff.strftime('%Y-%m-%d'),
        'window_end': latest.strftime('%Y-%m-%d'),
        'window_days': args.days,
        'window_basis': 'entry_date（PubMed 入库/新增窗口）',
        'source': 'PubMed abstract 全量周更产物 data/literature-recent.js',
        'method': 'LLM 受控主题标注（deepseek-chat）+ 代码聚合计数 + reasoner 差异归纳；PMID 与计数均由代码回验',
        'analysis_model': 'china-foreign-theme-divergence',
        'scope_note': (
            '本模块只描述该窗口内中外新增文献的发表重心，属于趋势观察；'
            '某侧本月 0 篇只说明本月未见发表，不代表该国在该主题上长期空白或证据落后。'
            '要判断长期差异需跨月累积同一口径的结果。'
        ),
        'label_convention': '两侧标签统一为「中国」与「国际」',
        'tone_guard': {
            'rule': '长期性判断词改写为窗口限定表述；模型自报篇数一律删除，篇数只由代码聚合后经界面展示',
            'long_term_terms_rewritten': counters['tone'],
            'model_count_claims_removed': counters['counts'],
        },
        'total_count': len(corpus),
        'china_total': sum(1 for c in corpus if c['china']),
        'non_china_total': sum(1 for c in corpus if not c['china']),
        'topic_counts': {TOPICS.get(k, k): {'china': v['china'], 'non_china': v['non_china'],
                                            'china_pmids': v['china_pmids'],
                                            'non_china_pmids': v['non_china_pmids']}
                         for k, v in agg.items()},
        'divergences': divergences,
    }
    tmp = args.out + '.tmp'
    json.dump(out, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, args.out)
    print(f"\n写入 {args.out}")
    for dv in divergences:
        print(f"  [{dv['id']}] {dv['theme']}  中国 {dv['china_count']} / 非中国 {dv['non_china_count']}  ({dv['confidence']})")


if __name__ == '__main__':
    main()
