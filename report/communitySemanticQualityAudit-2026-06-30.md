# MA-MG-HUB 社区语义层质量审计

生成时间：2026-06-30 10:50:18

## 总览

- 总文献：10635
- 已归类：8847（83.2%）
- 未归类：1788（16.8%）
- 低置信度：2771（26.1%）
- 冲突归类：2118（19.9%）
- wiki 专题覆盖：10/10 个社区

## 社区分布

| 社区 | 文献 | 占比 | 低置信度 | 冲突 | 专题 | 近14天 |
| --- | --- | --- | --- | --- | --- | --- |
| 临床亚型与人群分层 | 2584 | 24.3% | 959 | 629 | 27 | 4 |
| 未归类 | 1788 | 16.8% | 0 | 0 | 0 | 0 |
| 诊断、监测与预测 | 1361 | 12.8% | 601 | 266 | 13 | 8 |
| 机制与转化医学 | 1330 | 12.5% | 349 | 239 | 25 | 5 |
| 安全性与用药管理 | 846 | 8% | 417 | 256 | 23 | 4 |
| 疗效终点与疾病负担 | 674 | 6.3% | 226 | 203 | 18 | 10 |
| 真实世界证据与临床路径 | 671 | 6.3% | 175 | 178 | 15 | 4 |
| 竞争格局与间接比较 | 631 | 5.9% | 19 | 138 | 22 | 1 |
| 补体与其他新靶点 | 388 | 3.6% | 0 | 97 | 25 | 1 |
| FcRn 靶向治疗 | 289 | 2.7% | 0 | 98 | 26 | 4 |
| 指南、共识与卫生经济 | 73 | 0.7% | 25 | 14 | 3 | 0 |

## 主要质量信号

### 低置信度占比较高

| 社区 | 文献 | 低置信度 | 比例 |
| --- | --- | --- | --- |
| 临床亚型与人群分层 | 2584 | 959 | 37.1% |
| 诊断、监测与预测 | 1361 | 601 | 44.2% |
| 安全性与用药管理 | 846 | 417 | 49.3% |
| 机制与转化医学 | 1330 | 349 | 26.2% |
| 疗效终点与疾病负担 | 674 | 226 | 33.5% |
| 真实世界证据与临床路径 | 671 | 175 | 26.1% |
| 指南、共识与卫生经济 | 73 | 25 | 34.2% |

### 冲突归类 Top Pairs

| Primary | Secondary | 冲突数 | 样本 PMID |
| --- | --- | --- | --- |
| 临床亚型与人群分层 | 诊断、监测与预测 | 231 | 42303225；42266578；42064058 |
| 临床亚型与人群分层 | 机制与转化医学 | 209 | 42303225；41936333；41908611 |
| 临床亚型与人群分层 | 真实世界证据与临床路径 | 205 | 42266578；41959797；41936404 |
| 临床亚型与人群分层 | 安全性与用药管理 | 105 | 41969435；41936404；41793243 |
| 安全性与用药管理 | 诊断、监测与预测 | 101 | 42338513；42216195；42132748 |
| 机制与转化医学 | 临床亚型与人群分层 | 100 | 42256950；42216051；42083560 |
| 诊断、监测与预测 | 临床亚型与人群分层 | 97 | 42344535；42320955；42138399 |
| 诊断、监测与预测 | 真实世界证据与临床路径 | 97 | 42308878；42211300；42138399 |
| 诊断、监测与预测 | 机制与转化医学 | 92 | 42320955；42274862；42070048 |
| 真实世界证据与临床路径 | 临床亚型与人群分层 | 85 | 42336346；42190146；41884848 |
| 安全性与用药管理 | 真实世界证据与临床路径 | 83 | 42132748；41992576；41784328 |
| 临床亚型与人群分层 | 疗效终点与疾病负担 | 77 | 42046766；41631867；41579003 |

### 专题覆盖稀疏社区

| 社区 | 专题 | 本周更新专题 | 高置信专题 | 社区文献 |
| --- | --- | --- | --- | --- |
| 指南、共识与卫生经济 | 3 | 2 | 0 | 73 |
| 诊断、监测与预测 | 13 | 13 | 1 | 1361 |
| 真实世界证据与临床路径 | 15 | 11 | 1 | 671 |
| 疗效终点与疾病负担 | 18 | 15 | 5 | 674 |
| 竞争格局与间接比较 | 22 | 17 | 0 | 631 |
| 安全性与用药管理 | 23 | 17 | 4 | 846 |
| 机制与转化医学 | 25 | 20 | 2 | 1330 |
| 补体与其他新靶点 | 25 | 19 | 2 | 388 |

## 疑似边界问题

1. `clinicalSubtypesStratification` 已低于 25% 阈值（2584 篇，24.3%），但低置信度和冲突仍高，下一步应抽样 review 亚型/诊断/RWE 边界。
2. FcRn 疑似漏归类样本：61 篇 assignment 具有 FcRn 产品/术语信号但 primary 不是 FcRn 社区。需要检查这些是否应保留为疗效/RWE/安全性 primary，还是应提升 FcRn 优先级。
3. 补体/新靶点疑似漏归类样本：69 篇 assignment 具有补体产品/术语信号但 primary 不是补体社区。建议重点看联合比较、RWE 和 crisis/case report 的主语义。
4. `competitiveLandscapeIndirectComparison` 已扩展到 631 篇、22 个相关专题。下一步应抽样确认是否包含过多胸腺手术或非药物技术比较。

