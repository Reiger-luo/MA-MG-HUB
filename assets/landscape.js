/* MA-MG-HUB 诊治格局 */
(function() {
  'use strict';

  var data = window.MG_LANDSCAPE_DATA || {};
  var trackChart = null;

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function bindTabs() {
    var tabs = document.querySelectorAll('[data-landscape-tab]');
    var panels = document.querySelectorAll('.intel-tab-panel');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener('click', function() {
        var key = this.getAttribute('data-landscape-tab');
        for (var t = 0; t < tabs.length; t++) tabs[t].classList.remove('active');
        for (var p = 0; p < panels.length; p++) panels[p].classList.remove('active');
        this.classList.add('active');
        document.getElementById('landscape-' + key).classList.add('active');
        if (key === 'tracks' && trackChart) setTimeout(function() { trackChart.resize(); }, 50);
      });
    }
  }

  function renderEvidence() {
    var box = document.getElementById('evidenceMatrix');
    var questions = data.evidence_questions || [];
    box.innerHTML = questions.map(function(item) {
      var rows = (item.evidence_matrix || []).slice(0, 4).map(function(row) {
        return '<tr><td>' + escapeHtml(row.type) + '</td><td>' + escapeHtml(row.level) + '</td><td><a href="https://pubmed.ncbi.nlm.nih.gov/' + escapeHtml(row.pmid) + '/" target="_blank">PMID ' + escapeHtml(row.pmid) + '</a></td><td>' + escapeHtml(row.key_finding) + '</td></tr>';
      }).join('');
      return '<article class="matrix-card">' +
        '<div class="question-head"><strong>' + escapeHtml(item.question) + '</strong><span>' + (item.verified ? '已核实' : '待核实') + '</span></div>' +
        '<p>' + escapeHtml(item.summary || '') + '</p>' +
        '<table><tr><th>方向</th><th>等级</th><th>来源</th><th>关键发现</th></tr>' + rows + '</table>' +
      '</article>';
    }).join('');
  }

  function renderTracks() {
    var tracks = data.treatment_tracks || [];
    document.getElementById('trackList').innerHTML = tracks.map(function(track) {
      var refs = (track.references || []).slice(0, 5).map(function(ref) {
        return '<li><a href="' + ref.url + '" target="_blank">' + escapeHtml(ref.title) + '</a><span>PMID ' + escapeHtml(ref.pmid) + '</span></li>';
      }).join('');
      return '<article class="matrix-card"><h3>' + escapeHtml(track.name) + '</h3><div class="module-meta">关联文献 ' + track.article_count + ' 篇</div><ol class="timeline-list">' + refs + '</ol></article>';
    }).join('');
    if (typeof echarts === 'undefined') return;
    var el = document.getElementById('trackChart');
    trackChart = trackChart || echarts.init(el);
    trackChart.setOption({
      color: ['#60a5fa'],
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 24, bottom: 36 },
      xAxis: { type: 'category', data: tracks.map(function(t) { return t.name; }), axisLabel: { color: '#6b7280' } },
      yAxis: { type: 'value', axisLabel: { color: '#6b7280' }, splitLine: { lineStyle: { color: '#e5e7eb' } } },
      series: [{ type: 'bar', name: '关联文献', data: tracks.map(function(t) { return t.article_count; }), barMaxWidth: 34 }]
    });
  }

  function renderChinaDiff() {
    var rows = (data.china_difference || []).map(function(row) {
      return '<tr><td>' + escapeHtml(row.dimension) + '</td><td>' + escapeHtml(row.china) + '</td><td>' + escapeHtml(row.global) + '</td><td>' + escapeHtml(row.gap) + '</td></tr>';
    }).join('');
    document.getElementById('chinaDiff').innerHTML = '<table><tr><th>维度</th><th>中国</th><th>欧美/全球</th><th>差异</th></tr>' + rows + '</table>';
  }

  function renderPipeline() {
    var rows = (data.competitive_pipeline || []).map(function(item) {
      var refs = (item.references || []).slice(0, 2).map(function(ref) { return '<a href="' + ref.url + '" target="_blank">PMID ' + escapeHtml(ref.pmid) + '</a>'; }).join(' ');
      return '<tr><td>' + escapeHtml(item.name) + '</td><td>' + escapeHtml(item.target) + '</td><td>' + escapeHtml(item.route) + '</td><td>' + escapeHtml(item.status) + '</td><td>' + escapeHtml(item.owner) + '</td><td>' + refs + '</td></tr>';
    }).join('');
    document.getElementById('pipelineTable').innerHTML = '<table><tr><th>药物</th><th>靶点</th><th>给药</th><th>状态</th><th>公司</th><th>文献线索</th></tr>' + rows + '</table>';
  }

  function init() {
    bindTabs();
    renderEvidence();
    renderTracks();
    renderChinaDiff();
    renderPipeline();
    var badge = document.getElementById('landscapeBadge');
    if (badge) badge.textContent = (data.evidence_questions || []).length + ' 个证据问题 · ' + (data.competitive_pipeline || []).length + ' 条管线';
    window.addEventListener('resize', function() {
      if (trackChart) trackChart.resize();
    });
  }

  init();
})();
