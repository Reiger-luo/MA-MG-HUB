/* MA-MG-HUB Dashboard */
(function() {
  'use strict';

  var data = window.MG_DASHBOARD_DATA || { stats: {}, top_signals: [], work_items: [] };

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function renderStats() {
    var stats = data.stats || {};
    document.getElementById('dashboardStats').innerHTML = [
      ['全库文献', stats.total_articles || 0],
      ['近1年文献', stats.recent_articles || 0],
      ['中国相关', stats.china_articles || 0],
      ['14 天信号', stats.signals || 0],
      ['专家画像', stats.experts || 0],
      ['内容模块', stats.modules || 0]
    ].map(function(item) {
      return '<div class="signal-stat-card"><span>' + item[0] + '</span><strong>' + item[1] + '</strong></div>';
    }).join('');
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

  function renderWork() {
    document.getElementById('dashboardWork').innerHTML = (data.work_items || []).map(function(item) {
      return '<a class="work-item" href="' + item.href + '"><span>' + escapeHtml(item.type) + '</span><strong>' + escapeHtml(item.label) + '</strong><em>' + item.count + '</em></a>';
    }).join('');
  }

  function renderTeam() {
    var stats = data.stats || {};
    document.getElementById('teamOverview').innerHTML =
      '<div class="overview-row"><span>MSL 闭环</span><strong>本地 MVP 已就绪</strong></div>' +
      '<div class="overview-row"><span>专家候选池</span><strong>' + (stats.experts || 0) + ' 位</strong></div>' +
      '<div class="overview-row"><span>待确认模块</span><strong>' + (stats.modules || 0) + ' 个</strong></div>' +
      '<div class="overview-row"><span>更新时间</span><strong>' + escapeHtml(data.generated_at || '-') + '</strong></div>';
  }

  function init() {
    renderStats();
    renderSignals();
    renderWork();
    renderTeam();
    var badge = document.getElementById('dashboardBadge');
    if (badge) badge.textContent = '数据更新 ' + (data.generated_at || '-');
  }

  init();
})();
