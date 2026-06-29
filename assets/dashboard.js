/* MA-MG-HUB Dashboard */
(function() {
  'use strict';

  var data = window.MG_DASHBOARD_DATA || { stats: {}, stat_cards: [], sections: [], top_signals: [], work_items: [] };

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
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
      return '<a class="dashboard-section-card" href="' + escapeHtml(section.href || '#') + '">' +
        '<div class="dashboard-section-top"><strong>' + escapeHtml(section.title) + '</strong><em>' + escapeHtml(section.metric || '') + '</em></div>' +
        '<p>' + escapeHtml(section.summary || '') + '</p>' +
        '<div class="dashboard-section-facts">' + facts + '</div>' +
      '</a>';
    }).join('');
  }

  function renderWorkflows() {
    var target = document.getElementById('dashboardWorkflows');
    if (!target) return;
    var workflows = data.workflows || [];
    target.innerHTML = workflows.map(function(item) {
      return '<a class="dashboard-workflow-item" href="' + escapeHtml(item.href || '#') + '">' +
        '<span>' + escapeHtml(item.label) + '</span>' +
        '<strong>' + escapeHtml(item.value || '') + '</strong>' +
        '<em>' + escapeHtml(item.note || '') + '</em>' +
      '</a>';
    }).join('') || '<div class="empty-state small"><h3>暂无工作流数据</h3></div>';
  }

  function renderHealth() {
    var target = document.getElementById('dashboardHealth');
    if (!target) return;
    target.innerHTML = (data.data_health || []).map(function(item) {
      return '<div class="dashboard-health-row ' + escapeHtml(item.state || 'ok') + '">' +
        '<span>' + escapeHtml(item.label) + '</span>' +
        '<strong>' + escapeHtml(item.value || '') + '</strong>' +
      '</div>';
    }).join('') || '<div class="empty-state small"><h3>暂无数据状态</h3></div>';
  }

  function renderSignals() {
    var html = (data.top_signals || []).map(function(signal) {
      var article = signal.article || {};
      var drugHtml = (signal.drugs || []).map(function(d) {
        return '<span class="signal-drug">' + escapeHtml(d) + '</span>';
      }).join('');
      return '<article class="signal-card signal-' + escapeHtml(signal.strength) + '">' +
        '<div class="signal-card-head"><span class="signal-strength">' + escapeHtml(signal.strength) + '信号</span><span class="signal-type">' + escapeHtml(signal.type) + '</span></div>' +
        '<a class="signal-title" href="' + (article.url || '#') + '" target="_blank">' + escapeHtml(signal.summary) + '</a>' +
        '<div class="signal-meta">' + escapeHtml(article.journal || '') + ' · PMID ' + escapeHtml(article.pmid || '-') + '</div>' +
        (drugHtml ? '<div class="signal-topic-row">' + drugHtml + '</div>' : '') +
      '</article>';
    }).join('');
    document.getElementById('dashboardSignals').innerHTML = html || '<div class="empty-state small"><h3>暂无信号</h3></div>';
  }

  function init() {
    renderStats();
    renderSections();
    renderSignals();
    renderWorkflows();
    renderHealth();
    var badge = document.getElementById('dashboardBadge');
    if (badge) badge.textContent = '数据更新 ' + (data.generated_at || '-');
  }

  init();
})();
