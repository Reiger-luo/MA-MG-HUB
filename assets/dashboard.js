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
    var path = 'pages/literature.html?tab=signals';
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
        href: 'pages/literature.html?tab=signals',
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

  function renderSignals() {
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

  function renderTrials() {
    var target = document.getElementById('dashboardTrials');
    if (!target) return;
    var meta = clinicalTrialsData.meta || {};
    var sourceCounts = clinicalTrialsData.source_counts || [];
    var leadingMechanism = clinicalTrialsData.leading_mechanism || {};
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
      (leadingMechanism.label ? '<p class="dashboard-trial-highlight">机制热点：<strong>' +
        escapeHtml(leadingMechanism.label) + '</strong> · ' + escapeHtml(formatNumber(leadingMechanism.count)) + ' 项</p>' : '') +
      '<div class="dashboard-source-pills">' + sourceCounts.map(function(source) {
        return '<span>' + escapeHtml(source.source) + ' <strong>' + escapeHtml(formatNumber(source.count)) + '</strong></span>';
      }).join('') + '</div>' +
      '<p class="dashboard-data-note">数据更新 ' + escapeHtml(formatDateTime(meta.generated_at)) + '</p>';
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
    renderSignals();
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
