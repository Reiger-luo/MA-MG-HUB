# MA-MG-HUB 社区语义层质量审计

生成时间：2026-06-30 18:49:36

## 总览

- 总文献：10635
- 已归类：7890（74.2%）
- 未归类：2745（25.8%）
- 低置信度：1120（10.5%）
- 冲突归类：1481（13.9%）
- wiki 专题覆盖：10/10 个社区

## 社区分布

| 社区 | 文献 | 占比 | 低置信度 | 冲突 | 专题 | 近14天 |
| --- | --- | --- | --- | --- | --- | --- |
| 未归类 | 2745 | 25.8% | 0 | 0 | 0 | 0 |
| 临床亚型与人群分层 | 2055 | 19.3% | 452 | 439 | 27 | 4 |
| 安全性与用药管理 | 1647 | 15.5% | 40 | 206 | 26 | 10 |
| 诊断、监测与预测 | 1150 | 10.8% | 195 | 195 | 13 | 6 |
| 机制与转化医学 | 1064 | 10% | 195 | 137 | 21 | 3 |
| 真实世界证据与临床路径 | 723 | 6.8% | 69 | 201 | 20 | 4 |
| 疗效终点与疾病负担 | 553 | 5.2% | 153 | 138 | 18 | 5 |
| 补体与其他新靶点 | 290 | 2.7% | 0 | 65 | 22 | 2 |
| FcRn 靶向治疗 | 248 | 2.3% | 0 | 64 | 25 | 2 |
| 指南、共识与卫生经济 | 109 | 1% | 16 | 23 | 2 | 0 |
| 竞争格局与间接比较 | 51 | 0.5% | 0 | 13 | 9 | 2 |

## 主要质量信号

### 过大社区

| 社区 | 文献 | 占比 | 低置信度 | 冲突 | 专题 | 近14天 |
| --- | --- | --- | --- | --- | --- | --- |
| 未归类 | 2745 | 25.8% | 0 | 0 | 0 | 0 |

### 低置信度占比较高

| 社区 | 文献 | 低置信度 | 比例 |
| --- | --- | --- | --- |
| 疗效终点与疾病负担 | 553 | 153 | 27.7% |

### 冲突归类 Top Pairs

| Primary | Secondary | 冲突数 | 样本 PMID |
| --- | --- | --- | --- |
| 临床亚型与人群分层 | 诊断、监测与预测 | 178 | 42303225；42149058；42147223 |
| 临床亚型与人群分层 | 真实世界证据与临床路径 | 162 | 42256566；41936333；41926519 |
| 临床亚型与人群分层 | 机制与转化医学 | 154 | 42303225；42147223；41936333 |
| 真实世界证据与临床路径 | 临床亚型与人群分层 | 127 | 42102247；41960072；41908611 |
| 诊断、监测与预测 | 临床亚型与人群分层 | 101 | 42344535；42330780；42199478 |
| 临床亚型与人群分层 | 疗效终点与疾病负担 | 91 | 42256566；42064058；41940306 |
| 安全性与用药管理 | 临床亚型与人群分层 | 89 | 42168668；41969435；41960209 |
| 机制与转化医学 | 临床亚型与人群分层 | 71 | 42256950；42216051；41820352 |
| 安全性与用药管理 | 真实世界证据与临床路径 | 63 | 42160469；41960209；41882900 |
| 临床亚型与人群分层 | 安全性与用药管理 | 61 | 41793243；41559594；41487432 |
| 诊断、监测与预测 | 真实世界证据与临床路径 | 60 | 42211300；42199478；41998298 |
| 疗效终点与疾病负担 | 真实世界证据与临床路径 | 53 | 42365147；42223343；42131832 |

### 专题覆盖稀疏社区

| 社区 | 专题 | 本周更新专题 | 高置信专题 | 社区文献 |
| --- | --- | --- | --- | --- |
| 指南、共识与卫生经济 | 2 | 1 | 0 | 109 |
| 竞争格局与间接比较 | 9 | 7 | 0 | 51 |
| 诊断、监测与预测 | 13 | 13 | 1 | 1150 |
| 疗效终点与疾病负担 | 18 | 14 | 4 | 553 |
| 真实世界证据与临床路径 | 20 | 16 | 2 | 723 |
| 机制与转化医学 | 21 | 16 | 2 | 1064 |
| 补体与其他新靶点 | 22 | 16 | 2 | 290 |
| FcRn 靶向治疗 | 25 | 19 | 23 | 248 |

## 疑似边界问题

1. `clinicalSubtypesStratification` 已低于 25% 阈值（2055 篇，19.3%），但低置信度和冲突仍高，后续应继续把亚型/诊断/RWE 边界作为长期回归抽查对象。
2. FcRn 疑似漏归类样本：89 篇 assignment 具有 FcRn 产品/术语信号但 primary 不是 FcRn 社区。其中包含疗效终点、RWE、HEOR 和 competitive 作为合理 primary 的文献，不能直接等同于错误。
3. 补体/新靶点疑似漏归类样本：113 篇 assignment 具有补体产品/术语信号但 primary 不是补体社区。其中联合比较、RWE、HEOR 和宽泛综述需要保留 secondary/facet 解释，而不是一律提升补体 primary。
4. `competitiveLandscapeIndirectComparison` 当前收敛到 51 篇、9 个相关专题。v4d 已收窄为严格治疗策略、跨产品比较、NMA/ITC 或 evidence synthesis；普通 versus / controlled study 不再自动进入竞争格局。

