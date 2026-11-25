/* MA-MG-HUB 知识库 —— 沉淀层
 * 定位：首页更新流（刷）与 MSL 工作台（用）之后，愿意"坐下来"的地方。
 *   ① 书房入口：近期沉淀（流落在哪） / 精读架（读什么） / 值得想想（想什么）
 *   ② 知识地图：概念按类别分列，只画扣除各自热门度后仍明显同现的"特异关联"
 *   ③ 精读区：一个概念，三面镜子——知识 / 连接 / 思考
 * 数据来源：full PubMed abstract 派生的概念图谱、策展专题（静态快照）、
 *   本周文献与试验信号、临床问题、中外指南分歧、中国作者医院网络。
 * 边界：共现与"特异关联"只是同现强度，不代表因果；
 *   信号 / 问题到概念的"落点"由关键词关联推断，只用于导航，不代表证据归属；
 *   详细判断一律回到 PMID 原文。
 */
(function () {
  'use strict';

  var hub = window.MgHub || {};

  // ===== 数据接入（全部为公开产物；任一缺失时逐级降级，不报错） =====
  var graphData = window.MG_KNOWLEDGE_GRAPH || {};
  var graphHealthData = window.MG_GRAPH_HEALTH || { summary: {}, health: {} };
  var nodes = graphData.nodes || [];
  var coreEdges = graphData.edges || [];
  var allEdges = graphData.all_edges || coreEdges;
  var nodeRefs = graphData.node_references || {};
  var matrixRows = graphData.evidence_matrix || [];
  var curatedData = window.MG_CURATED_TOPICS || { topics: [], bridge_by_node: {}, stats: {} };
  var curatedTopics = curatedData.topics || [];
  var communityTaxonomy = window.MG_COMMUNITY_TAXONOMY || { communities: [] };
  var communityCardsData = window.MG_COMMUNITY_CARDS || { cards: [] };
  var signalsData = window.MG_SIGNALS_DATA || { signals: [] };
  var trialSignalsData = window.MG_TRIAL_SIGNALS_DATA || {};
  var clinicalQuestionGroups = (window.MG_CLINICAL_QUESTIONS || { groups: [] }).groups || [];
  // 编辑层：逐概念排查后撰写的导语 / 思考问题 / 重点关系解读；缺失时自动资产兜底。
  var editorialData = window.MG_KNOWLEDGE_EDITORIAL || { concepts: {}, relations: {} };

  // ===== 一、显示层字典 =====
  // 底座节点：见于全部命中文献，它与其他概念的连线没有区分意义，地图默认不画。
  var HUB_ID = 'myastheniaGravis';

  var typeLabel = {
    disease: '疾病',
    drug: '药物/干预',
    mechanism: '机制',
    population: '人群/亚型',
    outcome: '结局',
    evidence: '证据类型'
  };

  // 地图列顺序：人群 → 机制 → 药物 → 结局 → 证据类型
  var typeOrder = ['population', 'mechanism', 'drug', 'outcome', 'evidence'];

  // 中文显示名：药物只收录本站药物词典里已有的中文药名，不自拟；其余为通用术语。查不到时回退英文标题。
  var zhLabel = {
    myastheniaGravis: '重症肌无力',
    generalizedMg: '全身型 MG',
    ocularMg: '眼肌型 MG',
    myasthenicCrisis: '肌无力危象',
    refractoryMg: '难治性 MG',
    thymomaAssociatedMg: '胸腺瘤相关 MG',
    juvenileMg: '儿童/青少年 MG',
    achrPositive: 'AChR 抗体阳性 MG',
    muskPositive: 'MuSK 抗体阳性 MG',
    lrp4Positive: 'LRP4 抗体阳性 MG',
    seronegativeMg: '血清阴性 MG',
    chinaEvidence: '中国证据',
    fcrnInhibition: 'FcRn 抑制',
    complementInhibition: '补体抑制',
    bCellTargeting: 'B 细胞/浆细胞靶向',
    baffAprilModulation: 'BAFF/APRIL 调节',
    conventionalImmunosuppression: '传统免疫抑制',
    rapidRescue: '快速救援治疗',
    biomarkerPathogenesis: '生物标志物与发病机制',
    autoantibodyPathway: '自身抗体通路',
    cytokineSignaling: '细胞因子信号',
    geneticSusceptibility: '遗传易感性',
    immuneCellSignature: '免疫细胞特征',
    efgartigimod: '艾加莫德',
    rozanolixizumab: '罗泽利昔珠单抗',
    nipocalimab: '尼卡利单抗',
    batoclimab: '巴托利单抗',
    eculizumab: '依库珠单抗',
    ravulizumab: '瑞利珠单抗',
    zilucoplan: '泽卢克布仑钠',
    rituximab: '利妥昔单抗',
    telitacicept: '泰它西普',
    pyridostigmine: '溴吡斯的明',
    corticosteroids: '糖皮质激素',
    azathioprine: '硫唑嘌呤',
    mycophenolate: '吗替麦考酚酯',
    calcineurinInhibitors: '他克莫司/环孢素',
    ivig: '静注人免疫球蛋白',
    plasmaExchange: '血浆置换',
    rapidOnset: '快速起效',
    longTermDurability: '长期疗效与维持',
    safetyOutcome: '安全性与不良事件',
    steroidSparing: '激素减量',
    infectionRisk: '感染风险',
    infusionInjectionReactions: '输注/注射反应',
    mgAdl: 'MG-ADL 量表',
    qmg: 'QMG 量表',
    mgQol: '生活质量',
    caseEvidence: '病例证据',
    realWorldEvidence: '真实世界证据',
    rctEvidence: '随机对照证据',
    metaEvidence: '系统综述/间接比较',
    guidelineEvidence: '指南/共识',
    pharmacovigilanceEvidence: '药物警戒证据'
  };

  // 关键词别名：仅用于把信号 / 临床问题 / 指南分歧关联到概念（导航用途），不是证据归属。
  // 第二项为权重：3 = 专有名词或药物名；2 = 特异性概念词；1 = 泛化词。以 * 结尾表示前缀匹配。
  var nodeAlias = {
    achrPositive: [['achr', 3], ['acetylcholine receptor', 2]],
    thymomaAssociatedMg: [['thymoma', 3], ['thymectomy', 3], ['thymic', 2], ['胸腺', 3]],
    caseEvidence: [['case report*', 2], ['case series', 2], ['病例报告', 2]],
    realWorldEvidence: [['real-world', 2], ['real world', 2], ['rwe', 2], ['真实世界', 2], ['observational', 1], ['registry', 1]],
    chinaEvidence: [['china', 2], ['chinese', 2], ['中国', 2]],
    rapidOnset: [['rapid onset', 2], ['rapid response', 2], ['time-to-onset', 3], ['onset of action', 2], ['快速起效', 3], ['起效', 2]],
    autoantibodyPathway: [['autoantibod*', 2], ['antibody titer', 2], ['antibody titre', 2], ['serostatus', 2], ['antibody function', 2], ['自身抗体', 2]],
    corticosteroids: [['corticosteroid*', 2], ['prednisone', 3], ['prednisolone', 3], ['glucocorticoid*', 2], ['糖皮质激素', 3], ['激素', 2]],
    conventionalImmunosuppression: [['immunosuppress*', 2], ['免疫抑制', 2]],
    safetyOutcome: [['safety', 1], ['adverse event*', 2], ['adverse effect*', 2], ['tolerability', 2], ['安全性', 1], ['不良事件', 2]],
    myasthenicCrisis: [['myasthenic crisis', 3], ['crisis', 2], ['危象', 3]],
    rapidRescue: [['rescue', 2], ['抢救', 2], ['救援', 2]],
    muskPositive: [['musk', 3], ['muscle-specific kinase', 2]],
    biomarkerPathogenesis: [['biomarker*', 2], ['pathogenesis', 2], ['生物标志物', 2]],
    longTermDurability: [['long-term', 1], ['long term', 1], ['durability', 2], ['sustained', 1], ['persistent response', 2], ['长期', 1], ['维持', 1], ['remission', 1]],
    generalizedMg: [['generalized myasthenia', 2], ['generalised myasthenia', 2], ['gmg', 2], ['全身型', 2]],
    ocularMg: [['ocular myasthenia', 3], ['ocular mg', 3], ['omg', 2], ['眼肌型', 3], ['眼型', 3]],
    plasmaExchange: [['plasma exchange', 3], ['plasmapheresis', 3], ['plex', 2], ['dfpp', 2], ['血浆置换', 3]],
    mgAdl: [['mg-adl', 3], ['mg adl', 3], ['mg activities of daily living', 2]],
    pyridostigmine: [['pyridostigmine', 3], ['溴吡斯的明', 3]],
    geneticSusceptibility: [['genetic', 1], ['gwas', 2], ['hla-', 2], ['polymorphism', 2], ['遗传', 2]],
    immuneCellSignature: [['cd4', 2], ['cd8', 2], ['免疫细胞', 1]],
    mgQol: [['qol', 3], ['quality of life', 2], ['生活质量', 2], ['patient-reported', 2]],
    ivig: [['ivig', 3], ['intravenous immunoglobulin', 3], ['免疫球蛋白', 2]],
    rctEvidence: [['randomized', 1], ['randomised', 1], ['placebo-controlled', 2], ['rct*', 2]],
    refractoryMg: [['refractory', 2], ['treatment-resistant', 2], ['难治', 3]],
    complementInhibition: [['complement', 2], ['c5', 2], ['补体', 3]],
    cytokineSignaling: [['cytokine*', 2], ['interleukin', 2]],
    qmg: [['qmg', 3]],
    infectionRisk: [['infection', 2], ['meningococcal', 2], ['感染', 2]],
    bCellTargeting: [['b-cell*', 3], ['b cell*', 2], ['cd20', 3], ['cd19', 3], ['bcma', 3], ['b 细胞', 2], ['b细胞', 2]],
    rituximab: [['rituximab', 3], ['利妥昔单抗', 3]],
    metaEvidence: [['meta-analysis', 2], ['systematic review', 1], ['indirect comparison*', 3], ['indirect treatment', 2], ['network meta', 3], ['间接比较', 3]],
    seronegativeMg: [['seronegative', 3], ['血清阴性', 3]],
    efgartigimod: [['efgartigimod', 3], ['vyvgart', 3], ['argx-113', 3], ['艾加莫德', 3]],
    calcineurinInhibitors: [['tacrolimus', 3], ['cyclosporine', 3], ['calcineurin', 2], ['他克莫司', 3], ['环孢素', 3]],
    azathioprine: [['azathioprine', 3], ['硫唑嘌呤', 3]],
    fcrnInhibition: [['fcrn', 3], ['neonatal fc receptor', 3], ['igg recycling', 2]],
    eculizumab: [['eculizumab', 3], ['依库珠单抗', 3]],
    juvenileMg: [['juvenile', 3], ['pediatric', 3], ['paediatric', 3], ['children', 2], ['儿童', 3], ['青少年', 2]],
    lrp4Positive: [['lrp4', 3]],
    guidelineEvidence: [['guideline', 1], ['consensus', 1], ['指南', 1], ['共识', 1]],
    mycophenolate: [['mycophenolate', 3], ['麦考酚', 3]],
    steroidSparing: [['steroid-sparing', 3], ['steroid sparing', 3], ['激素减量', 3], ['减量', 2], ['taper*', 2]],
    ravulizumab: [['ravulizumab', 3], ['瑞利珠单抗', 3]],
    zilucoplan: [['zilucoplan', 3], ['泽卢克布仑钠', 3]],
    rozanolixizumab: [['rozanolixizumab', 3], ['罗泽利昔珠单抗', 3]],
    baffAprilModulation: [['baff', 3], ['blys', 3], ['april', 1], ['taci', 2]],
    infusionInjectionReactions: [['infusion reaction*', 2], ['injection-site', 2], ['infusion-related', 2], ['输注反应', 2]],
    nipocalimab: [['nipocalimab', 3], ['尼卡利单抗', 3]],
    telitacicept: [['telitacicept', 3], ['泰它西普', 3]],
    pharmacovigilanceEvidence: [['faers', 3], ['pharmacovigilance', 3], ['药物警戒', 3]],
    batoclimab: [['batoclimab', 3], ['巴托利单抗', 3]],
    cemdisiran: [['cemdisiran', 3]]
  };

  var topicSourceTypeLabel = {
    concept: '概念',
    entity: '事实',
    dataPoint: '数据',
    comparison: '对比'
  };

  // 策展快照日期：来自 curated-topics.js 的 generated_at，只取日期部分；它不等于各专题正文的更新日期。
  var topicSnapshotDate = (function () {
    var raw = curatedData.generated_at || '';
    return raw ? String(raw).slice(0, 10) : '未知';
  })();

  // 落点判定门槛：加权关键词得分达到该值才认为"落在"某个概念上。
  var LINK_MIN_SCORE = 6;
  // 特异关联的最小共现篇数：篇数太少时倍数噪声大，不参与排序与画图。
  var LIFT_MIN_COUNT = 5;
  // 地图骨干关系：每个概念最多保留几条最强关系。
  var BACKBONE_TOP = 3;

  // ===== 二、索引层 =====
  var nodesById = {};
  nodes.forEach(function (node) { nodesById[node.id] = node; });

  var matchedArticles = Number((graphData.stats || {}).matched_articles) || 0;
  if (!matchedArticles) {
    nodes.forEach(function (node) { matchedArticles = Math.max(matchedArticles, node.article_count || 0); });
  }
  if (!matchedArticles) matchedArticles = 1;

  var edgesById = {};
  allEdges.forEach(function (edge) { edgesById[edge.id] = edge; });

  // 关系明细索引：evidence_matrix 每行是一条"概念对"的交叉证据（含 references / limitation）。
  // 不是全量关系；没有矩阵记录的关系回退用 edge.pmids。
  var matrixByPairKey = {};
  function pairKey(a, b) { return [a, b].sort().join('::'); }
  matrixRows.forEach(function (row) {
    if (row.source_id && row.target_id) matrixByPairKey[pairKey(row.source_id, row.target_id)] = row;
  });

  // 每个概念的关联概念列表（排除底座节点），并预计算"特异度"：
  // 实际同现篇数 ÷ 按两者各自篇数得到的预期同现篇数。数值越高，越不能用"各自都热门"来解释。
  var neighborsByNode = {};
  nodes.forEach(function (node) { neighborsByNode[node.id] = []; });
  allEdges.forEach(function (edge) {
    if (!nodesById[edge.from] || !nodesById[edge.to]) return;
    addNeighbor(edge.from, edge.to, edge);
    addNeighbor(edge.to, edge.from, edge);
  });
  function addNeighbor(selfId, otherId, edge) {
    if (selfId === HUB_ID || otherId === HUB_ID) return;
    var expected = ((nodesById[selfId].article_count || 0) * (nodesById[otherId].article_count || 0)) / matchedArticles;
    neighborsByNode[selfId].push({
      edgeId: edge.id,
      otherId: otherId,
      count: edge.article_count || 0,
      lift: expected > 0 ? (edge.article_count || 0) / expected : 0,
      level: edge.best_evidence_level || ''
    });
  }

  // 主题分类（数据层仍叫 community）：只用于染色、筛选与说明，不单独成页。
  var taxonomyById = {};
  var communityCardsById = {};
  var communityRows = [];
  (communityTaxonomy.communities || []).forEach(function (item) { taxonomyById[item.id] = item; });
  (communityCardsData.cards || []).forEach(function (card) {
    communityCardsById[card.id] = card;
    communityRows.push(Object.assign({}, taxonomyById[card.id] || {}, card));
  });
  (communityTaxonomy.communities || []).forEach(function (item) {
    if (!communityCardsById[item.id]) communityRows.push(item);
  });
  var communityPalette = [
    '#2563eb', '#0891b2', '#16a34a', '#ca8a04', '#7c3aed',
    '#dc2626', '#0f766e', '#4f46e5', '#9333ea', '#64748b'
  ];
  var communityColorById = {};
  communityRows.forEach(function (community, index) {
    communityColorById[community.id] = communityPalette[index % communityPalette.length];
  });
  function communityColor(communityId) {
    return communityColorById[communityId] || '#64748b';
  }
  function domainTitle(communityId) {
    var card = communityCardsById[communityId] || {};
    var taxonomy = taxonomyById[communityId] || {};
    return card.title || taxonomy.title || '';
  }

  // 专题索引：bridge_by_node 给出"概念 → 专题"；预处理要点文本并按可读性排序。
  var topicsById = {};
  var topicPrep = {};
  var topicsByNode = {};
  curatedTopics.forEach(function (topic) { topicsById[topic.id] = topic; });
  // 专题排序：可读性优先；标题或摘要直接提到当前概念的专题再往前排。
  function topicRelevance(item, node) {
    var lower = (String(item.topic.title || '') + ' ' + String(item.topic.summary || '')).toLowerCase();
    var mentioned = [node.id, zhLabel[node.id] || '', node.title || ''].some(function (term) {
      return term && lower.indexOf(String(term).toLowerCase()) !== -1;
    });
    return item.quality + (mentioned ? 4 : 0);
  }
  nodes.forEach(function (node) {
    // 专题白名单：只显示逐节点审阅后确认相关的策展专题；未列出者如实显示空态。
    var ids = (editorialData.topics && editorialData.topics[node.id]) || [];
    topicsByNode[node.id] = ids.map(function (id) { return prepareTopic(topicsById[id]); })
      .filter(function (item) { return item && !item.isStub; })
      .sort(function (a, b) { return topicRelevance(b, node) - topicRelevance(a, node); });
  });

  // 关键词匹配规则（编译一次）。
  var aliasRules = [];
  Object.keys(nodeAlias).forEach(function (nodeId) {
    if (!nodesById[nodeId]) return;
    nodeAlias[nodeId].forEach(function (entry) {
      aliasRules.push({ id: nodeId, weight: entry[1], re: compileAlias(entry[0]) });
    });
  });

  // 落点索引：信号 / 临床问题 / 指南分歧 → 概念。
  var signalLinks = [];
  var questionLinks = [];
  var divergenceLinks = [];
  var signalsByNode = {};
  var questionsByNode = {};
  var divergencesByNode = {};
  // 文献信号跨周沉淀：本周 signals + signal_history  histórico（与试验信号同构）。
  var litHistory = signalsData.signal_history || [];
  litHistory.concat((signalsData.signals || []).filter(function (signal) {
    return !litHistory.some(function (item) {
      return String(item.candidateId || '') === String(signal.date) + '::' + String(signal.title);
    });
  })).forEach(function (signal) {
    var key = 'lit-' + String(signal.candidateId || signal.id || '');
    signalLinks.push({
      kind: 'lit',
      key: key,
      data: signal,
      hits: linkNodes([
        [signal.title, 3],
        [(signal.keywords || []).join(' '), 1],
        [signal.summary, 1],
        [signal.clinicalQuestion, 2],
        [signal.article && signal.article.title, 3],
        [signal.article && signal.article.key_evidence, 0.5]
      ])
    });
  });
  (trialSignalsData.signal_history || []).forEach(function (signal) {
    signalLinks.push({
      kind: 'trial',
      key: 'trial-' + String(signal.candidateId || signal.id || ''),
      data: signal,
      hits: linkNodes([
        [(signal.interventions || []).join(' '), 3],
        [(signal.conditions || []).join(' '), 1],
        [signal.title, 2]
      ])
    });
  });
  var allQuestions = [];
  clinicalQuestionGroups.forEach(function (group) {
    (group.questions || []).forEach(function (question) {
      allQuestions.push({ question: question, group: group });
      questionLinks.push({
        key: String(question.id || ''),
        data: question,
        group: group,
        hits: linkNodes([
          [(question.keywords || []).join(' '), 3],
          [question.question, 3],
          [question.whyOpen, 1],
          [(question.answer || []).map(function (item) { return item.text; }).join(' '), 1]
        ])
      });
    });
  });
  function indexLinksByNode(links) {
    var index = {};
    links.forEach(function (link) {
      filteredHits(link).forEach(function (hit) {
        index[hit[0]] = index[hit[0]] || [];
        index[hit[0]].push({ link: link, score: hit[1] });
      });
    });
    Object.keys(index).forEach(function (nodeId) {
      index[nodeId].sort(function (a, b) { return b.score - a.score; });
    });
    return index;
  }
  function filteredHits(link) {
    return (link.hits || []).filter(function (hit) { return hit[1] >= LINK_MIN_SCORE; }).slice(0, link.limit || 4);
  }
  function buildDivergenceLinks() {
    var landscape = window.MG_LANDSCAPE_DATA || {};
    var meta = (landscape.china_landscape || {}).guideline_divergence || {};
    divergenceLinks = (meta.divergences || []).map(function (divergence) {
      var link = {
        key: String(divergence.id || ''),
        data: divergence,
        via: {},
        // 指南分歧会补入"间接相关"的药物概念，命中上限放宽到 10
        limit: 10,
        hits: linkNodes([[divergence.dimension, 3], [divergence.title, 3]])
      };
      // 指南分歧多按机制或人群表述；与命中概念有强特异关联的药物视为"经该概念间接相关"，
      // 多个概念都命中时，取与该药物特异度最高的那个作为"经由"。
      var viaByDrug = {};
      filteredHits(link).forEach(function (hit) {
        var concept = nodesById[hit[0]];
        if (!concept || (concept.type !== 'mechanism' && concept.type !== 'population')) return;
        nodes.forEach(function (node) {
          if (node.type !== 'drug') return;
          var strong = neighborsByNode[node.id].filter(function (item) {
            return item.otherId === concept.id && item.lift >= 5 && item.count >= LIFT_MIN_COUNT;
          })[0];
          if (!strong) return;
          var previous = viaByDrug[node.id];
          if (!previous || strong.lift > previous.lift) viaByDrug[node.id] = { conceptId: concept.id, lift: strong.lift };
        });
      });
      Object.keys(viaByDrug).forEach(function (drugId) {
        if (filteredHits(link).some(function (item) { return item[0] === drugId; })) return;
        link.via[drugId] = viaByDrug[drugId].conceptId;
        link.hits.push([drugId, LINK_MIN_SCORE]);
      });
      return link;
    });
    divergencesByNode = indexLinksByNode(divergenceLinks);
  }
  signalsByNode = indexLinksByNode(signalLinks);
  questionsByNode = indexLinksByNode(questionLinks);
  buildDivergenceLinks();

  // ===== 三、通用工具 =====
  function escapeHtml(value) {
    if (hub.escapeText) return hub.escapeText(value);
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }

  function escapeHref(value, fallback) {
    if (hub.safeUrl) return hub.safeUrl(value, fallback || '#');
    return escapeHtml(fallback || '#');
  }

  function pageUrl(path) {
    if (hub.pageUrl) return hub.pageUrl(path);
    return path;
  }

  function safeClassToken(value, fallback) {
    return hub.safeClassToken ? hub.safeClassToken(value, fallback) : String(value || fallback || 'unknown').replace(/[^a-zA-Z0-9_-]+/g, '-');
  }

  function cssEscape(value) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(value);
    return String(value).replace(/"/g, '\\"');
  }

  function escapeRegExp(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function compactNumber(value) {
    var n = Number(value || 0);
    if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
    return String(n);
  }

  function unique(values) {
    var seen = {};
    var out = [];
    (values || []).forEach(function (value) {
      var key = String(value || '').trim();
      if (!key || seen[key]) return;
      seen[key] = true;
      out.push(key);
    });
    return out;
  }

  // 别名编译：英文词按词边界匹配，* 结尾按前缀匹配，中文或以连字符结尾的写法直接子串匹配。
  function compileAlias(alias) {
    var stem = /\*$/.test(alias);
    var body = stem ? alias.slice(0, -1) : alias;
    if (/[^\x00-\x7F]/.test(body) || /-$/.test(body)) {
      return { test: function (text) { return String(text).toLowerCase().indexOf(body.toLowerCase()) !== -1; } };
    }
    var source = stem
      ? '(^|[^a-z0-9])' + escapeRegExp(body)
      : '(^|[^a-z0-9])' + escapeRegExp(body) + '($|[^a-z0-9])';
    return new RegExp(source, 'i');
  }

  // fields：[[文本, 字段权重], ...]。返回 [[概念 id, 得分], ...]，按得分降序。
  function linkNodes(fields) {
    var scores = {};
    aliasRules.forEach(function (rule) {
      var hit = 0;
      for (var index = 0; index < fields.length; index += 1) {
        var text = fields[index][0];
        if (!text) continue;
        if (rule.re.test(String(text))) { hit = fields[index][1]; break; }
      }
      if (hit) scores[rule.id] = (scores[rule.id] || 0) + rule.weight * hit;
    });
    return Object.keys(scores).map(function (nodeId) { return [nodeId, scores[nodeId]]; })
      .sort(function (a, b) { return b[1] - a[1]; });
  }

  function fmtDate(value) {
    var raw = String(value || '').trim();
    var match = raw.match(/^\d{4}[-/](\d{2})[-/](\d{2})/);
    return match ? match[1] + '-' + match[2] : raw.slice(0, 10);
  }

  function pmidHref(pmid) {
    return 'https://pubmed.ncbi.nlm.nih.gov/' + encodeURIComponent(String(pmid)) + '/';
  }

  function pmidChip(pmid) {
    return '<a class="kg-pmid-link" href="' + escapeHref(pmidHref(pmid)) + '" target="_blank" rel="noopener">' +
      escapeHtml(pmid) + '</a>';
  }

  function renderReferenceItem(ref) {
    var meta = [
      ref.journal || '',
      ref.pub_date || '',
      ref.evidence_level ? 'Level ' + ref.evidence_level : '',
      (ref.study_types || []).slice(0, 2).join(' / ')
    ].filter(Boolean).join(' · ');
    return '<li><a class="text-link" href="' + escapeHref(ref.url) + '" target="_blank" rel="noopener">PMID ' +
      escapeHtml(ref.pmid) + '</a> ' + escapeHtml(ref.title || '') +
      '<br><span class="kg-ref-meta">' + escapeHtml(meta) + '</span></li>';
  }

  function truncateText(value, limit) {
    var text = String(value || '').replace(/\s+/g, ' ').trim();
    return text.length > limit ? text.slice(0, limit) + '…' : text;
  }

  // 中文名与英文标题的合并显示：任一方已包含对方时不重复。
  function nodeFull(node) {
    var zh = zhLabel[node.id] || '';
    var title = node.title || node.id;
    if (zh && zh.toLowerCase().indexOf(title.toLowerCase()) === -1 &&
      title.toLowerCase().indexOf(zh.toLowerCase()) === -1) return zh + ' ' + title;
    return zh || title;
  }

  function nodeShort(node) {
    return zhLabel[node.id] || node.title || node.id;
  }

  function nodeLinkHtml(node, extraClass) {
    return '<button class="kb-node-chip ' + (extraClass || '') + '" type="button" data-locate-node="' + escapeHtml(node.id) + '"' +
      ' style="--community-color:' + escapeHtml(communityColor(node.dominant_community_id)) + '"' +
      ' title="在图谱中定位「' + escapeHtml(nodeFull(node)) + '」；切换精读对象请点图谱圆点">' +
      escapeHtml(nodeShort(node)) + '</button>';
  }

  function levelRank(level) {
    var order = { I: 0, II: 1, III: 2, IV: 3, V: 4 };
    return order[level] == null ? 9 : order[level];
  }

  // 圆点颜色只标药物机制家族；其余概念一律中性色（类别已由同心圆环表达）。
  var familyColor = {
    fcrn: '#2563eb', complement: '#dc2626', bcell: '#7c3aed',
    conventional: '#ca8a04', symptomatic: '#0891b2', rescue: '#16a34a', other: '#94a3b8'
  };
  var drugFamily = {
    efgartigimod: 'fcrn', rozanolixizumab: 'fcrn', nipocalimab: 'fcrn', batoclimab: 'fcrn',
    eculizumab: 'complement', ravulizumab: 'complement', zilucoplan: 'complement', cemdisiran: 'complement',
    rituximab: 'bcell', telitacicept: 'bcell',
    corticosteroids: 'conventional', azathioprine: 'conventional', mycophenolate: 'conventional',
    calcineurinInhibitors: 'conventional',
    pyridostigmine: 'symptomatic',
    ivig: 'rescue', plasmaExchange: 'rescue'
  };
  function nodeFillColor(node) {
    return familyColor[drugFamily[node.id]] || familyColor.other;
  }

  function editorialForNode(nodeId) {
    return editorialData.concepts[nodeId] || null;
  }

  // 编辑层锚点 → 站内确切位置。统一走 pageUrl()，兼容 GitHub Pages 子路径。
  function editorialHref(spec, nodeId) {
    if (!spec) return '';
    var parts = String(spec).split(':');
    var kind = parts[0];
    var id = parts.slice(1).join(':');
    if (kind === 'question') return pageUrl('pages/landscape.html?tab=questions&question=' + encodeURIComponent(id));
    if (kind === 'chapter') return pageUrl('pages/landscape.html?tab=chapters&chapter=' + encodeURIComponent(id));
    if (kind === 'divergence') return pageUrl('pages/landscape.html?tab=overview&divergence=' + encodeURIComponent(id));
    if (kind === 'topic') return pageUrl('pages/knowledge.html?topic=' + encodeURIComponent(id) +
      (nodeId ? '&node=' + encodeURIComponent(nodeId) : ''));
    if (kind === 'signal') return homeUrl('?signal=' + encodeURIComponent(id));
    return '';
  }

  function editorialLinkLabel(spec) {
    return ({ question: '去诊治格局看这个问题', chapter: '去诊治格局看对应章节',
      divergence: '去诊治格局看立场差异', topic: '打开策展专题', signal: '回首页看信号卡' })[String(spec || '').split(':')[0]] || '查看出处';
  }

  // 重点关系有定制解读；其余按关系类型给出带边界的通用解读。
  function genericRelationReading(a, b, item) {
    if (a.type === 'drug' && b.type === 'drug') {
      return '两者都是药物，常在同一篇综述或间接比较中被一起讨论；同现说明"常被一起谈"，不代表疗效相当。';
    }
    if ((a.type === 'drug' && b.type === 'mechanism') || (b.type === 'drug' && a.type === 'mechanism')) {
      return '机制解释关系：' + nodeShort(a.type === 'drug' ? a : b) + ' 的讨论常落在 ' +
        nodeShort(a.type === 'mechanism' ? a : b) + ' 这一机制上。';
    }
    if ((a.type === 'drug' && b.type === 'outcome') || (b.type === 'drug' && a.type === 'outcome')) {
      return '终点关系：' + nodeShort(a.type === 'drug' ? a : b) + ' 的疗效或安全性讨论常用 ' +
        nodeShort(a.type === 'outcome' ? a : b) + ' 衡量。';
    }
    if (a.type === 'evidence' || b.type === 'evidence') {
      return '证据类型关系：这一主题的研究主要来自该类研究设计，读的时候先看研究等级再看结论。';
    }
    if (a.type === 'population' && b.type === 'mechanism') {
      return '人群与机制的关系：' + nodeShort(a) + ' 的机制解释常围绕 ' + nodeShort(b) + ' 展开。';
    }
    return '两者在同一批文献中同现，具体含义需要回到 PMID 原文核对。';
  }

  // ===== 专题预处理：把策展要点整理成可读文本；表格残片与元信息行归入"原始摘录" =====
  // 静态策展快照来自 wiki 笔记，原文里混有表格行、图例和重定向占位页，这里只做可读性整理，不改写观点。
  function prepClaim(claim) {
    var raw = String((claim && claim.text) || '').replace(/\s+/g, ' ').trim();
    var text = raw.replace(/^#{1,6}\s*/, '');
    var warn = false;
    if (/[\u2600-\u27bf]/.test(text.charAt(0))) {
      warn = text.charAt(0) === '\u26a0';
      text = text.replace(/^[\u2600-\u27bf]\ufe0f?\s*/, '');
    }
    var label = '';
    var match = text.match(/^([^：:，。；！？]{2,14})[：:]\s*(.+)$/);
    if (match && /(核心|张力|caveat|注意|关键|定义|命题|说明|解读|洞察)/i.test(match[1])) {
      label = match[1];
      text = match[2];
    }
    return {
      text: text,
      label: label,
      section: String((claim && claim.section) || '').trim(),
      warn: warn,
      truncated: /(\.\.\.|…)\s*$/.test(text),
      raw: /^(\||data source\s*[:：]|legend\s*[:：]|coverage\s*[:：]|this page serves as\b)/i.test(raw) ||
        /等待补充结构化摘要/.test(raw)
    };
  }

  function prepareTopic(topic) {
    if (!topic) return null;
    if (topicPrep[topic.id]) return topicPrep[topic.id];
    var usable = [];
    var raw = [];
    (topic.claims || []).forEach(function (claim) {
      var item = prepClaim(claim);
      if (!item.text) return;
      (item.raw ? raw : usable).push(item);
    });
    var pmids = unique((topic.evidence_pmids || []).concat((topic.evidence_refs || []).map(function (ref) { return ref.pmid; })));
    var sections = {};
    usable.forEach(function (item) { if (item.section) sections[item.section] = true; });
    var isStub = /等待补充结构化摘要/.test(String(topic.summary || '')) || /\(redirect\)/i.test(String(topic.title || ''));
    var hasZh = /[\u4e00-\u9fff]/.test(String(topic.summary || '') + (usable.length ? usable[0].text : ''));
    var quality = isStub ? 0 : usable.length * 2 + (Object.keys(sections).length >= 2 ? 2 : 0) +
      Math.min(pmids.length, 12) / 3 + (hasZh ? 1 : 0) - raw.length * 0.5;
    topicPrep[topic.id] = {
      topic: topic,
      usable: usable,
      raw: raw,
      pmids: pmids,
      isStub: isStub,
      hasZh: hasZh,
      quality: Math.max(0, quality)
    };
    return topicPrep[topic.id];
  }

  function cleanExcerpt(value, limit) {
    return truncateText(String(value || '').replace(/#{1,6}\s*/g, ' '), limit || 220);
  }

  // ===== 四、入口三栏：近期沉淀 / 精读架 / 值得想想 =====
  function strengthChip(strength) {
    var value = String(strength || '');
    if (!value) return '';
    return '<em class="kb-strength kb-strength-' + escapeHtml(value) + '">' + escapeHtml(value) + '</em>';
  }

  function renderBaseline() {
    var el = document.getElementById('kbBaseline');
    if (!el) return;
    var stats = graphData.stats || {};
    var landingCount = signalLinks.filter(function (link) { return filteredHits(link).length; }).length;
    var shelfCount = curatedTopics.filter(function (topic) {
      var item = prepareTopic(topic);
      return item && !item.isStub;
    }).length;
    el.innerHTML =
      '<span>命中文献 <strong>' + escapeHtml(compactNumber(stats.matched_articles)) + '</strong></span>' +
      '<span>概念 <strong>' + escapeHtml(nodes.length) + '</strong></span>' +
      '<span>主题分类 <strong>' + escapeHtml(communityRows.length) + '</strong></span>' +
      '<span>策展专题 <strong>' + escapeHtml(shelfCount) + '</strong></span>' +
      '<span>开放问题 <strong>' + escapeHtml(allQuestions.length) + '</strong></span>' +
      '<span>近期信号 <strong>' + escapeHtml(landingCount) + '</strong> 条已落点</span>';
  }

  // ===== 五、知识地图：概念按类别分列，相关概念对齐在同一高度 =====
  var elBadge = document.getElementById('knowledgeBadge');
  var elCanvas = document.getElementById('knowledgeGraph');
  var elZoomLabel = document.getElementById('kgZoomLabel');
  var elNodeSearch = document.getElementById('knowledgeNodeSearch');
  var elTypeFilter = document.getElementById('knowledgeTypeFilter');
  var elGraphCommunityFilter = document.getElementById('knowledgeCommunityFilter');
  var elResetFilters = document.getElementById('kgResetFilters');
  var elMapCount = document.getElementById('kgMapCount');
  var elRibbonText = document.getElementById('kgRibbonText');
  var elRibbonDot = document.getElementById('kgRibbonDot');
  var elRibbonToMap = document.getElementById('kgRibbonToMap');
  var elFromGraph = document.getElementById('kgFromGraph');
  var elGraphLegend = document.getElementById('knowledgeGraphLegend');
  var elMapSection = document.querySelector('.kb-map');

  var svgNamespace = 'http://www.w3.org/2000/svg';
  // 同心圆布局：中心是 MG 底座，向外依次人群 / 机制 / 药物 / 结局 / 证据类型
  var MAP = { w: 1200, h: 820 };
  var centerX = 600;
  var centerY = 410;
  var ringRadii = { population: 105, mechanism: 175, drug: 245, outcome: 335, evidence: 395 };
  var viewBox = { x: 0, y: 0, w: MAP.w, h: MAP.h };
  var zoomScale = 1;
  var scaleMin = 0.45;
  var scaleMax = 3.2;
  var drawnEdges = [];
  var drawnNeighborMap = {};

  function svgEl(tag, attrs) {
    var el = document.createElementNS(svgNamespace, tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === 'text') el.textContent = attrs[key];
        else el.setAttribute(key, attrs[key]);
      });
    }
    return el;
  }

  // 更新时间按 zh-CN 本地时区显示为「月/日 时:分」，与首页「数据截至」口径一致
  function formatUpdatedAt(value) {
    if (!value) return '时间待确认';
    var rawValue = String(value).trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(rawValue)) return rawValue.slice(5).replace('-', '/');
    var normalized = rawValue.indexOf('T') === -1 ? rawValue.replace(' ', 'T') : rawValue;
    var parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) return rawValue;
    return new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).format(parsed);
  }

  function renderBadge() {
    if (!elBadge) return;
    // 徽标回答「这份数据什么时候更新的」：优先跟随站点发布节奏，发布清单缺失才回退图谱生成时间。
    var release = window.MG_RELEASE_MANIFEST || {};
    var releasedAt = release.released_at || '';
    var generatedAt = graphData.generated_at || graphHealthData.generated_at || '';
    elBadge.textContent = '数据更新 ' + formatUpdatedAt(releasedAt || generatedAt);
    elBadge.title = releasedAt
      ? '数据发布时间 ' + releasedAt + (release.run_id ? '（发布编号 ' + release.run_id + '）' : '')
      : (generatedAt ? '概念图谱生成时间 ' + generatedAt : '数据更新时间待确认');
  }

  function landingCountOf(nodeId) {
    return signalsByNode[nodeId] ? signalsByNode[nodeId].length : 0;
  }

  function itemHasCommunity(item, communityId) {
    if (!communityId || communityId === 'all') return true;
    if (item.dominant_community_id === communityId) return true;
    return (item.community_profile || []).some(function (profile) {
      return profile.community_id === communityId;
    });
  }

  function nodeRadius(node) {
    return 5 + Math.min(Math.log((node.article_count || 0) + 1) * 0.9, 6);
  }

  function columnNodes(type) {
    return nodes.filter(function (node) { return node.type === type && node.id !== HUB_ID; });
  }

  function byLiftDesc(a, b) { return b.lift - a.lift || b.count - a.count; }
  function byCountDesc(a, b) { return b.count - a.count; }

  function domainIndexOf(node) {
    for (var index = 0; index < communityRows.length; index += 1) {
      if (communityRows[index].id === node.dominant_community_id) return index;
    }
    return 99;
  }

  // 地图骨干关系：只画明显超出热门度预期的关系（相关度 >= 2），每概念最多 3 条。
  function pickBackbone() {
    var picked = {};
    nodes.forEach(function (node) {
      if (node.id === HUB_ID) return;
      neighborsByNode[node.id]
        .filter(function (item) { return item.count >= LIFT_MIN_COUNT && item.lift >= 2; })
        .sort(byLiftDesc)
        .slice(0, BACKBONE_TOP)
        .forEach(function (item) { picked[item.edgeId] = true; });
    });
    return allEdges.filter(function (edge) {
      return picked[edge.id] && edge.from !== HUB_ID && edge.to !== HUB_ID;
    });
  }

  // 同心圆布局：同类概念在同一环，同一环内按主题排序；药物较多，拆成相邻两环。
  function computeLayout() {
    typeOrder.forEach(function (type) {
      var list = columnNodes(type).sort(function (a, b) {
        return domainIndexOf(a) - domainIndexOf(b) || (b.article_count || 0) - (a.article_count || 0);
      });
      var base = ringRadii[type] || 300;
      var split = type === 'drug' && list.length > 12;
      var innerCount = split ? Math.ceil(list.length / 2) : list.length;
      list.forEach(function (node, index) {
        var ring = split && index >= innerCount ? 1 : 0;
        var perRing = split ? (ring === 0 ? innerCount : list.length - innerCount) : list.length;
        var position = split && ring === 1 ? index - innerCount : index;
        var angle = -Math.PI / 2 + (Math.PI * 2 * (position + (ring ? 0.5 : 0))) / perRing;
        var radius = base + ring * 34;
        node._x = centerX + Math.cos(angle) * radius;
        node._y = centerY + Math.sin(angle) * radius;
        node._angle = angle;
        node._radius = radius;
      });
    });
    if (nodesById[HUB_ID]) {
      nodesById[HUB_ID]._x = centerX;
      nodesById[HUB_ID]._y = centerY;
      nodesById[HUB_ID]._angle = 0;
      nodesById[HUB_ID]._radius = 0;
    }
  }

  function edgeWidth(edge) {
    return 0.9 + Math.min(Math.log((edge.article_count || 0) + 1) * 0.22, 1.5);
  }

  function truncateLabel(title, limit) {
    var text = String(title || '');
    return text.length <= limit ? text : text.slice(0, limit - 1) + '…';
  }

  function edgePath(source, target) {
    var a1 = source._angle;
    var a2 = target._angle;
    var delta = Math.abs(a1 - a2);
    if (delta > Math.PI) delta = Math.PI * 2 - delta;
    var mid = a1 + (a2 - a1) / 2;
    if (delta > Math.PI) mid += Math.PI;
    var pull = source.type === target.type ? 1.04 : 0.82;
    var avg = (source._radius + target._radius) / 2;
    var cx = centerX + Math.cos(mid) * avg * pull;
    var cy = centerY + Math.sin(mid) * avg * pull;
    return 'M' + source._x.toFixed(1) + ',' + source._y.toFixed(1) +
      ' Q' + cx.toFixed(1) + ',' + cy.toFixed(1) + ' ' + target._x.toFixed(1) + ',' + target._y.toFixed(1);
  }

  function labelPlacement(node, radius) {
    var cos = Math.cos(node._angle);
    var sin = Math.sin(node._angle);
    if (Math.abs(cos) < 0.34) {
      return { x: 0, y: sin < 0 ? -(radius + 9) : radius + 17, anchor: 'middle' };
    }
    var left = cos < 0;
    return { x: left ? -(radius + 8) : radius + 8, y: 4.2, anchor: left ? 'end' : 'start' };
  }

  // 标签避让：先按圆上位置摆，再与已放置标签碰撞时上下轻推，避免字压字。
  function placeLabels() {
    var boxes = [];
    nodes.forEach(function (node) {
      var text = node.id === HUB_ID ? 'MG · 全库底座' : truncateLabel(nodeShort(node), 13);
      var radius = node.id === HUB_ID ? 18 : nodeRadius(node);
      var base = node.id === HUB_ID ? { x: 0, y: radius + 20, anchor: 'middle' } : labelPlacement(node, radius);
      var width = 0;
      for (var i = 0; i < text.length; i += 1) {
        width += /[\u4e00-\u9fff]/.test(text.charAt(i)) ? 12.5 : 7.2;
      }
      var ax = node._x + base.x;
      var ay = node._y + base.y;
      var box = {
        x0: base.anchor === 'start' ? ax : (base.anchor === 'end' ? ax - width : ax - width / 2),
        x1: base.anchor === 'start' ? ax + width : (base.anchor === 'end' ? ax : ax + width / 2),
        y0: ay - 10,
        y1: ay + 6
      };
      var shift = 0;
      for (var attempt = 0; attempt < 8; attempt += 1) {
        var clash = boxes.some(function (other) {
          return box.x0 < other.x1 + 3 && box.x1 > other.x0 - 3 &&
            box.y0 + shift < other.y1 + 2 && box.y1 + shift > other.y0 - 2;
        });
        if (!clash) break;
        shift += attempt % 2 === 0 ? 17 : -17;
      }
      node._labelText = text;
      node._labelX = base.x;
      node._labelY = base.y + shift;
      node._labelAnchor = base.anchor;
      boxes.push({ x0: box.x0, x1: box.x1, y0: box.y0 + shift, y1: box.y1 + shift });
    });
  }

  function buildGraph() {
    if (!elCanvas) return;
    drawnEdges = pickBackbone();
    computeLayout();
    placeLabels();
    drawnNeighborMap = {};
    nodes.forEach(function (node) { drawnNeighborMap[node.id] = {}; });
    drawnEdges.forEach(function (edge) {
      drawnNeighborMap[edge.from][edge.to] = true;
      drawnNeighborMap[edge.to][edge.from] = true;
    });

    elCanvas.innerHTML = '';
    elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);

    var guideLayer = svgEl('g', { class: 'kg-guide-layer' });
    [105, 175, 245, 279, 335, 395].forEach(function (radius) {
      guideLayer.appendChild(svgEl('circle', {
        class: 'kg-ring-guide', cx: centerX, cy: centerY, r: radius, fill: 'none'
      }));
    });
    elCanvas.appendChild(guideLayer);

    var edgeLayer = svgEl('g', { class: 'kg-edge-layer' });
    drawnEdges.forEach(function (edge) {
      var source = nodesById[edge.from];
      var target = nodesById[edge.to];
      if (!source || !target) return;
      edgeLayer.appendChild(svgEl('path', {
        class: 'kg-edge' + (source.type === target.type ? ' kg-edge-same' : ''),
        'data-id': edge.id,
        'data-from': edge.from,
        'data-to': edge.to,
        stroke: edgeWidth(edge),
        fill: 'none',
        d: edgePath(source, target)
      }));
    });
    elCanvas.appendChild(edgeLayer);

    var nodeLayer = svgEl('g', { class: 'kg-node-layer' });
    nodes.forEach(function (node) {
      var isHub = node.id === HUB_ID;
      var radius = isHub ? 18 : nodeRadius(node);
      var landings = landingCountOf(node.id);
      var group = svgEl('g', {
        class: 'kg-node type-' + safeClassToken(node.type, 'unknown') + (isHub ? ' kg-base-node' : ''),
        'data-id': node.id,
        'data-type': node.type,
        transform: 'translate(' + node._x.toFixed(1) + ',' + node._y.toFixed(1) + ')'
      });
      group.appendChild(svgEl('title', {
        text: nodeFull(node) + ' · ' + (node.article_count || 0) + ' 篇 abstract' +
          (landings ? ' · 近期 ' + landings + ' 条信号落点' : '')
      }));
      group.appendChild(svgEl('circle', { r: radius, style: '--node-color:' + nodeFillColor(node) }));
      if (landings) group.appendChild(svgEl('circle', { class: 'kg-landing-mark', cx: radius * 0.78, cy: -radius * 0.78, r: 4.5 }));
      group.appendChild(svgEl('text', {
        x: node._labelX, y: node._labelY, 'text-anchor': node._labelAnchor,
        text: node._labelText
      }));
      nodeLayer.appendChild(group);
    });
    elCanvas.appendChild(nodeLayer);
  }

  function applyViewBox() {
    var centerX = viewBox.x + viewBox.w / 2;
    var centerY = viewBox.y + viewBox.h / 2;
    viewBox.w = MAP.w / zoomScale;
    viewBox.h = MAP.h / zoomScale;
    viewBox.x = centerX - viewBox.w / 2;
    viewBox.y = centerY - viewBox.h / 2;
    elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);
    if (elZoomLabel) elZoomLabel.textContent = Math.round(zoomScale * 100) + '%';
  }

  function zoomTo(newScale, focusX, focusY) {
    if (!elCanvas) return;
    newScale = Math.max(scaleMin, Math.min(scaleMax, newScale));
    if (focusX != null && focusY != null && elCanvas.clientWidth && elCanvas.clientHeight) {
      var worldX = viewBox.x + (focusX / elCanvas.clientWidth) * viewBox.w;
      var worldY = viewBox.y + (focusY / elCanvas.clientHeight) * viewBox.h;
      zoomScale = newScale;
      viewBox.w = MAP.w / zoomScale;
      viewBox.h = MAP.h / zoomScale;
      viewBox.x = worldX - (focusX / elCanvas.clientWidth) * viewBox.w;
      viewBox.y = worldY - (focusY / elCanvas.clientHeight) * viewBox.h;
      elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);
    } else {
      zoomScale = newScale;
      applyViewBox();
    }
    if (elZoomLabel) elZoomLabel.textContent = Math.round(zoomScale * 100) + '%';
  }

  function resetView() {
    zoomScale = 1;
    viewBox = { x: 0, y: 0, w: MAP.w, h: MAP.h };
    if (elCanvas) elCanvas.setAttribute('viewBox', '0 0 ' + MAP.w + ' ' + MAP.h);
    if (elZoomLabel) elZoomLabel.textContent = '100%';
  }

  // 选中概念后，如用户已缩放/平移过，把它平移进视野。
  function ensureNodeInView(id) {
    if (!elCanvas || !nodesById[id] || zoomScale === 1) return;
    var node = nodesById[id];
    var marginX = viewBox.w * 0.18;
    var marginY = viewBox.h * 0.18;
    var nextX = viewBox.x;
    var nextY = viewBox.y;
    if (node._x < viewBox.x + marginX || node._x > viewBox.x + viewBox.w - marginX) nextX = node._x - viewBox.w / 2;
    if (node._y < viewBox.y + marginY || node._y > viewBox.y + viewBox.h - marginY) nextY = node._y - viewBox.h / 2;
    if (nextX !== viewBox.x || nextY !== viewBox.y) {
      viewBox.x = nextX;
      viewBox.y = nextY;
      elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);
    }
  }

  function attachPanZoom() {
    if (!elCanvas) return;
    elCanvas.addEventListener('wheel', function (event) {
      event.preventDefault();
      var rect = elCanvas.getBoundingClientRect();
      zoomTo(zoomScale * (event.deltaY < 0 ? 1.15 : 1 / 1.15), event.clientX - rect.left, event.clientY - rect.top);
    }, { passive: false });

    var dragging = false;
    var start = { x: 0, y: 0, viewX: 0, viewY: 0 };

    elCanvas.addEventListener('mousedown', function (event) {
      if (event.target.closest && event.target.closest('.kg-node')) return;
      dragging = true;
      start.x = event.clientX;
      start.y = event.clientY;
      start.viewX = viewBox.x;
      start.viewY = viewBox.y;
      elCanvas.classList.add('grabbing');
    });

    window.addEventListener('mousemove', function (event) {
      if (!dragging || !elCanvas.clientWidth || !elCanvas.clientHeight) return;
      var dx = event.clientX - start.x;
      var dy = event.clientY - start.y;
      viewBox.x = start.viewX - dx * (viewBox.w / elCanvas.clientWidth);
      viewBox.y = start.viewY - dy * (viewBox.h / elCanvas.clientHeight);
      elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);
    });

    window.addEventListener('mouseup', function () {
      dragging = false;
      elCanvas.classList.remove('grabbing');
    });

    var btnIn = document.getElementById('kgZoomIn');
    var btnOut = document.getElementById('kgZoomOut');
    var btnReset = document.getElementById('kgZoomReset');
    if (btnIn) btnIn.addEventListener('click', function () { zoomTo(zoomScale * 1.25); });
    if (btnOut) btnOut.addEventListener('click', function () { zoomTo(zoomScale / 1.25); });
    if (btnReset) btnReset.addEventListener('click', resetView);
  }

  // 高亮：当前概念及其关系线保留，其余变淡。
  function applyHighlight(id, dimOthers) {
    if (!elCanvas) return;
    var neighbors = drawnNeighborMap[id] || {};
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge'), function (line) {
      var touched = line.getAttribute('data-from') === id || line.getAttribute('data-to') === id;
      line.classList.toggle('hl', touched);
      line.classList.toggle('dim', Boolean(dimOthers) && !touched);
    });
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node'), function (nodeEl) {
      var nodeId = nodeEl.getAttribute('data-id');
      nodeEl.classList.toggle('dim', Boolean(dimOthers) && nodeId !== id && !neighbors[nodeId]);
    });
  }

  function clearHighlight() {
    if (!elCanvas) return;
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge.hl,.kg-edge.dim,.kg-node.dim'), function (el) {
      el.classList.remove('hl');
      el.classList.remove('dim');
    });
  }

  function markActiveNode(id) {
    if (!elCanvas) return;
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node'), function (nodeEl) {
      nodeEl.classList.toggle('active', nodeEl.getAttribute('data-id') === id);
    });
  }

  function attachGraphInteraction() {
    if (!elCanvas) return;
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node'), function (nodeEl) {
      var id = nodeEl.getAttribute('data-id');
      nodeEl.addEventListener('mouseenter', function () { applyHighlight(id, true); });
      nodeEl.addEventListener('mouseleave', function () { applyHighlight(state.nodeId, false); });
      nodeEl.addEventListener('click', function (event) {
        event.stopPropagation();
        selectNode(id, { scroll: true });
      });
    });
    // 点空白只退出"选关系"，不取消当前精读对象
    elCanvas.onclick = function () {
      if (state.edgeId) hideEvidencePane();
    };
  }

  function populateCommunitySelect(selectEl, fallbackLabel) {
    if (!selectEl) return;
    selectEl.innerHTML = '<option value="all">' + escapeHtml(fallbackLabel) + '</option>' +
      communityRows.map(function (community) {
        return '<option value="' + escapeHtml(community.id) + '">' + escapeHtml(community.title || community.id) + '</option>';
      }).join('');
  }

  function renderGraphLegend() {
    if (!elGraphLegend) return;
    var items = ['<span class="kg-legend-item"><span class="kg-ring-dot"></span>中心 MG · 底座</span>'];
    [
      ['fcrn', 'FcRn 药物'], ['complement', '补体药物'], ['bcell', 'B 细胞药物'],
      ['conventional', '传统免疫抑制'], ['symptomatic', '对症治疗'], ['rescue', '快速救援'],
      ['other', '其他概念（机制 / 人群 / 结局 / 证据）']
    ].forEach(function (entry) {
      items.push('<span class="kg-legend-item"><span class="kg-legend-dot" style="background:' +
        familyColor[entry[0]] + '"></span>' + escapeHtml(entry[1]) + '</span>');
    });
    items.push('<span class="kg-legend-item"><span class="kg-legend-line"></span>最相关的关系</span>');
    items.push('<span class="kg-legend-item"><span class="kg-legend-landing"></span>近期有信号落点</span>');
    elGraphLegend.innerHTML = items.join('');
  }

  function initializeCommunityControls() {
    populateCommunitySelect(elGraphCommunityFilter, '全部主题');
    renderGraphLegend();
  }

  function nodeSearchText(node) {
    var aliases = (nodeAlias[node.id] || []).map(function (entry) { return entry[0]; }).join(' ');
    return [node.id, node.title, zhLabel[node.id] || '', aliases, node.summary, typeLabel[node.type], domainTitle(node.dominant_community_id)]
      .join(' ').toLowerCase();
  }

  // 筛选只让不匹配的概念变淡，不改变布局，保证地图始终是"一张完整的图"。
  function applyNodeFilters() {
    if (!elCanvas) return;
    var keyword = ((elNodeSearch && elNodeSearch.value) || '').trim().toLowerCase();
    var type = (elTypeFilter && elTypeFilter.value) || 'all';
    var communityId = (elGraphCommunityFilter && elGraphCommunityFilter.value) || 'all';
    var hasFilter = !!keyword || type !== 'all' || communityId !== 'all';
    var matched = {};
    var count = 0;
    nodes.forEach(function (node) {
      matched[node.id] = !hasFilter ||
        ((!keyword || nodeSearchText(node).indexOf(keyword) !== -1) &&
        (type === 'all' || node.type === type) && itemHasCommunity(node, communityId));
      if (matched[node.id]) count += 1;
    });
    if (keyword) {
      nodes.forEach(function (node) {
        if (matched[node.id]) return;
        if (Object.keys(drawnNeighborMap[node.id] || {}).some(function (otherId) { return matched[otherId]; })) {
          matched[node.id] = true;
          count += 1;
        }
      });
    }
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node'), function (nodeEl) {
      nodeEl.classList.toggle('kb-dim', !matched[nodeEl.getAttribute('data-id')]);
    });
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge'), function (line) {
      line.classList.toggle('kb-dim', !matched[line.getAttribute('data-from')] || !matched[line.getAttribute('data-to')]);
    });
    if (elMapCount) {
      elMapCount.textContent = hasFilter
        ? '显示 ' + count + ' / ' + nodes.length + ' 个概念'
        : nodes.length + ' 个概念 · ' + drawnEdges.length + ' 条连线';
    }
  }

  function attachNodeFilters() {
    if (elNodeSearch) elNodeSearch.addEventListener('input', applyNodeFilters);
    if (elTypeFilter) elTypeFilter.addEventListener('change', applyNodeFilters);
    if (elGraphCommunityFilter) elGraphCommunityFilter.addEventListener('change', applyNodeFilters);
    if (elResetFilters) elResetFilters.addEventListener('click', function () {
      if (elNodeSearch) elNodeSearch.value = '';
      if (elTypeFilter) elTypeFilter.value = 'all';
      if (elGraphCommunityFilter) elGraphCommunityFilter.value = 'all';
      applyNodeFilters();
    });
    if (elRibbonToMap) elRibbonToMap.addEventListener('click', function () {
      var map = document.querySelector('.kb-map');
      if (map && map.scrollIntoView) map.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  // ===== 六、精读区：一个概念，三面镜子——知识 / 连接 / 思考 =====
  var elWorkbench = document.getElementById('knowledgeWorkbench');
  var elWorkbenchTitle = document.getElementById('kgWorkbenchTitle');
  var elWorkbenchNote = document.getElementById('kgWorkbenchNote');
  var elIdentity = document.getElementById('kgIdentity');
  var elRelationList = document.getElementById('kgRelationList');
  var elCurationPanel = document.getElementById('kgCurationPanel');
  var elHospitalsPanel = document.getElementById('kgHospitalsPanel');
  var elEvidencePane = document.getElementById('kgEvidencePane');
  var elEvidenceBody = document.getElementById('kgEvidenceBody');
  var elEvidenceTitle = document.getElementById('kgEvidenceTitle');
  var elEvidenceMeta = document.getElementById('kgEvidenceMeta');
  var lensPanels = {
    knowledge: document.getElementById('kgLensKnowledge'),
    connect: document.getElementById('kgLensConnect'),
    think: document.getElementById('kgLensThink')
  };
  var lensCounts = {
    knowledge: document.getElementById('kgLensCountKnowledge'),
    connect: document.getElementById('kgLensCountConnect'),
    think: document.getElementById('kgLensCountThink')
  };
  var lensOrder = ['knowledge', 'connect', 'think'];

  // 精读状态：当前概念 / 当前视角 / 关系排序 / 选中的关系 / 需要定位的卡片。
  var state = { nodeId: '', lens: 'knowledge', edgeId: '', focusKey: '' };
  var activeNodeId = null;

  // 选中来源提示：下方内容由图谱点击决定，这里给出明确的视觉因果。
  function updateRibbon(node) {
    if (elRibbonText) {
      elRibbonText.textContent = '已选中「' + nodeShort(node) + '」· 下方三镜内容随图谱切换（点其他圆点换概念）';
    }
    if (elRibbonDot) elRibbonDot.style.background = nodeFillColor(node);
    if (elFromGraph) elFromGraph.textContent = '来自图谱 · 点圆点切换';
    if (elWorkbench) {
      elWorkbench.classList.remove('just-selected');
      void elWorkbench.offsetWidth;
      elWorkbench.classList.add('just-selected');
    }
  }

  function selectNode(id, options) {
    if (!nodesById[id]) return;
    options = options || {};
    state.nodeId = id;
    state.edgeId = '';
    if (options.lens) state.lens = options.lens;
    state.focusKey = options.focusKey || '';
    activeNodeId = id;
    if (elCanvas) {
      Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node.located'), function (el) { el.classList.remove('located'); });
    }
    renderWorkbench(nodesById[id]);
    setLens(state.lens);
    markActiveNode(id);
    applyHighlight(id, false);
    ensureNodeInView(id);
    updateRibbon(nodesById[id]);
    if (options.topicId) openTopic(options.topicId);
    if (state.focusKey) applyFocus();
    else if (options.scroll) scrollToReading();
  }

  // 卡片里的其他概念只"定位"到图谱，不切换精读对象——换概念请点图谱圆点。
  function locateNode(id) {
    if (!nodesById[id] || !elCanvas) return;
    var node = nodesById[id];
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node.located'), function (el) { el.classList.remove('located'); });
    var el = elCanvas.querySelector('.kg-node[data-id="' + cssEscape(id) + '"]');
    if (el) el.classList.add('located');
    applyHighlight(id, true);
    if (elRibbonText) {
      elRibbonText.textContent = '已在图谱中定位「' + nodeShort(node) + '」；点圆点才会切换精读对象。';
    }
  }

  function scrollToReading() {
    if (!elWorkbench || !elWorkbench.scrollIntoView) return;
    try {
      elWorkbench.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      elWorkbench.scrollIntoView();
    }
  }

  // 高亮并滚动到 state.focusKey 指向的卡片（入口三栏点进来的那张）。
  function applyFocus() {
    if (!elWorkbench || !state.focusKey) return;
    var target = elWorkbench.querySelector('[data-focus="' + cssEscape(state.focusKey) + '"]');
    if (!target) return;
    target.classList.add('is-focused');
    Array.prototype.forEach.call(target.querySelectorAll('details'), function (details) { details.open = true; });
    if (target.scrollIntoView) {
      try { target.scrollIntoView({ block: 'center' }); } catch (err) { target.scrollIntoView(); }
    }
  }

  function setLens(lens) {
    if (!lensPanels[lens]) lens = 'knowledge';
    state.lens = lens;
    Array.prototype.forEach.call(document.querySelectorAll('[data-kg-lens]'), function (tab) {
      var active = tab.getAttribute('data-kg-lens') === lens;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    lensOrder.forEach(function (key) {
      if (lensPanels[key]) lensPanels[key].hidden = key !== lens;
    });
    if (lens === 'think') ensureLandscapeData();
  }

  function levelToken(level) {
    return ({ I: 'l1', II: 'l2', III: 'l3', IV: 'l4', V: 'l5', '未分级': 'lx' })[level] || 'lx';
  }

  function renderEgoMap(node) {
    var list = neighborsByNode[node.id].filter(function (item) { return item.count >= LIFT_MIN_COUNT; })
      .sort(byLiftDesc).slice(0, 8);
    if (!list.length) return '';
    var cx = 190;
    var cy = 126;
    var parts = [];
    list.forEach(function (item, index) {
      var angle = -Math.PI / 2 + (Math.PI * 2 * index) / list.length;
      var x = cx + Math.cos(angle) * 148;
      var y = cy + Math.sin(angle) * 100;
      var other = nodesById[item.otherId];
      var radius = 4 + Math.min(Math.log((other.article_count || 0) + 1) * 0.7, 4);
      var left = x < cx - 20;
      parts.push('<line class="kg-ego-edge" x1="' + cx + '" y1="' + cy + '" x2="' + x + '" y2="' + y +
        '" style="stroke-width:' + (0.8 + Math.min(item.lift / 6, 2)).toFixed(2) + '"/>');
      parts.push('<g class="kg-ego-node" data-locate-node="' + escapeHtml(other.id) + '"><title>' + escapeHtml(nodeFull(other)) +
        ' · ' + item.count + ' 篇 · 特异 ×' + item.lift.toFixed(1) + '</title>' +
        '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + radius.toFixed(1) + '" style="fill:' + escapeHtml(nodeFillColor(other)) + '"/>' +
        '<text x="' + (x + (left ? -radius - 5 : radius + 5)).toFixed(1) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="' +
        (left ? 'end' : 'start') + '">' + escapeHtml(truncateLabel(nodeShort(other), 9)) + '</text></g>');
    });
    parts.push('<circle cx="' + cx + '" cy="' + cy + '" r="16" style="fill:' + escapeHtml(nodeFillColor(node)) + '"/>');
    parts.push('<text x="' + cx + '" y="' + (cy + 36) + '" text-anchor="middle" class="kg-ego-center-label">' +
      escapeHtml(truncateLabel(nodeShort(node), 10)) + '</text>');
    return '<div class="kg-ego-head"><span class="kg-workbench-kicker">特异关联速览</span>' +
      '<span class="kg-workbench-note">扣掉各自热门度后最常一起出现的概念，点圆点可切换</span></div>' +
      '<svg class="kg-ego-svg" viewBox="0 0 380 250" xmlns="' + svgNamespace + '" role="img" aria-label="特异关联速览">' +
      parts.join('') + '</svg>';
  }

  // 身份头：这个概念是什么、有多厚、证据结构如何；右侧是它的特异关联速览。
  function renderIdentity(node) {
    if (!elIdentity) return;
    var total = node.article_count || 0;
    var levels = node.evidence_levels || {};
    var known = ['I', 'II', 'III', 'IV', 'V', '未分级'].filter(function (level) { return levels[level] != null; });
    Object.keys(levels).forEach(function (level) { if (known.indexOf(level) === -1) known.push(level); });
    var graded = known.reduce(function (sum, level) { return sum + (Number(levels[level]) || 0); }, 0);
    var bar = known.map(function (level) {
      var count = Number(levels[level]) || 0;
      return '<i class="kg-ev-seg kg-ev-' + levelToken(level) + '" style="width:' +
        (graded ? ((count / graded) * 100).toFixed(2) : 0) + '%" title="' + escapeHtml('Level ' + level + ' · ' + count + ' 篇') + '"></i>';
    }).join('');
    var legend = known.map(function (level) {
      return '<span class="kg-ev-item"><i class="kg-ev-dot kg-ev-' + levelToken(level) + '"></i>' +
        escapeHtml(level) + ' ' + escapeHtml(levels[level]) + '</span>';
    }).join('');
    var domain = node.dominant_community_id ? domainTitle(node.dominant_community_id) : '';
    var share = matchedArticles ? ((total / matchedArticles) * 100).toFixed(1) : '0';
    var coverageLabel = ({ high: '覆盖充分', medium: '覆盖中等', low: '覆盖较少' })[node.confidence] || '覆盖未知';
    var studyTypes = (node.top_study_types || []).slice(0, 4).map(function (item) {
      return '<span class="mini-chip">' + escapeHtml(item) + '</span>';
    }).join('');
    var domainInfo = taxonomyById[node.dominant_community_id] || {};
    // 没有强关联概念（如底座节点）时不留空的速览栏
    var egoInner = renderEgoMap(node);
    var egoHtml = egoInner ? '<div class="kg-ego">' + egoInner + '</div>' : '';
    elIdentity.className = 'kg-identity' + (egoInner ? '' : ' kg-identity-solo');
    elIdentity.innerHTML =
      '<div class="kg-identity-main">' +
        '<span class="kg-detail-type">' + escapeHtml(typeLabel[node.type] || node.type) +
        (domain ? ' · 主题分类：' + escapeHtml(domain) : '') + '</span>' +
        '<h3>' + escapeHtml(nodeFull(node)) + '</h3>' +
        '<div class="kg-badges">' +
          '<span class="kg-badge">' + escapeHtml(total) + ' 篇 abstract</span>' +
          '<span class="kg-badge">占命中文献 ' + escapeHtml(share) + '%</span>' +
          '<span class="kg-badge">' + escapeHtml(coverageLabel) + '</span>' +
          (node.updated ? '<span class="kg-badge">最近入库 ' + escapeHtml(formatUpdatedAt(node.updated)) + '</span>' : '') +
        '</div>' +
        '<p class="kg-detail-summary">' + escapeHtml(node.summary || '') + '</p>' +
        '<div class="kg-evidence-bar" aria-label="证据等级构成">' + bar + '</div>' +
        '<div class="kg-evidence-legend">' + legend + '</div>' +
        (studyTypes ? '<div class="kg-tags">' + studyTypes + '</div>' : '') +
        (domainInfo.definition ? '<p class="kg-detail-note">主题分类说明：' + escapeHtml(domainInfo.definition) + '</p>' : '') +
      '</div>' +
      egoHtml;
  }

  function sectionHead(title, count, note) {
    return '<div class="kb-section-head"><h4>' + escapeHtml(title) +
      (count ? '<span class="kb-section-count">' + escapeHtml(count) + '</span>' : '') + '</h4>' +
      (note ? '<p>' + escapeHtml(note) + '</p>' : '') + '</div>';
  }

  function renderClaim(item) {
    return '<div class="kb-claim' + (item.warn ? ' kb-claim-warn' : '') + '">' +
      ((item.label || item.section)
        ? '<div class="kb-claim-meta">' +
          (item.label ? '<em class="kb-claim-label">' + escapeHtml(item.label) + '</em>' : '') +
          (item.section ? '<span>' + escapeHtml(item.section) + '</span>' : '') + '</div>'
        : '') +
      '<p>' + escapeHtml(item.text) +
      (item.truncated ? '<span class="kb-truncated">（快照原文在此截断）</span>' : '') + '</p></div>';
  }

  function renderTopicCard(item, node) {
    var topic = item.topic;
    var kind = topicSourceTypeLabel[topic.source_type] || '专题';
    var focusKey = 'topic:' + topic.id;
    var focused = state.focusKey === focusKey;
    var visible = item.usable.slice(0, 3);
    var more = item.usable.slice(3);
    var body = visible.length
      ? visible.map(renderClaim).join('') +
        (more.length ? '<details class="kb-more"' + (focused ? ' open' : '') + '><summary>其余 ' + more.length + ' 条要点</summary>' +
          more.map(renderClaim).join('') + '</details>' : '')
      : '<p class="kb-excerpt">' + escapeHtml(cleanExcerpt(topic.summary)) + '</p>';
    var pmids = item.pmids.slice(0, 8).map(pmidChip).join('');
    var anchors = (topic.anchor_nodes || [])
      .filter(function (id) { return nodesById[id] && id !== node.id && id !== HUB_ID; })
      .map(function (id) { return nodeLinkHtml(nodesById[id]); }).join('');
    return '<article class="kb-topic' + (focused ? ' is-focused' : '') + '" data-focus="' + escapeHtml(focusKey) + '">' +
      '<header class="kb-topic-head">' +
        '<span class="kb-entry-meta"><em class="kb-kind kb-kind-' + escapeHtml(topic.source_type) + '">' + escapeHtml(kind) + '</em>' +
        (item.hasZh ? '' : '<em class="kb-kind kb-kind-lang">EN</em>') +
        escapeHtml('更新 ' + (topic.updated || '未知') + ' · ' + item.usable.length + ' 条要点 · ' + item.pmids.length + ' 篇 PMID') + '</span>' +
        '<h5>' + escapeHtml(topic.title) + '</h5>' +
      '</header>' +
      '<div class="kb-claims">' + body + '</div>' +
      (item.raw.length ? '<details class="kb-raw"><summary>原始摘录 ' + item.raw.length + ' 条（表格或元信息，未整理）</summary>' +
        item.raw.map(function (raw) { return '<p>' + escapeHtml(raw.text) + '</p>'; }).join('') + '</details>' : '') +
      (pmids || anchors ? '<footer class="kb-topic-foot">' +
        (pmids ? '<div class="kb-pmid-chips">' + pmids +
          (item.pmids.length > 8 ? '<span class="kg-ref-meta">等 ' + item.pmids.length + ' 篇</span>' : '') + '</div>' : '') +
        (anchors ? '<div class="kb-anchor-row"><span class="kg-ref-meta">同属概念</span>' + anchors + '</div>' : '') +
        '</footer>' : '') +
      '</article>';
  }

  // 编辑层卡片：逐概念排查后撰写，导语只重述站内已有证据与策展观点。
  function renderEditorialKnowledge(node) {
    var item = editorialForNode(node.id);
    if (!item) return '';
    return '<article class="kb-editorial-card">' +
      '<div class="kb-signal-head"><em class="kb-kind kb-kind-concept">精读导语</em>' +
      '<span class="kg-ref-meta">编辑策展 · 只重述站内已有证据与观点</span></div>' +
      '<p class="kb-editorial-lead">' + escapeHtml(item.lead) + '</p>' +
      '<p class="kb-editorial-line"><strong>怎么读</strong>' + escapeHtml(item.point) + '</p>' +
      '<p class="kb-editorial-caution"><strong>口径</strong>' + escapeHtml(item.caution) + '</p>' +
      '</article>';
  }

  function renderEditorialThought(node) {
    var item = editorialForNode(node.id);
    if (!item || !item.thought) return '';
    var href = editorialHref(item.link, node.id);
    return sectionHead('值得先想的一个问题', '编辑策展', '这个问题由站内资产串起来；答案不在知识库，去对应位置看原文。') +
      '<article class="kb-editorial-card kb-editorial-thought">' +
      '<h5>' + escapeHtml(item.thought) + '</h5>' +
      (href ? '<p class="kb-card-foot"><a class="text-link" href="' + escapeHref(href) +
        '" target="_blank" rel="noopener">' + escapeHtml(editorialLinkLabel(item.link)) + ' ↗</a></p>' : '') +
      '</article>';
  }

  // 镜一 · 知识：编辑导语 + 策展专题 + 代表文献。
  function renderKnowledge(node) {
    var panel = lensPanels.knowledge;
    if (!panel) return;
    var topics = topicsByNode[node.id] || [];
    var refs = (nodeRefs[node.id] || []).slice().sort(function (a, b) {
      return levelRank(a.evidence_level) - levelRank(b.evidence_level);
    });
    if (lensCounts.knowledge) lensCounts.knowledge.textContent = topics.length + refs.length + (editorialForNode(node.id) ? 1 : 0);
    panel.innerHTML =
      renderEditorialKnowledge(node) +
      sectionHead('精读专题', topics.length ? topics.length + ' 篇' : '',
        '静态策展快照 · 数据截至 ' + topicSnapshotDate + '；观点性整理，引用前请核对 PMID 原文。') +
      (topics.length ? topics.map(function (item) { return renderTopicCard(item, node); }).join('') :
        '<div class="kg-empty-hint">这个概念下还没有策展专题。策展专题目前只覆盖部分核心概念，可到"连接"里顺着相关概念继续读。</div>') +
      sectionHead('代表文献', refs.length ? '证据等级优先' : '', '') +
      (refs.length ? '<ul class="kg-study-list kb-ref-list">' + refs.slice(0, 6).map(renderReferenceItem).join('') + '</ul>' :
        '<div class="kg-empty-hint">暂无代表文献。</div>');
  }

  // 关系按"启示"分组排序：同一组里才比相关度，避免热门概念霸榜。
  var INSIGHT_ORDER = ['赛道绑定结构', '反常绑定', '证据缺口与行动'];

  function insightGroupFor(node, item) {
    var meaning = editorialData.relations[pairKey(node.id, item.otherId)];
    return meaning && meaning.insightGroup ? meaning.insightGroup : '赛道绑定结构';
  }

  // 只列明显超出热门度预期的关系（相关度 >= 2）；每节点最多 12 条，按启示分组展示。
  function relationsFor(node) {
    var list = (neighborsByNode[node.id] || []).filter(function (item) {
      return item.count >= LIFT_MIN_COUNT && item.lift >= 2;
    }).map(function (item) {
      var meaning = editorialData.relations[pairKey(node.id, item.otherId)];
      return {
        edgeId: item.edgeId, otherId: item.otherId, count: item.count, lift: item.lift, level: item.level,
        insightGroup: meaning && meaning.insightGroup ? meaning.insightGroup : '赛道绑定结构'
      };
    });
    // 三类启示各留名额：不能让"赛道绑定"凭 lift 优势吃满，否则看不到反常与证据缺口。
    var buckets = {};
    INSIGHT_ORDER.forEach(function (group) { buckets[group] = []; });
    list.forEach(function (item) { buckets[item.insightGroup].push(item); });
    Object.keys(buckets).forEach(function (group) { buckets[group].sort(byLiftDesc); });
    var result = [];
    [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1], [0, 2], [1, 2], [2, 2], [0, 3], [1, 3], [2, 3]]
      .forEach(function (slot) {
        var item = buckets[INSIGHT_ORDER[slot[0]]][slot[1]];
        if (item) result.push(item);
      });
    result.sort(function (a, b) {
      var groupDiff = INSIGHT_ORDER.indexOf(a.insightGroup) - INSIGHT_ORDER.indexOf(b.insightGroup);
      return groupDiff || byLiftDesc(a, b);
    });
    return result;
  }

  function relationSignalHits(node, otherId) {
    var mine = signalsByNode[node.id] || [];
    var theirs = signalsByNode[otherId] || [];
    var shared = sharedEntries(signalsByNode, node.id, otherId);
    var sharedKeys = shared.map(function (entry) { return entry.link.key; });
    var mineOnly = mine.filter(function (entry) {
      return sharedKeys.indexOf(entry.link.key) === -1 &&
        !(theirs || []).some(function (other) { return other.link.key === entry.link.key; });
    });
    var theirsOnly = theirs.filter(function (entry) {
      return sharedKeys.indexOf(entry.link.key) === -1 &&
        !(mine || []).some(function (other) { return other.link.key === entry.link.key; });
    });
    return { shared: shared, mineOnly: mineOnly, theirsOnly: theirsOnly };
  }

  function relationSignalSummary(node, item) {
    var hits = relationSignalHits(node, item.otherId);
    var total = hits.shared.length + hits.mineOnly.length + hits.theirsOnly.length;
    if (!total) return '暂无近期信号落点';
    var parts = [];
    if (hits.shared.length) parts.push('共同 ' + hits.shared.length);
    if (hits.mineOnly.length) parts.push('本概念 ' + hits.mineOnly.length);
    if (hits.theirsOnly.length) parts.push('对方 ' + hits.theirsOnly.length);
    return parts.join(' · ');
  }

  function renderRelationList(node) {
    if (!elRelationList) return;
    var list = relationsFor(node);
    if (lensCounts.connect) lensCounts.connect.textContent = String(list.length);
    if (node.id === HUB_ID) {
      elRelationList.innerHTML = '<div class="kg-empty-hint">底座节点见于全部命中文献，和每个概念都同现，单列关系没有区分意义。请点图谱里的圆点选一个具体概念。</div>';
      return;
    }
    if (!list.length) {
      elRelationList.innerHTML = '<div class="kg-empty-hint">这个概念暂时没有达到最小共现篇数的关联概念。</div>';
      return;
    }
    var html = '';
    var lastGroup = '';
    list.forEach(function (item) {
      var group = item.insightGroup || '赛道绑定结构';
      if (group !== lastGroup) {
        html += '<div class="kg-relation-group"><span class="kg-group-dot kg-group-' +
          escapeHtml(group === '赛道绑定结构' ? 'track' : (group === '反常绑定' ? 'anomaly' : 'gap')) +
          '"></span>' + escapeHtml(group) + '</div>';
        lastGroup = group;
      }
      var other = nodesById[item.otherId];
      html += '<button class="kg-relation-pick' + (item.edgeId === state.edgeId ? ' selected' : '') +
        '" type="button" data-edge="' + escapeHtml(item.edgeId) + '">' +
        '<strong>' + escapeHtml(nodeShort(other)) + '</strong>' +
        '<span>' + escapeHtml(item.count + ' 篇 · 相关度 ' + item.lift.toFixed(1) +
          (item.level ? ' · 最佳证据 ' + item.level : '')) + '</span>' +
        '<em class="kg-relation-signal">' + escapeHtml(relationSignalSummary(node, item)) + '</em>' +
        '</button>';
    });
    elRelationList.innerHTML = html;
  }

  function markSelectedEdge(edgeId) {
    if (!elCanvas) return;
    var edge = edgesById[edgeId];
    if (!edge) return;
    var line = elCanvas.querySelector('.kg-edge[data-id="' + cssEscape(edgeId) + '"]');
    if (line) line.classList.add('edge-selected');
    var otherId = edge.from === state.nodeId ? edge.to : edge.from;
    var otherEl = elCanvas.querySelector('.kg-node[data-id="' + cssEscape(otherId) + '"]');
    if (otherEl) otherEl.classList.add('edge-peer');
  }

  function clearSelectedEdge() {
    if (!elCanvas) return;
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge.edge-selected,.kg-node.edge-peer'), function (el) {
      el.classList.remove('edge-selected');
      el.classList.remove('edge-peer');
    });
  }

  function selectEdge(edgeId) {
    var edge = edgesById[edgeId];
    if (!edge || !state.nodeId) return;
    state.edgeId = edgeId;
    clearSelectedEdge();
    markSelectedEdge(edgeId);
    renderRelationList(nodesById[state.nodeId]);
    renderCuration(edgeId);
    renderCrossEvidence(edgeId);
  }

  function liftWord(lift) {
    if (lift >= 5) return '强特异关联';
    if (lift >= 2) return '中等特异关联';
    return '接近按各自篇数的预期';
  }

  function sharedEntries(index, primaryId, otherId) {
    return (index[primaryId] || []).filter(function (entry) {
      return (index[otherId] || []).some(function (other) { return other.link.key === entry.link.key; });
    });
  }

  // 关系解读：这一对概念同现有多强，以及它们一起出现在哪些专题 / 问题 / 信号里。
  function renderCuration(edgeId) {
    if (!elCurationPanel) return;
    var edge = edgesById[edgeId];
    var primary = nodesById[state.nodeId];
    if (!edge || !primary) return;
    var otherId = edge.from === primary.id ? edge.to : edge.from;
    var other = nodesById[otherId] || { id: otherId, title: otherId };
    var item = neighborsByNode[primary.id].find(function (entry) { return entry.edgeId === edgeId; }) ||
      { count: edge.article_count || 0, lift: 0, level: edge.best_evidence_level || '' };
    var meaning = editorialData.relations[pairKey(primary.id, otherId)] || null;
    var reading = meaning ? meaning.read : genericRelationReading(primary, other, item);
    var cautionLine = meaning && meaning.caution ? meaning.caution : '跨研究比较前先对齐人群与终点定义。';
    var sharedTopics = (topicsByNode[primary.id] || []).filter(function (entry) {
      return (entry.topic.anchor_nodes || []).indexOf(otherId) !== -1;
    });
    var sharedQuestions = sharedEntries(questionsByNode, primary.id, otherId);
    var sharedSignals = sharedEntries(signalsByNode, primary.id, otherId);
    var signalHits = relationSignalHits(primary, otherId);
    var groupName = meaning && meaning.insightGroup ? meaning.insightGroup : '赛道绑定结构';
    var groupWhy = (editorialData.insightGroupRules || {})[groupName] || '这条关系属于竞品/机制地图。';
    elCurationPanel.innerHTML =
      '<div class="kg-insight-banner kg-insight-' +
        escapeHtml(groupName === '赛道绑定结构' ? 'track' : (groupName === '反常绑定' ? 'anomaly' : 'gap')) + '">' +
        '<strong>' + escapeHtml(groupName) + '</strong><span>' + escapeHtml(groupWhy) + '</span></div>' +
      '<div class="kg-curation-head">' +
        '<span class="kg-detail-type">关系解读 · 启示</span>' +
        '<h4>' + escapeHtml(nodeShort(primary)) + ' × ' + escapeHtml(nodeShort(other)) + '</h4>' +
        '<div class="kg-badges">' +
          '<span class="kg-badge">' + escapeHtml(edge.relation || '摘要共现') + '</span>' +
          '<span class="kg-badge">' + escapeHtml(item.count) + ' 篇</span>' +
          '<span class="kg-badge">特异 ×' + escapeHtml(item.lift.toFixed(1)) + '</span>' +
          (item.level ? '<span class="kg-badge">最佳证据 ' + escapeHtml(item.level) + '</span>' : '') +
          '<span class="kg-badge relation-peer-badge">' + escapeHtml(liftWord(item.lift)) + '</span>' +
        '</div>' +
        '<p class="kg-detail-summary">两者在 ' + escapeHtml(item.count) + ' 篇摘要中同现，约为按各自篇数预期的 ' +
        escapeHtml(item.lift.toFixed(1)) + ' 倍：' + escapeHtml(reading) + '</p>' +
        '<p class="kg-detail-note">' + escapeHtml(cautionLine) + ' 共现不代表疗效或因果。</p>' +
        (meaning ? '<p class="kg-detail-note kb-editorial-mark">编辑策展 · 针对这一对关系撰写</p>' : '') +
      '</div>' +
      (sharedTopics.length ? '<div class="kg-curation-section"><h5>一起出现的策展专题</h5><div class="kb-chip-row">' +
        sharedTopics.map(function (entry) {
          return '<button class="kb-focus-chip" type="button" data-focus-topic="' + escapeHtml(entry.topic.id) + '">' +
            escapeHtml(truncateText(entry.topic.title, 34)) + '</button>';
        }).join('') + '</div></div>' : '') +
      (sharedQuestions.length ? '<div class="kg-curation-section"><h5>共同关联的开放问题</h5><div class="kb-chip-row">' +
        sharedQuestions.map(function (entry) {
          return '<button class="kb-focus-chip" type="button" data-focus-question="' + escapeHtml(entry.link.key) + '">' +
            escapeHtml(truncateText(entry.link.data.question, 40)) + '</button>';
        }).join('') + '</div></div>' : '') +
      (sharedSignals.length ? '<div class="kg-curation-section"><h5>共同落点的近期信号</h5><div class="kb-chip-row">' +
        sharedSignals.map(function (entry) {
          return '<button class="kb-focus-chip" type="button" data-focus-signal="' + escapeHtml(entry.link.key) + '">' +
            escapeHtml(truncateText(entry.link.data.title, 40)) + '</button>';
        }).join('') + '</div></div>' : '') +
      ((signalHits.mineOnly.length || signalHits.theirsOnly.length)
        ? '<div class="kg-curation-section"><h5>近期信号落点（单侧，可交叉验证）</h5>' +
          (signalHits.mineOnly.length ? '<div class="kb-chip-row"><span class="kg-signal-side">落在' +
            escapeHtml(nodeShort(primary)) + '：</span>' + signalHits.mineOnly.map(function (entry) {
              return '<button class="kb-focus-chip" type="button" data-focus-signal="' + escapeHtml(entry.link.key) + '">' +
                escapeHtml(truncateText(entry.link.data.title, 38)) + '</button>';
            }).join('') + '</div>' : '') +
          (signalHits.theirsOnly.length ? '<div class="kb-chip-row"><span class="kg-signal-side">落在' +
            escapeHtml(nodeShort(other)) + '：</span>' + signalHits.theirsOnly.map(function (entry) {
              return '<button class="kb-focus-chip" type="button" data-focus-signal="' + escapeHtml(entry.link.key) + '">' +
                escapeHtml(truncateText(entry.link.data.title, 38)) + '</button>';
            }).join('') + '</div>' : '') +
          '</div>' : '') +
      (!sharedTopics.length && !sharedQuestions.length && !signalHits.shared.length &&
        !signalHits.mineOnly.length && !signalHits.theirsOnly.length
        ? '<div class="kg-empty-hint">这对关系暂时还没有沉淀的专题、问题或信号；下方可看两者的交叉证据文献。</div>' : '') +
      '<p class="kg-detail-note">点专题切到「知识」、点问题或信号切到「思考」；下方是这对关系的交叉证据文献清单。</p>';
  }

  function crossEvidenceFor(edge, primaryId) {
    var otherId = edge.from === primaryId ? edge.to : edge.from;
    var row = matrixByPairKey[pairKey(primaryId, otherId)] || null;
    if (row) {
      return {
        references: row.references || [],
        key_pmids: row.key_pmids || [],
        article_count: row.article_count || edge.article_count || 0,
        level: row.best_evidence_level || edge.best_evidence_level || '',
        relation: row.relation || edge.relation || '',
        limitation: row.limitation || '',
        hasMatrix: true
      };
    }
    var refs = (edge.pmids || []).map(function (pmid) {
      return { pmid: String(pmid), title: '（摘要级代表文献，标题请回 PMID 原文核对）', url: pmidHref(pmid) };
    });
    return {
      references: refs,
      key_pmids: edge.pmids || [],
      article_count: edge.article_count || 0,
      level: edge.best_evidence_level || '',
      relation: edge.relation || '',
      limitation: '这条关系未进入证据矩阵明细，仅提供摘要级代表 PMID，不能作为完整文献清单。',
      hasMatrix: false
    };
  }

  // 下方文献清单：这对概念在 evidence_matrix 中的交叉证据。
  function renderCrossEvidence(edgeId) {
    if (!elEvidencePane || !elEvidenceBody) return;
    var edge = edgesById[edgeId];
    if (!edge || !state.nodeId) return;
    var primary = nodesById[state.nodeId];
    var otherId = edge.from === primary.id ? edge.to : edge.from;
    var other = nodesById[otherId] || { id: otherId, title: otherId };
    var x = crossEvidenceFor(edge, primary.id);
    if (elEvidenceTitle) elEvidenceTitle.textContent = nodeFull(primary) + ' × ' + nodeFull(other);
    if (elEvidenceMeta) {
      elEvidenceMeta.textContent = x.article_count + ' 篇共现 abstract · ' + (x.level ? '最佳证据 ' + x.level : '证据等级未标注');
    }
    var refsHtml = x.references.length
      ? '<ul class="kg-study-list">' + x.references.slice(0, 20).map(renderReferenceItem).join('') + '</ul>'
      : '<div class="kg-empty-hint">这条关系没有可展示的代表文献。</div>';
    elEvidenceBody.innerHTML =
      '<div class="cross-evidence-head">' +
        '<span class="kg-badge">' + escapeHtml(x.relation || '共现关系') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(x.key_pmids.length) + ' 条代表 PMID</span>' +
        (x.hasMatrix ? '' : '<span class="kg-badge conf-low">非完整清单</span>') +
      '</div>' +
      (x.limitation ? '<p class="kg-detail-note">' + escapeHtml(x.limitation) + '</p>' : '') +
      (function () {
        var editorial = editorialData.relations[pairKey(primary.id, otherId)];
        return editorial && editorial.evidenceFocus
          ? '<p class="kb-evidence-focus"><strong>证据该看什么</strong>' + escapeHtml(editorial.evidenceFocus) + '</p>'
          : '';
      }()) +
      '<p class="kg-detail-note">以下为两者在同一批文献中共同出现时被抽到的代表文献（PMID 可点回原文）。共现不代表疗效或因果。</p>' +
      refsHtml;
    elEvidencePane.hidden = false;
  }

  // 收起文献清单即退出"选关系"：解读回提示态、左栏与图谱取消高亮。
  function hideEvidencePane() {
    if (elEvidencePane) elEvidencePane.hidden = true;
    state.edgeId = '';
    clearSelectedEdge();
    if (elCurationPanel) {
      elCurationPanel.innerHTML = '<div class="kg-empty-hint">点左侧一条关系，这里解释两者怎么关联；下方展开交叉证据文献。</div>';
    }
    if (elRelationList) {
      Array.prototype.forEach.call(elRelationList.querySelectorAll('[data-edge]'), function (button) {
        button.classList.remove('selected');
      });
    }
  }

  // 中国研究医院：复用中国作者联络图的药物发文统计（全作者口径）。网络数据按需加载。
  function renderHospitals(node) {
    if (!elHospitalsPanel) return;
    var network = window.MG_CHINA_AUTHOR_NETWORK || null;
    if (node.type !== 'drug') {
      elHospitalsPanel.innerHTML = '';
      return;
    }
    if (!network) {
      elHospitalsPanel.innerHTML = '<div class="kb-hospitals"><p class="kg-detail-note">想知道中国哪些医院在研究它？数据来自中国作者联络图，按需加载。</p>' +
        '<button class="btn" type="button" data-load-hospitals="1">加载中国研究医院</button></div>';
      return;
    }
    var inCatalog = (network.drug_catalog || []).some(function (drug) { return drug.id === node.id; });
    if (!inCatalog) {
      elHospitalsPanel.innerHTML = '';
      return;
    }
    var rows = (network.nodes || []).filter(function (hospital) {
      return (hospital.all_author_drug_counts || {})[node.id];
    }).sort(function (a, b) {
      return (b.all_author_drug_counts[node.id] || 0) - (a.all_author_drug_counts[node.id] || 0);
    }).slice(0, 6);
    if (!rows.length) {
      elHospitalsPanel.innerHTML = '';
      return;
    }
    elHospitalsPanel.innerHTML =
      '<div class="kg-curation-section kb-hospitals"><h5>中国研究医院 · 全作者口径</h5><ol class="kb-hospital-list">' +
      rows.map(function (hospital) {
        return '<li><span>' + escapeHtml(hospital.label) +
          (hospital.province ? '<em>' + escapeHtml(hospital.province) + '</em>' : '') + '</span>' +
          '<strong>' + escapeHtml(hospital.all_author_drug_counts[node.id]) + ' 篇</strong></li>';
      }).join('') + '</ol>' +
      '<button class="text-link kb-network-link" type="button" data-open-network="' + escapeHtml(node.id) + '">在中国作者联络图中看合作网络 ↗</button>' +
      '<p class="kg-detail-note">药物标签是文献相关线索，按标题命中优先，不等同于干预结论。</p></div>';
  }

  function dlRow(label, value) {
    if (!value) return '';
    return '<dt>' + escapeHtml(label) + '</dt><dd>' + escapeHtml(value) + '</dd>';
  }

  function renderSignalCard(link) {
    var signal = link.data;
    var focusKey = 'signal:' + link.key;
    var focused = state.focusKey === focusKey;
    if (link.kind === 'trial') {
      var registry = (signal.registryRefs || []).map(function (ref) {
        return '<a class="text-link" href="' + escapeHref(ref.url) + '" target="_blank" rel="noopener">' +
          escapeHtml(ref.registryId || ref.registry) + '</a>';
      }).join(' ');
      return '<article class="kb-signal-card' + (focused ? ' is-focused' : '') + '" data-focus="' + escapeHtml(focusKey) + '">' +
        '<div class="kb-signal-head">' + strengthChip(signal.strength) +
        '<span class="kg-ref-meta">试验信号 · ' + escapeHtml(fmtDate(signal.date)) +
        (signal.phase ? ' · ' + escapeHtml(signal.phase) : '') + '</span></div>' +
        '<h5>' + escapeHtml(signal.title) + '</h5>' +
        '<dl class="kb-dl">' + dlRow('一句话', signal.changeSummary || signal.takeaway) +
        dlRow('为何值得关注', signal.whySignal) + dlRow('证据边界', signal.evidenceBoundary) + '</dl>' +
        '<p class="kb-card-foot"><span class="kg-ref-meta">注册/开发信号，不代表疗效证据</span> ' + registry +
        ' <a class="text-link" href="' + escapeHref(pageUrl('pages/literature.html?tab=trials')) + '" target="_blank" rel="noopener">情报中心试验页 ↗</a></p>' +
        '</article>';
    }
    var medicalAffairs = signal.medical_affairs || {};
    var pmids = (signal.related_pmids || []).slice(0, 4).map(pmidChip).join(' ');
    return '<article class="kb-signal-card' + (focused ? ' is-focused' : '') + '" data-focus="' + escapeHtml(focusKey) + '">' +
      '<div class="kb-signal-head">' + strengthChip(signal.strength) +
      '<span class="kg-ref-meta">文献信号 · ' + escapeHtml(fmtDate(signal.date)) +
      (signal.capturedAt ? ' · 收录批次 ' + escapeHtml(signal.capturedAt) : '') +
      (signal.type ? ' · ' + escapeHtml(signal.type) : '') + '</span></div>' +
      '<h5>' + escapeHtml(signal.title) + '</h5>' +
      '<dl class="kb-dl">' + dlRow('临床问题', signal.clinicalQuestion) + dlRow('概念推进', signal.conceptAdvance) +
      dlRow('临床启示', signal.clinicalImplication) + dlRow('建议追问', medicalAffairs.suggested_kol_question) + '</dl>' +
      '<p class="kb-card-foot"><span class="kg-ref-meta">摘要级解读；完整证据与边界见首页信号卡</span> ' + pmids +
      ' <a class="text-link" href="' + escapeHref(homeUrl('?signal=' + encodeURIComponent(signal.id))) +
      '" target="_blank" rel="noopener">回首页看信号卡 ↗</a></p>' +
      '</article>';
  }

  function renderQuestionCard(entry, node) {
    var question = entry.link.data;
    var focusKey = 'question:' + entry.link.key;
    var insufficient = question.stance === '证据不足';
    var others = (entry.link.hits || []).filter(function (hit) {
      return hit[1] >= LINK_MIN_SCORE && hit[0] !== node.id && nodesById[hit[0]];
    }).slice(0, 3).map(function (hit) { return nodeLinkHtml(nodesById[hit[0]]); }).join('');
    return '<article class="kb-question-card' + (state.focusKey === focusKey ? ' is-focused' : '') +
      '" data-focus="' + escapeHtml(focusKey) + '">' +
      '<div class="kb-signal-head"><em class="kb-stance kb-stance-' + (insufficient ? 'insufficient' : 'cautious') + '">' +
      escapeHtml(question.stance || '待评估') + '</em><span class="kg-ref-meta">' + escapeHtml(entry.link.group.title || '') + '</span></div>' +
      '<h5>' + escapeHtml(question.question) + '</h5>' +
      (question.whyOpen ? '<p class="kb-open">未解决点：' + escapeHtml(question.whyOpen) + '</p>' : '') +
      '<p class="kb-card-foot">' + (others ? '<span class="kg-ref-meta">还关联</span>' + others : '') +
      '<a class="text-link" href="' + escapeHref(pageUrl('pages/landscape.html?tab=questions&question=' + encodeURIComponent(entry.link.key))) +
      '" target="_blank" rel="noopener">去诊治格局看答案 ↗</a></p>' +
      '</article>';
  }

  function renderDivergenceCard(entry, node) {
    var divergence = entry.link.data;
    var viaId = entry.link.via ? entry.link.via[node.id] : '';
    return '<article class="kb-divergence-card" data-focus="divergence:' + escapeHtml(entry.link.key) + '">' +
      '<div class="kb-signal-head"><em class="kb-kind kb-kind-guideline">指南分歧</em>' +
      '<span class="kg-ref-meta">' + escapeHtml(divergence.dimension || '') + '</span></div>' +
      '<h5>' + escapeHtml(divergence.title) + '</h5>' +
      (viaId ? '<p class="kg-detail-note">该分歧按「' + escapeHtml(nodeShort(nodesById[viaId])) + '」表述，' +
        escapeHtml(nodeShort(node)) + '经与它的强特异关联间接相关。</p>' : '') +
      '<div class="kb-two-side">' +
        '<div><span>中国</span><p>' + escapeHtml(truncateText(divergence.china, 150)) + '</p></div>' +
        '<div><span>国际</span><p>' + escapeHtml(truncateText(divergence.international, 150)) + '</p></div>' +
      '</div>' +
      '<p class="kb-card-foot"><a class="text-link" href="' + escapeHref(pageUrl('pages/landscape.html?tab=overview&divergence=' + encodeURIComponent(entry.link.key))) +
      '" target="_blank" rel="noopener">去诊治格局看原文引文 ↗</a></p>' +
      '</article>';
  }

  // 镜三 · 思考：还没有定论的东西——近期信号、开放问题、指南分歧。
  function renderThink(node) {
    var panel = lensPanels.think;
    if (!panel) return;
    var signalEntries = signalsByNode[node.id] || [];
    var questionEntries = questionsByNode[node.id] || [];
    var divergenceEntries = divergencesByNode[node.id] || [];
    var landscapeReady = Boolean(window.MG_LANDSCAPE_DATA);
    if (lensCounts.think) {
      lensCounts.think.textContent = String(signalEntries.length + questionEntries.length + divergenceEntries.length +
        (editorialForNode(node.id) ? 1 : 0));
    }
    panel.innerHTML =
      renderEditorialThought(node) +
      sectionHead('近期信号落点', signalEntries.length ? signalEntries.length + ' 条' : '',
        '首页更新流里与这个概念相关的信号；这里展示的是首页信号卡没有展开的部分。') +
      (signalEntries.length ? signalEntries.map(function (entry) { return renderSignalCard(entry.link); }).join('') :
        '<div class="kg-empty-hint">近期没有落在「' + escapeHtml(nodeShort(node)) + '」上的信号。</div>') +
      sectionHead('开放问题', questionEntries.length ? questionEntries.length + ' 问' : '',
        '还没有定论的临床问题；这里只把问题连到概念上，答案在诊治格局。') +
      (questionEntries.length ? questionEntries.map(function (entry) { return renderQuestionCard(entry, node); }).join('') :
        '<div class="kg-empty-hint">暂无关联的开放问题。</div>') +
      sectionHead('指南分歧', landscapeReady && divergenceEntries.length ? divergenceEntries.length + ' 条' : '',
        '中外指南共识在这一点上的立场差异。') +
      (!landscapeReady ? '<div class="kg-empty-hint">指南分歧数据加载中…</div>' :
        (divergenceEntries.length ? divergenceEntries.map(function (entry) { return renderDivergenceCard(entry, node); }).join('') :
          '<div class="kg-empty-hint">暂无直接相关的指南分歧。</div>')) +
      '<p class="kg-detail-note kb-think-note">落点由关键词关联推断，仅供导航；正式表述前请回到 PMID 原文、指南原文与官方登记核对。</p>';
  }

  var landscapeLoading = false;
  // 指南分歧数据体积较大（约 700KB），首次打开"思考"镜时才加载。
  function ensureLandscapeData() {
    if (window.MG_LANDSCAPE_DATA || landscapeLoading || !hub.loadScript) return;
    landscapeLoading = true;
    hub.loadScript('data/landscape-data.js', function (ok) {
      landscapeLoading = false;
      if (!ok || !window.MG_LANDSCAPE_DATA) return;
      buildDivergenceLinks();
      if (state.lens === 'think' && state.nodeId) {
        renderThink(nodesById[state.nodeId]);
        applyFocus();
      }
    });
  }

  function renderWorkbench(node) {
    if (!node) return;
    if (elWorkbenchTitle) elWorkbenchTitle.textContent = nodeFull(node);
    if (elWorkbenchNote) {
      elWorkbenchNote.textContent = (typeLabel[node.type] || '') + ' · 近期 ' + landingCountOf(node.id) + ' 条信号落点';
    }
    renderIdentity(node);
    renderKnowledge(node);
    renderRelationList(node);
    renderHospitals(node);
    renderThink(node);
    hideEvidencePane();
  }

  // 深链 ?topic=：在"知识"镜里展开该策展专题。
  function openTopic(topicId) {
    renderTopicCuration(topicId);
  }
  function renderTopicCuration(topicId) {
    if (!topicsById[topicId] || !state.nodeId) return;
    state.lens = 'knowledge';
    state.focusKey = 'topic:' + topicId;
    setLens('knowledge');
    applyFocus();
  }

  // ===== 七、导出、深链、页签与初始化 =====
  // 首页链接：从 pages/ 目录回到站点根，兼容本地与 GitHub Pages 子路径。
  function homeUrl(query) {
    var suffix = query || '';
    if (!hub.basePath && /\/pages\/[^/]*$/.test(window.location.pathname || '')) return '../' + suffix;
    return pageUrl('index.html' + suffix);
  }

  // 精读卡：把当前概念的"知识 / 连接 / 思考"整理成可带走的 Markdown（预览 + 复制）。
  function buildConceptCard(node) {
    var levels = node.evidence_levels || {};
    var levelText = Object.keys(levels).map(function (level) { return level + ' ' + levels[level]; }).join(' · ');
    var domain = node.dominant_community_id ? domainTitle(node.dominant_community_id) : '';
    var lines = ['# ' + nodeFull(node) + ' · 知识卡', ''];
    lines.push('- 类别：' + (typeLabel[node.type] || node.type) + (domain ? '；主题分类：' + domain : ''));
    lines.push('- 规模：' + (node.article_count || 0) + ' 篇 abstract；证据构成：' + (levelText || '未标注'));
    if (node.summary) lines.push('- 释义：' + node.summary);

    var topics = topicsByNode[node.id] || [];
    lines.push('', '## 精读专题（' + topics.length + ' 篇；静态策展快照，数据截至 ' + topicSnapshotDate + '）');
    topics.slice(0, 6).forEach(function (item) {
      var kind = topicSourceTypeLabel[item.topic.source_type] || '专题';
      lines.push('', '### ' + item.topic.title + '（' + kind + ' · 更新 ' + (item.topic.updated || '未知') + '）');
      item.usable.forEach(function (claim) {
        lines.push('- ' + (claim.label ? claim.label + '：' : '') + claim.text);
      });
      if (item.pmids.length) lines.push('- PMID：' + item.pmids.slice(0, 10).join('、'));
    });

    lines.push('', '## 特异关联（扣除各自热门度后的同现强度，不代表因果）');
    relationsFor(node, 'lift').slice(0, 8).forEach(function (item) {
      lines.push('- ' + nodeShort(nodesById[item.otherId]) + '：' + item.count + ' 篇 · 特异 ×' + item.lift.toFixed(1) +
        (item.level ? ' · 最佳证据 ' + item.level : ''));
    });

    var signalEntries = signalsByNode[node.id] || [];
    lines.push('', '## 近期信号落点（' + signalEntries.length + ' 条）');
    signalEntries.forEach(function (entry) {
      var signal = entry.link.data;
      lines.push('- [' + fmtDate(signal.date) + '] ' + signal.title + '；临床问题：' + (signal.clinicalQuestion || '—'));
    });

    var questionEntries = questionsByNode[node.id] || [];
    lines.push('', '## 开放问题（' + questionEntries.length + ' 问，答案见诊治格局）');
    questionEntries.forEach(function (entry) {
      lines.push('- ' + entry.link.data.question + '（' + (entry.link.data.stance || '待评估') + '）');
    });
    lines.push('', hub.briefFooter ? hub.briefFooter() : '');
    return lines.join('\n');
  }

  function queryParam(name) {
    try {
      var params = new URLSearchParams(window.location.search || '');
      return params.get(name) || '';
    } catch (err) {
      return '';
    }
  }

  function getInitialKnowledgeCommunityId() {
    var communityId = queryParam('community');
    if (communityId && (taxonomyById[communityId] || communityCardsById[communityId])) return communityId;
    return '';
  }

  function getInitialKnowledgeTab() {
    return queryParam('tab');
  }

  function getInitialKnowledgeNodeId() {
    var nodeId = queryParam('node');
    if (nodeId && nodesById[nodeId]) return nodeId;
    return '';
  }

  function getInitialKnowledgeTopicId() {
    var topicId = queryParam('topic');
    if (topicId && topicsById[topicId]) return topicId;
    return '';
  }

  function getInitialKnowledgeLens() {
    var lens = queryParam('lens');
    return lensOrder.indexOf(lens) !== -1 ? lens : '';
  }

  function openCommunityGraph(communityId) {
    activateTab('graph');
    if (elGraphCommunityFilter) elGraphCommunityFilter.value = communityId;
    renderGraphLegend();
    applyNodeFilters();
    var firstNode = nodes.find(function (node) { return itemHasCommunity(node, communityId); });
    if (firstNode) selectNode(firstNode.id);
  }

  var tabController = null;

  function activateTab(key) {
    if (tabController) {
      tabController.activate(key, false);
    } else {
      Array.prototype.forEach.call(document.querySelectorAll('[data-knowledge-tab]'), function (tab) {
        tab.classList.toggle('active', tab.getAttribute('data-knowledge-tab') === key);
      });
      Array.prototype.forEach.call(document.querySelectorAll('.intel-tab-panel'), function (panel) {
        panel.classList.remove('active');
      });
      var panel = document.getElementById('knowledge-' + key + '-panel');
      if (panel) panel.classList.add('active');
    }
    if (key === 'china-network') {
      // 联络图数据只在页签点击时按需加载；深链或页内跳转进入时补发一次点击。
      var tab = document.querySelector('[data-knowledge-tab="china-network"]');
      if (tab && tab.click) tab.click();
    }
  }

  function attachTabs() {
    if (hub.initTabs) {
      tabController = hub.initTabs({
        tabAttr: 'data-knowledge-tab',
        panelFor: function (key) { return document.getElementById('knowledge-' + key + '-panel'); }
      });
      return;
    }
    Array.prototype.forEach.call(document.querySelectorAll('[data-knowledge-tab]'), function (tab) {
      tab.addEventListener('click', function () { activateTab(tab.getAttribute('data-knowledge-tab')); });
    });
  }

  // 在当前概念内切换视角并定位到指定卡片
  function focusInPlace(lens, focusKey) {
    state.focusKey = focusKey;
    setLens(lens);
    applyFocus();
  }

  function loadHospitals() {
    if (!hub.loadScript) return;
    if (elHospitalsPanel) elHospitalsPanel.innerHTML = '<div class="kb-hospitals"><span class="kg-empty-hint">正在加载中国作者网络数据…</span></div>';
    hub.loadScript('data/china-author-network.js', function (ok) {
      if (!ok || !window.MG_CHINA_AUTHOR_NETWORK) {
        if (elHospitalsPanel) elHospitalsPanel.innerHTML = '<div class="kb-hospitals"><span class="kg-empty-hint">中国作者网络数据加载失败，请稍后重试或直接打开「中国作者联络图」。</span></div>';
        return;
      }
      if (state.nodeId) renderHospitals(nodesById[state.nodeId]);
    });
  }

  function openChinaNetwork(nodeId) {
    activateTab('china-network');
    var select = document.getElementById('chinaNetworkDrugFilter');
    if (!select) return;
    select.value = nodeId;
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function bindWorkbenchEvents() {
    if (elWorkbench) {
      elWorkbench.addEventListener('click', function (event) {
        var target = event.target && event.target.closest
          ? event.target.closest('[data-kg-lens],[data-edge],[data-locate-node],[data-focus-topic],[data-focus-question],[data-focus-signal],[data-load-hospitals],[data-open-network]')
          : null;
        if (!target) return;
        if (target.hasAttribute('data-kg-lens')) setLens(target.getAttribute('data-kg-lens'));
        else if (target.hasAttribute('data-edge')) selectEdge(target.getAttribute('data-edge'));
        else if (target.hasAttribute('data-locate-node')) locateNode(target.getAttribute('data-locate-node'));
        else if (target.hasAttribute('data-focus-topic')) focusInPlace('knowledge', 'topic:' + target.getAttribute('data-focus-topic'));
        else if (target.hasAttribute('data-focus-question')) focusInPlace('think', 'question:' + target.getAttribute('data-focus-question'));
        else if (target.hasAttribute('data-focus-signal')) focusInPlace('think', 'signal:' + target.getAttribute('data-focus-signal'));
        else if (target.hasAttribute('data-load-hospitals')) loadHospitals();
        else if (target.hasAttribute('data-open-network')) openChinaNetwork(target.getAttribute('data-open-network'));
      });
    }

    var closeEvidenceBtn = document.getElementById('kgEvidenceClose');
    if (closeEvidenceBtn) closeEvidenceBtn.addEventListener('click', hideEvidencePane);

    var exportBtn = document.getElementById('kgExportCard');
    if (exportBtn) exportBtn.addEventListener('click', function () {
      if (!state.nodeId || !hub.openBriefModal) return;
      hub.openBriefModal('精读卡 · ' + nodeShort(nodesById[state.nodeId]), buildConceptCard(nodesById[state.nodeId]));
    });

    var showOnMapBtn = document.getElementById('kgShowOnMap');
    if (showOnMapBtn) showOnMapBtn.addEventListener('click', function () {
      activateTab('graph');
      if (state.nodeId) ensureNodeInView(state.nodeId);
      if (elMapSection && elMapSection.scrollIntoView) {
        try { elMapSection.scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch (err) { elMapSection.scrollIntoView(); }
      }
    });
  }

  function init() {
    renderBadge();
    renderBaseline();
    initializeCommunityControls();
    buildGraph();
    attachPanZoom();
    attachGraphInteraction();
    attachNodeFilters();
    attachTabs();
    bindWorkbenchEvents();
    applyNodeFilters();

    var initialCommunityId = getInitialKnowledgeCommunityId();
    var initialNodeId = getInitialKnowledgeNodeId();
    var initialTopicId = getInitialKnowledgeTopicId();
    var initialTab = getInitialKnowledgeTab();
    var initialLens = getInitialKnowledgeLens();
    var defaultNodeId = nodesById.efgartigimod ? 'efgartigimod' : (nodes[0] && nodes[0].id);

    if (initialTopicId) {
      // 专题深链：选一个锚点概念作为精读对象，并在"知识"镜里展开该专题。
      var topic = topicsById[initialTopicId];
      var anchors = (topic.anchor_nodes || []).filter(function (id) { return nodesById[id] && id !== HUB_ID; });
      var anchorNodeId = anchors[0] || defaultNodeId;
      activateTab('graph');
      selectNode(anchorNodeId, { topicId: initialTopicId });
    } else if (initialNodeId) {
      activateTab('graph');
      selectNode(initialNodeId, { lens: initialLens });
    } else if (initialCommunityId) {
      openCommunityGraph(initialCommunityId);
    } else {
      selectNode(defaultNodeId, { lens: initialLens });
      if (['graph', 'china-network'].indexOf(initialTab) !== -1) activateTab(initialTab);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
