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
    },
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
    countryRank: $('conferenceCountryRank'),
    typeRank: $('conferenceTypeRank'),
    topicCloud: $('conferenceTopicCloud'),
    drugBoard: $('conferenceDrugBoard'),
    breakthroughs: $('conferenceBreakthroughs'),
    insightCount: $('conferenceInsightCount'),
    highlights: $('conferenceHighlights'),
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
      item.programNumber, (item.topics || []).join(' '), (item.drugs || []).join(' ')
    ].join(' ').toLowerCase();
  }

  function containsAny(item, terms) {
    var text = itemText(item);
    return (terms || []).some(function(term) {
      return text.indexOf(String(term).toLowerCase()) !== -1;
    });
  }

  function buildBreakthrough(dimension, title, conclusion, maUse, representatives, tags) {
    return {
      dimension: dimension,
      title: title,
      conclusion: conclusion,
      maUse: maUse,
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
        '用于 congress debrief 的治疗格局页、竞品问题清单和 KOL 访谈主线。',
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
        '用于专家拜访前的问题分层、患者画像 slide 和本地证据 gap 梳理。',
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
        '用于 KOL mapping、会后 follow-up、区域医学计划和本地数据生成假设。',
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
        '用于疾病教育、患者旅程、价值沟通和安全性追问清单。',
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
        '用于 advisory board 议题、机制教育材料和下一轮文献/试验监控关键词。',
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
        '<p>' + escapeHtml(signal.conclusion) + '</p>' +
        '<div class="conference-breakthrough-work"><span>医学事务转化</span><p>' + escapeHtml(signal.maUse) + '</p></div>' +
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

  function buildInsight(dimension, title, why, mslUse, representatives, tags) {
    return {
      dimension: dimension,
      title: title,
      why: why,
      mslUse: mslUse,
      representatives: representatives || [],
      tags: tags || []
    };
  }

  function buildConferenceInsights(module, summary, items) {
    if (!items.length) return [];
    var insights = [];
    var topCountries = topNames(summary.countries, 3);
    var topDrugs = topNames(summary.drugs, 3);
    var topTopics = topNames(summary.topics, 4);

    var treatmentItems = findRepresentativeItems(items, function(item) {
      return (item.drugs || []).length > 0 || hasTopic(item, 'FcRn') || hasTopic(item, '补体') || hasTopic(item, 'B细胞/免疫重置');
    }, 2);
    if (treatmentItems.length) {
      insights.push(buildInsight(
        '治疗格局',
        joinNames(topDrugs.length ? topDrugs : topTopics.slice(0, 2), '治疗机制') + ' 是本会议 MG 治疗复盘主线',
        '药物和机制类摘要集中出现，提示会后 brief 应优先比较机制、人群、终点和安全性叙事，而不是只摘录单篇结果。',
        '用于内部 congress debrief、KOL 拜访前问题准备和竞争信息追踪。',
        treatmentItems,
        topDrugs.concat(topTopics.slice(0, 2)).slice(0, 5)
      ));
    }

    var evidenceItems = findRepresentativeItems(items, function(item) {
      return item.researchType === summary.topType || (item.priorityScore || 0) >= 6;
    }, 2);
    insights.push(buildInsight(
      '证据结构',
      summary.topType + ' 是主要证据形态',
      '研究类型结构决定了这次会议内容适合形成何种医学判断：随机/对照更适合进入核心证据，真实世界和 PRO 更适合补充临床实践与患者负担。',
      '用于区分“可进入材料的证据”和“仅适合趋势观察的摘要级线索”。',
      evidenceItems,
      [summary.topType, '高优先级 ' + summary.highPriority + ' 条']
    ));

    if (summary.chinaRelated > 0) {
      var chinaItems = findRepresentativeItems(items, function(item) { return item.isChinaRelated; }, 2);
      insights.push(buildInsight(
        '中国线索',
        '中国相关摘要 ' + summary.chinaRelated + ' 条，适合会后单独追踪',
        '中国作者、机构或患者数据提示本地证据沟通和专家协作机会，但仍需要逐条核查机构、研究设计和患者来源。',
        '用于中国 KOL mapping、本地证据 gap 梳理和后续全文/会议材料追踪。',
        chinaItems,
        ['中国相关'].concat(topCountries).slice(0, 5)
      ));
    }

    var safetyItems = findRepresentativeItems(items, function(item) {
      return item.researchType === '安全性' || hasTopic(item, '安全性');
    }, 2);
    if (safetyItems.length) {
      insights.push(buildInsight(
        '安全性与用药管理',
        '安全性信号需要和疗效信号并行复盘',
        '会议摘要中安全性常以开放标签延长期、真实世界或病例形式出现，适合形成用药管理问题清单，但不宜单独作为结论。',
        '用于 MSL 准备安全性追问、患者管理讨论和后续全文核查清单。',
        safetyItems,
        ['安全性'].concat(topDrugs).slice(0, 5)
      ));
    }

    var patientItems = findRepresentativeItems(items, function(item) {
      return hasTopic(item, 'PRO/生活质量') || hasTopic(item, '数字监测');
    }, 2);
    if (patientItems.length) {
      insights.push(buildInsight(
        '患者旅程',
        'PRO、生活质量和数字监测可补足治疗结果叙事',
        '这类摘要适合解释患者负担、症状波动和治疗体验，能够把药物疗效讨论延伸到医学事务更常用的患者旅程语言。',
        '用于患者负担 slide、疾病教育和 KOL 对真实世界 unmet need 的访谈。',
        patientItems,
        ['PRO/生活质量', '数字监测']
      ));
    }

    var countryItems = findRepresentativeItems(items, function(item) {
      return (item.countries || []).some(function(country) { return topCountries.indexOf(country) !== -1; });
    }, 2);
    if (topCountries.length) {
      insights.push(buildInsight(
        'KOL/机构线索',
        joinNames(topCountries, '多国') + ' 是本会议主要投稿/机构线索',
        '国家/地区排名可作为会后 KOL mapping 的第一层入口，但作者和机构仍需在摘要详情中逐条核查。',
        '用于会后专家地图、区域证据布局和潜在合作机构筛选。',
        countryItems,
        topCountries
      ));
    }

    return insights.slice(0, 6);
  }

  function renderHighlights(module, items) {
    if (!el.highlights) return;
    var summary = summarizeModule(items);
    if (el.insightCount) {
      el.insightCount.textContent = items.length ? '基于 ' + items.length + ' 条摘要生成' : module.status;
    }
    if (!items.length) {
      el.highlights.innerHTML = '<div class="conference-empty-focus wide"><strong>' + escapeHtml(module.emptyNote || '暂无结构化摘要') + '</strong><p>当前模块先呈现入口、字段规划和监控状态；后台扫描口已保留。</p></div>';
      return;
    }
    var insights = buildConferenceInsights(module, summary, items);
    el.highlights.innerHTML = insights.map(function(insight) {
      var refs = insight.representatives.slice(0, 2);
      return '<article class="conference-highlight-card conference-insight-card">' +
        '<div class="conference-insight-top">' +
          '<span class="conference-highlight-label">' + escapeHtml(insight.dimension) + '</span>' +
          '<strong>' + escapeHtml(insight.title) + '</strong>' +
        '</div>' +
        '<p>' + escapeHtml(insight.why) + '</p>' +
        '<div class="conference-insight-use"><span>MSL 用途</span><p>' + escapeHtml(insight.mslUse) + '</p></div>' +
        '<div class="conference-insight-refs">' +
          '<span>代表摘要</span>' +
          (refs.length ? refs.map(function(item) {
            return '<a href="' + escapeHref(item.sourceUrl || item.pageUrl) + '" target="_blank" rel="noopener">' + escapeHtml(truncateText(item.title, 86)) + '</a>';
          }).join('') : '<em>暂无代表摘要，待源数据补充。</em>') +
        '</div>' +
        '<div class="conference-card-head">' + insight.tags.slice(0, 5).map(function(tag) {
          return '<span class="conference-badge">' + escapeHtml(tag) + '</span>';
        }).join('') + '</div>' +
        '<em class="conference-source-note">' + escapeHtml(getMeetingSourceLimitation(module)) + '</em>' +
      '</article>';
    }).join('');
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
        (item.topics || []).join(' '), (item.drugs || []).join(' '), (item.countries || []).join(' ')
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
    var tags = [item.researchType].concat(item.drugs || []).concat(item.topics || []).slice(0, 4);
    return '<article class="conference-result-row">' +
      '<div>' +
        '<a class="conference-card-title" href="' + escapeHref(item.sourceUrl || item.pageUrl) + '" target="_blank" rel="noopener">' + escapeHtml(item.title) + '</a>' +
        '<p>' + escapeHtml([item.conference, item.presentationType, (item.countries || []).slice(0, 4).join('、')].filter(Boolean).join(' · ')) + '</p>' +
        '<p class="conference-result-analysis">' + escapeHtml(item.analysisZh || '中文分析待生成；请展开摘要核查来源。') + '</p>' +
        '<div class="conference-abstract open" id="conference-abs-' + escapeHtml(item.id) + '">' + escapeHtml(item.abstract || '摘要正文待公开。') + '</div>' +
      '</div>' +
      '<div class="conference-result-tags">' + tags.map(function(tag) {
        return '<span class="conference-badge">' + escapeHtml(tag) + '</span>';
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
    renderRank(el.countryRank, summary.countries, 8);
    renderRank(el.typeRank, summary.types, 8);
    renderTopics(summary);
    renderBreakthroughs(module, summary, currentItems);
    renderHighlights(module, currentItems);
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