## 抽样入口

### FcRn 疑似漏归类样本

- PMID 42360473 — Health-related quality of life outcomes with nipocalimab versus placebo in generalized myast...；primary=疗效终点与疾病负担；confidence=high
- PMID 42304705 — Comparing Efficacy and Safety of Various Monoclonal Antibodies in Myasthenia Gravis: A Syste...；primary=竞争格局与间接比较；confidence=high
- PMID 42254001 — Real-world study of efgartigimod in AChR antibody-positive generalized myasthenia gravis: th...；primary=疗效终点与疾病负担；confidence=high
- PMID 42157574 — Evaluation of Sustained Disease Control With Nipocalimab Versus Placebo in the Phase 3 Vivac...；primary=疗效终点与疾病负担；confidence=high
- PMID 42096038 — Effectiveness and safety of efgartigimod in myasthenia gravis: A meta-analysis of different ...；primary=疗效终点与疾病负担；confidence=high
- PMID 42064058 — Thymoma-associated anti-AMPAR encephalitis with myasthenia gravis: a case report.；primary=临床亚型与人群分层；confidence=medium
- PMID 42043767 — Treatment Characteristics and Healthcare Resource Utilization Among Patients with Myasthenia...；primary=真实世界证据与临床路径；confidence=high
- PMID 42030590 — Combined inhibition of complement C5 and neonatal Fc receptor in refractory generalized myas...；primary=补体与其他新靶点；confidence=high
- PMID 41928685 — Targeting Autoimmunity in Myasthenia Gravis: From Conventional to Novel Therapeutic Approaches.；primary=补体与其他新靶点；confidence=medium
- PMID 41760990 — Early versus late add-on therapy in generalized myasthenia gravis: a multicenter real-world ...；primary=补体与其他新靶点；confidence=high
- PMID 41582064 — Heterogeneous response to efgartigimod in real-world experience with myasthenia gravis: Pred...；primary=疗效终点与疾病负担；confidence=high
- PMID 41572778 — Efgartigimod in Very-Late-Onset Generalized Myasthenia Gravis: A Real-World Study on Effecti...；primary=疗效终点与疾病负担；confidence=high

### 补体疑似漏归类样本

- PMID 42315783 — Multidomain Fatigue, Cognitive, and Quality of Life Observations in Generalized Myasthenia G...；primary=疗效终点与疾病负担；confidence=high
- PMID 42304705 — Comparing Efficacy and Safety of Various Monoclonal Antibodies in Myasthenia Gravis: A Syste...；primary=竞争格局与间接比较；confidence=high
- PMID 42271114 — Eculizumab in Myasthenia Gravis: A Multicenter Retrospective Real-World Study in China.；primary=真实世界证据与临床路径；confidence=medium
- PMID 42266700 — Real-world efficacy of eculizumab in generalized myasthenia gravis patients with poor early ...；primary=FcRn 靶向治疗；confidence=medium
- PMID 42168668 — Anti-acetylcholine receptor antibody overshoot following efgartigimod in myasthenia gravis: ...；primary=FcRn 靶向治疗；confidence=high
- PMID 41979428 — Insufficient immunosuppressive treatment in patients with myasthenia gravis in the context o...；primary=FcRn 靶向治疗；confidence=medium
- PMID 41925914 — Efficacy and safety of complement inhibitors and FcRn blockers in generalized AChR antibody-...；primary=FcRn 靶向治疗；confidence=high
- PMID 41904994 — Real-world effectiveness and safety of zilucoplan in patients with anti-AChR myasthenia grav...；primary=真实世界证据与临床路径；confidence=high
- PMID 41847264 — Effectiveness and Safety of Eculizumab in Highly Active AChR+gMG and Its Therapeutic Respons...；primary=疗效终点与疾病负担；confidence=high
- PMID 41591648 — Assessing the Value Contribution of Vyvgart® (Efgartigimod Alfa) in the Treatment of General...；primary=FcRn 靶向治疗；confidence=high
- PMID 41553721 — Eculizumab as a Fast-Acting Therapy in a Myasthenic Crisis Patient With Poor Response to Efg...；primary=FcRn 靶向治疗；confidence=high
- PMID 41524776 — Pharmacological and speech-language pathology management of dysphagia in patients with myast...；primary=FcRn 靶向治疗；confidence=high

## 建议下一步

1. 先做人工抽样 review，不直接上 LLM 仲裁。
2. P0：抽查 `clinicalSubtypesStratification`、`diagnosisMonitoringPrediction`、`safetyMedicationManagement` 的低置信度样本，决定是否继续收窄宽泛词。
3. P0：抽查 FcRn / complement 疑似漏归类样本，区分“治疗机制 primary”与“疗效/RWE/安全性 primary”。
4. P1：抽查 `competitiveLandscapeIndirectComparison` 扩展后的样本，必要时把外科路径比较降到 clinical/RWE。
5. P1：规则稳定后再考虑 LLM/人工仲裁剩余低置信度样本。

## 暂不进入 Phase 4

动态诊治格局应等待上述 taxonomy review 和重跑后的社区质量指标稳定，再读取社区变化、图谱变化和 wiki 覆盖变化生成洞察。
