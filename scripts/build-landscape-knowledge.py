#!/usr/bin/env python3
"""生成诊治格局的「诊疗现状」与「临床问题」两个知识产物。

内容原则：
- 指南立场只引用本地 guideline-divergence.json 已回验语料（gNN 短名）；
- 文献引文不手写标题/期刊，统一按 PMID 从 literature-full.json 反查，查不到即报错（fail closed）；
- 每条陈述带角标引用，中文指南与指南类文献不生成链接，英文 PMID 文献生成 PubMed 链接。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL_PATH = ROOT / "data" / "literature-full.json"
DIVERGENCE_PATH = ROOT / "data" / "guideline-divergence.json"
OUT_CHAPTERS = ROOT / "data" / "treatmentChapters.js"
OUT_QUESTIONS = ROOT / "data" / "clinicalQuestions.js"

full = json.loads(FULL_PATH.read_text())
articles = full if isinstance(full, list) else full.get("items") or full.get("articles") or []
BY_PMID = {str(a.get("pmid")): a for a in articles}
divergence = json.loads(DIVERGENCE_PATH.read_text())
GUIDELINES = {c["key"]: c for c in divergence["corpus"]}


def A(pmid: str) -> dict:
    """文献引用：按 PMID 反查本地库，查不到直接报错。"""
    article = BY_PMID.get(str(pmid))
    if not article:
        raise SystemExit(f"PMID {pmid} 不在本地文献库，禁止虚构引用")
    return {"kind": "article", "pmid": str(pmid)}


def G(key: str) -> dict:
    if key not in GUIDELINES:
        raise SystemExit(f"指南代号 {key} 不在语料库")
    return {"kind": "guideline", "key": key}


def build_refs(items: list[dict], used_keys: list[str]) -> list[dict]:
    refs = []
    for idx, item in enumerate(items, start=1):
        if item["kind"] == "guideline":
            g = GUIDELINES[item["key"]]
            refs.append({
                "n": idx,
                "kind": "guideline",
                "text": f"{g['short_name']}（{g['year']}）",
                "lang": "zh" if g["region"] in ("china", "taiwan") else "en",
            })
        else:
            a = BY_PMID[item["pmid"]]
            year = str(a.get("pub_date") or a.get("entry_date") or "")[:4]
            refs.append({
                "n": idx,
                "kind": "article",
                "pmid": item["pmid"],
                "text": f"{a.get('title', '')}. {a.get('journal', '')}. {year}.",
                "url": a.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{item['pmid']}/",
                "lang": "en",
            })
    return refs


def collect_keys(statements: list[dict], branches: list[dict]) -> list[str]:
    keys = []
    for st in statements:
        for r in st.get("refs", []):
            keys.append(r["pmid"] if r["kind"] == "article" else r["key"])
    for br in branches:
        for side in br["sides"]:
            for r in side.get("refs", []):
                keys.append(r["pmid"] if r["kind"] == "article" else r["key"])
    seen = []
    for k in keys:
        if k not in seen:
            seen.append(k)
    return seen


def finalize(body: dict) -> dict:
    """把 statements/branches 里的引用键收集为带编号的参考文献表。"""
    statements = body.get("statements", [])
    branches = body.get("branches", [])
    keys = collect_keys(statements, branches)
    items = []
    for k in keys:
        items.append(G(k) if k in GUIDELINES else A(k))
    ref_map = {}
    refs = build_refs(items, keys)
    for item, ref in zip(items, refs):
        key = item["pmid"] if item["kind"] == "article" else item["key"]
        ref_map[key] = ref["n"]
    body["refs"] = refs
    body["ref_map"] = ref_map
    return body


CHAPTERS = [
    {
        "id": "goals",
        "title": "治疗目标与达标定义",
        "summary": "MSE/MMS 已成中外共同底线，分歧集中在激素剂量阈值与是否追求停药缓解。",
        "statements": [
            {"text": "中国 2025 MG 指南把最小症状表达（MSE）设为治疗目标，即 MG-ADL 0 或 1 分，同时限定药物不良反应不超过 CTCAE 1 级；部分中国文件另把泼尼松 5~10 mg/d 写进达标条件。", "refs": [G("g23"), G("g33")]},
            {"text": "国际文件采用同一目标框架，但激素阈值更严：日本 2022、英国 2025 与国际 2026 管理目标共识都以泼尼松龙 ≤5 mg/d 作为达标条件。", "refs": [G("g09"), G("g27"), G("g28")]},
            {"text": "部分国际指南进一步把完全稳定缓解（CSR，停药缓解）列为理想目标；MGFA 2016 附录则只要求 MMS 或更好且副作用 ≤CTCAE 1 级，未设激素剂量阈值。", "refs": [G("g21"), G("g24"), G("g02")]},
        ],
        "branches": [
            {
                "topic": "达标时的激素剂量上限",
                "sides": [
                    {"label": "中国", "text": "2025 MG 指南允许泼尼松 5~10 mg/d 仍算达标；2026 临床治疗研究共识收紧到 ≤5 mg/d。", "refs": [G("g23"), G("g33")]},
                    {"label": "国际", "text": "日本、英国与国际 2026 共识统一按 ≤5 mg/d 执行；MGFA 2016 不设剂量阈值。", "refs": [G("g09"), G("g27"), G("g28"), G("g02")]},
                ],
            },
            {
                "topic": "是否把停药缓解列为目标",
                "sides": [
                    {"label": "中国", "text": "以 MMS/MSE 或更好加不良反应 ≤1 级为达标，未把停药缓解列为首要目标。", "refs": [G("g16"), G("g23")]},
                    {"label": "国际", "text": "比利时 2024 把 CSR 列为理想目标并允许稳定 2 年后减停；以色列 2025 把停药缓解、药物缓解或 MMS 并列为首选目标。", "refs": [G("g21"), G("g24")]},
                ],
            },
        ],
    },
    {
        "id": "steroid",
        "title": "糖皮质激素方案与减量",
        "summary": "减量节奏国际更慢、目标更低；真实世界的“靶向药助减激素”仍是观察性证据。",
        "statements": [
            {"text": "中国 2025 MG 指南建议每 2 周减 5 mg 或 0.1 mg/kg，减至 5~10 mg/d 维持或减停；眼肌型共识另给出隔日维持的递减方案。", "refs": [G("g23"), G("g22")]},
            {"text": "英国 2025 的阶梯更慢：每 2~4 周减 5 mg 至 20 mg，再减 2~2.5 mg 至 10 mg，之后每月减 1 mg，目标 5 mg/d；激素需求 ≥7 mg/d 即提示加用非激素免疫抑制。", "refs": [G("g27")]},
            {"text": "国际 2026 管理目标共识要求把激素减至 ≤10 mg/d、理想 ≤5 mg/d，必要时换药并密切监测恶化；以色列 2025 把最佳维持量定在 5~7.5 mg/d。", "refs": [G("g28"), G("g24")]},
            {"text": "真实世界队列观察到靶向治疗伴随激素减量，但多为单臂、小样本、短随访；激素相关并发症与减量的关系仍在积累证据。", "refs": [A("42127467"), A("42420579")]},
        ],
        "branches": [
            {
                "topic": "减量速度与维持量",
                "sides": [
                    {"label": "中国", "text": "每 2 周减 5 mg 或 0.1 mg/kg，维持区间 5~10 mg/d；眼肌型可按每 2~4 周减 5~10 mg 的递减方案。", "refs": [G("g23"), G("g22")]},
                    {"label": "国际", "text": "英国按月阶梯减量，目标 5 mg/d；国际 2026 理想 ≤5 mg/d；以色列最佳 5~7.5 mg/d。", "refs": [G("g27"), G("g28"), G("g24")]},
                ],
            },
        ],
    },
    {
        "id": "targeted",
        "title": "靶向生物制剂定位（FcRn 与补体抑制剂）",
        "summary": "两类靶向药均已进入中外指南，但中国线位靠前、国际强调传统治疗失败后再用。",
        "statements": [
            {"text": "中国 2026 抗体药物药学共识对艾加莫德用于 AChR 抗体阳性成人全身型 MG 给出 1a 强推荐；中国 2026 补体抑制剂建议把终末补体 C5 列为核心干预策略。", "refs": [G("g31"), G("g32")]},
            {"text": "中国部分共识把 FcRn 拮抗剂或补体抑制剂用于高活动性患者的一线治疗，但明确注明这一做法尚未获得国际共识。", "refs": [G("g33")]},
            {"text": "国际 2026 管理目标共识要求常规治疗 6~12 个月未控制症状才启动靶向治疗；以色列 2025 把艾加莫德和 nipocalimab 列为五线选择。", "refs": [G("g28"), G("g24")]},
            {"text": "支撑各品种进入指南的关键随机证据包括：艾加莫德 ADAPT、rozanolixizumab MycarinG、zilucoplan RAISE、ravulizumab CHAMPION、依库珠单抗 REGAIN、nipocalimab Vivacity-MG3。", "refs": [A("34146511"), A("37059507"), A("37059508"), A("38319212"), A("29066163"), A("39862879")]},
        ],
        "branches": [
            {
                "topic": "靶向药的治疗线位",
                "sides": [
                    {"label": "中国", "text": "艾加莫德用于 AChR 阳性成人 gMG 联合治疗为强推荐；危象前/危象等急性加重在感染控制后可用；部分共识提及高活动性可作一线。", "refs": [G("g31"), G("g16"), G("g33")]},
                    {"label": "国际", "text": "北欧、比利时等多定位为传统免疫抑制无效后的二线或替代；以色列列为五线；2026 国际共识设 6~12 个月传统治疗未达标的前置条件。", "refs": [G("g20"), G("g21"), G("g24"), G("g28")]},
                ],
            },
            {
                "topic": "补体抑制剂的适用指征",
                "sides": [
                    {"label": "中国", "text": "依库珠单抗用于 AChR 阳性难治性 gMG，900 mg 每周 ×4 周后 1200 mg 每 2 周；用药前需脑膜炎球菌疫苗接种。", "refs": [G("g16")]},
                    {"label": "国际", "text": "日本限定 IVIg 或血浆置换无法控制时使用；多国要求在其他免疫治疗未达标后再考虑，并强调疫苗或预防性抗生素。", "refs": [G("g09"), G("g27")]},
                ],
            },
        ],
    },
    {
        "id": "rescue",
        "title": "抢救治疗：IVIG、血浆置换与免疫吸附",
        "summary": "IVIG/PLEX 的抢救地位未被靶向药取代；MuSK 人群与剂量分层是主要分歧点。",
        "statements": [
            {"text": "中国 2022 IVIG 指南把 IVIG 列为 MG 危象和中重度全身型加重期的有效短期治疗，疗效与血浆置换相当，总量 2 g/kg、2~5 天用完（ⅠA 级）。", "refs": [G("g12")]},
            {"text": "MuSK 抗体阳性难治性 gMG：中国 2024 共识明确加重期选用血浆置换或 LPE、不推荐 IVIG；MGFA 2016 附录记载 MuSK-MG 对 PLEX 反应迅速良好、IVIG 应答率仅 11%~46%。", "refs": [G("g16"), G("g02")]},
            {"text": "双重滤过血浆置换与艾加莫德的前瞻对照研究提示抢救路径正在被重新评估，但尚不足以改写指南推荐。", "refs": [A("42764579")]},
        ],
        "branches": [
            {
                "topic": "MuSK 阳性患者能否用 IVIG",
                "sides": [
                    {"label": "中国", "text": "2024 难治性共识明确不推荐 IVIG，应选血浆置换/LPE；2022 IVIG 指南也注明 MuSK 阳性者疗效欠佳。", "refs": [G("g16"), G("g12")]},
                    {"label": "国际", "text": "MGFA 2016 以 PLEX 为优先但未完全否定 IVIG；日本 2022 仅推荐血浆置换，未把 IVIG 列为 MuSK 选项。", "refs": [G("g02"), G("g09")]},
                ],
            },
            {
                "topic": "IVIG 抢救剂量",
                "sides": [
                    {"label": "中国", "text": "多为固定足量：0.4 g·kg⁻¹·d⁻¹ ×5 天（总 2 g/kg）；围术期可用 3~5 天。", "refs": [G("g12"), G("g34")]},
                    {"label": "国际", "text": "英国按病情分层：显著球部症状但无需通气者 1 g/kg 分 2~3 天、5~7 天无反应可重复；濒临通气衰竭者 2 g/kg 分 5 天。", "refs": [G("g27"), G("g04")]},
                ],
            },
        ],
    },
    {
        "id": "thymectomy",
        "title": "胸腺切除与胸腺瘤处理",
        "summary": "MGTX 确立了非胸腺瘤 AChR 阳性 GMG 的手术获益，分歧集中在年龄上限与眼肌型适应证。",
        "statements": [
            {"text": "中国 2025 MG 指南建议非胸腺瘤 AChR 抗体阳性 GMG 在 18~65 岁早期手术，确诊 2 年内为宜、最晚不超过 5 年；<18 岁和 >65 岁结合病情与影像决定。", "refs": [G("g23")]},
            {"text": "国际推荐核心年龄更窄：英国、比利时等以 <50 岁为主，50~65 岁仅讨论或考虑，>65 岁一般不推荐。", "refs": [G("g27"), G("g21"), G("g20")]},
            {"text": "随机证据来自 MGTX：胸腺切除联合泼尼松优于单用泼尼松，长期随访显示获益可维持；中国另有外科治疗与围术期管理共识规范手术路径。", "refs": [A("27959594"), A("30692052"), G("g10"), G("g34")]},
        ],
        "branches": [
            {
                "topic": "手术年龄上限与眼肌型适应证",
                "sides": [
                    {"label": "中国", "text": "窗口放宽至 65 岁；眼肌型对胆碱酯酶抑制剂反应不足、无法耐受免疫抑制或难治性 AChR 阳性者也可考虑手术。", "refs": [G("g23"), G("g22")]},
                    {"label": "国际", "text": "以 <50 岁为推荐核心，50~65 岁仅个体化讨论；>65 岁一般不推荐。", "refs": [G("g27"), G("g21")]},
                ],
            },
        ],
    },
    {
        "id": "ocular",
        "title": "眼肌型 MG 的处理",
        "summary": "中国倾向早期联合免疫抑制，国际多为先对症、不足再阶梯加药。",
        "statements": [
            {"text": "中国 2025 MG 指南建议眼肌型首选胆碱酯酶抑制剂对症治疗，同时为快速持久达标联合免疫抑制（Ⅱb/B）；糖皮质激素为基础免疫治疗（Ⅰb/A），无效、不耐受或高转化风险者加非激素类免疫抑制剂。", "refs": [G("g23")]},
            {"text": "国际多为阶梯式：英国先用溴吡斯的明、不足再加泼尼松龙；以色列一线溴吡斯的明、二线激素±AZA/MMF/MTX；日本先胆碱酯酶抑制剂，必要时低剂量泼尼松龙。", "refs": [G("g27"), G("g24"), G("g09")]},
            {"text": "眼肌型向全身型转化的风险是早期干预的主要依据：英国 2025 引用约 50% 患者 2 年内、75% 患者 3 年内发展为全身型 MG。", "refs": [G("g27")]},
        ],
        "branches": [
            {
                "topic": "是否常规联合免疫抑制",
                "sides": [
                    {"label": "中国", "text": "在对症治疗同时即建议联合免疫抑制，偏向早期疾病修饰以降低全身化风险。", "refs": [G("g23"), G("g22")]},
                    {"label": "国际", "text": "先对症、疗效不足再加免疫抑制，强调阶梯式加药；低剂量激素常作为第二步。", "refs": [G("g27"), G("g24"), G("g09")]},
                ],
            },
        ],
    },
    {
        "id": "access",
        "title": "药物可及性与专科路径",
        "summary": "国际用专科中心、MDT 与报销标准限制新药使用，中国路径更宽、强调医保可承受。",
        "statements": [
            {"text": "中国 2024 FcRn 专家建议提出在医保能承受的范围内规律接受 FcRn 拮抗剂长期维持治疗，未设专科中心或 MDT 前置门槛。", "refs": [G("g18")]},
            {"text": "英国 2025 规定靶向药仅经专科门诊 MG MDT 讨论、早期可及项目或临床试验获得；比利时要求 NMRC 神经科医生处方且须符合报销标准。", "refs": [G("g27"), G("g21")]},
        ],
        "branches": [
            {
                "topic": "新药可及路径",
                "sides": [
                    {"label": "中国", "text": "强调医保可承受与长期维持，未设专科前置门槛；需同时关注超适应证使用与长期费用。", "refs": [G("g18"), G("g16")]},
                    {"label": "国际", "text": "以专科中心、MDT 与报销标准控制使用；以色列将靶向药限为五线且限明确难治者。", "refs": [G("g27"), G("g21"), G("g24")]},
                ],
            },
        ],
    },
]


QUESTION_GROUPS = [
    {
        "id": "fcrn",
        "title": "FcRn 治疗",
        "questions": [
            {
                "id": "q-fcrn-compare",
                "question": "不同 FcRn 拮抗剂之间如何选药？能否直接比较疗效？",
                "stance": "可谨慎回答",
                "whyOpen": "没有头对头随机试验，各注册研究入组人群、给药方案与背景治疗不同。",
                "answer": [
                    {"text": "ADAPT、MycarinG、Vivacity-MG3 均为安慰剂对照设计，不能据此比较品种间优劣。", "refs": [A("34146511"), A("37059507"), A("39862879")]},
                    {"text": "已有间接比较研究，但其结论依赖调整假设，不能替代头对头证据。", "refs": [A("41817915")]},
                    {"text": "现阶段选择更多落在给药途径、周期安排、可及性与患者偏好；指南按类别推荐，未按品种排次序。", "refs": [G("g28"), G("g31")]},
                ],
                "keywords": ["efgartigimod", "rozanolixizumab", "nipocalimab", "fcrn", "indirect comparison"],
            },
            {
                "id": "q-fcrn-predict",
                "question": "哪些患者更可能从 FcRn 治疗获益？有没有可靠的疗效预测指标？",
                "stance": "可谨慎回答",
                "whyOpen": "目前没有被前瞻验证的预测标志物，亚组与事后分析均属探索性。",
                "answer": [
                    {"text": "batoclimab III 期事后分析提示血清 IgG 快速下降与短期临床改善相关，可作为药效学参考，但不能用作选药或停药门槛。", "refs": [A("42867600")]},
                    {"text": "ADAPT 亚组分析显示不同诊断时长、既往治疗背景的患者均可应答，支持较广人群使用，但均属事后探索。", "refs": [A("42234197")]},
                    {"text": "AChR 抗体亚型与应答的关联仍停留在机制研究层面，尚无临床可用的分层标准。", "refs": [A("42242900")]},
                ],
                "keywords": ["fcrn", "efgartigimod", "response", "predictor", "igg", "subgroup"],
            },
            {
                "id": "q-fcrn-safety",
                "question": "FcRn 降低 IgG 会带来多少感染风险？疫苗和免疫球蛋白如何管理？",
                "stance": "可谨慎回答",
                "whyOpen": "长期低 IgG 状态下的感染谱与疫苗时机缺乏统一方案。",
                "answer": [
                    {"text": "ADAPT 及其开放扩展随访中总体耐受性良好，未出现新的安全信号；皮下剂型的长期扩展数据方向一致。", "refs": [A("34146511"), A("38318236"), A("42699831")]},
                    {"text": "nipocalimab 已有针对疫苗与病毒感染 IgG 应答的研究，提示需要关注免疫球蛋白管理，但个体化意义仍待评估。", "refs": [A("42084498")]},
                    {"text": "各指南把感染筛查、活动性感染控制后用药作为前提；具体疫苗接种时机尚无一致推荐。", "refs": [G("g31"), G("g16")]},
                ],
                "keywords": ["fcrn", "infection", "igg", "vaccine", "immunoglobulin", "safety"],
            },
            {
                "id": "q-fcrn-schedule",
                "question": "周期性给药与持续给药哪种更好？复发后如何再治疗？",
                "stance": "证据不足",
                "whyOpen": "没有比较两种给药策略的随机试验，复治时机也无统一标准。",
                "answer": [
                    {"text": "ADAPT 采用按需周期给药，Vivacity-MG3 采用每周持续给药，两种方案各自有效，无法据此判断优劣。", "refs": [A("34146511"), A("39862879")]},
                    {"text": "真实世界已有非周期性给药探索，但样本小、属观察性，不能作为方案选择依据。", "refs": [A("42162585")]},
                    {"text": "开放扩展研究中重复周期治疗仍有获益描述；实际复治多以症状驱动，缺乏统一间隔标准。", "refs": [A("38318236")]},
                ],
                "keywords": ["fcrn", "cyclic", "weekly", "retreatment", "relapse", "schedule"],
            },
            {
                "id": "q-fcrn-special",
                "question": "FcRn 能用于 MuSK 阳性、血清阴性或危象患者吗？",
                "stance": "可谨慎回答",
                "whyOpen": "注册试验以 AChR 阳性 gMG 为主，特殊人群证据多为病例系列与个案。",
                "answer": [
                    {"text": "MuSK 阳性使用艾加莫德的诱导与维持治疗有个案系列报道，不能外推为该类人群的确证疗效。", "refs": [A("40144041")]},
                    {"text": "血清阴性 MG 的系统综述显示该组人群异质性大、治疗证据总体有限；三重血清阴性难治者使用 rozanolixizumab 仅见个案。", "refs": [A("42387811"), A("41211783")]},
                    {"text": "危象/危象前使用艾加莫德的报告逐渐增多（含皮下给药个案）；中国部分共识在感染控制后给出推荐，国际指南尚未形成一致意见。", "refs": [A("39735402"), A("38939234"), G("g16"), G("g31")]},
                ],
                "keywords": ["fcrn", "musk", "seronegative", "crisis", "efgartigimod"],
            },
        ],
    },
    {
        "id": "complement",
        "title": "补体抑制与靶向联合",
        "questions": [
            {
                "id": "q-complement-refractory",
                "question": "补体抑制剂无应答或耐药时怎么办？",
                "stance": "证据不足",
                "whyOpen": "缺少预测无应答的统一指标，换药与联合次序没有随机证据。",
                "answer": [
                    {"text": "需先确认诊断、依从性与罕见药理原因；已有 ravulizumab 无应答而 zilucoplan 有效的 C5 p.Arg885 变异个案，提示基因检测在特定情形有价值。", "refs": [A("41771246")]},
                    {"text": "REGAIN 中部分患者应答不足，目前尚无公认的应答预测流程。", "refs": [A("29066163")]},
                    {"text": "同类内换药或换靶点的次序主要参考个案与小系列，指南未给固定流程。", "refs": [A("34590717"), A("38572524")]},
                ],
                "keywords": ["complement", "eculizumab", "ravulizumab", "zilucoplan", "refractory", "c5"],
            },
            {
                "id": "q-complement-meningococcal",
                "question": "补体抑制剂的脑膜炎球菌疫苗接种与突破感染如何管理？",
                "stance": "可谨慎回答",
                "whyOpen": "疫苗接种后仍有突破感染报告，预防性抗生素的使用时机没有统一标准。",
                "answer": [
                    {"text": "真实世界数据显示接种过疫苗的患者仍发生血清群 Y 脑膜炎球菌突破感染，提示疫苗不能完全消除风险。", "refs": [A("42790255")]},
                    {"text": "中国 2024 难治性共识要求用药前完成脑膜炎球菌疫苗接种。", "refs": [G("g16")]},
                    {"text": "英国 2025 等国际指南另提示可考虑预防性抗生素；各文件对接种后延迟起药的间隔表述不一。", "refs": [G("g27"), G("g09")]},
                ],
                "keywords": ["meningococcal", "vaccine", "eculizumab", "ravulizumab", "prophylaxis", "antibiotic"],
            },
            {
                "id": "q-complement-naive",
                "question": "未经过传统免疫抑制的患者能否直接起始补体抑制？",
                "stance": "证据不足",
                "whyOpen": "注册试验入组者多已接受背景免疫治疗，初治人群证据来自事后亚组。",
                "answer": [
                    {"text": "zilucoplan 在未接受过免疫抑制治疗的患者中有专项疗效分析，结果提示有效，但样本有限且非前瞻分层设计。", "refs": [A("40450840")]},
                    {"text": "日本 2022 指南限定依库珠单抗用于 IVIg 或血浆置换无法控制的患者。", "refs": [G("g09")]},
                    {"text": "国际 2026 管理目标共识要求常规治疗 6~12 个月未达标才启动靶向治疗。", "refs": [G("g28")]},
                ],
                "keywords": ["complement", "zilucoplan", "treatment-naive", "first-line", "eculizumab"],
            },
            {
                "id": "q-complement-switch",
                "question": "依库珠单抗与 ravulizumab、zilucoplan 之间如何转换？",
                "stance": "证据不足",
                "whyOpen": "转换指征、间隔与疗效保持情况没有随机对照数据。",
                "answer": [
                    {"text": "真实世界已有依库珠单抗转换至 ravulizumab 的系列报道，转换后疗效与安全性总体维持。", "refs": [A("38572524")]},
                    {"text": "ravulizumab 无应答伴 C5 p.Arg885 变异者换用 zilucoplan 有效的个案提示转换前可评估药理原因。", "refs": [A("41771246")]},
                    {"text": "转换决策目前以个体化判断为主，缺少统一流程。", "refs": [G("g16")]},
                ],
                "keywords": ["eculizumab", "ravulizumab", "zilucoplan", "switch", "conversion"],
            },
            {
                "id": "q-complement-combine",
                "question": "补体抑制剂能否与 FcRn 拮抗剂或传统免疫抑制联合？",
                "stance": "可谨慎回答",
                "whyOpen": "联合方案的安全性叠加与获益增量缺乏对照证据。",
                "answer": [
                    {"text": "真实世界数据显示补体抑制剂常与传统免疫抑制和激素长期联用，但属于治疗模式描述而非方案验证。", "refs": [A("42880190")]},
                    {"text": "中国 2026 抗体药物药学共识对靶向药与传统治疗的联合与衔接给出药学管理建议。", "refs": [G("g31")]},
                    {"text": "补体与 FcRn 双靶点联合的证据目前限于个案与小型系列。", "refs": [A("38799457")]},
                ],
                "keywords": ["complement", "fcrn", "combination", "immunosuppress", "concomitant"],
            },
        ],
    },
    {
        "id": "crisis",
        "title": "危象与抢救治疗",
        "questions": [
            {
                "id": "q-rescue-role",
                "question": "靶向治疗时代，IVIG 和血浆置换的位置变了吗？",
                "stance": "可谨慎回答",
                "whyOpen": "新型靶向药进入抢救场景后，传统抢救治疗的排序需要重新评估。",
                "answer": [
                    {"text": "中外指南仍把 IVIG/PLEX 作为危象与中重度加重期的短期抢救基础，剂量与分层各有差异。", "refs": [G("g12"), G("g27"), G("g04")]},
                    {"text": "双重滤过血浆置换与艾加莫德的前瞻对照提示抢救路径正在被重新评估，但证据尚不足以改写指南。", "refs": [A("42764579")]},
                    {"text": "MuSK 阳性患者仍优先血浆置换，IVIG 在该人群应答率低。", "refs": [G("g16"), G("g02")]},
                ],
                "keywords": ["ivig", "plasmapheresis", "plex", "crisis", "rescue", "dfpp"],
            },
            {
                "id": "q-crisis-predict",
                "question": "肌无力危象能否预测？哪些工具有效？",
                "stance": "可谨慎回答",
                "whyOpen": "现有预测工具多为单中心回顾性建模，缺乏外部验证。",
                "answer": [
                    {"text": "POLAR 评分用于预测危象患者是否需要延长机械通气，属回顾性推导。", "refs": [A("38329540")]},
                    {"text": "危象结局预测因素分析提示起病速度、感染诱因与球部症状与结局相关，但阈值尚未统一。", "refs": [A("40698586")]},
                    {"text": "护理导向的危象风险列线图已有报道，验证范围有限；中国 2024 危象前状态共识给出识别框架但未定量化。", "refs": [A("40804363"), G("g19")]},
                ],
                "keywords": ["crisis", "predict", "nomogram", "polar", "ventilation", "respiratory"],
            },
            {
                "id": "q-crisis-bridge",
                "question": "危象或危象前急性期之后，如何衔接长期治疗？",
                "stance": "可谨慎回答",
                "whyOpen": "急性期过渡方案的比较数据很少，衔接时机主要靠经验。",
                "answer": [
                    {"text": "已有艾加莫德后序贯 telitacicept 的快速起效方案报道，但属小样本探索。", "refs": [A("42853026")]},
                    {"text": "中国 2024 难治性共识与危象前状态共识把急性期后的免疫维持治疗作为核心议题，但未给固定衔接流程。", "refs": [G("g16"), G("g19")]},
                    {"text": "艾加莫德在危象前/危象患者感染控制后使用的推荐见中国 2026 共识。", "refs": [G("g31")]},
                ],
                "keywords": ["crisis", "bridge", "sequential", "maintenance", "telitacicept", "efgartigimod"],
            },
            {
                "id": "q-crisis-gap",
                "question": "中国危象与呼吸管理的证据缺口怎么补？",
                "stance": "证据不足",
                "whyOpen": "近一年中国侧该主题仅新增 5 篇，而国际为 34 篇，多中心呼吸管理队列缺位。",
                "answer": [
                    {"text": "双重滤过血浆置换与艾加莫德的前瞻对照是中国侧少见的急性期对照研究。", "refs": [A("42764579")]},
                    {"text": "危象前状态共识提供了识别框架，但呼吸管理证据仍以国际队列为主。", "refs": [G("g19"), G("g23")]},
                    {"text": "国际侧 POLAR 评分、通气策略比较与 ICU 结局队列已形成连续证据链。", "refs": [A("38329540"), A("40698586")]},
                ],
                "keywords": ["crisis", "respiratory", "ventilation", "china", "evidence gap"],
            },
        ],
    },
    {
        "id": "steroid",
        "title": "激素与传统免疫抑制",
        "questions": [
            {
                "id": "q-steroid-taper",
                "question": "激素减量路径与维持目标怎么定？",
                "stance": "可谨慎回答",
                "whyOpen": "中外减量速度与维持量标准不同，减停诱发的复发风险缺乏量化工具。",
                "answer": [
                    {"text": "中国 2025 MG 指南建议每 2 周减 5 mg 或 0.1 mg/kg，减至 5~10 mg/d 维持或减停。", "refs": [G("g23")]},
                    {"text": "英国 2025 采用更慢的月度阶梯并以 5 mg/d 为目标；国际 2026 共识要求减至 ≤10 mg/d、理想 ≤5 mg/d 并监测恶化。", "refs": [G("g27"), G("g28")]},
                    {"text": "以色列 2025 把最佳维持量定在 5~7.5 mg/d。", "refs": [G("g24")]},
                ],
                "keywords": ["steroid", "taper", "prednisone", "maintenance", "remission"],
            },
            {
                "id": "q-steroid-complication",
                "question": "长期激素的并发症如何管理？",
                "stance": "可谨慎回答",
                "whyOpen": "并发症管理与减量的平衡缺乏 MG 人群的专门对照研究。",
                "answer": [
                    {"text": "国际 2025 激素并发症共识与意大利 2025 激素管理建议提供了系统管理框架。", "refs": [G("g25"), G("g26")]},
                    {"text": "真实世界研究显示口服激素治疗的并发症发生与加重风险相关，剂量越大暴露越明显。", "refs": [A("42420579")]},
                ],
                "keywords": ["steroid", "complication", "glucocorticoid", "long-term", "adverse"],
            },
            {
                "id": "q-ist-choice",
                "question": "非激素免疫抑制剂如何选择与换药？",
                "stance": "可谨慎回答",
                "whyOpen": "各类传统免疫抑制剂之间缺乏头对头比较，选择多基于经验与安全性。",
                "answer": [
                    {"text": "MGFA 2016 附表 e-1 按起效时间与安全性整理了各药的使用位置。", "refs": [G("g04")]},
                    {"text": "中国 2025 MG 指南按疗效不足、不耐受与高转化风险给出加用非激素类免疫抑制剂的阶梯。", "refs": [G("g23")]},
                    {"text": "真实世界治疗模式研究显示激素与非激素免疫抑制剂的联用组合差异较大，尚未收敛到统一路径。", "refs": [A("42880190")]},
                ],
                "keywords": ["immunosuppress", "azathioprine", "mycophenolate", "methotrexate", "tacrolimus", "choice"],
            },
            {
                "id": "q-ocular-early",
                "question": "眼肌型 MG 要不要早期联合免疫抑制？",
                "stance": "可谨慎回答",
                "whyOpen": "早期疾病修饰能否降低全身化风险缺乏随机对照验证。",
                "answer": [
                    {"text": "中国 2025 MG 指南建议眼肌型在对症治疗同时联合免疫抑制（Ⅱb/B），激素为基础（Ⅰb/A）。", "refs": [G("g23")]},
                    {"text": "国际多为阶梯式：英国先用溴吡斯的明、不足再加泼尼松龙，并引用约 50% 患者 2 年内全身化的转化数据。", "refs": [G("g27")]},
                    {"text": "中国 2025 眼肌型共识另给出激素与免疫抑制剂的递减与隔日维持方案。", "refs": [G("g22")]},
                ],
                "keywords": ["ocular", "immunosuppress", "conversion", "generalisation", "early treatment"],
            },
        ],
    },
    {
        "id": "special",
        "title": "特殊人群",
        "questions": [
            {
                "id": "q-special-pregnancy",
                "question": "妊娠期 MG 管理与靶向药安全性如何把握？",
                "stance": "证据不足",
                "whyOpen": "妊娠期暴露数据以药物警戒和登记为主，缺乏对照设计。",
                "answer": [
                    {"text": "全国性队列研究提示妊娠与产后是 MG 加重的风险窗口。", "refs": [A("42127347")]},
                    {"text": "ravulizumab 已有全球药物警戒分析，但样本与观察期有限，不能视为确定性安全结论。", "refs": [A("42853533")]},
                    {"text": "妊娠与产后母婴结局的队列数据正在积累，FcRn 类妊娠证据更少。", "refs": [A("42855151")]},
                ],
                "keywords": ["pregnancy", "postpartum", "ravulizumab", "safety", "newborn"],
            },
            {
                "id": "q-special-juvenile",
                "question": "儿童/青少年 MG 的治疗证据到了哪一步？",
                "stance": "证据不足",
                "whyOpen": "注册试验基本排除儿童，证据以开放标签和回顾为主。",
                "answer": [
                    {"text": "依库珠单抗在青少年难治性 gMG 有开放标签 III 期数据。", "refs": [A("38810600")]},
                    {"text": "单中心青少年队列回顾提示治疗反应模式与成人接近，但证据等级有限。", "refs": [A("42749614")]},
                    {"text": "托珠单抗在儿童眼肌型难治个案中也有探索。", "refs": [A("42864259")]},
                ],
                "keywords": ["juvenile", "pediatric", "adolescent", "eculizumab", "children"],
            },
            {
                "id": "q-special-elderly",
                "question": "老年晚发 MG 的治疗策略有何不同？",
                "stance": "可谨慎回答",
                "whyOpen": "老年人群共病多、耐受性差，随机证据少。",
                "answer": [
                    {"text": "极晚发 MG 的系统综述与荟萃分析提示其严重程度与长期结局具有异质性。", "refs": [A("42842206")]},
                    {"text": "单中心队列显示难治性老年患者对依库珠单抗可快速应答。", "refs": [A("42646495")]},
                    {"text": "中国 2025 MG 指南对老年患者的免疫抑制选择给出专门提醒。", "refs": [G("g23")]},
                ],
                "keywords": ["elderly", "late-onset", "older", "comorbid"],
            },
            {
                "id": "q-special-comorbidity",
                "question": "合并其他 IgG 介导疾病或 ICI 相关 MG 怎么处理？",
                "stance": "可谨慎回答",
                "whyOpen": "叠加自身免疫与免疫检查点抑制剂相关 MG 的处理证据以个案与药物警戒为主。",
                "answer": [
                    {"text": "中国 35 例 AChR 阳性 gMG 队列显示约三分之一存在重叠自身免疫共病，共病亚组应答更明显但属探索性观察。", "refs": [A("42903245")]},
                    {"text": "ICI 相关心肌炎-肌炎-MG 重叠综合征已有单中心系列与 FAERS 药物警戒分析，提示需要多学科急症处理。", "refs": [A("42878911"), A("42840483")]},
                ],
                "keywords": ["comorbidity", "overlap", "immune checkpoint", "myocarditis", "triple-m"],
            },
        ],
    },
    {
        "id": "antibody",
        "title": "抗体分型与血清阴性",
        "questions": [
            {
                "id": "q-seronegative",
                "question": "血清阴性 MG 如何诊断与治疗？",
                "stance": "可谨慎回答",
                "whyOpen": "血清阴性人群异质性大，指南未给出独立的靶向治疗路径。",
                "answer": [
                    {"text": "血清阴性不等于排除 MG：需结合重复抗体检测、电生理与临床特征，并鉴别其他神经肌肉病；2026 年系统综述对此有专门梳理。", "refs": [A("42387811"), A("42104987")]},
                    {"text": "治疗证据多来自小样本；三重血清阴性难治性 gMG 使用 rozanolixizumab 抢救成功仅见个案报道。", "refs": [A("41211783")]},
                    {"text": "现阶段按表型与既往治疗反应个体化处理，靶向药选择不能简单套用 AChR 阳性人群证据。", "refs": [G("g23"), G("g28")]},
                ],
                "keywords": ["seronegative", "double-seronegative", "triple-seronegative", "diagnosis", "antibody"],
            },
            {
                "id": "q-musk-optimization",
                "question": "MuSK 阳性 MG 的治疗如何优化？",
                "stance": "可谨慎回答",
                "whyOpen": "MuSK 人群对传统靶向药应答模式不同，最优方案未定。",
                "answer": [
                    {"text": "利妥昔单抗在 MuSK 阳性 MG 的长期随访数据相对充分，是常用选择。", "refs": [A("42492144")]},
                    {"text": "个体化 ofatumumab 与固定低剂量利妥昔单抗的比较队列提示 B 细胞耗竭策略内部也在分化。", "refs": [A("42837864")]},
                    {"text": "MuSK 阳性难治性患者不推荐 IVIG，急性加重应选血浆置换或 LPE。", "refs": [G("g16")]},
                ],
                "keywords": ["musk", "rituximab", "ofatumumab", "b-cell"],
            },
            {
                "id": "q-antibody-novel",
                "question": "新型抗体发现（抗体功能亚类、LRP4 等）会改变治疗决策吗？",
                "stance": "证据不足",
                "whyOpen": "抗体功能层面的细分与治疗应答的连接尚处机制阶段。",
                "answer": [
                    {"text": "MuSK 抗体价位与表位特异性的差异可影响信号级联，提示抗体质量而非仅滴度决定病理。", "refs": [A("42391746")]},
                    {"text": "IgA 自身抗体在 MuSK MG 中显示出新的致病机制线索。", "refs": [A("41147199")]},
                    {"text": "AChR 与 LRP4 双抗体阳性难治患者对依库珠单抗有效的个案提示抗体组合或可指导靶向选择。", "refs": [A("42035597")]},
                ],
                "keywords": ["lrp4", "igg4", "valency", "epitope", "biomarker", "mechanism"],
            },
        ],
    },
    {
        "id": "thymectomy",
        "title": "胸腺切除与胸腺瘤",
        "questions": [
            {
                "id": "q-thymectomy-age",
                "question": "胸腺切除的年龄上限与眼肌型适应证怎么定？",
                "stance": "可谨慎回答",
                "whyOpen": "MGTX 之后缺少新的随机证据，年龄与眼肌型适应证中外指南分歧明显。",
                "answer": [
                    {"text": "中国 2025 MG 指南建议 18~65 岁非胸腺瘤 AChR 阳性 GMG 早期手术；国际推荐核心年龄更窄。", "refs": [G("g23"), G("g27"), G("g21")]},
                    {"text": "MGTX 随机试验及长期随访显示胸腺切除联合泼尼松改善结局。", "refs": [A("27959594"), A("30692052")]},
                    {"text": "眼肌型对药物治疗失败者可考虑手术，属中国共识立场。", "refs": [G("g22")]},
                ],
                "keywords": ["thymectomy", "age", "mgtx", "ocular", "thymoma"],
            },
            {
                "id": "q-thymectomy-periop",
                "question": "围术期如何避免肌无力危象？",
                "stance": "可谨慎回答",
                "whyOpen": "术前免疫治疗时长与围术期危象风险的关系缺乏随机验证。",
                "answer": [
                    {"text": "中国 2026 胸腺切除围术期共识给出 IVIG 0.4 g·kg⁻¹·d⁻¹ ×3~5 天等围术期方案。", "refs": [G("g34")]},
                    {"text": "术前免疫治疗时长延长可降低术后加重风险（III 级证据）。", "refs": [A("42365147")]},
                    {"text": "术中胸膜破损等手术因素与围术期及远期结局的关联也有队列描述。", "refs": [A("42853014")]},
                ],
                "keywords": ["perioperative", "ivig", "crisis", "thymectomy", "preoperative"],
            },
            {
                "id": "q-thymoma-mg",
                "question": "胸腺瘤相关 MG 的治疗有何特殊性？",
                "stance": "可谨慎回答",
                "whyOpen": "胸腺瘤人群的靶向药证据少，治疗以肿瘤处理加对症与免疫治疗为主线。",
                "answer": [
                    {"text": "中国 2022 外科治疗共识规范了胸腺瘤合并 MG 的手术与围术期路径。", "refs": [G("g10")]},
                    {"text": "AChR 与 LRP4 双抗体阳性难治患者对依库珠单抗有效的个案提示难治性胸腺瘤相关 MG 仍可尝试补体抑制。", "refs": [A("42035597")]},
                    {"text": "胸腔镜扩大胸腺切除的远期结局队列支持微创路径。", "refs": [A("42736463")]},
                ],
                "keywords": ["thymoma", "surgery", "vat", "eculizumab", "refractory"],
            },
        ],
    },
    {
        "id": "outcome",
        "title": "疗效评估与结局",
        "questions": [
            {
                "id": "q-outcome-mse",
                "question": "MSE/MMS 作为治疗目标在临床落地时怎么把握？",
                "stance": "可谨慎回答",
                "whyOpen": "目标定义中外不完全一致，落地时的激素阈值与随访强度缺少操作指南。",
                "answer": [
                    {"text": "中国 2025 MG 指南把 MSE 定义为 MG-ADL 0 或 1 分且不良反应 ≤CTCAE 1 级。", "refs": [G("g23")]},
                    {"text": "MGFA 2016 的 PIS 分类是国际通用的干预后状态框架。", "refs": [G("g02")]},
                    {"text": "MGNet 2023 结局评价指南规范了临床试验与临床实践中的结局选择。", "refs": [G("g15")]},
                ],
                "keywords": ["mse", "mms", "pis", "mg-adl", "treatment goal"],
            },
            {
                "id": "q-outcome-correlation",
                "question": "MG-ADL 与 QMG 评分的换算与局限是什么？",
                "stance": "可谨慎回答",
                "whyOpen": "两个量表的相关性研究较早，跨量表推断的误差边界常被忽略。",
                "answer": [
                    {"text": "MG-ADL 与 QMG 存在相关性但不等价，跨量表换算应谨慎。", "refs": [A("29684239")]},
                    {"text": "MGNet 2023 结局评价指南对不同量表的适用场景给出规范。", "refs": [G("g15")]},
                ],
                "keywords": ["mg-adl", "qmg", "scale", "correlation", "outcome"],
            },
            {
                "id": "q-outcome-pro",
                "question": "疲劳、认知等患者报告结局要不要进入常规评估？",
                "stance": "可谨慎回答",
                "whyOpen": "PRO 与传统量表的关系及对治疗决策的增量价值仍在积累。",
                "answer": [
                    {"text": "ravulizumab 研究的多维度疲劳、认知与生活质量观察提示传统量表之外仍有未被捕捉的负担。", "refs": [A("42315783")]},
                    {"text": "运动与康复的系统综述总结了非药物干预对结局的影响。", "refs": [A("42763723")]},
                    {"text": "疾病成本系统综述从社会视角补充了负担维度。", "refs": [A("42842039")]},
                ],
                "keywords": ["pro", "fatigue", "cognitive", "quality of life", "burden"],
            },
        ],
    },
    {
        "id": "rwe",
        "title": "真实世界与本土证据",
        "questions": [
            {
                "id": "q-rwe-china",
                "question": "中国真实世界证据能支撑哪些沟通？",
                "stance": "可谨慎回答",
                "whyOpen": "中国 RWE 多为单臂、回顾或小样本队列，证据层级有限。",
                "answer": [
                    {"text": "艾加莫德真实世界队列报告了疗效与激素减量获益，但属单臂设计。", "refs": [A("42127467")]},
                    {"text": "依库珠单抗中国多中心回顾性研究提供了本土安全性与疗效描述。", "refs": [A("42271114")]},
                    {"text": "telitacicept 的贝叶斯真实世界研究探索了高效概率，但设计限制仍在。", "refs": [A("41786016")]},
                ],
                "keywords": ["real-world", "china", "efgartigimod", "eculizumab", "telitacicept"],
            },
            {
                "id": "q-rwe-registry",
                "question": "登记与疾病负担数据的缺口怎么补？",
                "stance": "证据不足",
                "whyOpen": "近一年中国侧疾病负担与登记类新增仅 2 篇，国际为 14 篇。",
                "answer": [
                    {"text": "国际疾病成本系统综述（I 级）覆盖患者与社会视角，中国数据在其样本中占比有限。", "refs": [A("42842039")]},
                    {"text": "全国性队列研究（如肥胖与 MG 风险）提供了登记数据利用的范例。", "refs": [A("41824214")]},
                    {"text": "血清阴性人群患病率与特征研究提示登记体系需要覆盖抗体状态维度。", "refs": [A("42104987")]},
                ],
                "keywords": ["registry", "burden", "cost", "nationwide", "china"],
            },
            {
                "id": "q-rwe-access",
                "question": "可及性与药物经济学证据如何影响治疗路径？",
                "stance": "可谨慎回答",
                "whyOpen": "中外支付体系不同，经济学证据难以直接移植。",
                "answer": [
                    {"text": "中国 2024 FcRn 专家建议把医保可承受作为长期维持治疗的前提。", "refs": [G("g18")]},
                    {"text": "英国 2025 通过 MDT 讨论与早期可及项目限制新药使用。", "refs": [G("g27")]},
                    {"text": "国际疾病成本系统综述为可及性讨论提供了负担基线。", "refs": [A("42842039")]},
                ],
                "keywords": ["access", "cost", "reimbursement", "economic", "pathway"],
            },
        ],
    },
    {
        "id": "pipeline",
        "title": "新靶点与在研管线",
        "questions": [
            {
                "id": "q-pipeline-nipocalimab",
                "question": "nipocalimab 的定位与亚洲人群数据如何？",
                "stance": "可谨慎回答",
                "whyOpen": "Vivacity-MG3 之后仍需真实世界验证与头对头定位。",
                "answer": [
                    {"text": "Vivacity-MG3 III 期确认了每周持续给药方案的疗效。", "refs": [A("39862879")]},
                    {"text": "亚洲亚组分析显示疗效与总体人群一致。", "refs": [A("42421405")]},
                    {"text": "持续疾病控制的延伸分析提供了维持治疗的参考。", "refs": [A("42157574")]},
                ],
                "keywords": ["nipocalimab", "vivacity", "asian", "sustained"],
            },
            {
                "id": "q-pipeline-telitacicept",
                "question": "telitacicept 的证据到了哪一级？",
                "stance": "证据不足",
                "whyOpen": "II 期开放标签加真实世界研究为主，缺少安慰剂对照 III 期。",
                "answer": [
                    {"text": "多中心随机开放标签 II 期研究显示 Adult gMG 患者的疗效信号。", "refs": [A("38726639")]},
                    {"text": "贝叶斯真实世界研究给出高有效概率估计，但设计限制明确。", "refs": [A("41786016")]},
                    {"text": "难治性 gMG 回顾性研究补充了安全性经验。", "refs": [A("38751755")]},
                ],
                "keywords": ["telitacicept", "phase 2", "real-world", "refractory"],
            },
            {
                "id": "q-pipeline-cemdisiran",
                "question": "靶向肝源的 siRNA（cemdisiran）代表什么方向？",
                "stance": "可谨慎回答",
                "whyOpen": "NIMBLE 之后仍需长期数据与注射给药的依从性比较。",
                "answer": [
                    {"text": "NIMBLE 双盲随机对照试验显示 cemdisiran 的疗效与安全信号。", "refs": [A("42030965")]},
                    {"text": "同期评论文章讨论了补体通路抑制从静脉单抗到皮下 siRNA 的范式变化。", "refs": [A("42431187")]},
                ],
                "keywords": ["cemdisiran", "sirna", "nimble", "complement", "subcutaneous"],
            },
            {
                "id": "q-pipeline-cell",
                "question": "CD19/CAR-T 细胞疗法在难治 MG 中的位置？",
                "stance": "证据不足",
                "whyOpen": "CAR-T 证据以病例系列与综述为主，长期安全性与复治策略未明。",
                "answer": [
                    {"text": "自体 CD19/BCMA CAR-T 在重症难治 MG 的研究显示深度 B 细胞清除后的临床改善。", "refs": [A("41966710")]},
                    {"text": "自身免疫病 CAR-T 系统综述梳理了跨病种的疗效与安全性谱。", "refs": [A("42235055")]},
                    {"text": "综述文章总结了 CAR-T 在 MG 的进展与安全挑战。", "refs": [A("41958278")]},
                    {"text": "MuSK 阳性人群中个体化 ofatumumab 与低剂量利妥昔单抗的比较提供了 CAR-T 之外的 B 细胞耗竭选择。", "refs": [A("42837864")]},
                ],
                "keywords": ["car-t", "cd19", "bcma", "cell therapy", "refractory"],
            },
        ],
    },
]



def build():
    chapters = [finalize(dict(ch)) for ch in CHAPTERS]
    groups = []
    for group in QUESTION_GROUPS:
        questions = []
        for q in group["questions"]:
            body = dict(q)
            body["statements"] = body.pop("answer")
            body["branches"] = []
            finalize(body)
            body["answer"] = body.pop("statements")
            body.pop("branches", None)
            questions.append(body)
        groups.append({"id": group["id"], "title": group["title"], "questions": questions})

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    from common.io import atomic_write_js_global
    atomic_write_js_global(OUT_CHAPTERS, "MG_TREATMENT_CHAPTERS", {
        "generated_at": stamp,
        "version": "2026-10-27-v1",
        "basis": "34 份中外指南/共识（已回验立场卡）+ 本地 PubMed 证据库；引文按 PMID 反查生成",
        "update_rule": "周更后仅高等级证据（I/II 级或新指南原文）且经人工确认才写入正文；候选证据先入待确认队列",
        "chapters": chapters,
    }, header="/* 诊疗现状章节：由 scripts/build-landscape-knowledge.py 生成，请勿手动编辑 */\n")
    atomic_write_js_global(OUT_QUESTIONS, "MG_CLINICAL_QUESTIONS", {
        "generated_at": stamp,
        "version": "2026-10-27-v1",
        "basis": "基于指南语料、PubMed 摘要证据与未解决问题梳理；问题与答案均可滚动修订",
        "update_rule": "问题可新增/退役；证据更新需高等级且经人工确认；候选证据入待确认队列",
        "groups": groups,
    }, header="/* 临床问题库：由 scripts/build-landscape-knowledge.py 生成，请勿手动编辑 */\n")
    print(f"chapters={len(chapters)} question_groups={len(groups)}")
    print("OK")


if __name__ == "__main__":
    build()
