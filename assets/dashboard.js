/* MA-MG-HUB 首页行动工作台 */
(function() {
  'use strict';

  var hub = window.MgHub || {};
  var data = window.MG_DASHBOARD_DATA || {
    stats: {},
    stat_cards: [],
    sections: [],
    signal_summary: null,
    top_signals: []
  };
  var communityWeeklyData = window.MG_COMMUNITY_WEEKLY || { communities: [], hot_communities: [] };
  var expertData = window.MG_EXPERT_PROFILES || { summary: {} };
  var clinicalTrialsData = window.MG_CLINICAL_TRIALS_SUMMARY || {
    meta: {},
    source_counts: [],
    decision_signals: []
  };
  var pipelineData = window.MG_PIPELINE_STATUS || { storage: {} };
  var releaseData = window.MG_RELEASE_MANIFEST || {};
  var literatureArticles = window.MG_LITERATURE_DATA || [];
  var signalItems = [];
  var signalFilter = 'all';
  var signalSummaryFilterBound = false;
  var articleSignalStrengthByPmid = {};
  var signalDeepLinkHandled = false;

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

  function safeClass(value, fallback) {
    if (hub.safeClassToken) return hub.safeClassToken(value, fallback || 'default');
    return String(value || fallback || 'default').replace(/[^a-zA-Z0-9_-]+/g, '-');
  }

  function pageUrl(path) {
    return hub.pageUrl ? hub.pageUrl(path) : path;
  }

  function numberValue(value, fallback) {
    var parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : Number(fallback || 0);
  }

  function formatNumber(value) {
    return new Intl.NumberFormat('zh-CN').format(numberValue(value, 0));
  }

  function formatDateTime(value) {
    if (!value) return '时间待确认';
    var normalized = String(value).indexOf('T') === -1 ? String(value).replace(' ', 'T') : String(value);
    var parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    }).format(parsed);
  }

  function findStatCard(label) {
    return (data.stat_cards || []).find(function(card) { return card.label === label; }) || {};
  }

  function signalStrengthClass(value) {
    return ({ '强': 'strong', '中': 'medium', '弱': 'weak' })[value] || 'weak';
  }

  function signalDetailUrl(signal) {
    var path = 'pages/literature.html?tab=literature';
    if (signal && signal.id) path += '&signal=' + encodeURIComponent(signal.id);
    return pageUrl(path);
  }

  function renderReleaseStatus() {
    var target = document.getElementById('dashboardReleaseStatus');
    if (!target) return;
    var storage = pipelineData.storage || {};
    var releaseStatus = releaseData.pipeline_status || '';
    var releaseOk = releaseStatus === 'success' || releaseStatus === 'success_with_warnings';
    var releaseLabel = releaseStatus === 'success_with_warnings' ? '完整发布有提示' :
      releaseOk ? '完整发布成功' : '等待完整发布证明';
    var releaseClass = releaseStatus === 'success' ? 'ok' : 'warn';
    var releasedAt = releaseData.released_at || data.generated_at || '';
    var publicCount = storage.public_rolling_count != null ?
      storage.public_rolling_count : (data.stats || {}).recent_articles;
    var fullCount = storage.semantic_full_count != null ?
      storage.semantic_full_count : (data.stats || {}).total_articles;

    target.innerHTML =
      '<span class="dashboard-release-state ' + releaseClass + '">' +
        '<i aria-hidden="true"></i>' + escapeHtml(releaseLabel) +
      '</span>' +
      '<span class="dashboard-release-chip">公开滚动 <strong>' + escapeHtml(formatNumber(publicCount)) + '</strong></span>' +
      '<span class="dashboard-release-chip">语义底座 <strong>' + escapeHtml(formatNumber(fullCount)) + '</strong></span>' +
      '<span class="dashboard-release-chip">完整发布 <time datetime="' + escapeHtml(releasedAt) + '">' +
        escapeHtml(formatDateTime(releasedAt)) +
      '</time></span>';
  }

  function renderStats() {
    var target = document.getElementById('dashboardStats');
    if (!target) return;
    var stats = data.stats || {};
    var signalSummary = data.signal_summary || {};
    var strengthCounts = signalSummary.strength_counts || {};
    var trialMeta = clinicalTrialsData.meta || {};
    var expertSummary = expertData.summary || {};
    var chinaStat = findStatCard('中国证据');
    var cards = [
      {
        label: '强信号',
        value: strengthCounts.strong || 0,
        note: formatNumber(signalSummary.total_count || stats.signals || 0) + ' 条聚合信号',
        href: 'pages/literature.html?tab=literature',
        tone: 'urgent'
      },
      {
        label: '近一年中国证据',
        value: stats.china_articles || 0,
        note: chinaStat.note || 'MG-core 公开滚动层',
        href: 'pages/literature.html?tab=china',
        tone: 'china'
      },
      {
        label: '招募中试验',
        value: clinicalTrialsData.recruiting_count || 0,
        note: formatNumber(trialMeta.total_count || 0) + ' 条 · 3 个注册源',
        href: 'pages/literature.html?tab=trials',
        tone: 'trial'
      },
      {
        label: '中国作者索引',
        value: expertSummary.indexed_china_experts || 0,
        note: 'China-only MSL 索引',
        href: 'pages/msl.html',
        tone: 'msl'
      }
    ];

    target.innerHTML = cards.map(function(card) {
      return '<a class="dashboard-kpi-card ' + safeClass(card.tone) + '" href="' + escapeHref(card.href) + '">' +
        '<span>' + escapeHtml(card.label) + '</span>' +
        '<strong>' + escapeHtml(formatNumber(card.value)) + '</strong>' +
        '<em>' + escapeHtml(card.note) + '</em>' +
      '</a>';
    }).join('');
  }

  function parseDate(value) {
    if (!value) return null;
    var normalized = String(value).indexOf('T') === -1 ? String(value).replace(' ', 'T') : String(value);
    var parsed = new Date(normalized);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function normalizePmid(value) {
    return String(value == null ? '' : value).trim();
  }

  function signalStrengthRank(strength) {
    return { '强': 3, '中': 2, '弱': 1 }[strength || ''] || 0;
  }

  function compareSignals(a, b) {
    var strengthDiff = signalStrengthRank(b.strength) - signalStrengthRank(a.strength);
    if (strengthDiff !== 0) return strengthDiff;
    if (b.score !== a.score) return b.score - a.score;
    return (b.date || 0) - (a.date || 0);
  }

  function buildSignals() {
    var sourceSignals = window.MG_SIGNALS_DATA && Array.isArray(window.MG_SIGNALS_DATA.signals) ?
      window.MG_SIGNALS_DATA.signals : [];
    signalItems = sourceSignals.map(function(signal) {
      return {
        id: signal.id || '',
        article: signal.article || {},
        date: parseDate(signal.date || (signal.article && signal.article.entry_date)),
        type: signal.type || '新证据',
        title: signal.title || signal.summary || (signal.article && signal.article.title) || '',
        summary: signal.summary || signal.title || '',
        strength: signal.strength || '弱',
        topics: signal.keywords || [],
        drugs: signal.drugs || [],
        score: signal.score || 0,
        age: 0,
        article_count: signal.article_count || (signal.related_pmids || []).length || 1,
        date_range: signal.date_range || null,
        china_related: Boolean(signal.china_related || (signal.article && signal.article.china_related)),
        related_pmids: signal.related_pmids || [],
        refs: signal.refs || [],
        evidenceItems: signal.evidenceItems || [],
        takeaway: signal.takeaway || '',
        whySignal: signal.whySignal || '',
        evidenceBoundary: signal.evidenceBoundary || '',
        gapBefore: signal.gapBefore || '',
        gapFilled: signal.gapFilled || '',
        remainingGap: signal.remainingGap || '',
        maUse: signal.maUse || '',
        talkingPoints: signal.talkingPoints || signal.kolFocus || [],
        signal_to_kol: signal.signal_to_kol || null,
        kol_leads: signal.kol_leads || [],
        institution_leads: signal.institution_leads || [],
        medical_affairs: signal.medical_affairs || {},
        medical_affairs_implication: signal.medical_affairs_implication ||
          (signal.medical_affairs && signal.medical_affairs.implication) || ''
      };
    });
    signalItems.sort(compareSignals);
  }

  function rebuildArticleSignalStrengthIndex() {
    articleSignalStrengthByPmid = {};
    for (var i = 0; i < literatureArticles.length; i++) {
      var article = literatureArticles[i] || {};
      var articlePmid = normalizePmid(article.pmid);
      var articleStrength = article.signal_strength || '';
      if (articlePmid && ['强', '中', '弱'].indexOf(articleStrength) !== -1) {
        articleSignalStrengthByPmid[articlePmid] = articleStrength;
      }
    }
    for (var signalIndex = 0; signalIndex < signalItems.length; signalIndex++) {
      var item = signalItems[signalIndex];
      var pmids = (item.related_pmids || []).slice();
      if (item.article && item.article.pmid) pmids.push(item.article.pmid);
      for (var refIndex = 0; refIndex < (item.refs || []).length; refIndex++) {
        if (item.refs[refIndex] && item.refs[refIndex].pmid) pmids.push(item.refs[refIndex].pmid);
      }
      for (var evidenceIndex = 0; evidenceIndex < (item.evidenceItems || []).length; evidenceIndex++) {
        if (item.evidenceItems[evidenceIndex] && item.evidenceItems[evidenceIndex].pmid) {
          pmids.push(item.evidenceItems[evidenceIndex].pmid);
        }
      }
      for (var pmidIndex = 0; pmidIndex < pmids.length; pmidIndex++) {
        var pmid = normalizePmid(pmids[pmidIndex]);
        if (!pmid) continue;
        if (articleSignalStrengthByPmid[pmid]) continue;
        var previous = articleSignalStrengthByPmid[pmid] || '';
        if (signalStrengthRank(item.strength) > signalStrengthRank(previous)) {
          articleSignalStrengthByPmid[pmid] = item.strength;
        }
      }
    }
  }

  function getFilteredSignalItems() {
    return signalItems.filter(function(item) {
      return signalFilter === 'all' || item.strength === signalFilter;
    });
  }

  function uniqueSignalPmids(item) {
    var pmids = [];
    var seen = {};
    var candidates = (item.related_pmids || []).slice();
    if (item.article && item.article.pmid) candidates.push(item.article.pmid);
    (item.refs || []).forEach(function(ref) { if (ref && ref.pmid) candidates.push(ref.pmid); });
    (item.evidenceItems || []).forEach(function(evidence) { if (evidence && evidence.pmid) candidates.push(evidence.pmid); });
    candidates.forEach(function(value) {
      var pmid = normalizePmid(value);
      if (!pmid || seen[pmid]) return;
      seen[pmid] = true;
      pmids.push(pmid);
    });
    return pmids;
  }

  function stripPmidMentions(value) {
    var pmidWord = 'P' + 'MID';
    var pmidPattern = new RegExp(pmidWord + 's?\\s*\\d{6,9}(?:\\s*[、,，/]\\s*(?:' + pmidWord + 's?\\s*)?\\d{6,9})*', 'gi');
    return String(value || '')
      .replace(pmidPattern, '')
      .replace(/（\s*）|\(\s*\)/g, '')
      .replace(/\s+([，。；：])/g, '$1')
      .replace(/^[：:、，,；;\s]+|[：:、，,；;\s]+$/g, '')
      .replace(/\s{2,}/g, ' ')
      .trim();
  }

  function getRequestedSignalId() {
    var params = new URLSearchParams(window.location.search || '');
    return String(params.get('signal') || '');
  }

  function focusDeepLinkedSignal() {
    if (signalDeepLinkHandled) return;
    var requestedSignal = getRequestedSignalId();
    if (!requestedSignal) return;
    var target = document.getElementById('signal-' + safeClass(requestedSignal, 'signal'));
    if (!target) return;
    signalDeepLinkHandled = true;
    target.classList.add('is-targeted');
    window.requestAnimationFrame(function() {
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: 'start' });
    });
  }

  function renderSignalSummary() {
    var target = document.getElementById('signalSummary');
    if (!target) return;
    var counts = { all: signalItems.length, '强': 0, '中': 0, '弱': 0 };
    for (var i = 0; i < signalItems.length; i++) {
      var signal = signalItems[i];
      if (counts[signal.strength] != null) counts[signal.strength]++;
    }
    target.innerHTML = [
      { label: '全部', count: counts.all, filter: 'all', tone: '' },
      { label: '强', count: counts['强'], filter: '强', tone: 'strong' },
      { label: '中', count: counts['中'], filter: '中', tone: 'medium' },
      { label: '弱', count: counts['弱'], filter: '弱', tone: 'weak' }
    ].map(function(card) {
      var isActive = signalFilter === card.filter;
      return '<button type="button" class="signal-stat-card' + (card.tone ? ' ' + card.tone : '') + '" ' +
        'data-signal-filter="' + escapeHtml(card.filter) + '" aria-pressed="' + (isActive ? 'true' : 'false') + '">' +
        '<span>' + escapeHtml(card.label) + '</span>' +
        '<strong>' + escapeHtml(formatNumber(card.count)) + '</strong>' +
        '<em>' + escapeHtml(isActive ? '筛选中' : '点击筛选') + '</em>' +
      '</button>';
    }).join('');

    if (!signalSummaryFilterBound) {
      target.addEventListener('click', function(event) {
        var button = event.target;
        while (button && button !== target && button.tagName !== 'BUTTON') {
          button = button.parentNode;
        }
        if (!button || button === target) return;
        var nextFilter = button.getAttribute('data-signal-filter') || 'all';
        if (nextFilter === 'all') {
          signalFilter = 'all';
        } else {
          signalFilter = signalFilter === nextFilter ? 'all' : nextFilter;
        }
        renderSignalBoard();
      });
      signalSummaryFilterBound = true;
    }
  }

  function renderSignalStrengthLegend() {
    var target = document.getElementById('signalStrengthLegend');
    if (!target) return;
    var legendItems = [
      {
        tone: 'strong',
        label: '强信号',
        detail: 'I/II 级，或 IF ≥ 10 且不是 V 级机制推理。'
      },
      {
        tone: 'medium',
        label: '中信号',
        detail: 'IF ≥ 5、III/IV 级、中国相关，或未达到强信号标准的 efgartigimod（艾加莫德）相关内容。'
      },
      {
        tone: 'weak',
        label: '弱信号',
        detail: '其余达到入选门槛的线索。'
      }
    ];
    target.innerHTML = legendItems.map(function(item) {
      return '<span class="signal-legend-item ' + escapeHtml(item.tone) + '">' +
        '<i aria-hidden="true"></i>' +
        '<strong>' + escapeHtml(item.label) + '</strong>' +
        escapeHtml(item.detail) +
      '</span>';
    }).join('');
  }

  function renderSignalEvidence(item, renderedPmids) {
    var refs = item.refs || [];
    var refsByPmid = {};
    refs.forEach(function(ref) {
      if (ref && ref.pmid) refsByPmid[String(ref.pmid)] = ref;
    });
    var evidenceItems = [];
    var evidenceByPmid = {};
    (item.evidenceItems || []).forEach(function(evidence) {
      var pmid = evidence && evidence.pmid ? String(evidence.pmid) : '';
      if (!pmid || evidenceByPmid[pmid]) return;
      evidenceByPmid[pmid] = evidence;
      evidenceItems.push(evidence);
    });
    refs.forEach(function(ref) {
      var pmid = ref && ref.pmid ? String(ref.pmid) : '';
      if (!pmid || evidenceByPmid[pmid]) return;
      var fallback = {
        pmid: pmid,
        finding: ref.key_evidence || '',
        gapContribution: '',
        boundary: ''
      };
      evidenceByPmid[pmid] = fallback;
      evidenceItems.push(fallback);
    });
    if (!evidenceItems.length) return '';

    var pmidLabel = 'P' + 'MID';
    var rows = evidenceItems.map(function(evidence) {
      var pmid = String(evidence.pmid || '');
      if (!pmid || renderedPmids[pmid]) return '';
      renderedPmids[pmid] = true;
      var ref = refsByPmid[pmid] || {};
      var href = ref.url || evidence.url || '';
      var pmidHtml = href
        ? '<a class="literature-signal-ref" href="' + escapeHref(href) + '" target="_blank" rel="noopener">' + escapeHtml(pmidLabel + ' ' + pmid) + '</a>'
        : '<span class="literature-signal-ref">' + escapeHtml(pmidLabel + ' ' + pmid) + '</span>';
      var design = (ref.study_types || evidence.studyTypes || []).slice(0, 2).join(' / ');
      var articleStrength = articleSignalStrengthByPmid[pmid] || '';
      var meta = [ref.evidence_level ? '证据 ' + ref.evidence_level : '', design,
        articleStrength ? '文献级 ' + articleStrength : ''
      ].filter(Boolean).map(function(value) {
        return '<span>' + escapeHtml(value) + '</span>';
      }).join('');
      var finding = stripPmidMentions(evidence.finding || evidence.keyFinding || ref.key_evidence || '摘要结果待补充，需阅读全文核查。');
      var contribution = stripPmidMentions(evidence.gapContribution || evidence.contribution || '为该信号补充了一项可追溯的摘要级研究结果。');
      var boundary = stripPmidMentions(evidence.boundary || evidence.limit || '研究设计与外推范围需结合全文核查。');
      var evidenceTitle = stripPmidMentions(evidence.title || ref.title || '研究证据');
      return '<article class="literature-evidence-item">' +
        '<div class="literature-evidence-head"><div>' + pmidHtml + meta + '</div></div>' +
        (evidenceTitle ? '<h4>' + escapeHtml(evidenceTitle) + '</h4>' : '') +
        '<div class="literature-evidence-result"><span>研究结果</span><p>' + escapeHtml(finding) + '</p></div>' +
        '<div class="literature-evidence-gap"><span>这篇补了什么 gap</span><p>' + escapeHtml(contribution) + '</p></div>' +
        '<p class="literature-evidence-boundary"><strong>边界</strong> · ' + escapeHtml(boundary) + '</p>' +
      '</article>';
    }).join('');
    return rows ? '<section class="literature-evidence-ledger"><div class="literature-signal-section-title">证据怎么支持</div>' + rows + '</section>' : '';
  }

  function renderLiteratureTalkingPoints(item) {
    var points = item.talkingPoints || item.kolFocus || [];
    if (!item.takeaway && !item.whySignal && !item.evidenceBoundary && !points.length && !(item.refs || []).length) return '';
    var renderedPmids = {};
    var pointHtml = points.slice(0, 4).map(function(point, index) {
      var tier = point.priorityTier || 'disease_progress';
      var tierLabel = point.priorityLabel || (tier === 'efgar' ? 'efgar重点传递' : tier === 'competitor_response' ? '竞品应对解读' : '疾病进展传递');
      var seenMessages = {};
      var messages = (point.keyMessages || []).map(function(message) {
        var cleanMessage = stripPmidMentions(message);
        if (!cleanMessage || seenMessages[cleanMessage]) return '';
        seenMessages[cleanMessage] = true;
        return '<li>' + escapeHtml(cleanMessage) + '</li>';
      }).join('');
      return '<article class="literature-signal-point">' +
        '<div class="literature-signal-point-head"><span>' + escapeHtml(point.dimension || ('交流 ' + String(index + 1).padStart(2, '0'))) + '</span><em class="literature-signal-tier ' + escapeHtml(tier) + '">' + escapeHtml(tierLabel) + '</em></div>' +
        '<strong>' + escapeHtml(stripPmidMentions(point.title || '')) + '</strong>' +
        (point.whyKol ? '<p class="literature-signal-why">' + escapeHtml(stripPmidMentions(point.whyKol)) + '</p>' : '') +
        (messages ? '<ul>' + messages + '</ul>' : '') +
      '</article>';
    }).join('');
    var gapBefore = stripPmidMentions(item.gapBefore || '');
    var gapFilled = stripPmidMentions(item.gapFilled || item.whySignal || '');
    var remainingGap = stripPmidMentions(item.remainingGap || item.evidenceBoundary || '');
    var gapHtml = [
      gapBefore ? '<div><span>原有 gap</span><p>' + escapeHtml(gapBefore) + '</p></div>' : '',
      gapFilled ? '<div class="filled"><span>本期补充</span><p>' + escapeHtml(gapFilled) + '</p></div>' : '',
      remainingGap ? '<div><span>仍待回答</span><p>' + escapeHtml(remainingGap) + '</p></div>' : ''
    ].join('');
    var ma = item.medical_affairs || {};
    var kolQuestion = stripPmidMentions(ma.suggested_kol_question || '');
    var mslAction = stripPmidMentions(ma.msl_action || '');
    var evidenceHtml = renderSignalEvidence(item, renderedPmids);
    return '<div class="literature-signal-narrative">' +
      '<section class="literature-signal-change"><div class="literature-signal-section-title">信号是什么</div>' +
        (item.takeaway ? '<p class="literature-signal-takeaway">' + escapeHtml(stripPmidMentions(item.takeaway)) + '</p>' : '') +
      '</section>' +
      (gapHtml ? '<section class="literature-signal-gap-grid"><div class="literature-signal-section-title">为什么构成信号</div>' + gapHtml + '</section>' : '') +
      evidenceHtml +
      (pointHtml ? '<section class="literature-signal-points"><div class="literature-signal-section-title">KOL 交流要点</div>' + pointHtml +
        (kolQuestion ? '<div class="literature-kol-question"><span>建议追问</span><p>' + escapeHtml(kolQuestion) + '</p></div>' : '') +
        (mslAction ? '<p class="literature-msl-action"><strong>会前动作</strong> · ' + escapeHtml(mslAction) + '</p>' : '') +
      '</section>' : '') +
    '</div>';
  }

  function renderSignalToKol(item) {
    if ((item.talkingPoints || item.kolFocus || []).length) return '';
    var leads = item.kol_leads || [];
    var institutions = item.institution_leads || [];
    var ma = item.medical_affairs || {};
    var implication = item.medical_affairs_implication || ma.implication || '';
    if (!item.signal_to_kol && !leads.length && !institutions.length && !implication) return '';
    var leadHtml = leads.slice(0, 2).map(function(lead) {
      var roles = (lead.roles || []).join('/');
      var meta = [roles, lead.institution, lead.country || lead.region].filter(Boolean).join(' · ');
      return '<span class="signal-kol-chip"><strong>' + escapeHtml(lead.name || 'Unknown KOL') + '</strong><em>' + escapeHtml(meta) + '</em></span>';
    }).join('');
    var institutionHtml = institutions.slice(0, 2).map(function(inst) {
      var meta = [inst.country || inst.region, (inst.article_author_count ? inst.article_author_count + ' authors' : '')].filter(Boolean).join(' · ');
      return '<span class="signal-kol-chip institution"><strong>' + escapeHtml(inst.name || 'Unknown institution') + '</strong><em>' + escapeHtml(meta) + '</em></span>';
    }).join('');
    var actionHtml = ma.msl_action ? '<p><strong>MSL action</strong>：' + escapeHtml(ma.msl_action) + '</p>' : '';
    var questionHtml = ma.suggested_kol_question ? '<p><strong>KOL question</strong>：' + escapeHtml(ma.suggested_kol_question) + '</p>' : '';
    return '<div class="signal-kol-bridge">' +
      '<div class="signal-kol-kicker">Signal → KOL</div>' +
      (implication ? '<p>' + escapeHtml(implication) + '</p>' : '') +
      (leadHtml ? '<div class="signal-kol-row">' + leadHtml + '</div>' : '') +
      (institutionHtml ? '<div class="signal-kol-row institutions">' + institutionHtml + '</div>' : '') +
      actionHtml + questionHtml +
    '</div>';
  }

  function renderSignalCard(item) {
    var a = item.article || {};
    var signalId = item.id || (a.pmid ? 'pmid-' + a.pmid : '');
    var signalAnchor = 'signal-' + safeClass(signalId || item.title || item.summary || 'item');
    var signalClass = ['signal', 'card'].join('-');
    var signalHeadClass = signalClass + '-head';
    var signalTitleClass = 'signal-title';
    var signalMetaClass = 'signal-meta';
    var signalTopicRowClass = 'signal-topic-row';
    var signalTitle = stripPmidMentions(item.title || item.summary || a.title || '(无标题)');
    var dateStr = item.date ? item.date.toLocaleDateString('zh-CN') : (a.pub_date || '');
    var topics = item.topics || [];
    var drugs = item.drugs || [];
    var topicHtml = '';
    for (var i = 0; i < topics.length; i++) {
      topicHtml += '<span class="signal-topic">' + escapeHtml(topics[i]) + '</span>';
    }
    var drugHtml = '';
    for (var d = 0; d < drugs.length; d++) {
      drugHtml += '<span class="signal-drug">' + escapeHtml(drugs[d]) + '</span>';
    }
    var tagHtml = topicHtml + drugHtml + (item.china_related ? '<span class="signal-topic china">中国相关</span>' : '');
    var kolHtml = renderSignalToKol(item);
    var narrativeHtml = renderLiteratureTalkingPoints(item);
    var meta = escapeHtml(formatNumber(item.article_count || 0) + ' 篇文献 · ' + (item.date_range ? item.date_range.from + '–' + item.date_range.to : dateStr));
    return '' +
      '<article id="' + escapeHtml(signalAnchor) + '" data-signal-id="' + escapeHtml(signalId) +
        '" class="' + signalClass + ' signal-' + escapeHtml(item.strength) + '" tabindex="-1">' +
        '<div class="' + signalHeadClass + '">' +
          '<span class="signal-strength">' + escapeHtml(item.strength) + '信号</span>' +
          '<span class="signal-type">' + escapeHtml(item.type) + '</span>' +
        '</div>' +
        '<h3 class="' + signalTitleClass + '">' + escapeHtml(signalTitle) + '</h3>' +
        '<div class="' + signalMetaClass + '">' + meta + '</div>' +
        narrativeHtml +
        kolHtml +
        '<div class="' + signalTopicRowClass + '">' + tagHtml + '</div>' +
        '<div class="dashboard-priority-actions">' +
          '<a class="text-link" href="' + escapeHref(signalDetailUrl(item)) + '">查看文献</a>' +
          '<a class="text-link" href="' + escapeHref(pageUrl('pages/msl.html')) + '">准备 KOL 讨论</a>' +
        '</div>' +
      '</article>';
  }

  function renderSignals() {
    var target = document.getElementById('signalList');
    if (!target) return;
    var filtered = getFilteredSignalItems().slice();
    if (!filtered.length) {
      target.innerHTML = '<div class="empty-state small"><h3>本周暂无信号</h3><p>切换筛选条件或等待下一轮数据更新</p></div>';
      return;
    }

    var requestedSignal = getRequestedSignalId();
    if (!signalDeepLinkHandled && requestedSignal) {
      for (var i = 0; i < signalItems.length; i++) {
        if (String(signalItems[i].id || '') !== requestedSignal) continue;
        var requestedIndex = filtered.indexOf(signalItems[i]);
        if (requestedIndex > 0) {
          filtered.splice(requestedIndex, 1);
          filtered.unshift(signalItems[i]);
        } else if (requestedIndex === -1) {
          filtered.unshift(signalItems[i]);
        }
        break;
      }
    }

    target.innerHTML = filtered.map(function(item) {
      return renderSignalCard(item);
    }).join('');
    focusDeepLinkedSignal();
  }

  function renderSignalBoard() {
    if (!document.getElementById('signalSummary') || !document.getElementById('signalList')) return;
    renderSignalSummary();
    renderSignalStrengthLegend();
    renderSignals();
  }

  function initSignalBoard() {
    buildSignals();
    rebuildArticleSignalStrengthIndex();
    renderSignalBoard();
  }

  function renderPrioritySignalsLegacy() {
    var target = document.getElementById('dashboardSignals');
    if (!target) return;
    var signals = Array.isArray(data.top_signals) ? data.top_signals.slice() : [];
    signals.sort(function(a, b) {
      var rank = { '强': 0, '中': 1, '弱': 2 };
      return (rank[a.strength] == null ? 3 : rank[a.strength]) -
        (rank[b.strength] == null ? 3 : rank[b.strength]);
    });
    signals = signals.slice(0, 3);
    if (!signals.length) {
      target.innerHTML = '<div class="empty-state small"><h3>暂无近期信号</h3><p>请前往数据状态检查最新构建。</p></div>';
      return;
    }

    target.innerHTML = '<div class="dashboard-priority-list">' + signals.map(function(signal) {
      var medicalAffairs = signal.medical_affairs || {};
      var implication = medicalAffairs.implication || signal.medical_affairs_implication ||
        signal.takeaway || signal.summary || '等待补充医学事务解读。';
      var evidenceContext = medicalAffairs.evidence_context || '';
      var refCount = (signal.refs || signal.evidenceItems || []).length || signal.article_count || 0;
      var strengthClass = signalStrengthClass(signal.strength);
      var detailHref = signalDetailUrl(signal);
      return '<article class="dashboard-priority-card ' + strengthClass + '">' +
        '<div class="dashboard-priority-card-head">' +
          '<span class="dashboard-signal-badge ' + strengthClass + '">' + escapeHtml(signal.strength || '待判定') + '信号</span>' +
          '<span class="dashboard-priority-meta">' + escapeHtml(signal.type || '近期证据') + ' · ' +
            escapeHtml(formatNumber(refCount)) + ' 篇</span>' +
        '</div>' +
        '<a class="dashboard-priority-link" href="' + escapeHref(detailHref) + '">' +
          '<h3>' + escapeHtml(signal.title || '未命名信号') + '</h3>' +
          '<p>' + escapeHtml(implication) + '</p>' +
          (evidenceContext ? '<small>' + escapeHtml(evidenceContext) + '</small>' : '') +
        '</a>' +
        '<div class="dashboard-priority-actions">' +
          '<a href="' + escapeHref(detailHref) + '">查看详细信号</a>' +
          '<a href="' + escapeHref('pages/msl.html') + '">准备 KOL 讨论</a>' +
        '</div>' +
      '</article>';
    }).join('') + '</div>';
  }
  function renderTrialChangeRow(item, dotClass, detailText) {
    var changeItem = item || {};
    var registryId = String(changeItem.registry_id || '');
    var title = String(changeItem.title || changeItem.registry_id || '(无标题)');
    var url = String(changeItem.url || (registryId ? 'https://clinicaltrials.gov/study/' + registryId : '#'));
    var drugName = String(changeItem.drug_name || '');
    var phaseLabel = String(changeItem.phase_label || '');
    var changeSummary = String(changeItem.change_summary || '');

    // 主行：变化类型标签 + 药物 + 阶段（优先呈现"变了什么"）
    var changeLabelMap = {
      added: '新增', status: '状态变化', results: '结果发布', updated: '更新', removed: '移除'
    };
    var changeLabel = changeLabelMap[dotClass] || '更新';
    var mainParts = [changeLabel];
    if (drugName) mainParts.push(drugName);
    if (phaseLabel) mainParts.push(phaseLabel);
    var mainText = mainParts.join(' · ');

    // 副行：NCT编号 + 变化详情（日期/状态转换等）
    var metaParts = [];
    if (registryId) metaParts.push(registryId);
    if (detailText) metaParts.push(detailText);
    var metaText = metaParts.join(' · ');

    // 副行2：研究标题截断（过长时只保留前 80 字符）
    var shortTitle = title.length > 80 ? title.slice(0, 80) + '…' : title;

    return '<a class="dashboard-trial-change-row" href="' + escapeHref(url) + '" target="_blank" rel="noopener">' +
      '<i class="dot ' + escapeHtml(dotClass) + '" aria-hidden="true"></i>' +
      '<div>' +
        '<strong>' + escapeHtml(mainText) + '</strong>' +
        '<em>' + escapeHtml(metaText) + '</em>' +
        (changeSummary ? '<span class="dashboard-trial-change-summary">' + escapeHtml(changeSummary) + '</span>' : '') +
        (shortTitle ? '<span class="dashboard-trial-change-title">' + escapeHtml(shortTitle) + '</span>' : '') +
      '</div>' +
    '</a>';
  }

  function renderTrialChanges(weeklyChanges) {
    var changes = weeklyChanges || {};
    var previousSnapshotAt = String(changes.previous_snapshot_at || '').trim();
    var windowDays = numberValue(changes.window_days, 7);
    var addedItems = Array.isArray(changes.added) ? changes.added : [];
    var statusChangeItems = Array.isArray(changes.status_changes) ? changes.status_changes : [];
    var resultsPostedItems = Array.isArray(changes.results_posted) ? changes.results_posted : [];
    var updatedItems = Array.isArray(changes.updated) ? changes.updated : [];
    var removedItems = Array.isArray(changes.removed) ? changes.removed : [];
    var addedCount = numberValue(changes.added_count, addedItems.length);
    var statusChangeCount = numberValue(changes.status_change_count, statusChangeItems.length);
    var resultsPostedCount = numberValue(changes.results_posted_count, resultsPostedItems.length);
    var updatedCount = numberValue(changes.updated_count, updatedItems.length);
    var removedCount = numberValue(changes.removed_count, removedItems.length);
    var hasAnyChange = addedCount > 0 || statusChangeCount > 0 || resultsPostedCount > 0 || updatedCount > 0 || removedCount > 0;
    var rowHtml = [];

    if (!hasAnyChange && !previousSnapshotAt) {
      return '<p class="dashboard-data-note">ClinicalTrials.gov 为目前唯一周更注册源；变化要点自下一次周更起在此自动呈现。</p>';
    }

    addedItems.forEach(function(item) {
      var addedItem = item || {};
      rowHtml.push(renderTrialChangeRow(addedItem, 'added', String(addedItem.first_post_date || '日期待确认')));
    });
    statusChangeItems.forEach(function(item) {
      var statusItem = item || {};
      var fromLabel = statusItem.from_label || statusItem.from_status || '未知状态';
      var toLabel = statusItem.to_label || statusItem.to_status || '未知状态';
      rowHtml.push(renderTrialChangeRow(statusItem, 'status', fromLabel + ' → ' + toLabel + ' · ' + (statusItem.updated_date || '日期待确认')));
    });
    resultsPostedItems.forEach(function(item) {
      var resultsItem = item || {};
      rowHtml.push(renderTrialChangeRow(resultsItem, 'results', String(resultsItem.results_post_date || '日期待确认')));
    });
    if (updatedItems.length) {
      updatedItems.slice(0, 4).forEach(function(item) {
        var updatedItem = item || {};
        rowHtml.push(renderTrialChangeRow(updatedItem, 'updated', String(updatedItem.updated_date || '日期待确认')));
      });
      if (updatedItems.length > 4) {
        rowHtml.push('<p class="dashboard-trial-change-more">+' +
          escapeHtml(formatNumber(updatedItems.length - 4)) + ' 项其他更新</p>');
      }
    }
    if (removedCount > 0) {
      rowHtml.push('<p class="dashboard-trial-removed">移除 ' + escapeHtml(formatNumber(removedCount)) + ' 项</p>');
    }
    if (!rowHtml.length && previousSnapshotAt) {
      rowHtml.push('<p class="dashboard-data-note">本周暂无注册变化。</p>');
    }

    return '<div class="dashboard-trial-changes">' +
      '<div class="dashboard-trial-changes-head"><strong>本周注册变化</strong><span>近 ' +
        escapeHtml(formatNumber(windowDays)) + ' 天 · 对比 ' +
        escapeHtml(previousSnapshotAt || '首次基线 · 下周起自动对比') +
      '</span></div>' +
      rowHtml.join('') +
    '</div>';
  }

  function renderTrialInsights(insights) {
    var data = insights || {};
    var population = Array.isArray(data.population_distribution) ? data.population_distribution : [];
    var phases = Array.isArray(data.phase_concentration) ? data.phase_concentration : [];
    var recent = data.recent_registrations || {};
    var recentDrugs = Array.isArray(recent.top_drugs) ? recent.top_drugs : [];
    var recentPhases = Array.isArray(recent.top_phases) ? recent.top_phases : [];
    var recentCount = numberValue(recent.count, 0);
    if (!population.length && !phases.length && !recentCount) return '';

    function pills(items, maxItems) {
      var slice = items.slice(0, maxItems || 6);
      return slice.map(function(item) {
        return '<span class="dashboard-insight-pill"><em>' + escapeHtml(item.label) +
          '</em><strong>' + escapeHtml(formatNumber(item.count)) + '</strong></span>';
      }).join('');
    }

    var html = '<div class="dashboard-trial-insights">';
    if (population.length) {
      html += '<div class="dashboard-insight-group"><span class="dashboard-insight-label">人群覆盖</span>' +
        '<div class="dashboard-insight-pills">' + pills(population, 6) + '</div></div>';
    }
    if (phases.length) {
      html += '<div class="dashboard-insight-group"><span class="dashboard-insight-label">阶段集中度</span>' +
        '<div class="dashboard-insight-pills">' + pills(phases, 6) + '</div></div>';
    }
    if (recentCount) {
      var trendParts = ['近 6 月新开 ' + formatNumber(recentCount) + ' 项'];
      if (recentDrugs.length) {
        trendParts.push('药物 ' + recentDrugs.map(function(d) {
          return escapeHtml(d.label) + '(' + formatNumber(d.count) + ')';
        }).join('、'));
      }
      if (recentPhases.length) {
        trendParts.push('阶段 ' + recentPhases.map(function(p) {
          return escapeHtml(p.label) + '(' + formatNumber(p.count) + ')';
        }).join('、'));
      }
      html += '<div class="dashboard-insight-group"><span class="dashboard-insight-label">新开趋势</span>' +
        '<p class="dashboard-insight-trend">' + trendParts.join(' · ') + '</p></div>';
    }
    html += '</div>';
    return html;
  }

  function renderTrials() {
    var target = document.getElementById('dashboardTrials');
    if (!target) return;
    var meta = clinicalTrialsData.meta || {};
    var sourceCounts = clinicalTrialsData.source_counts || [];
    var leadingMechanism = clinicalTrialsData.leading_mechanism || {};
    var weeklyChanges = clinicalTrialsData.weekly_changes || {};
    var trialInsights = clinicalTrialsData.trial_insights || {};
    var totalCount = meta.total_count || 0;
    var matrixCount = clinicalTrialsData.pipeline_matrix_count || 0;
    var recentCount = clinicalTrialsData.recent_registration_count || 0;

    if (!totalCount) {
      target.innerHTML = '<div class="empty-state small"><h3>临床试验摘要待生成</h3><p>完整矩阵仍可在情报中心查看。</p></div>';
      return;
    }

    target.innerHTML =
      '<div class="dashboard-trial-kpis">' +
        '<span><em>注册记录</em><strong>' + escapeHtml(formatNumber(totalCount)) + '</strong></span>' +
        '<span><em>药物聚合</em><strong>' + escapeHtml(formatNumber(matrixCount)) + '</strong></span>' +
        '<span><em>招募中</em><strong>' + escapeHtml(formatNumber(clinicalTrialsData.recruiting_count || 0)) + '</strong></span>' +
        '<span><em>近 6 月登记</em><strong>' + escapeHtml(formatNumber(recentCount)) + '</strong></span>' +
      '</div>' +
      '<div class="dashboard-source-pills">' + sourceCounts.map(function(source) {
        return '<span>' + escapeHtml(source.source) + ' <strong>' + escapeHtml(formatNumber(source.count)) + '</strong></span>';
      }).join('') + '</div>' +
      (leadingMechanism.label ? '<p class="dashboard-trial-highlight">机制热点：<strong>' +
        escapeHtml(leadingMechanism.label) + '</strong> · ' + escapeHtml(formatNumber(leadingMechanism.count)) + ' 项</p>' : '') +
      renderTrialInsights(trialInsights) +
      '<p class="dashboard-data-note">数据更新 ' + escapeHtml(formatDateTime(meta.generated_at)) + '</p>' +
      renderTrialChanges(weeklyChanges);
  }

  function communityLevel(value) {
    var level = String(value || '').toLowerCase();
    if (level === 'active' || level === 'high') return { label: '活跃', className: 'active' };
    if (level === 'medium' || level === 'watch') return { label: '观察', className: 'watch' };
    return { label: '平稳', className: 'stable' };
  }

  function renderCommunityDynamics() {
    var target = document.getElementById('dashboardCommunityDynamics');
    if (!target) return;
    var source = (communityWeeklyData.hot_communities && communityWeeklyData.hot_communities.length) ?
      communityWeeklyData.hot_communities : (communityWeeklyData.communities || []);
    var rows = source.slice().sort(function(a, b) {
      return numberValue(b.recent_count) - numberValue(a.recent_count) ||
        numberValue(b.high_evidence_count) - numberValue(a.high_evidence_count);
    }).slice(0, 3);
    if (!rows.length) {
      target.innerHTML = '<div class="empty-state small"><h3>暂无社区动态</h3><p>请前往数据状态检查社区周更。</p></div>';
      return;
    }

    target.innerHTML = '<div class="dashboard-community-list">' + rows.map(function(row) {
      var communityId = row.community_id || row.id;
      var topRef = (row.top_refs || [])[0] || {};
      var level = communityLevel(row.signal_level);
      var highEvidenceCount = row.high_evidence_count != null ? row.high_evidence_count : 0;
      var href = pageUrl('pages/knowledge.html?tab=communities&community=' + encodeURIComponent(communityId));
      return '<a class="dashboard-community-row level-' + safeClass(level.className) + '" href="' + escapeHref(href) + '">' +
        '<div class="dashboard-community-head">' +
          '<span>' + escapeHtml(level.label) + '</span>' +
          '<em>本周 ' + escapeHtml(formatNumber(row.recent_count || 0)) + ' 篇</em>' +
        '</div>' +
        '<strong>' + escapeHtml(row.title || communityId) + '</strong>' +
        '<small>高等级新增 ' + escapeHtml(formatNumber(highEvidenceCount)) +
          ' · 中国相关 ' + escapeHtml(formatNumber(row.china_count || 0)) + '</small>' +
        (topRef.title ? '<p>' + escapeHtml(topRef.title) + '</p>' : '') +
      '</a>';
    }).join('') + '</div>';
  }

  function init() {
    renderReleaseStatus();
    renderStats();
    initSignalBoard();
    renderTrials();
    renderCommunityDynamics();

    var badge = document.getElementById('dashboardBadge');
    var releasedAt = releaseData.released_at || data.generated_at || '';
    if (badge) {
      badge.textContent = '完整发布 ' + formatDateTime(releasedAt);
      badge.title = String(releasedAt || '');
    }
  }

  init();
})();
