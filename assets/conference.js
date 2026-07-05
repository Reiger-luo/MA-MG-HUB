/* MA-MG-HUB 会议资讯页面 JS */
(function() {
  'use strict';

  var hub = window.MgHub || {};
  var payload = window.MG_CONFERENCE_DATA || {
    summary: {},
    abstracts: [],
    sourceMonitor: [],
    futureMeetings: []
  };

  var meetingModules = [
    {
      id: 'aan',
      label: 'AAN',
      edition: '2026',
      title: 'AAN Annual Meeting 2026',
      subtitle: 'Mirasmart abstract website + insight synthesis',
      meetingKeys: ['AAN 2026'],
      monitorIds: ['aan'],
      url: 'https://index.mirasmart.com/AAN2026/',
      status: '已结构化',
      statusTone: 'ready',
      intro: 'AAN 2026 适合追踪神经病学大会里的 MG 治疗进展，尤其是 FcRn、补体、CAR-T、真实世界和 seronegative gMG。',
      breakthroughNote: '结合 AAN 2026 已结构化摘要，优先提炼会改变治疗格局、证据叙事、中国协作或患者价值沟通的突破。',
      emptyNote: ''
    },
    {
      id: 'ean',
      label: 'EAN',
      edition: '2026',
      title: 'EAN Congress 2026',
      subtitle: 'European Journal of Neurology abstract book',
      meetingKeys: ['EAN 2026'],
      monitorIds: ['ean'],
      url: 'https://www.ean.org/congress2026/abstracts/important-information/ean-2026-congress-abstract-book',
      status: '已结构化',
      statusTone: 'ready',
      intro: 'EAN 2026 以欧洲多中心数据、治疗结局和 ePoster Virtual 为主要内容。分析重点放在国家协作网络、治疗机制和公开摘要完整度。',
      breakthroughNote: '结合 EAN 摘要集的机制、长期管理、真实世界和患者价值研究，提炼可复用到医学事务工作的突破判断。',
      emptyNote: ''
    },
    {
      id: 'mgfa',
      label: 'MGFA',
      edition: '2025',
      title: 'MGFA 2025 摘要集',
      subtitle: 'International Conference + Scientific Session',
      meetingKeys: ['MGFA IC 2025', 'MGFA SS 2025'],
      monitorIds: ['mgfa-ic', 'mgfa-scientific'],
      url: 'https://myasthenia.org/mgfa-international-conference/',
      status: '已结构化',
      statusTone: 'ready',
      intro: 'MGFA 是本网站的核心会议源。本模块合并 2025 International Conference 与 2025 Scientific Session，优先看治疗机制、临床结局、患者旅程和中国机构线索。',
      breakthroughNote: '基于高优先级药物、随机/对照试验、机制转化和中国相关线索，提炼可进入会后复盘的重大突破。',
      emptyNote: ''
    },
    {
      id: 'aanem',
      label: 'AANEM',
      edition: '2025',
      title: 'AANEM Annual Meeting 2025',
      subtitle: 'Abstracts Guide 已定位',
      meetingKeys: [],
      monitorIds: ['aanem'],
      url: 'https://online.flippingbook.com/view/442003187/',
      status: '待结构化',
      statusTone: 'watch',
      intro: 'AANEM 2025 官方 Abstracts Guide 位于 FlippingBook 阅读器。当前已定位 myasthenia 检索页段，待稳定文本层或 Wiley supplement 后接入完整摘要字段。',
      breakthroughNote: 'AANEM 暂先作为摘要源监控；待结构化后再提炼临床路径、诊断监测和肌病交叉管理的突破线索。',
      emptyNote: '已定位官方 2025 Abstracts Guide；阅读器内 myasthenia 搜索可见多个页段，下一步补抓题名、poster 编号、作者、机构和摘要正文。'
    }
  ];

  var state = {
    activeModule: 'aan',
    keyword: '',
    researchType: 'all',
    country: 'all',
    chinaOnly: false,
    topic: null,
    page: 0
  };

  var pageSize = 8;
  var currentItems = [];
  var filteredItems = [];

  function $(id) {
    return document.getElementById(id);
  }

  var el = {
    badge: $('conferenceBadge'),
    meetingCards: $('conferenceMeetingCards'),
    moduleEyebrow: $('conferenceModuleEyebrow'),
    moduleTitle: $('conferenceModuleTitle'),
    moduleIntro: $('conferenceModuleIntro'),
    moduleLink: $('conferenceModuleLink'),
    moduleKpis: $('conferenceModuleKpis'),
    briefTakeaways: $('conferenceBriefTakeaways'),
    strategicNarrative: $('conferenceStrategicNarrative'),
    countryRank: $('conferenceCountryRank'),
    typeRank: $('conferenceTypeRank'),
    topicCloud: $('conferenceTopicCloud'),
    drugBoard: $('conferenceDrugBoard'),
    breakthroughs: $('conferenceBreakthroughs'),
    futureMeetings: $('conferenceFutureMeetings'),
    sourceMonitor: $('conferenceSourceMonitor'),
    results: $('conferenceResults'),
    resultCount: $('conferenceResultCount'),
    keyword: $('conferenceKeyword'),
    typeFilter: $('conferenceTypeFilter'),
    countryFilter: $('conferenceCountryFilter'),
    chinaOnly: $('conferenceChinaOnly')
  };

  function escapeHtml(value) {
    if (hub.escapeText) return hub.escapeText(value);
    return String(value == null ? '' : value).replace(/[&<>"']/g, function(char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }

  function escapeHref(value, fallback) {
    if (hub.safeUrl) return hub.safeUrl(value, fallback || '#');
    return escapeHtml(fallback || '#');
  }

  function compactNumber(value) {
    if (value == null || value === '') return '0';
    var n = Number(value);
    if (!Number.isFinite(n)) return String(value);
    if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
    return String(n);
  }

  function getModule(moduleId) {
    return meetingModules.filter(function(module) { return module.id === moduleId; })[0] || meetingModules[0];
  }

  function getModuleItems(module) {
    return (payload.abstracts || []).filter(function(item) {
      return module.meetingKeys.indexOf(item.conference) !== -1;
    });
  }

  function countValues(items, getter) {
    var map = {};
    items.forEach(function(item) {
      var values = getter(item) || [];
      if (!Array.isArray(values)) values = [values];
      values.forEach(function(value) {
        if (!value) return;
        map[value] = (map[value] || 0) + 1;
      });
    });
    return Object.keys(map).map(function(key) {
      return { name: key, count: map[key] };
    }).sort(function(a, b) {
      return b.count - a.count || String(a.name).localeCompare(String(b.name), 'zh-CN');
    });
  }

  function summarizeModule(items) {
    var countries = countValues(items, function(item) { return item.countries || []; }).filter(function(item) { return item.name !== '未识别'; });
    var types = countValues(items, function(item) { return item.researchType || '其他临床研究'; });
    var topics = countValues(items, function(item) { return item.topics || []; });
    var drugs = countValues(items, function(item) { return item.drugs || []; });
    return {
      total: items.length,
      countries: countries,
      types: types,
      topics: topics,
      drugs: drugs,
      countryCount: countries.length,
      chinaRelated: items.filter(function(item) { return item.isChinaRelated; }).length,
      highPriority: items.filter(function(item) { return (item.priorityScore || 0) >= 6; }).length,
      topCountry: countries[0] ? countries[0].name : '待识别',
      topType: types[0] ? types[0].name : '待识别',
      topTopic: topics[0] ? topics[0].name : '待识别',
      topDrug: drugs[0] ? drugs[0].name : '待识别'
    };
  }

  function topNames(rows, limit) {
    return (rows || []).slice(0, limit || 3).map(function(row) { return row.name; }).filter(Boolean);
  }

  function joinNames(names, fallback) {
    var list = (names || []).filter(Boolean);
    if (!list.length) return fallback || '待识别';
    return list.join('、');
  }

  function hasTopic(item, topicName) {
    return (item.topics || []).indexOf(topicName) !== -1;
  }

  function findRepresentativeItems(items, test, limit) {
    return items.filter(test || function() { return true; }).slice().sort(function(a, b) {
      return (b.priorityScore || 0) - (a.priorityScore || 0) || String(a.title || '').localeCompare(String(b.title || ''));
    }).slice(0, limit || 2);
  }

  function truncateText(text, max) {
    var value = String(text || '');
    if (value.length <= max) return value;
    return value.slice(0, max - 1) + '…';
  }

  function getMeetingSourceLimitation(module) {
    if (module.id === 'aanem') return 'AANEM 2025 摘要源已定位，但稳定结构化字段尚待补抓。';
    if (module.id === 'aan') return '基于 AAN Mirasmart 摘要页；presentation 细节仍需会后核查。';
    if (module.id === 'ean') return '基于 EAN / European Journal of Neurology abstract book；部分 ePoster 信息可能缺少完整会话语境。';
    return '基于 MGFA 公开 program / poster abstract guide；未公开全文或口头报告材料时仅作摘要级复盘。';
  }

  function renderBriefTakeaways(module, summary, items) {
    if (!el.briefTakeaways) return;
    var takeaways = [];
    var countryNames = topNames(summary.countries, 3);
    var mechanismNames = topNames(summary.drugs.length ? summary.drugs : summary.topics, 3);

    if (!items.length) {
      takeaways = [
        module.emptyNote || '该会议暂未接入结构化 MG 摘要。',
        '当前页面先保留会议入口、摘要源状态和后续扫描口，避免把其他会议内容混入本模块。',
        getMeetingSourceLimitation(module)
      ];
    } else {
      takeaways.push('本模块已结构化 ' + summary.total + ' 条 MG 摘要，主导主题为 ' + summary.topTopic + '，研究类型以 ' + summary.topType + ' 为主。');
      takeaways.push('投稿/机构线索集中在 ' + joinNames(countryNames, '待识别国家/地区') + '；中国相关 ' + summary.chinaRelated + ' 条，可作为会后 KOL 与机构追踪入口。');
      takeaways.push('药物/机制信号以 ' + joinNames(mechanismNames, '待识别机制') + ' 为核心；高优先级摘要 ' + summary.highPriority + ' 条，适合优先进入 MSL briefing 候选池。');
      takeaways.push('本页把会议资讯转成“重大突破、工作用途、来源核查”三层结构，避免只停留在摘要新闻流。');
    }

    el.briefTakeaways.innerHTML = '<div class="conference-takeaway-list">' + takeaways.slice(0, 4).map(function(text, index) {
      return '<article class="conference-takeaway-card">' +
        '<span>' + escapeHtml('0' + (index + 1)) + '</span>' +
        '<p>' + escapeHtml(text) + '</p>' +
      '</article>';
    }).join('') + '</div>';
  }

  function renderStrategicNarrative(module, items) {
    if (!el.strategicNarrative) return;
    var conferenceName = module.meetingKeys[0];
    var narrative = conferenceName && payload.meetingNarratives ? payload.meetingNarratives[conferenceName] : null;
    if (!items.length || !narrative) {
      el.strategicNarrative.innerHTML = '';
      return;
    }
    var depth = narrative.contentDepth || {};
    var chapters = narrative.chapters || [];
    var questions = narrative.briefingQuestions || [];
    var sourceId = items[0] && items[0].sourceId;
    var audit = sourceId && payload.coverageAudits ? payload.coverageAudits[sourceId] : null;
    var comparison = narrative.competitiveComparison || null;
    var auditHtml = audit ? '<div class="conference-audit-strip">' +
      '<span><b>' + escapeHtml(audit.rawSearchResults || 0) + '</b>raw search</span>' +
      '<span><b>' + escapeHtml(audit.curatedMgIncluded || 0) + '</b>MG-core</span>' +
      '<span><b>' + escapeHtml(audit.excludedByRule || 0) + '</b>规则剔除</span>' +
      '<p>' + escapeHtml(audit.exclusionPrinciple || '') + '</p>' +
    '</div>' : '';
    var comparisonHtml = comparison ? '<div class="conference-comparison-card">' +
      '<div><span>竞品对照</span><a href="' + escapeHref(comparison.url || '#') + '" target="_blank" rel="noopener">' + escapeHtml(comparison.label || '参考页面') + '</a></div>' +
      '<p>' + escapeHtml(comparison.verdict || '') + '</p>' +
      '<ul>' + (comparison.advantages || []).slice(0, 4).map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') + '</ul>' +
    '</div>' : '';
    el.strategicNarrative.innerHTML =
      '<section class="conference-narrative-panel">' +
        '<div class="conference-narrative-head">' +
          '<span>全景剖析 · MA 工作流版本</span>' +
          '<strong>' + escapeHtml(narrative.headline || '') + '</strong>' +
          '<p>' + escapeHtml(narrative.strategicRead || '') + '</p>' +
        '</div>' +
        '<div class="conference-depth-strip">' +
          '<span><b>' + escapeHtml(depth.abstracts || 0) + '</b>摘要</span>' +
          '<span><b>' + escapeHtml(depth.highPriority || 0) + '</b>优先核查</span>' +
          '<span><b>' + escapeHtml(depth.chinaRelated || 0) + '</b>中国线索</span>' +
          '<span><b>' + escapeHtml((depth.topDrugs || depth.topTopics || []).slice(0, 3).join(' / ') || '机制待识别') + '</b>核心机制</span>' +
        '</div>' +
        auditHtml +
        comparisonHtml +
        '<div class="conference-chapter-grid">' + chapters.map(function(chapter, idx) {
          var refs = chapter.refs || [];
          return '<article class="conference-chapter-card">' +
            '<div class="conference-chapter-index">' + escapeHtml('线索 0' + (idx + 1)) + '</div>' +
            '<h3>' + escapeHtml(chapter.title || '') + '</h3>' +
            '<p>' + escapeHtml(chapter.takeaway || '') + '</p>' +
            '<em>' + escapeHtml(chapter.maUse || '') + '</em>' +
            '<div class="conference-chapter-refs">' + refs.slice(0, 3).map(function(ref) {
              var metrics = (ref.keyMetrics || []).slice(0, 1).join('；');
              return '<a href="' + escapeHref(ref.sourceUrl || '#') + '" target="_blank" rel="noopener">' +
                '<strong>' + escapeHtml(truncateText(ref.title || 'Untitled', 72)) + '</strong>' +
                (metrics ? '<span>' + escapeHtml(metrics) + '</span>' : '') +
              '</a>';
            }).join('') + '</div>' +
          '</article>';
        }).join('') + '</div>' +
        '<div class="conference-briefing-questions">' +
          '<span>MSL briefing 必答问题</span>' +
          '<ol>' + questions.slice(0, 4).map(function(question) { return '<li>' + escapeHtml(question) + '</li>'; }).join('') + '</ol>' +
        '</div>' +
      '</section>';
  }

  function renderMeetingCards() {
    if (!el.meetingCards) return;
    el.meetingCards.innerHTML = meetingModules.map(function(module) {
      var items = getModuleItems(module);
      var summary = summarizeModule(items);
      var active = module.id === state.activeModule;
      return '<button type="button" class="conference-meeting-card' + (active ? ' active' : '') + '" data-conference-module="' + escapeHtml(module.id) + '" aria-pressed="' + (active ? 'true' : 'false') + '">' +
        '<span class="conference-meeting-status ' + escapeHtml(module.statusTone) + '">' + escapeHtml(module.status) + '</span>' +
        '<strong>' + escapeHtml(module.label) + '<em>' + escapeHtml(module.edition) + '</em></strong>' +
        '<p>' + escapeHtml(module.subtitle) + '</p>' +
        '<div class="conference-meeting-metrics">' +
          '<span><b>' + escapeHtml(compactNumber(summary.total)) + '</b>摘要</span>' +
          '<span><b>' + escapeHtml(summary.countryCount || '-') + '</b>地区</span>' +
          '<span><b>' + escapeHtml(summary.topTopic) + '</b>主题</span>' +
        '</div>' +
      '</button>';
    }).join('');

    var buttons = el.meetingCards.querySelectorAll('[data-conference-module]');
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener('click', function() {
        state.activeModule = this.getAttribute('data-conference-module');
        state.keyword = '';
        state.researchType = 'all';
        state.country = 'all';
        state.chinaOnly = false;
        state.topic = null;
        state.page = 0;
        if (el.keyword) el.keyword.value = '';
        if (el.chinaOnly) el.chinaOnly.checked = false;
        render();
      });
    }
  }

  function renderKpis(module, summary) {
    if (!el.moduleKpis) return;
    var cards = [
      { label: '结构化摘要', value: summary.total, note: module.status },
      { label: '国家/地区', value: summary.countryCount || 0, note: '机构字段推断' },
      { label: '高优先级', value: summary.highPriority || 0, note: '试验/药物/中国' },
      { label: '中国相关', value: summary.chinaRelated || 0, note: '机构或地点命中' },
      { label: '主导主题', value: summary.topTopic, note: summary.topDrug !== '待识别' ? summary.topDrug : summary.topType }
    ];
    el.moduleKpis.innerHTML = cards.map(function(card) {
      return '<div class="conference-kpi-card">' +
        '<span>' + escapeHtml(card.label) + '</span>' +
        '<strong>' + escapeHtml(compactNumber(card.value)) + '</strong>' +
        '<em>' + escapeHtml(card.note) + '</em>' +
      '</div>';
    }).join('');
  }

  function renderRank(target, items, limit) {
    if (!target) return;
    var rows = (items || []).slice(0, limit || 8);
    if (!rows.length) {
      target.innerHTML = '<div class="conference-empty-line">暂无可计算数据</div>';
      return;
    }
    var max = rows[0].count || 1;
    target.innerHTML = '<div class="conference-rank">' + rows.map(function(item) {
      var width = Math.max(7, Math.round((item.count || 0) / max * 100));
      return '<div class="conference-rank-row">' +
        '<span title="' + escapeHtml(item.name) + '">' + escapeHtml(item.name) + '</span>' +
        '<div class="conference-rank-track"><i style="--rank-width:' + width + '%"></i></div>' +
        '<strong>' + escapeHtml(item.count || 0) + '</strong>' +
      '</div>';
    }).join('') + '</div>';
  }

  function renderTopics(summary) {
    if (!el.topicCloud) return;
    var topics = (summary.topics || []).slice(0, 12);
    if (!topics.length) {
      el.topicCloud.innerHTML = '<div class="conference-empty-line">暂无主题数据</div>';
    } else {
      el.topicCloud.innerHTML = topics.map(function(topic) {
        var active = state.topic === topic.name;
        return '<button type="button" class="conference-topic-pill' + (active ? ' active' : '') + '" data-conference-topic="' + escapeHtml(topic.name) + '">' +
          '<span>' + escapeHtml(topic.name) + '</span><b>' + escapeHtml(topic.count) + '</b>' +
        '</button>';
      }).join('');
      var buttons = el.topicCloud.querySelectorAll('[data-conference-topic]');
      for (var i = 0; i < buttons.length; i++) {
        buttons[i].addEventListener('click', function() {
          var topic = this.getAttribute('data-conference-topic');
          state.topic = state.topic === topic ? null : topic;
          state.page = 0;
          renderTopics(summarizeModule(currentItems));
          applyFilters();
        });
      }
    }

    if (!el.drugBoard) return;
    var drugs = (summary.drugs || []).slice(0, 8);
    el.drugBoard.innerHTML = drugs.length ? drugs.map(function(drug) {
      return '<span class="conference-drug-chip">' + escapeHtml(drug.name) + '<b>' + escapeHtml(drug.count) + '</b></span>';
    }).join('') : '<div class="conference-empty-line">暂无药物/靶点命中</div>';
  }

  function hasAnyTopic(item, topicNames) {
    return (topicNames || []).some(function(topicName) {
      return hasTopic(item, topicName);
    });
  }

  function itemText(item) {
    return [
      item.title, item.abstract, item.analysisZh, item.sessionName,
      item.programNumber, (item.topics || []).join(' '), (item.drugs || []).join(' '),
      item.deepInsight && item.deepInsight.clinicalReadoutZh,
      item.deepInsight && item.deepInsight.maImplicationZh,
      item.deepInsight && (item.deepInsight.actionTags || []).join(' '),
      item.deepInsight && (item.deepInsight.kolQuestions || []).join(' ')
    ].join(' ').toLowerCase();
  }

  function containsAny(item, terms) {
    var text = itemText(item);
    return (terms || []).some(function(term) {
      return text.indexOf(String(term).toLowerCase()) !== -1;
    });
  }

  function buildBreakthrough(dimension, title, conclusion, why, maUse, nextStep, representatives, tags) {
    return {
      dimension: dimension,
      title: title,
      conclusion: conclusion,
      why: why,
      maUse: maUse,
      nextStep: nextStep,
      representatives: representatives || [],
      tags: tags || []
    };
  }

  function buildBreakthroughSignals(module, summary, items) {
    if (!items.length) return [];
    var signals = [];
    var topDrugs = topNames(summary.drugs, 4);
    var topTopics = topNames(summary.topics, 5);

    var treatmentItems = findRepresentativeItems(items, function(item) {
      return item.researchType === '随机/对照试验' ||
        (item.priorityScore || 0) >= 8 ||
        containsAny(item, ['phase 3', 'phase three', 'pivotal', 'primary endpoint', 'final results']) ||
        hasAnyTopic(item, ['FcRn', '补体', 'B细胞/免疫重置']);
    }, 3);
    if (treatmentItems.length) {
      signals.push(buildBreakthrough(
        '治疗范式',
        '靶向治疗从“有结果”进入“可定位”阶段',
        '高优先级摘要集中在 ' + joinNames(topDrugs.length ? topDrugs : topTopics.slice(0, 3), '核心机制') + '，真正的会后价值不是复述单篇结果，而是比较机制、人群、终点、给药便利性和安全性边界。',
        '这类内容通常对应大会中最容易被 KOL 追问的“治疗选择”问题：同一患者路径中，FcRn、补体、B 细胞/免疫重置或其他机制分别解决什么痛点，证据强度是否足以改变讨论重心。医学事务复盘时应把药物结果放回治疗目标框架，而不是按药名逐条罗列。',
        '用于 congress debrief 的治疗格局页、竞品问题清单和 KOL 访谈主线。',
        '优先核查研究设计、入组抗体分型、主要终点、随访长度、给药方式和安全性采集口径；再决定是否进入内部材料或仅作为趋势观察。',
        treatmentItems,
        topDrugs.concat(['高优先级 ' + summary.highPriority + ' 条']).slice(0, 5)
      ));
    }

    var subgroupItems = findRepresentativeItems(items, function(item) {
      return containsAny(item, [
        'seronegative', 'anti-acetylcholine receptor antibody-negative', 'ocular',
        'juvenile', 'pediatric', 'paediatric', 'adolescent', 'musk', 'lrp4',
        'thymoma', 'pregnancy', 'early disease', 'refractory', 'crisis'
      ]);
    }, 3);
    if (subgroupItems.length) {
      signals.push(buildBreakthrough(
        '人群边界',
        '特殊亚群正在成为下一轮差异化证据入口',
        '血清分型、眼肌型、青少年/妊娠、MuSK/LRP4、胸腺瘤或危象相关线索提示，会议复盘要从“gMG 总体疗效”推进到“哪些患者最需要新策略”。',
        '参考页里的 AAN/EAN 全景叙事都把特殊人群作为重要章节，这一点值得保留；但在工作台里更应该转成患者画像和证据缺口。若某一治疗在特定亚群中只有探索性摘要，不能直接外推为定位结论，却很适合生成专家访谈问题。',
        '用于专家拜访前的问题分层、患者画像 slide 和本地证据 gap 梳理。',
        '逐条确认亚组是否预设、样本量是否足够、是否有对照组、终点是否与总体研究一致，并标出仍需全文或后续研究验证的部分。',
        subgroupItems,
        ['特殊人群', '抗体分型', '精准管理']
      ));
    }

    var chinaItems = findRepresentativeItems(items, function(item) {
      return item.isChinaRelated;
    }, 3);
    if (chinaItems.length) {
      signals.push(buildBreakthrough(
        '中国转化',
        '中国相关摘要应转成专家网络和本土证据机会',
        '中国作者、机构或患者数据不只是投稿统计；它们可以帮助医学事务判断哪些研究可跟进全文、哪些专家适合深访、哪些话题能补足中国路径证据。',
        '这部分是本网站区别于普通资讯页的关键：会议报道只会说“中国参与度提高”，而医学事务需要知道参与的是全球多中心、真实世界、机制研究还是患者价值研究。不同类型对应不同后续动作，比如 KOL mapping、研究合作、证据 gap 或本土沟通材料。',
        '用于 KOL mapping、会后 follow-up、区域医学计划和本地数据生成假设。',
        '核查作者机构、患者来源、是否包含中国数据、研究是否由中国团队主导，以及能否和现有中国情报、专家画像和内容模块相互引用。',
        chinaItems,
        ['中国相关', 'KOL mapping', '本土证据']
      ));
    }

    var valueItems = findRepresentativeItems(items, function(item) {
      return item.researchType === '真实世界/队列' ||
        item.researchType === 'PRO/HEOR' ||
        hasAnyTopic(item, ['真实世界/登记', 'PRO/生活质量', '安全性', '危象/急性加重', '数字监测']) ||
        containsAny(item, ['burden', 'quality of life', 'steroid', 'cost', 'preference', 'registry']);
    }, 3);
    if (valueItems.length) {
      signals.push(buildBreakthrough(
        '落地价值',
        '真实世界、PRO 与安全性正在重塑“理想治疗”语言',
        '会议摘要里关于激素减量、长期控制、患者负担、用药管理和数字监测的信号，能把药物结果转成临床实践更关心的治疗目标。',
        '这一层并不一定是“最突破”的疗效结果，却常常最能进入 MSL 日常工作。真实世界和 PRO 可以把治疗讨论从评分改善延伸到激素减量、复发/危象、给药负担、生活质量和资源使用；安全性摘要则帮助提前准备更具体的临床管理追问。',
        '用于疾病教育、患者旅程、价值沟通和安全性追问清单。',
        '区分 RCT 延长期、回顾性队列、登记研究、claims/HEOR 和病例报告的证据边界；价值或负担数据不能写成疗效结论，应作为临床实践语境补充。',
        valueItems,
        ['真实世界', 'PRO/生活质量', '安全性']
      ));
    }

    var mechanismItems = findRepresentativeItems(items, function(item) {
      return item.researchType === '机制/转化' ||
        hasAnyTopic(item, ['B细胞/免疫重置', '数字监测']) ||
        containsAny(item, ['car-t', 'cd19', 'bcma', 'biomarker', 'protease', 'omics', 'cytokine', 'digital']);
    }, 3);
    if (mechanismItems.length) {
      signals.push(buildBreakthrough(
        '机制外溢',
        '机制与监测信号正在生成新的医学假设',
        'B 细胞、免疫重置、抗体功能、数字监测和生物标志物类摘要，适合从会议资讯升级为后续研究问题，而不是只作为背景知识收藏。',
        '机制类摘要的价值在于帮助解释“为什么会有不同反应”和“下一步该监控什么”。它们通常还不能直接支撑临床定位，但可以连接知识库、诊治格局和后续文献监控，形成更连续的医学假设链。',
        '用于 advisory board 议题、机制教育材料和下一轮文献/试验监控关键词。',
        '标记该信号属于体外/动物/探索性人群/转化研究中的哪一类，并把关键词写入后续监控列表，避免把机制推测包装成临床结论。',
        mechanismItems,
        ['机制/转化', '生物标志物', '研究假设']
      ));
    }

    return signals.slice(0, 4);
  }

  function renderBreakthroughs(module, summary, items) {
    if (!el.breakthroughs) return;
    var signals = buildBreakthroughSignals(module, summary, items);
    if (!signals.length) {
      el.breakthroughs.innerHTML = '<div class="conference-empty-focus"><strong>重大突破待结构化</strong><p>' + escapeHtml(module.breakthroughNote || '当前先保留会议入口与摘要源状态，待摘要结构化后再提炼突破与转化洞察。') + '</p></div>';
      return;
    }
    el.breakthroughs.innerHTML = '<div class="conference-breakthrough-grid">' + signals.map(function(signal, index) {
      var refs = signal.representatives.slice(0, 2);
      return '<article class="conference-breakthrough-card">' +
        '<div class="conference-breakthrough-top">' +
          '<span class="conference-breakthrough-index">' + escapeHtml('突破 0' + (index + 1)) + '</span>' +
          '<em>' + escapeHtml(signal.dimension) + '</em>' +
        '</div>' +
        '<strong>' + escapeHtml(signal.title) + '</strong>' +
        '<div class="conference-breakthrough-analysis">' +
          '<span>洞察分析</span>' +
          '<p>' + escapeHtml(signal.conclusion) + '</p>' +
          '<p>' + escapeHtml(signal.why) + '</p>' +
        '</div>' +
        '<div class="conference-breakthrough-work"><span>医学事务转化</span><p>' + escapeHtml(signal.maUse) + '</p></div>' +
        '<div class="conference-breakthrough-work"><span>核查与落地</span><p>' + escapeHtml(signal.nextStep) + '</p></div>' +
        '<div class="conference-breakthrough-refs">' +
          '<span>优先核查摘要</span>' +
          (refs.length ? refs.map(function(item) {
            return '<a href="' + escapeHref(item.sourceUrl || item.pageUrl) + '" target="_blank" rel="noopener">' + escapeHtml(truncateText(item.title, 82)) + '</a>';
          }).join('') : '<em>暂无代表摘要，待源数据补充。</em>') +
        '</div>' +
        '<div class="conference-card-head">' + signal.tags.slice(0, 5).map(function(tag) {
          return '<span class="conference-badge highlight">' + escapeHtml(tag) + '</span>';
        }).join('') + '</div>' +
        '<em class="conference-source-note">' + escapeHtml(getMeetingSourceLimitation(module)) + '</em>' +
      '</article>';
    }).join('') + '</div>';
  }

  function populateSelect(select, options, allLabel, selectedValue) {
    if (!select) return;
    var value = selectedValue || 'all';
    select.innerHTML = '<option value="all">' + escapeHtml(allLabel) + '</option>' + options.map(function(option) {
      return '<option value="' + escapeHtml(option) + '">' + escapeHtml(option) + '</option>';
    }).join('');
    select.value = options.indexOf(value) !== -1 ? value : 'all';
  }

  function updateFilters(items) {
    populateSelect(el.typeFilter, countValues(items, function(item) { return item.researchType; }).map(function(item) { return item.name; }), '全部研究类型', state.researchType);
    populateSelect(el.countryFilter, countValues(items, function(item) { return item.countries || []; }).filter(function(item) { return item.name !== '未识别'; }).map(function(item) { return item.name; }), '全部国家/地区', state.country);
  }

  function itemMatches(item) {
    if (state.researchType !== 'all' && item.researchType !== state.researchType) return false;
    if (state.country !== 'all' && (item.countries || []).indexOf(state.country) === -1) return false;
    if (state.chinaOnly && !item.isChinaRelated) return false;
    if (state.topic && (item.topics || []).indexOf(state.topic) === -1) return false;
    if (state.keyword) {
      var haystack = [
        item.title, item.authors, item.abstract, item.researchType,
        (item.topics || []).join(' '), (item.drugs || []).join(' '), (item.countries || []).join(' '),
        item.deepInsight && item.deepInsight.clinicalReadoutZh,
        item.deepInsight && item.deepInsight.maImplicationZh,
        item.deepInsight && (item.deepInsight.actionTags || []).join(' '),
        item.deepInsight && (item.deepInsight.kolQuestions || []).join(' ')
      ].join(' ').toLowerCase();
      if (haystack.indexOf(state.keyword) === -1) return false;
    }
    return true;
  }

  function applyFilters() {
    filteredItems = currentItems.filter(itemMatches).sort(function(a, b) {
      return (b.priorityScore || 0) - (a.priorityScore || 0) || String(a.title || '').localeCompare(String(b.title || ''));
    });
    renderResults();
  }

  function renderResults() {
    if (!el.results) return;
    if (el.resultCount) el.resultCount.textContent = filteredItems.length + ' 条';
    if (!currentItems.length) {
      el.results.innerHTML = '<div class="conference-empty-line">该会议暂未接入结构化摘要，先看上方接口状态。</div>';
      return;
    }
    if (!filteredItems.length) {
      el.results.innerHTML = '<div class="conference-empty-line">暂无匹配摘要，调整关键词、国家或研究类型。</div>';
      return;
    }
    var totalPages = Math.ceil(filteredItems.length / pageSize);
    if (state.page >= totalPages) state.page = Math.max(0, totalPages - 1);
    var pageItems = filteredItems.slice(state.page * pageSize, state.page * pageSize + pageSize);
    el.results.innerHTML = '<div class="conference-result-table">' + pageItems.map(renderResultRow).join('') + '</div>' + renderPagination(totalPages);
    bindResultActions();
  }

  function renderResultRow(item) {
    var insight = item.deepInsight || {};
    var tags = [item.researchType].concat(item.drugs || []).concat(item.topics || []).slice(0, 4);
    var actionTags = insight.actionTags || [];
    var metrics = insight.keyMetrics || [];
    var kolQuestions = insight.kolQuestions || [];
    return '<article class="conference-result-row conference-result-row-deep">' +
      '<div>' +
        '<a class="conference-card-title" href="' + escapeHref(item.sourceUrl || item.pageUrl) + '" target="_blank" rel="noopener">' + escapeHtml(item.title) + '</a>' +
        '<p>' + escapeHtml([item.conference, item.presentationType, (item.countries || []).slice(0, 4).join('、')].filter(Boolean).join(' · ')) + '</p>' +
        '<div class="conference-deep-readout">' +
          '<span>临床读数</span>' +
          '<p>' + escapeHtml(insight.clinicalReadoutZh || item.analysisZh || '中文分析待生成；请展开摘要核查来源。') + '</p>' +
        '</div>' +
        '<div class="conference-ma-implication">' +
          '<span>MA 转化</span>' +
          '<p>' + escapeHtml(insight.maImplicationZh || '待补充医学事务转化判断。') + '</p>' +
        '</div>' +
        (metrics.length ? '<div class="conference-metric-list">' + metrics.slice(0, 3).map(function(metric) { return '<em>' + escapeHtml(metric) + '</em>'; }).join('') + '</div>' : '') +
        '<details class="conference-evidence-detail">' +
          '<summary>证据边界 / KOL 问题 / 原始摘要</summary>' +
          '<p><strong>证据边界：</strong>' + escapeHtml(insight.evidenceBoundaryZh || '需回到原始摘要核查。') + '</p>' +
          '<p><strong>下一步：</strong>' + escapeHtml(insight.evidenceNeed || '核查来源后再进入材料。') + '</p>' +
          (kolQuestions.length ? '<ol>' + kolQuestions.slice(0, 4).map(function(q) { return '<li>' + escapeHtml(q) + '</li>'; }).join('') + '</ol>' : '') +
          '<div class="conference-abstract open" id="conference-abs-' + escapeHtml(item.id) + '">' + escapeHtml(item.abstract || '摘要正文待公开。') + '</div>' +
        '</details>' +
      '</div>' +
      '<div class="conference-result-tags">' + tags.map(function(tag) {
        return '<span class="conference-badge">' + escapeHtml(tag) + '</span>';
      }).join('') + actionTags.map(function(tag) {
        return '<span class="conference-badge highlight">' + escapeHtml(tag) + '</span>';
      }).join('') + '</div>' +
    '</article>';
  }

  function renderPagination(totalPages) {
    if (totalPages <= 1) return '';
    return '<div class="pagination">' +
      '<button class="btn" type="button" data-conference-page="prev"' + (state.page === 0 ? ' disabled' : '') + '>‹ 上一页</button>' +
      '<span style="font-size:0.85rem;color:var(--fg3)">' + (state.page + 1) + ' / ' + totalPages + ' 页</span>' +
      '<button class="btn" type="button" data-conference-page="next"' + (state.page >= totalPages - 1 ? ' disabled' : '') + '>下一页 ›</button>' +
    '</div>';
  }

  function bindResultActions() {
    var pageButtons = el.results.querySelectorAll('[data-conference-page]');
    for (var i = 0; i < pageButtons.length; i++) {
      pageButtons[i].addEventListener('click', function() {
        var action = this.getAttribute('data-conference-page');
        if (action === 'prev' && state.page > 0) state.page--;
        if (action === 'next') state.page++;
        renderResults();
      });
    }
  }

  function renderFutureMeetings() {
    if (!el.futureMeetings) return;
    var items = payload.futureMeetings || [];
    el.futureMeetings.innerHTML = '<div class="conference-future-list">' + items.map(function(item) {
      return '<article class="conference-mini-card">' +
        '<strong>' + escapeHtml(item.meeting) + '</strong>' +
        '<span>' + escapeHtml(item.date + ' · ' + item.location) + '</span>' +
        '<em>' + escapeHtml(item.status || '') + '</em>' +
        '<a href="' + escapeHref(item.url) + '" target="_blank" rel="noopener">官网更新</a>' +
      '</article>';
    }).join('') + '</div>';
  }

  function renderSourceMonitor(module) {
    if (!el.sourceMonitor) return;
    var items = (payload.sourceMonitor || []).filter(function(item) {
      return module.monitorIds.indexOf(item.id) !== -1;
    });
    if (!items.length) items = payload.sourceMonitor || [];
    el.sourceMonitor.innerHTML = '<div class="conference-source-list">' + items.map(function(item) {
      var warn = /监控|入口|待|定位/.test(item.status || '');
      return '<article class="conference-mini-card">' +
        '<span class="conference-source-status' + (warn ? ' warn' : '') + '">' + escapeHtml(item.status || '-') + '</span>' +
        '<strong>' + escapeHtml(item.organization || item.id) + '</strong>' +
        '<p>' + escapeHtml(item.evidence || '') + '</p>' +
        '<em>' + escapeHtml(item.nextAction || '') + '</em>' +
        '<a href="' + escapeHref(item.url) + '" target="_blank" rel="noopener">源页面</a>' +
      '</article>';
    }).join('') + '</div>';
  }

  function bindFilters() {
    if (el.keyword) {
      el.keyword.addEventListener('input', function() {
        state.keyword = (this.value || '').trim().toLowerCase();
        state.page = 0;
        applyFilters();
      });
    }
    if (el.typeFilter) {
      el.typeFilter.addEventListener('change', function() {
        state.researchType = this.value;
        state.page = 0;
        applyFilters();
      });
    }
    if (el.countryFilter) {
      el.countryFilter.addEventListener('change', function() {
        state.country = this.value;
        state.page = 0;
        applyFilters();
      });
    }
    if (el.chinaOnly) {
      el.chinaOnly.addEventListener('change', function() {
        state.chinaOnly = this.checked;
        state.page = 0;
        applyFilters();
      });
    }
  }

  function render() {
    var module = getModule(state.activeModule);
    currentItems = getModuleItems(module);
    var summary = summarizeModule(currentItems);

    if (el.badge) el.badge.textContent = '会议数据更新 ' + (payload.generated_at || '-');
    if (el.moduleEyebrow) el.moduleEyebrow.textContent = module.label + ' · ' + module.edition + ' · ' + module.status;
    if (el.moduleTitle) el.moduleTitle.textContent = module.title;
    if (el.moduleIntro) el.moduleIntro.textContent = module.intro;
    if (el.moduleLink) el.moduleLink.href = module.url;

    renderMeetingCards();
    renderKpis(module, summary);
    renderBriefTakeaways(module, summary, currentItems);
    renderStrategicNarrative(module, currentItems);
    renderRank(el.countryRank, summary.countries, 8);
    renderRank(el.typeRank, summary.types, 8);
    renderTopics(summary);
    renderBreakthroughs(module, summary, currentItems);
    renderSourceMonitor(module);
    updateFilters(currentItems);
    applyFilters();
  }

  function init() {
    if (!$('tab-conference')) return;
    renderFutureMeetings();
    bindFilters();
    render();
  }

  init();
})();
