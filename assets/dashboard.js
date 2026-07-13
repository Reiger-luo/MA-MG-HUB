/* MA-MG-HUB Dashboard */
(function() {
  'use strict';

  var hub = window.MgHub || {};
  var data = window.MG_DASHBOARD_DATA || { stats: {}, stat_cards: [], sections: [], signal_summary: null, top_signals: [], work_items: [] };
  var communityCardsData = window.MG_COMMUNITY_CARDS || { cards: [] };
  var communityWeeklyData = window.MG_COMMUNITY_WEEKLY || { communities: [], hot_communities: [] };
  var topicCoverageData = window.MG_WIKI_TOPIC_COVERAGE || { community_coverage: [] };
  var communityCardsById = {};
  var topicCoverageByCommunityId = {};
  (communityCardsData.cards || []).forEach(function(card) { communityCardsById[card.id] = card; });
  (topicCoverageData.community_coverage || []).forEach(function(item) { topicCoverageByCommunityId[item.community_id] = item; });

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

  function pageUrl(path) {
    return hub.pageUrl ? hub.pageUrl(path) : path;
  }

  function compactNumber(value) {
    var n = Number(value || 0);
    if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
    return String(n);
  }

  function renderStats() {
    var stats = data.stats || {};
    var cards = data.stat_cards && data.stat_cards.length ? data.stat_cards : [
      { label: '全库文献', value: stats.total_articles || 0, note: 'PubMed' },
      { label: '近1年文献', value: stats.recent_articles || 0, note: '前端情报池' },
      { label: '中国相关', value: stats.china_articles || 0, note: '本土证据' },
      { label: '14 天信号', value: stats.signals || 0, note: '规则评分' },
      { label: '专家画像', value: stats.experts || 0, note: '作者-机构索引' },
      { label: '内容模块', value: stats.modules || 0, note: 'MSL 工作台' }
    ];
    document.getElementById('dashboardStats').innerHTML = cards.map(function(card) {
      return '<article class="signal-stat-card dashboard-stat-card">' +
        '<span>' + escapeHtml(card.label) + '</span>' +
        '<strong>' + escapeHtml(compactNumber(card.value)) + '</strong>' +
        '<em>' + escapeHtml(card.note || '') + '</em>' +
      '</article>';
    }).join('');
  }

  function renderSections() {
    var target = document.getElementById('dashboardSections');
    if (!target) return;
    var sections = data.sections || [];
    target.innerHTML = sections.map(function(section) {
      var facts = (section.facts || []).map(function(item) {
        return '<span>' + escapeHtml(item) + '</span>';
      }).join('');
      return '<a class="dashboard-section-card" href="' + escapeHref(section.href || '#') + '">' +
        '<div class="dashboard-section-top"><strong>' + escapeHtml(section.title) + '</strong><em>' + escapeHtml(section.metric || '') + '</em></div>' +
        '<p>' + escapeHtml(section.summary || '') + '</p>' +
        '<div class="dashboard-section-facts">' + facts + '</div>' +
      '</a>';
    }).join('');
  }

  function rankSignalFacts(signals, field, limit) {
    var counts = {};
    var order = {};
    (signals || []).forEach(function(signal) {
      var values = field === 'keywords' ? (signal.keywords || []) : [signal[field]];
      var seen = {};
      values.forEach(function(value) {
        var label = String(value || '').trim();
        if (!label || seen[label]) return;
        seen[label] = true;
        if (order[label] == null) order[label] = Object.keys(order).length;
        counts[label] = (counts[label] || 0) + 1;
      });
    });
    return Object.keys(counts).sort(function(a, b) {
      return counts[b] - counts[a] || order[a] - order[b] || a.localeCompare(b);
    }).slice(0, limit).map(function(label) {
      return { label: label, count: counts[label] };
    });
  }

  function buildSignalSummaryFallback() {
    var signals = Array.isArray(data.top_signals) ? data.top_signals : [];
    var stats = data.stats || {};
    var strengthCounts = { strong: 0, medium: 0, weak: 0 };
    var strengthKeys = { '强': 'strong', '中': 'medium', '弱': 'weak' };
    var strongThemes = [];
    signals.forEach(function(signal) {
      var strengthKey = strengthKeys[signal.strength] || 'weak';
      strengthCounts[strengthKey] += 1;
      if (strengthKey === 'strong' && signal.title && strongThemes.indexOf(signal.title) === -1) {
        strongThemes.push(signal.title);
      }
    });
    var leadingTypes = rankSignalFacts(signals, 'type', 3);
    var topTopics = rankSignalFacts(signals, 'keywords', 3);
    var totalCount = Number(stats.signals || signals.length || 0);
    var overviewParts = ['近 14 天共形成 ' + totalCount + ' 条信号'];
    if (leadingTypes.length) {
      overviewParts.push('主要类型为' + leadingTypes.slice(0, 2).map(function(item) { return item.label; }).join('、'));
    }
    if (strongThemes.length) {
      overviewParts.push('强信号聚焦“' + strongThemes.slice(0, 2).join('”、“') + '”');
    }
    if (topTopics.length) {
      overviewParts.push('高频主题为' + topTopics.map(function(item) { return item.label; }).join('、'));
    }
    return {
      total_count: totalCount,
      strength_counts: strengthCounts,
      overview: overviewParts.join('；') + '。',
      leading_types: leadingTypes,
      strong_themes: strongThemes.slice(0, 2),
      top_topics: topTopics
    };
  }

  function renderSignals() {
    var target = document.getElementById('dashboardSignals');
    if (!target) return;
    var summary = data.signal_summary || buildSignalSummaryFallback();
    var counts = summary.strength_counts || {};
    var factHtml = [];
    (summary.leading_types || []).slice(0, 3).forEach(function(item) {
      factHtml.push('<span class="dashboard-signal-fact type"><em>类型</em><strong>' + escapeHtml(item.label) + '</strong><small>' + escapeHtml(item.count || 0) + ' 条</small></span>');
    });
    (summary.top_topics || []).slice(0, 3).forEach(function(item) {
      factHtml.push('<span class="dashboard-signal-fact topic"><em>主题</em><strong>' + escapeHtml(item.label) + '</strong><small>' + escapeHtml(item.count || 0) + ' 条</small></span>');
    });
    target.innerHTML = '<article class="dashboard-signal-summary">' +
      '<div class="dashboard-signal-summary-head">' +
        '<div class="dashboard-signal-total"><span>信号总量</span><strong>' + escapeHtml(summary.total_count || 0) + '</strong><em>条</em></div>' +
        '<div class="dashboard-signal-strengths">' +
          '<span><em>强</em><strong>' + escapeHtml(counts.strong || 0) + '</strong></span>' +
          '<span><em>中</em><strong>' + escapeHtml(counts.medium || 0) + '</strong></span>' +
          '<span><em>弱</em><strong>' + escapeHtml(counts.weak || 0) + '</strong></span>' +
        '</div>' +
      '</div>' +
      '<p class="dashboard-signal-overview">' + escapeHtml(summary.overview || '暂无可用的近期信号汇总。') + '</p>' +
      (factHtml.length ? '<div class="dashboard-signal-facts">' + factHtml.join('') + '</div>' : '') +
    '</article>';
  }

  function renderCommunityDynamics() {
    var target = document.getElementById('dashboardCommunityDynamics');
    if (!target) return;
    var source = (communityWeeklyData.hot_communities && communityWeeklyData.hot_communities.length) ?
      communityWeeklyData.hot_communities : (communityWeeklyData.communities || []);
    var rows = source.slice().sort(function(a, b) {
      return (b.recent_count || 0) - (a.recent_count || 0) ||
        (b.high_evidence_count || 0) - (a.high_evidence_count || 0);
    }).slice(0, 4);
    if (!rows.length) {
      target.innerHTML = '<div class="empty-state small"><h3>暂无社区动态</h3></div>';
      return;
    }
    target.innerHTML = '<div class="dashboard-community-list">' + rows.map(function(row) {
      var communityId = row.community_id || row.id;
      var card = communityCardsById[communityId] || {};
      var coverage = topicCoverageByCommunityId[communityId] || {};
      var topTopic = (coverage.top_topics || [])[0] || {};
      var href = pageUrl('pages/knowledge.html?community=' + encodeURIComponent(communityId));
      var meta = '本周 ' + compactNumber(row.recent_count || card.recent_14d_count || 0) +
        ' · 高等级 ' + compactNumber(row.high_evidence_count || card.high_evidence_count || 0) +
        ' · 专题 ' + compactNumber(coverage.topic_count || 0);
      return '<a class="dashboard-community-row" href="' + href + '">' +
        '<span>' + escapeHtml(row.signal_level === 'high' ? '活跃' : row.signal_level === 'medium' ? '观察' : '平稳') + '</span>' +
        '<strong>' + escapeHtml(row.title || card.title || communityId) + '</strong>' +
        '<em>' + escapeHtml(meta) + '</em>' +
        (topTopic.title ? '<small>' + escapeHtml(topTopic.title) + '</small>' : '') +
      '</a>';
    }).join('') + '</div>';
  }

  function init() {
    renderStats();
    renderCommunityDynamics();
    renderSections();
    renderSignals();
    var badge = document.getElementById('dashboardBadge');
    if (badge) badge.textContent = '数据更新 ' + (data.generated_at || '-');
  }

  init();
})();
