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
      isNew: true,
      meetingKeys: ['AAN 2026'],
      monitorIds: ['aan'],
      url: 'https://index.mirasmart.com/AAN2026/',
      status: '',
      statusTone: 'ready',
      intro: 'AAN 2026 适合追踪神经病学大会里的 MG 治疗进展，尤其是 FcRn、补体、CAR-T、真实世界和 seronegative gMG。',
      breakthroughNote: '结合 AAN 2026 摘要，优先提炼会改变治疗格局、证据叙事、中国协作或患者价值沟通的突破。',
      emptyNote: ''
    },
    {
      id: 'ean',
      label: 'EAN',
      edition: '2026',
      title: 'EAN Congress 2026',
      subtitle: 'European Journal of Neurology abstract book',
      isNew: true,
      meetingKeys: ['EAN 2026'],
      monitorIds: ['ean'],
      url: 'https://www.ean.org/congress2026/abstracts/important-information/ean-2026-congress-abstract-book',
      status: '',
      statusTone: 'ready',
      intro: 'EAN 2026 以欧洲多中心数据、治疗结局和 ePoster Virtual 为主要内容。分析重点放在国家协作网络、治疗机制和公开摘要完整度。',
      breakthroughNote: '结合 EAN 摘要集的机制、长期管理、真实世界和患者价值研究，提炼可复用到医学事务工作的突破判断。',
      emptyNote: ''
    },
    {
      id: 'mgfa',
      label: 'MGFA',
      edition: '',
      title: 'MGFA',
      subtitle: '待提供数据源链接',
      meetingKeys: [],
      monitorIds: [],
      url: '',
      status: '',
      statusTone: 'watch',
      intro: 'MGFA 后台数据已清空，等待新的会议摘要链接后再接入。',
      breakthroughNote: '待提供数据源链接后，再提炼治疗机制、临床结局、患者旅程和中国机构线索。',
      emptyNote: 'MGFA 后台数据已清空；提供会议摘要链接后再重新接入。'
    },
    {
      id: 'aanem',
      label: 'AANEM',
      edition: '',
      title: 'AANEM',
      subtitle: '待提供数据源链接',
      meetingKeys: [],
      monitorIds: [],
      url: '',
      status: '',
      statusTone: 'watch',
      intro: 'AANEM 后台数据已清空，等待新的会议摘要链接后再接入。',
      breakthroughNote: '待提供数据源链接后，再提炼临床路径、诊断监测和肌病交叉管理线索。',
      emptyNote: 'AANEM 后台数据已清空；提供会议摘要链接后再重新接入。'
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
    activeFilter: $('conferenceActiveFilter'),
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

  function safeDomId(value) {
    return String(value || '').replace(/[^A-Za-z0-9_-]+/g, '-');
  }

  function findAbstractById(id) {
    if (!id) return null;
    var source = currentItems.length ? currentItems : (payload.abstracts || []);
    for (var i = 0; i < source.length; i++) {
      if (source[i].id === id) return source[i];
    }
    var all = payload.abstracts || [];
    for (var j = 0; j < all.length; j++) {
      if (all[j].id === id) return all[j];
    }
    return null;
  }

  function getLocalToken(item) {
    if (!item) return '';
    if (item.programNumber) return item.programNumber;
    var id = String(item.id || '');
    if (id.indexOf('::') !== -1) return id.split('::').pop();
    return '';
  }

  function getSourceLocator(ref) {
    var item = ref && ref.id ? (findAbstractById(ref.id) || ref) : ref;
    if (!item) return '摘要';
    var conference = item.conference || '';
    var token = getLocalToken(item);
    var page = item.page ? 'p.' + item.page : '';
    return [token, page].filter(Boolean).join(' · ') || conference || truncateText(item.title || '摘要', 36);
  }

  function getSourceHref(item) {
    if (!item) return '#';
    var url = item.sourceUrl || item.pageUrl || '#';
    if (url !== '#' && item.page && /\.pdf(\?|#|$)/i.test(url) && url.indexOf('#page=') === -1) {
      return url + '#page=' + item.page;
    }
    return url;
  }

  function getKeyMetrics(item, limit) {
    var insight = item && item.deepInsight ? item.deepInsight : {};
    var metrics = insight.keyMetrics || (item && item.keyMetrics) || [];
    return (metrics || []).filter(Boolean).slice(0, limit || 2);
  }

  function getChineseAbstract(item) {
    if (!item) return '中文摘要待生成；请回到原始摘要核查全文。';
    var insight = item && item.deepInsight ? item.deepInsight : {};
    return item.abstractZh || insight.abstractZh || '中文摘要全文翻译待生成；当前不展示自动分析，避免误认为摘要全文。';
  }

  function getEvidenceStatement(item) {
    if (!item) return '该摘要暂缺明确量化数据，需回到站内摘要或原始来源核查。';
    var insight = item && item.deepInsight ? item.deepInsight : {};
    if (insight.kolKeyMessageZh) return insight.kolKeyMessageZh;
    var metrics = getKeyMetrics(item, 2);
    if (metrics.length) return metrics.join('；');
    return insight.clinicalReadoutZh || item.analysisZh || '该摘要暂缺明确量化数据，需回到站内摘要或原始来源核查。';
  }

  function renderKolKeyMessages(refs, fallback) {
    var messages = (refs || []).slice(0, 3).map(function(item) {
      return getEvidenceStatement(item);
    }).filter(Boolean);
    if (!messages.length && fallback) messages = [fallback];
    if (!messages.length) return '<p>暂无可直接传递的量化 key message，需回到摘要核查。</p>';
    return renderKeyMessageList(messages);
  }

  function renderKeyMessageList(messages) {
    var list = (messages || []).filter(Boolean).slice(0, 3);
    if (!list.length) return '';
    return '<ul class="conference-key-message-list">' + list.map(function(message) {
      return '<li>' + escapeHtml(message) + '</li>';
    }).join('') + '</ul>';
  }

  function renderLocatorChips(refs, limit) {
    var items = (refs || []).slice(0, limit || 4);
    if (!items.length) return '<span class="conference-ref-empty">暂无定位摘要</span>';
    return items.map(function(ref) {
      var item = ref && ref.id ? (findAbstractById(ref.id) || ref) : ref;
      var id = item && item.id;
      var locator = getSourceLocator(item || ref);
      var title = item && item.title ? item.title : ref.title || '';
      if (!id) return '<span class="conference-ref-chip" title="' + escapeHtml(title) + '">' + escapeHtml(locator) + '</span>';
      return '<button type="button" class="conference-ref-chip" data-conference-focus="' + escapeHtml(id) + '" title="' + escapeHtml(title) + '">' + escapeHtml(locator) + '</button>';
    }).join('');
  }

  function getKolTier(signal) {
    return signal && signal.priorityTier ? signal.priorityTier : 'disease_progress';
  }

  function getKolTierLabel(signal) {
    if (signal && signal.priorityLabel) return signal.priorityLabel;
    var tier = getKolTier(signal);
    if (tier === 'efgar') return 'efgar重点传递';
    if (tier === 'competitor_response') return '竞品应对解读';
    return '疾病进展传递';
  }

  function getKolTierRank(signal) {
    var tier = getKolTier(signal);
    if (tier === 'efgar') return 0;
    if (tier === 'competitor_response') return 1;
    return 2;
  }

  function sortKolSignals(signals) {
    return (signals || []).slice().sort(function(a, b) {
      return getKolTierRank(a) - getKolTierRank(b) ||
        (Number(b.kolScore || 0) - Number(a.kolScore || 0)) ||
        String(a.title || '').localeCompare(String(b.title || ''), 'zh-CN');
    });
  }

  function getChapterTalkingPoints(narrative, chapter) {
    if (chapter && Array.isArray(chapter.talkingPoints) && chapter.talkingPoints.length) {
      return sortKolSignals(chapter.talkingPoints);
    }
    var id = chapter && chapter.id;
    var title = chapter && chapter.title;
    return sortKolSignals((narrative.kolFocus || []).filter(function(point) {
      return (id && point.parentSignalId === id) || (title && point.parentSignalTitle === title);
    }));
  }

  function renderScorePill(label, value) {
    if (value == null || value === '') return '';
    return '<span class="conference-score-pill">' + escapeHtml(label + ' ' + value + '/5') + '</span>';
  }

  function renderTalkingPointCard(point, index, compact) {
    var refs = point.refs || point.representatives || [];
    var messages = point.keyMessages && point.keyMessages.length ? point.keyMessages : [];
    var cls = compact ? 'conference-nested-kol-card' : 'conference-breakthrough-card';
    var tier = getKolTier(point);
    var parentHtml = !compact && point.parentSignalTitle ? '<p class="conference-kol-parent">来自线索：' + escapeHtml(point.parentSignalTitle) + '</p>' : '';
    var reasonHtml = point.whyKol ? '<p class="conference-kol-why">' + escapeHtml(point.whyKol) + '</p>' : '';
    return '<article class="' + cls + '">' +
      '<div class="conference-breakthrough-top">' +
        '<span class="conference-breakthrough-index">' + escapeHtml((compact ? '交流 ' : '优先 ') + String(index + 1).padStart(2, '0')) + '</span>' +
        '<em class="conference-kol-tier ' + escapeHtml(tier) + '">' + escapeHtml(getKolTierLabel(point)) + '</em>' +
      '</div>' +
      '<strong>' + escapeHtml(point.title || '') + '</strong>' +
      parentHtml +
      reasonHtml +
      '<div class="conference-breakthrough-analysis">' +
        '<span>传递信息</span>' +
        (messages.length ? renderKeyMessageList(messages) : renderKolKeyMessages(refs, point.conclusion)) +
      '</div>' +
      '<div class="conference-breakthrough-evidence">' +
        '<span>明确数据证据</span><div class="conference-breakthrough-anchor-row">' + renderLocatorChips(refs, 4) + '</div>' +
      '</div>' +
      (point.kolScore ? '<div class="conference-kol-score-row">' + renderScorePill('交流优先级', point.kolScore) + '</div>' : '') +
    '</article>';
  }

  function scrollToResults() {
    var target = document.querySelector('.conference-drilldown');
    if (target && target.scrollIntoView) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function renderActiveFilterSummary() {
    if (!el.activeFilter) return;
    var total = filteredItems.length;
    var start = total ? (state.page * pageSize + 1) : 0;
    var end = Math.min(total, (state.page + 1) * pageSize);
    var pageText = total ? '当前显示 ' + start + '–' + end + ' 条' : '当前无匹配摘要';
    var filters = [];
    if (state.topic) filters.push('标签：' + state.topic);
    if (state.keyword) filters.push('关键词：' + state.keyword);
    if (!filters.length) {
      el.activeFilter.innerHTML = '<span>未筛选 · 全部 <strong>' + escapeHtml(total) + '</strong> 条 · ' + escapeHtml(pageText) + '</span>';
      return;
    }
    el.activeFilter.innerHTML = '<span>' + escapeHtml(filters.join(' · ')) + ' · 命中 <strong>' + escapeHtml(total) + '</strong> 条 · ' + escapeHtml(pageText) + '</span>' +
      '<button type="button" data-conference-clear-filter="1">清除筛选</button>';
    var clear = el.activeFilter.querySelector('[data-conference-clear-filter]');
    if (clear) {
      clear.addEventListener('click', function() {
        state.topic = null;
        state.keyword = '';
        state.page = 0;
        if (el.keyword) el.keyword.value = '';
        renderTopics(summarizeModule(currentItems));
        applyFilters();
      });
    }
  }

  function getMeetingSourceLimitation(module) {
    if (module.id === 'mgfa' || module.id === 'aanem') return module.label + ' 后台数据已清空，待提供稳定会议摘要链接后再接入。';
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
      takeaways.push('本模块已接入 ' + summary.total + ' 条 MG 摘要，主导主题为 ' + summary.topTopic + '，研究类型以 ' + summary.topType + ' 为主。');
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
    var auditHtml = audit ? '<div class="conference-audit-strip">' +
      '<span><b>' + escapeHtml(audit.rawSearchResults || 0) + '</b>检索命中</span>' +
      '<span><b>' + escapeHtml(audit.curatedMgIncluded || 0) + '</b>MG 摘要</span>' +
      '<span><b>' + escapeHtml(audit.excludedByRule || 0) + '</b>规则剔除</span>' +
      '<p>' + escapeHtml(audit.exclusionPrinciple || '') + '</p>' +
    '</div>' : '';
    el.strategicNarrative.innerHTML =
      '<section class="conference-narrative-panel">' +
        '<div class="conference-narrative-head">' +
          '<span>全景剖析 · MA 工作流版本</span>' +
          '<strong>' + escapeHtml(narrative.headline || '') + '</strong>' +
          (narrative.strategicRead ? '<p>' + escapeHtml(narrative.strategicRead) + '</p>' : '') +
        '</div>' +
        '<div class="conference-depth-strip">' +
          '<span><b>' + escapeHtml(depth.abstracts || 0) + '</b>站内摘要</span>' +
          '<span><b>' + escapeHtml(depth.highPriority || 0) + '</b>重点候选</span>' +
          '<span><b>' + escapeHtml(depth.chinaRelated || 0) + '</b>中国线索</span>' +
          '<span><b>站内卡 + 来源定位</b>证据入口</span>' +
        '</div>' +
        auditHtml +
        '<div class="conference-chapter-grid">' + chapters.map(function(chapter, idx) {
          var refs = chapter.refs || [];
          var talkingPoints = getChapterTalkingPoints(narrative, chapter);
          var scoreHtml = renderScorePill('线索强度', chapter.signalScore);
          var whyHtml = chapter.whySignal ? '<div class="conference-signal-reason"><span>为什么是线索</span><p>' + escapeHtml(chapter.whySignal) + '</p></div>' : '';
          var boundaryHtml = chapter.evidenceBoundary ? '<div class="conference-signal-boundary"><span>证据边界</span><p>' + escapeHtml(chapter.evidenceBoundary) + '</p></div>' : '';
          var talkingHtml = talkingPoints.length ? '<div class="conference-signal-kol"><span>可转化 KOL 交流</span><div class="conference-nested-kol-list">' +
            talkingPoints.map(function(point, pointIndex) { return renderTalkingPointCard(point, pointIndex, true); }).join('') +
            '</div></div>' : '';
          return '<article class="conference-chapter-card">' +
            '<div class="conference-chapter-top"><div class="conference-chapter-index">' + escapeHtml('线索 ' + String(idx + 1).padStart(2, '0')) + '</div>' + scoreHtml + '</div>' +
            '<h3>' + escapeHtml(chapter.title || '') + '</h3>' +
            '<p>' + escapeHtml(chapter.takeaway || '') + '</p>' +
            whyHtml +
            boundaryHtml +
            (chapter.maUse ? '<p class="conference-signal-use">' + escapeHtml(chapter.maUse) + '</p>' : '') +
            '<div class="conference-chapter-refs"><span>证据锚点</span><div>' + renderLocatorChips(refs, 4) + '</div></div>' +
            talkingHtml +
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
      var editionHtml = module.edition ? '<em>' + escapeHtml(module.edition) + '</em>' : '';
      var newHtml = module.isNew ? '<span class="conference-new-badge" aria-label="new">NEW</span>' : '';
      return '<button type="button" class="conference-meeting-card' + (active ? ' active' : '') + '" data-conference-module="' + escapeHtml(module.id) + '" aria-pressed="' + (active ? 'true' : 'false') + '">' +
        '<strong class="conference-meeting-title">' + escapeHtml(module.label) + editionHtml + newHtml + '</strong>' +
        '<p>' + escapeHtml(module.subtitle) + '</p>' +
        '<div class="conference-meeting-metrics">' +
          '<span><b>' + escapeHtml(compactNumber(summary.total)) + '</b>摘要</span>' +
          '<span><b>' + escapeHtml(summary.countryCount || '-') + '</b>地区</span>' +
          '<span><b>' + escapeHtml(summary.chinaRelated || 0) + '</b>中国相关</span>' +
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
      { label: '摘要', value: summary.total, note: '会议源条目' },
      { label: '国家/地区', value: summary.countryCount || 0, note: '机构字段推断' },
      { label: '重点候选', value: summary.highPriority || 0, note: '规则评分，仅作入口' },
      { label: '中国相关', value: summary.chinaRelated || 0, note: '机构或地点命中' }
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
    function setFilter(value) {
      state.topic = state.topic === value ? null : value;
      state.page = 0;
      renderTopics(summarizeModule(currentItems));
      applyFilters();
      scrollToResults();
    }
    var chips = [];
    (summary.topics || []).slice(0, 8).forEach(function(topic) {
      chips.push({ kind: '主题', name: topic.name, count: topic.count });
    });
    (summary.drugs || []).slice(0, 8).forEach(function(drug) {
      chips.push({ kind: '药物', name: drug.name, count: drug.count });
    });
    if (!chips.length) {
      el.topicCloud.innerHTML = '<div class="conference-empty-line">暂无主题/药物数据</div>';
    } else {
      el.topicCloud.innerHTML = chips.map(function(chip) {
        var active = state.topic === chip.name;
        return '<button type="button" class="conference-topic-pill' + (active ? ' active' : '') + '" data-conference-topic="' + escapeHtml(chip.name) + '">' +
          '<small>' + escapeHtml(chip.kind) + '</small><span>' + escapeHtml(chip.name) + '</span><b>' + escapeHtml(chip.count) + '</b>' +
        '</button>';
      }).join('');
      var buttons = el.topicCloud.querySelectorAll('[data-conference-topic]');
      for (var i = 0; i < buttons.length; i++) {
        buttons[i].addEventListener('click', function() {
          setFilter(this.getAttribute('data-conference-topic'));
        });
      }
    }

    if (el.drugBoard) el.drugBoard.innerHTML = '';
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

    return signals;
  }

  function renderBreakthroughs(module, summary, items) {
    if (!el.breakthroughs) return;
    var conferenceName = module.meetingKeys[0];
    var narrative = conferenceName && payload.meetingNarratives ? payload.meetingNarratives[conferenceName] : null;
    var signals = narrative && Array.isArray(narrative.kolFocus) && narrative.kolFocus.length ? sortKolSignals(narrative.kolFocus) : buildBreakthroughSignals(module, summary, items);
    if (!signals.length) {
      el.breakthroughs.innerHTML = '<div class="conference-empty-focus"><strong>KOL 交流重点待提炼</strong><p>' + escapeHtml(module.breakthroughNote || '当前先保留会议入口与摘要源状态，待摘要接入后再提炼可向 KOL 传递的摘要与关键数据。') + '</p></div>';
      return;
    }
    el.breakthroughs.innerHTML = '<div class="conference-priority-rule">' +
      '<span>排序原则</span><strong>efgar数据优先 → 竞品应对解读 → 重要疾病进展</strong>' +
    '</div>' +
    '<div class="conference-breakthrough-grid">' + signals.map(function(signal, index) {
      return renderTalkingPointCard(signal, index, false);
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
    if (state.topic && (item.topics || []).indexOf(state.topic) === -1 && (item.drugs || []).indexOf(state.topic) === -1) return false;
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
    renderActiveFilterSummary();
  }

  function renderResults() {
    if (!el.results) return;
    if (el.resultCount) el.resultCount.textContent = filteredItems.length + ' 条';
    if (!currentItems.length) {
      el.results.innerHTML = '<div class="conference-empty-line">该会议暂未接入摘要，先看上方接口状态。</div>';
      return;
    }
    if (!filteredItems.length) {
      el.results.innerHTML = '<div class="conference-empty-line">暂无匹配摘要，调整关键词、国家或研究类型。</div>';
      return;
    }
    var totalPages = Math.ceil(filteredItems.length / pageSize);
    if (state.page >= totalPages) state.page = Math.max(0, totalPages - 1);
    var pageItems = filteredItems.slice(state.page * pageSize, state.page * pageSize + pageSize);
    if (el.resultCount) {
      var start = state.page * pageSize + 1;
      var end = Math.min(filteredItems.length, (state.page + 1) * pageSize);
      el.resultCount.textContent = filteredItems.length + ' 条 · 显示 ' + start + '–' + end;
    }
    el.results.innerHTML = '<div class="conference-result-table">' + pageItems.map(renderResultRow).join('') + '</div>' + renderPagination(totalPages);
    bindResultActions();
  }

  function renderResultRow(item) {
    var locator = getSourceLocator(item);
    var countries = (item.countries || []).filter(function(country) { return country && country !== '未识别'; }).slice(0, 4).join('、') || '国家/地区未识别';
    return '<article class="conference-result-row conference-result-row-compact" id="conference-item-' + escapeHtml(safeDomId(item.id)) + '" data-conference-item-id="' + escapeHtml(item.id || '') + '">' +
      '<strong class="conference-card-title">' + escapeHtml(item.title) + '</strong>' +
      '<p>' + escapeHtml([locator, countries].filter(Boolean).join(' · ')) + '</p>' +
      '<details class="conference-evidence-detail">' +
        '<summary>点击展开中文摘要</summary>' +
        '<div class="conference-abstract open" id="conference-abs-' + escapeHtml(item.id) + '">' + escapeHtml(getChineseAbstract(item)) + '</div>' +
      '</details>' +
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
        renderActiveFilterSummary();
      });
    }
  }

  function focusAbstract(itemId) {
    if (!itemId || !findAbstractById(itemId)) return;
    state.keyword = '';
    state.researchType = 'all';
    state.country = 'all';
    state.chinaOnly = false;
    state.topic = null;
    state.page = 0;
    if (el.keyword) el.keyword.value = '';
    if (el.chinaOnly) el.chinaOnly.checked = false;
    updateFilters(currentItems);
    renderTopics(summarizeModule(currentItems));
    filteredItems = currentItems.filter(itemMatches).sort(function(a, b) {
      return (b.priorityScore || 0) - (a.priorityScore || 0) || String(a.title || '').localeCompare(String(b.title || ''));
    });
    var index = filteredItems.findIndex(function(item) { return item.id === itemId; });
    if (index >= 0) state.page = Math.floor(index / pageSize);
    renderResults();
    renderActiveFilterSummary();
    window.setTimeout(function() {
      var row = document.getElementById('conference-item-' + safeDomId(itemId));
      if (!row) return;
      row.classList.add('is-focused');
      if (row.scrollIntoView) row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      window.setTimeout(function() { row.classList.remove('is-focused'); }, 1800);
    }, 50);
  }

  function bindFocusLinks() {
    var root = $('tab-conference');
    if (!root) return;
    root.addEventListener('click', function(event) {
      var target = event.target.closest && event.target.closest('[data-conference-focus]');
      if (!target) return;
      event.preventDefault();
      focusAbstract(target.getAttribute('data-conference-focus'));
    });
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
    if (!items.length) {
      el.sourceMonitor.innerHTML = '<div class="conference-empty-line">待提供会议摘要数据源链接。</div>';
      return;
    }
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
    if (el.moduleEyebrow) el.moduleEyebrow.textContent = [module.label, module.edition].filter(Boolean).join(' · ');
    if (el.moduleTitle) el.moduleTitle.textContent = module.title;
    if (el.moduleIntro) el.moduleIntro.textContent = module.intro;
    if (el.moduleLink) {
      if (module.url) {
        el.moduleLink.href = module.url;
        el.moduleLink.style.display = '';
      } else {
        el.moduleLink.href = '#';
        el.moduleLink.style.display = 'none';
      }
    }

    renderMeetingCards();
    renderKpis(module, summary);
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
    bindFocusLinks();
    render();
  }

  init();
})();
