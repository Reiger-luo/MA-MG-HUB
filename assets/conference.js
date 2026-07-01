/* MA-MG-HUB 会议资讯页面 JS */
(function() {
  'use strict';

  var payload = window.MG_CONFERENCE_DATA || {
    summary: {},
    abstracts: [],
    sourceMonitor: [],
    futureMeetings: [],
    lateBreakerSessions: []
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
      lateNote: 'MGFA 2025 公开材料未单独标注 late-breaking；本页用高优先级药物、随机试验和中国相关作为重点会话替代入口。',
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
      lateNote: 'AANEM 2025 暂不作为 late-breaking 主源；后续扫描 Muscle & Nerve supplement 与官方 guide 更新。',
      emptyNote: '已定位官方 2025 Abstracts Guide；阅读器内 myasthenia 搜索可见多个页段，下一步补抓题名、poster 编号、作者、机构和摘要正文。'
    },
    {
      id: 'aan',
      label: 'AAN',
      edition: '2026',
      title: 'AAN Annual Meeting 2026',
      subtitle: 'Mirasmart abstract website + LS1/LS2',
      meetingKeys: ['AAN 2026'],
      monitorIds: ['aan'],
      url: 'https://index.mirasmart.com/AAN2026/',
      status: '已结构化',
      statusTone: 'ready',
      intro: 'AAN 2026 适合追踪神经病学大会里的 MG 治疗进展，尤其是 FcRn、补体、CAR-T、真实世界和 seronegative gMG。',
      lateNote: 'AAN LS1/LS2 late-breaking science 已作为固定重点入口展示；MG 相关 late-breaking 摘要公开后再进入结构化池。',
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
      lateNote: 'EAN 2026 当前 abstract book 未单列 MG late-breaking；若后续官网标注 late-breaking/late abstract，将进入本区。',
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
    lateBreakers: $('conferenceLateBreakers'),
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
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function escapeHref(value, fallback) {
    var href = String(value || '').trim();
    if (/^(https?:)?\/\//i.test(href) || href.indexOf('/MA-MG-HUB/') === 0) {
      return escapeHtml(href);
    }
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
      lateBreaker: items.filter(function(item) { return item.isLateBreaker; }).length,
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
    if (module.id === 'aan') return '基于 AAN Mirasmart 摘要页和公开 late-breaking 会话入口；presentation 细节仍需会后核查。';
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
      if (module.id === 'aan') {
        takeaways.push('AAN LS1/LS2 late-breaking 会话已定位；MG 相关 late-breaking 摘要公开后应第一时间补入本模块复盘。');
      }
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

  function renderLate(module, items) {
    if (!el.lateBreakers) return;
    var sessions = module.id === 'aan' ? (payload.lateBreakerSessions || []) : [];
    var lateItems = items.filter(function(item) { return item.isLateBreaker; }).slice(0, 4);
    var html = '';

    if (sessions.length) {
      html += '<div class="conference-late-grid">' + sessions.map(function(session) {
        return '<article class="conference-late-card">' +
          '<span>AAN late-breaking</span>' +
          '<strong>' + escapeHtml(session.session) + '</strong>' +
          '<p>' + escapeHtml(session.meeting + ' · ' + session.time) + '</p>' +
          '<em>' + escapeHtml(session.status) + '</em>' +
          '<a href="' + escapeHref(session.url) + '" target="_blank" rel="noopener">查看官网会话</a>' +
        '</article>';
      }).join('') + '</div>';
    }

    if (lateItems.length) {
      html += '<div class="conference-late-grid compact">' + lateItems.map(function(item) {
        return '<article class="conference-late-card">' +
          '<span>已入库 late-breaking</span>' +
          '<strong>' + escapeHtml(item.title) + '</strong>' +
          '<p>' + escapeHtml(item.researchType + ' · ' + item.conference) + '</p>' +
          '<a href="' + escapeHref(item.sourceUrl || item.pageUrl) + '" target="_blank" rel="noopener">查看摘要</a>' +
        '</article>';
      }).join('') + '</div>';
    }

    if (!html) {
      html = '<div class="conference-empty-focus"><strong>暂无单列 late-breaking 摘要</strong><p>' + escapeHtml(module.lateNote) + '</p></div>';
    }
    el.lateBreakers.innerHTML = html;
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

    if (module.id === 'aan') {
      insights.unshift(buildInsight(
        'Late-breaking 追踪',
        'AAN LS1/LS2 已定位，MG late-breaking 需会后补扫',
        'AAN late-breaking 会话通常是会后复盘的最高优先级入口。当前先保留官网会话入口，等 MG 相关摘要公开后再纳入结构化池。',
        '用于会后第一轮 congress debrief 的待办清单和更新提醒。',
        findRepresentativeItems(items, function(item) { return (item.priorityScore || 0) >= 6; }, 2),
        ['late-breaking', 'AAN LS1/LS2']
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
      '</div>' +
      '<div class="conference-result-tags">' + tags.map(function(tag) {
        return '<span class="conference-badge">' + escapeHtml(tag) + '</span>';
      }).join('') + '</div>' +
      '<button type="button" data-conference-abstract="' + escapeHtml(item.id) + '">摘要</button>' +
      '<div class="conference-abstract" id="conference-abs-' + escapeHtml(item.id) + '">' + escapeHtml(item.abstract || '摘要正文待公开。') + '</div>' +
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
    var abstractButtons = el.results.querySelectorAll('[data-conference-abstract]');
    for (var j = 0; j < abstractButtons.length; j++) {
      abstractButtons[j].addEventListener('click', function() {
        var target = document.getElementById('conference-abs-' + this.getAttribute('data-conference-abstract'));
        if (!target) return;
        target.classList.toggle('open');
        this.textContent = target.classList.contains('open') ? '收起' : '摘要';
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
    renderLate(module, currentItems);
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
