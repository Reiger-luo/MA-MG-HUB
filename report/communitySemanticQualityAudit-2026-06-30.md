# MA-MG-HUB 社区语义层质量审计

生成时间：2026-06-30 15:50:34

## 总览

- 总文献：10635
- 已归类：8931（84%）
- 未归类：1704（16%）
- 低置信度：2433（22.9%）
- 冲突归类：1995（18.8%）
- wiki 专题覆盖：10/10 个社区

## 社区分布

| 社区 | 文献 | 占比 | 低置信度 | 冲突 | 专题 | 近14天 |
| --- | --- | --- | --- | --- | --- | --- |
| 临床亚型与人群分层 | 2379 | 22.4% | 881 | 585 | 27 | 4 |
| 未归类 | 1704 | 16% | 0 | 0 | 0 | 0 |
| 机制与转化医学 | 1287 | 12.1% | 332 | 222 | 25 | 4 |
| 诊断、监测与预测 | 1261 | 11.9% | 562 | 246 | 13 | 7 |
| 安全性与用药管理 | 1132 | 10.6% | 263 | 229 | 24 | 7 |
| 真实世界证据与临床路径 | 945 | 8.9% | 147 | 260 | 24 | 4 |
| 疗效终点与疾病负担 | 676 | 6.4% | 224 | 188 | 18 | 8 |
| 竞争格局与间接比较 | 453 | 4.3% | 3 | 103 | 12 | 1 |
| 补体与其他新靶点 | 365 | 3.4% | 2 | 76 | 24 | 2 |
| FcRn 靶向治疗 | 289 | 2.7% | 0 | 61 | 26 | 3 |
| 指南、共识与卫生经济 | 144 | 1.4% | 19 | 25 | 4 | 1 |

## 主要质量信号

### 低置信度占比较高

| 社区 | 文献 | 低置信度 | 比例 |
| --- | --- | --- | --- |
| 临床亚型与人群分层 | 2379 | 881 | 37% |
| 诊断、监测与预测 | 1261 | 562 | 44.6% |
| 机制与转化医学 | 1287 | 332 | 25.8% |
| 疗效终点与疾病负担 | 676 | 224 | 33.1% |

### 冲突归类 Top Pairs

| Primary | Secondary | 冲突数 | 样本 PMID |
| --- | --- | --- | --- |
| 临床亚型与人群分层 | 诊断、监测与预测 | 225 | 42303225；42266578；42064058 |
| 临床亚型与人群分层 | 机制与转化医学 | 204 | 42303225；41936333；41542987 |
| 临床亚型与人群分层 | 真实世界证据与临床路径 | 191 | 42266578；41959797；41936404 |
| 真实世界证据与临床路径 | 临床亚型与人群分层 | 162 | 42336346；42102247；41960072 |
| 临床亚型与人群分层 | 安全性与用药管理 | 111 | 42261457；41969435；41936404 |
| 机制与转化医学 | 临床亚型与人群分层 | 100 | 42256950；42216051；42083560 |
| 诊断、监测与预测 | 临床亚型与人群分层 | 94 | 42344535；42320955；42081930 |
| 诊断、监测与预测 | 真实世界证据与临床路径 | 86 | 42308878；42211300；41895003 |
| 临床亚型与人群分层 | 疗效终点与疾病负担 | 83 | 42046766；41579003；41429676 |
| 诊断、监测与预测 | 机制与转化医学 | 81 | 42320955；42070048；41776695 |
| 安全性与用药管理 | 真实世界证据与临床路径 | 73 | 42190146；42104265；42028749 |
| 机制与转化医学 | 诊断、监测与预测 | 71 | 42342167；42256950；42244451 |

### 专题覆盖稀疏社区

| 社区 | 专题 | 本周更新专题 | 高置信专题 | 社区文献 |
| --- | --- | --- | --- | --- |
| 指南、共识与卫生经济 | 4 | 3 | 0 | 144 |
| 竞争格局与间接比较 | 12 | 9 | 0 | 453 |
| 诊断、监测与预测 | 13 | 13 | 1 | 1261 |
| 疗效终点与疾病负担 | 18 | 14 | 4 | 676 |
| 安全性与用药管理 | 24 | 18 | 4 | 1132 |
| 真实世界证据与临床路径 | 24 | 18 | 3 | 945 |
| 补体与其他新靶点 | 24 | 18 | 2 | 365 |
| 机制与转化医学 | 25 | 20 | 2 | 1287 |

## 疑似边界问题

1. `clinicalSubtypesStratification` 已低于 25% 阈值（2379 篇，22.4%），但低置信度和冲突仍高，后续应继续把亚型/诊断/RWE 边界作为长期回归抽查对象。
2. FcRn 疑似漏归类样本：59 篇 assignment 具有 FcRn 产品/术语信号但 primary 不是 FcRn 社区。其中包含疗效终点、RWE、HEOR 和 competitive 作为合理 primary 的文献，不能直接等同于错误。
3. 补体/新靶点疑似漏归类样本：70 篇 assignment 具有补体产品/术语信号但 primary 不是补体社区。其中联合比较、RWE、HEOR 和宽泛综述需要保留 secondary/facet 解释，而不是一律提升补体 primary。
4. `competitiveLandscapeIndirectComparison` 已扩展到 453 篇、12 个相关专题。v4c 已收窄外科术式、健康对照和非药物剂量比较，后续做小样本回归即可。