## 抽样入口

### FcRn 疑似漏归类样本

- PMID 42360473 — Health-related quality of life outcomes with nipocalimab versus placebo in generalized myast...；primary=疗效终点与疾病负担；confidence=medium
- PMID 42358945 — Ofatumumab in refractory anti-muscle-specific tyrosine kinase antibody-positive myasthenia g...；primary=临床亚型与人群分层；confidence=high
- PMID 42322065 — Efgartigimod Versus Lymphoplasmapheresis as Preoperative Rapid Antibody-Clearing Therapies f...；primary=竞争格局与间接比较；confidence=high
- PMID 42304705 — Comparing Efficacy and Safety of Various Monoclonal Antibodies in Myasthenia Gravis: A Syste...；primary=竞争格局与间接比较；confidence=high
- PMID 42266700 — Real-world efficacy of eculizumab in generalized myasthenia gravis patients with poor early ...；primary=补体与其他新靶点；confidence=medium
- PMID 42168668 — Anti-acetylcholine receptor antibody overshoot following efgartigimod in myasthenia gravis: ...；primary=安全性与用药管理；confidence=medium
- PMID 42110106 — Severe Hypogammaglobulinemia (IgG) During Efgartigimod Therapy in Neurological Practice: A R...；primary=安全性与用药管理；confidence=high
- PMID 42064058 — Thymoma-associated anti-AMPAR encephalitis with myasthenia gravis: a case report.；primary=临床亚型与人群分层；confidence=medium
- PMID 42043767 — Treatment Characteristics and Healthcare Resource Utilization Among Patients with Myasthenia...；primary=真实世界证据与临床路径；confidence=high
- PMID 42030590 — Combined inhibition of complement C5 and neonatal Fc receptor in refractory generalized myas...；primary=补体与其他新靶点；confidence=high
- PMID 41993163 — Case report: Efgartigimod combined with intravenous methylprednisolone in a case of co-occur...；primary=安全性与用药管理；confidence=medium
- PMID 41979428 — Insufficient immunosuppressive treatment in patients with myasthenia gravis in the context o...；primary=真实世界证据与临床路径；confidence=high

### 补体疑似漏归类样本

- PMID 42304705 — Comparing Efficacy and Safety of Various Monoclonal Antibodies in Myasthenia Gravis: A Syste...；primary=竞争格局与间接比较；confidence=high
- PMID 42220523 — Complement C5 inhibition in generalized myasthenia gravis is associated with improved surviv...；primary=竞争格局与间接比较；confidence=high
- PMID 42168668 — Anti-acetylcholine receptor antibody overshoot following efgartigimod in myasthenia gravis: ...；primary=安全性与用药管理；confidence=medium
- PMID 41979428 — Insufficient immunosuppressive treatment in patients with myasthenia gravis in the context o...；primary=真实世界证据与临床路径；confidence=high
- PMID 41928685 — Targeting Autoimmunity in Myasthenia Gravis: From Conventional to Novel Therapeutic Approaches.；primary=机制与转化医学；confidence=high
- PMID 41925914 — Efficacy and safety of complement inhibitors and FcRn blockers in generalized AChR antibody-...；primary=竞争格局与间接比较；confidence=high
- PMID 41872753 — Complement C5 inhibition with eculizumab or ravulizumab is associated with increased cardiov...；primary=安全性与用药管理；confidence=medium
- PMID 41822500 — Analysis of adverse drug reactions associated with ravulizumab: a retrospective pharmacovigi...；primary=安全性与用药管理；confidence=high
- PMID 41760990 — Early versus late add-on therapy in generalized myasthenia gravis: a multicenter real-world ...；primary=真实世界证据与临床路径；confidence=high
- PMID 41591648 — Assessing the Value Contribution of Vyvgart® (Efgartigimod Alfa) in the Treatment of General...；primary=竞争格局与间接比较；confidence=high
- PMID 41524776 — Pharmacological and speech-language pathology management of dysphagia in patients with myast...；primary=疗效终点与疾病负担；confidence=medium
- PMID 41520205 — Health economic evaluations of myasthenia gravis: a systematic review.；primary=指南、共识与卫生经济；confidence=high

## 建议下一步

1. v4d 已完成第二轮 LLM review 后的 P0.5 cleanup：competitive 收窄、safety override 增强、MG 背景文献更积极进入 unassigned / review queue。
2. 由于 v4d 是质量优先版本，unassigned 占比升高是预期结果；后续重点抽查 recent high-evidence unassigned，而不是追求覆盖率最大化。
3. P1：把 FcRn / complement 疑似漏归类样本拆成“合理 secondary”和“真实漏归类”两类，避免只看泄漏计数做误判。
4. P1：为 `competitiveLandscapeIndirectComparison` 增加前端解释，说明该社区只代表药物、治疗策略、HEOR 或 evidence synthesis 的比较，不代表所有 versus 文献。
5. 若下一次周更 recent unassigned 没有高等级 MG 核心文献，可进入 Phase 4 动态诊治格局。

## Phase 4 进入条件

动态诊治格局可以在 v4d 规则稳定后进入，但生成洞察时必须展示 PMID、证据等级、社区 primary/secondary、图谱节点和 abstract-level 局限；unassigned 文献只能作为待审信号，不能直接生成格局结论。