## 抽样入口

### FcRn 疑似漏归类样本

- PMID 42360473 — Health-related quality of life outcomes with nipocalimab versus placebo in generalized myast...；primary=疗效终点与疾病负担；confidence=medium
- PMID 42322065 — Efgartigimod Versus Lymphoplasmapheresis as Preoperative Rapid Antibody-Clearing Therapies f...；primary=指南、共识与卫生经济；confidence=high
- PMID 42304705 — Comparing Efficacy and Safety of Various Monoclonal Antibodies in Myasthenia Gravis: A Syste...；primary=竞争格局与间接比较；confidence=high
- PMID 42266700 — Real-world efficacy of eculizumab in generalized myasthenia gravis patients with poor early ...；primary=补体与其他新靶点；confidence=high
- PMID 42064058 — Thymoma-associated anti-AMPAR encephalitis with myasthenia gravis: a case report.；primary=临床亚型与人群分层；confidence=medium
- PMID 42043767 — Treatment Characteristics and Healthcare Resource Utilization Among Patients with Myasthenia...；primary=真实世界证据与临床路径；confidence=high
- PMID 42030590 — Combined inhibition of complement C5 and neonatal Fc receptor in refractory generalized myas...；primary=补体与其他新靶点；confidence=high
- PMID 41979428 — Insufficient immunosuppressive treatment in patients with myasthenia gravis in the context o...；primary=真实世界证据与临床路径；confidence=high
- PMID 41928685 — Targeting Autoimmunity in Myasthenia Gravis: From Conventional to Novel Therapeutic Approaches.；primary=机制与转化医学；confidence=high
- PMID 41925914 — Efficacy and safety of complement inhibitors and FcRn blockers in generalized AChR antibody-...；primary=竞争格局与间接比较；confidence=medium
- PMID 41837820 — Double-Filtration Plasmapheresis Versus Efgartigimod for Generalized Myasthenia Gravis: Seve...；primary=竞争格局与间接比较；confidence=high
- PMID 41817916 — Correction: Assessing the Value Contribution of Vyvgart® (Efgartigimod Alfa) in the Treatmen...；primary=指南、共识与卫生经济；confidence=high

### 补体疑似漏归类样本

- PMID 42304705 — Comparing Efficacy and Safety of Various Monoclonal Antibodies in Myasthenia Gravis: A Syste...；primary=竞争格局与间接比较；confidence=high
- PMID 42168668 — Anti-acetylcholine receptor antibody overshoot following efgartigimod in myasthenia gravis: ...；primary=FcRn 靶向治疗；confidence=high
- PMID 41979428 — Insufficient immunosuppressive treatment in patients with myasthenia gravis in the context o...；primary=真实世界证据与临床路径；confidence=high
- PMID 41928685 — Targeting Autoimmunity in Myasthenia Gravis: From Conventional to Novel Therapeutic Approaches.；primary=机制与转化医学；confidence=high
- PMID 41925914 — Efficacy and safety of complement inhibitors and FcRn blockers in generalized AChR antibody-...；primary=竞争格局与间接比较；confidence=medium
- PMID 41760990 — Early versus late add-on therapy in generalized myasthenia gravis: a multicenter real-world ...；primary=真实世界证据与临床路径；confidence=medium
- PMID 41591648 — Assessing the Value Contribution of Vyvgart® (Efgartigimod Alfa) in the Treatment of General...；primary=指南、共识与卫生经济；confidence=high
- PMID 41524776 — Pharmacological and speech-language pathology management of dysphagia in patients with myast...；primary=疗效终点与疾病负担；confidence=high
- PMID 41520205 — Health economic evaluations of myasthenia gravis: a systematic review.；primary=指南、共识与卫生经济；confidence=high
- PMID 41505161 — Novel Therapies for Generalized Myasthenia Gravis: Insights Into FcRn and Complement Inhibit...；primary=FcRn 靶向治疗；confidence=medium
- PMID 41422493 — Body weight distribution of US patients with myasthenia gravis.；primary=指南、共识与卫生经济；confidence=medium
- PMID 41389129 — Oral Corticosteroid and Nonsteroidal Immunosuppressant Therapy Use in Patients with Myasthen...；primary=真实世界证据与临床路径；confidence=high

## 建议下一步

1. v4c 已完成 LLM 抽样 review 后的 P0 规则回写；后续每次规则调整都应保留 30-50 篇固定回归样本。
2. P1：继续抽查 `clinicalSubtypesStratification`、`diagnosisMonitoringPrediction` 的低置信度样本，重点看 MG 只是背景/鉴别诊断的文献是否应进入 unassigned。
3. P1：把 FcRn / complement 疑似漏归类样本拆成“合理 secondary”和“真实漏归类”两类，避免只看泄漏计数做误判。
4. P1：为 `competitiveLandscapeIndirectComparison` 增加前端解释，说明该社区只代表药物、治疗策略、HEOR 或 evidence synthesis 的比较，不代表所有 versus 文献。
5. 若下一次周更后 low/conflict 未反弹，可进入 Phase 4 动态诊治格局，让 LLM 读取社区变化、图谱变化和 wiki 覆盖变化生成月度洞察。

## Phase 4 进入条件

动态诊治格局可以在 v4c 规则稳定后进入，但生成洞察时必须展示 PMID、证据等级、社区 primary/secondary、图谱节点和 abstract-level 局限。
