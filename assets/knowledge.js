/* MA-MG-HUB 知识库 — 私有知识图谱浏览器
 * 数据来源: efgartigimod-wiki Obsidian vault（经 build-knowledge-data.py 提取）
 * 纯 vanilla JS + SVG，零外部依赖。
 */
(function () {
  'use strict';

  var data = window.MG_KNOWLEDGE_GRAPH || { nodes: [], edges: [], study_links: {}, stats: {} };
  var questions = (window.MG_LANDSCAPE_DATA && window.MG_LANDSCAPE_DATA.evidence_questions) || [];
  var articles = window.MG_LITERATURE_DATA || [];
  var experts = (window.MG_EXPERT_PROFILES && window.MG_EXPERT_PROFILES.experts) || [];

  // ── DOM 引用 ──
  var elBadge = document.getElementById('knowledgeBadge');
  var elCanvas = document.getElementById('knowledgeGraph');
  var elDetail = document.getElementById('knowledgeDetail');
  var elZoomLabel = document.getElementById('kgZoomLabel');
  var elQList = document.getElementById('knowledgeQuestions');
  var elSearch = document.getElementById('knowledgeSearch');
  var elSearchResults = document.getElementById('knowledgeSearchResults');

  // ── 视图状态（缩放 + 平移）──
  var VB = { x: 0, y: 0, w: 1100, h: 720 };  // viewBox 初始
  var scale = 1;
  var SCALE_MIN = 0.4;
  var SCALE_MAX = 3;

  var nodesById = {};
  data.nodes.forEach(function (n) { nodesById[n.id] = n; });
  var neighbors = {};  // id -> { id: true }
  data.nodes.forEach(function (n) { neighbors[n.id] = {}; });
  data.edges.forEach(function (e) {
    neighbors[e.from] = neighbors[e.from] || {};
    neighbors[e.to] = neighbors[e.to] || {};
    neighbors[e.from][e.to] = true;
    neighbors[e.to][e.from] = true;
  });

  var TYPE_LABEL = {
    'entity': '实体',
    'concept': '概念',
    'data-point': '数据点',
    'comparison': '对比'
  };

  function escapeHtml(v) {
    var d = document.createElement('div');
    d.textContent = v == null ? '' : String(v);
    return d.innerHTML;
  }

  // ════════════════════════════════════════════════
  //  1. 顶部 badge
  // ════════════════════════════════════════════════
  function renderBadge() {
    if (!elBadge) return;
    var s = data.stats || {};
    elBadge.textContent =
      (s.total_nodes || 0) + ' 核心节点 · ' +
      (s.high_confidence || 0) + ' 高置信 · ' +
      (s.contested || 0) + ' 争议 · ' +
      (s.edges || 0) + ' 条关联';
  }

  // ════════════════════════════════════════════════
  //  2. SVG 图谱渲染
  // ════════════════════════════════════════════════
  var SVG_NS = 'http://www.w3.org/2000/svg';

  function svgEl(tag, attrs) {
    var e = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      for (var k in attrs) {
        if (k === 'text') e.textContent = attrs[k];
        else e.setAttribute(k, attrs[k]);
      }
    }
    return e;
  }

  function nodeRadius(n) {
    // 基础 + 关联研究数 + 高置信加成
    var r = 9 + Math.min((n.study_count || 0) * 0.5, 9);
    if (n.confidence === 'high') r += 2;
    return r;
  }

  function buildGraph() {
    if (!elCanvas) return;
    elCanvas.setAttribute('viewBox', VB.x + ' ' + VB.y + ' ' + VB.w + ' ' + VB.h);

    // 边层
    var edgeLayer = svgEl('g', { 'class': 'kg-edge-layer' });
    data.edges.forEach(function (e) {
      var a = nodesById[e.from], b = nodesById[e.to];
      if (!a || !b) return;
      var line = svgEl('line', {
        'class': 'kg-edge',
        x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        'data-from': e.from, 'data-to': e.to
      });
      edgeLayer.appendChild(line);
    });
    elCanvas.appendChild(edgeLayer);

    // 节点层
    var nodeLayer = svgEl('g', { 'class': 'kg-node-layer' });
    data.nodes.forEach(function (n) {
      var g = svgEl('g', {
        'class': 'kg-node type-' + n.type + (n.contested ? ' contested' : ''),
        'data-id': n.id,
        transform: 'translate(' + n.x + ',' + n.y + ')'
      });
      var r = nodeRadius(n);
      g.appendChild(svgEl('circle', { r: r }));
      // 争议角标
      if (n.contested) {
        g.appendChild(svgEl('text', {
          'class': 'kg-contest-mark',
          x: r * 0.72, y: -r * 0.72,
          text: '!'
        }));
      }
      // 节点标签文字（在节点下方）
      var label = truncateLabel(n.title, n.type);
      g.appendChild(svgEl('text', { y: r + 13, text: label }));
      nodeLayer.appendChild(g);
    });
    elCanvas.appendChild(nodeLayer);
  }

  function truncateLabel(title, type) {
    // 实体类型用短名，其他截断
    var max = type === 'entity' ? 22 : 18;
    var t = title.replace(/^Efgartigimod\s+/i, 'Efg ');
    if (t.length <= max) return t;
    return t.slice(0, max - 1) + '…';
  }

  // ════════════════════════════════════════════════
  //  3. 缩放 + 平移
  // ════════════════════════════════════════════════
  function applyViewBox() {
    var cx = VB.x + VB.w / 2, cy = VB.y + VB.h / 2;
    var newW = 1100 / scale, newH = 720 / scale;
    VB.w = newW; VB.h = newH;
    VB.x = cx - newW / 2; VB.y = cy - newH / 2;
    elCanvas.setAttribute('viewBox', VB.x + ' ' + VB.y + ' ' + VB.w + ' ' + VB.h);
    if (elZoomLabel) elZoomLabel.textContent = Math.round(scale * 100) + '%';
  }

  function zoomTo(newScale, focusX, focusY) {
    newScale = Math.max(SCALE_MIN, Math.min(SCALE_MAX, newScale));
    if (focusX != null && focusY != null) {
      // 以鼠标位置为锚点缩放
      var worldX = VB.x + (focusX / elCanvas.clientWidth) * VB.w;
      var worldY = VB.y + (focusY / elCanvas.clientHeight) * VB.h;
      scale = newScale;
      VB.w = 1100 / scale; VB.h = 720 / scale;
      VB.x = worldX - (focusX / elCanvas.clientWidth) * VB.w;
      VB.y = worldY - (focusY / elCanvas.clientHeight) * VB.h;
      elCanvas.setAttribute('viewBox', VB.x + ' ' + VB.y + ' ' + VB.w + ' ' + VB.h);
    } else {
      scale = newScale;
      applyViewBox();
    }
    if (elZoomLabel) elZoomLabel.textContent = Math.round(scale * 100) + '%';
  }

  function resetView() {
    scale = 1;
    VB = { x: 0, y: 0, w: 1100, h: 720 };
    elCanvas.setAttribute('viewBox', '0 0 1100 720');
    if (elZoomLabel) elZoomLabel.textContent = '100%';
  }

  function attachPanZoom() {
    if (!elCanvas) return;

    // 滚轮缩放
    elCanvas.addEventListener('wheel', function (ev) {
      ev.preventDefault();
      var rect = elCanvas.getBoundingClientRect();
      var fx = ev.clientX - rect.left;
      var fy = ev.clientY - rect.top;
      var factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
      zoomTo(scale * factor, fx, fy);
    }, { passive: false });

    // 拖拽平移
    var dragging = false;
    var start = { x: 0, y: 0, vbx: 0, vby: 0 };

    elCanvas.addEventListener('mousedown', function (ev) {
      if (ev.target.closest('.kg-node')) return;  // 节点交给 click 处理
      dragging = true;
      start.x = ev.clientX; start.y = ev.clientY;
      start.vbx = VB.x; start.vby = VB.y;
      elCanvas.classList.add('grabbing');
    });

    window.addEventListener('mousemove', function (ev) {
      if (!dragging) return;
      var dx = ev.clientX - start.x;
      var dy = ev.clientY - start.y;
      var scaleX = VB.w / elCanvas.clientWidth;
      var scaleY = VB.h / elCanvas.clientHeight;
      VB.x = start.vbx - dx * scaleX;
      VB.y = start.vby - dy * scaleY;
      elCanvas.setAttribute('viewBox', VB.x + ' ' + VB.y + ' ' + VB.w + ' ' + VB.h);
    });

    window.addEventListener('mouseup', function () {
      if (dragging) {
        dragging = false;
        elCanvas.classList.remove('grabbing');
      }
    });

    // 触屏支持（单指平移）
    elCanvas.addEventListener('touchstart', function (ev) {
      if (ev.touches.length !== 1) return;
      if (ev.target.closest('.kg-node')) return;
      dragging = true;
      var t = ev.touches[0];
      start.x = t.clientX; start.y = t.clientY;
      start.vbx = VB.x; start.vby = VB.y;
    }, { passive: true });
    elCanvas.addEventListener('touchmove', function (ev) {
      if (!dragging || ev.touches.length !== 1) return;
      var t = ev.touches[0];
      var dx = t.clientX - start.x;
      var dy = t.clientY - start.y;
      var scaleX = VB.w / elCanvas.clientWidth;
      var scaleY = VB.h / elCanvas.clientHeight;
      VB.x = start.vbx - dx * scaleX;
      VB.y = start.vby - dy * scaleY;
      elCanvas.setAttribute('viewBox', VB.x + ' ' + VB.y + ' ' + VB.w + ' ' + VB.h);
    }, { passive: true });
    elCanvas.addEventListener('touchend', function () { dragging = false; });

    // 工具栏按钮
    var btnIn = document.getElementById('kgZoomIn');
    var btnOut = document.getElementById('kgZoomOut');
    var btnReset = document.getElementById('kgZoomReset');
    if (btnIn) btnIn.addEventListener('click', function () { zoomTo(scale * 1.25); });
    if (btnOut) btnOut.addEventListener('click', function () { zoomTo(scale / 1.25); });
    if (btnReset) btnReset.addEventListener('click', resetView);
  }

  // ════════════════════════════════════════════════
  //  4. 节点交互（悬停高亮 + 点击详情）
  // ════════════════════════════════════════════════
  var activeId = null;

  function attachNodeInteraction() {
    if (!elCanvas) return;
    var nodeEls = elCanvas.querySelectorAll('.kg-node');

    Array.prototype.forEach.call(nodeEls, function (nodeEl) {
      var id = nodeEl.getAttribute('data-id');

      nodeEl.addEventListener('mouseenter', function () {
        if (activeId) return;  // 有选中节点时不响应悬停高亮
        highlightNeighborhood(id);
      });
      nodeEl.addEventListener('mouseleave', function () {
        if (activeId) return;
        clearHighlight();
      });

      nodeEl.addEventListener('click', function (ev) {
        ev.stopPropagation();
        selectNode(id);
      });
    });

    // 点击空白取消选中
    elCanvas.addEventListener('click', function () {
      if (activeId) {
        activeId = null;
        clearActive();
        clearHighlight();
        var defaultId = nodesById['efgartigimod'] ? 'efgartigimod' : (data.nodes[0] && data.nodes[0].id);
        if (defaultId) renderDetail(defaultId);
      }
    });
  }

  function highlightNeighborhood(id) {
    var nb = neighbors[id] || {};
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge'), function (line) {
      var f = line.getAttribute('data-from');
      var t = line.getAttribute('data-to');
      if (f === id || t === id) line.classList.add('hl');
      else line.classList.add('dim');
    });
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node'), function (n) {
      var nid = n.getAttribute('data-id');
      if (nid === id || nb[nid]) { /* keep visible */ }
      else n.classList.add('dim');
    });
  }

  function clearHighlight() {
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge.hl'), function (e) { e.classList.remove('hl'); });
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge.dim'), function (e) { e.classList.remove('dim'); });
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node.dim'), function (n) { n.classList.remove('dim'); });
  }

  function clearActive() {
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node.active'), function (n) { n.classList.remove('active'); });
  }

  function selectNode(id) {
    activeId = id;
    clearActive();
    clearHighlight();
    var nodeEl = elCanvas.querySelector('.kg-node[data-id="' + cssEscape(id) + '"]');
    if (nodeEl) nodeEl.classList.add('active');
    highlightNeighborhood(id);
    renderDetail(id);
  }

  function cssEscape(s) {
    return String(s).replace(/"/g, '\\"');
  }

  // ════════════════════════════════════════════════
  //  5. 详情面板
  // ════════════════════════════════════════════════
  function renderDetail(id) {
    if (!elDetail) return;
    var n = nodesById[id];
    if (!n) { elDetail.innerHTML = '<div class="kg-empty-hint">未选中节点</div>'; return; }

    var studies = data.study_links[id] || [];

    var badgesHtml = '';
    var conf = (n.confidence || 'unknown');
    var confText = { high: '高置信', medium: '中置信', low: '低置信', unknown: '置信度未知' }[conf] || '置信度未知';
    badgesHtml += '<span class="kg-badge conf-' + (conf === 'unknown' ? 'low' : conf) + '">' + escapeHtml(confText) + '</span>';
    if (n.contested) badgesHtml += '<span class="kg-badge contested">⚠ 存在争议</span>';
    badgesHtml += '<span class="kg-badge">' + escapeHtml(TYPE_LABEL[n.type] || n.type) + '</span>';
    if (n.study_count) badgesHtml += '<span class="kg-badge">' + n.study_count + ' 项关联研究</span>';
    if (n.updated) badgesHtml += '<span class="kg-badge">更新 ' + escapeHtml(n.updated) + '</span>';

    var contradictionHtml = '';
    if (n.contradictions && n.contradictions.length) {
      contradictionHtml = '<div class="kg-detail-contradiction">⚠ 与以下笔记存在矛盾：<br>' +
        n.contradictions.map(function (c) { return '· ' + escapeHtml(c); }).join('<br>') +
        '</div>';
    }

    var tagsHtml = '';
    if (n.tags && n.tags.length) {
      tagsHtml = '<div class="kg-detail-section"><h4>标签</h4><div class="kg-tags">' +
        n.tags.map(function (t) { return '<span class="mini-chip">' + escapeHtml(t) + '</span>'; }).join('') +
        '</div></div>';
    }

    var studyHtml = '';
    if (studies.length) {
      studyHtml = '<div class="kg-detail-section"><h4>关联研究 (' + studies.length + ')</h4><ul class="kg-study-list">' +
        studies.map(function (s) {
          return '<li>' + escapeHtml(s.title) + '</li>';
        }).join('') + '</ul></div>';
    }

    elDetail.innerHTML =
      '<div class="kg-detail-type">' + escapeHtml(TYPE_LABEL[n.type] || n.type) + '</div>' +
      '<h2>' + escapeHtml(n.title) + '</h2>' +
      '<div class="kg-badges">' + badgesHtml + '</div>' +
      contradictionHtml +
      '<div class="kg-detail-summary">' + escapeHtml(n.summary) + '</div>' +
      tagsHtml +
      studyHtml +
      '<div class="kg-detail-actions">' +
        '<a class="kg-obsidian-btn" href="' + escapeHtml(n.obsidian_url) + '">📓 在 Obsidian 中打开</a>' +
      '</div>';
  }

  // ════════════════════════════════════════════════
  //  6. 折叠区：临床问答证据状态
  // ════════════════════════════════════════════════
  function renderQuestions() {
    if (!elQList) return;
    var qCountEl = document.getElementById('knowledgeQCount');
    if (qCountEl) qCountEl.textContent = '· ' + questions.length + ' 个';
    if (!questions.length) {
      elQList.innerHTML = '<div class="empty-state small"><h3>暂无临床问答</h3></div>';
      return;
    }
    elQList.innerHTML = questions.map(function (q) {
      var refs = q.evidence_matrix || q.references || [];
      var verified = q.verified;
      var statusLabel = verified ? '✅ 已有证据支持' : '🔍 证据待确认';
      var statusClass = verified ? 'verified' : 'unverified';
      var supportCount = (q.evidence_matrix || []).filter(function (e) { return e.type === '支持'; }).length;
      var meta = '';
      if (q.evidence_matrix && q.evidence_matrix.length) {
        meta = '<div class="chip-row">' +
          '<span class="mini-chip">' + q.evidence_matrix.length + ' 条证据</span>' +
          '<span class="mini-chip">' + supportCount + ' 条支持</span>' +
          '</div>';
      } else if (refs.length) {
        meta = '<div class="chip-row"><span class="mini-chip">' + refs.length + ' 篇引用</span></div>';
      }
      return '<article class="evidence-question-card">' +
        '<div class="question-head"><strong>' + escapeHtml(q.question) + '</strong>' +
        '<span class="eq-status ' + statusClass + '">' + statusLabel + '</span></div>' +
        (q.summary ? '<p>' + escapeHtml(q.summary) + '</p>' : '') +
        meta +
        '</article>';
    }).join('');
  }

  // ════════════════════════════════════════════════
  //  7. 折叠区：辅助检索（跨图谱节点 + 文献 + 专家）
  // ════════════════════════════════════════════════
  function attachSearch() {
    if (!elSearch || !elSearchResults) return;
    elSearch.addEventListener('input', renderSearch);
    renderSearch();
  }

  function renderSearch() {
    if (!elSearchResults) return;
    var kw = (elSearch.value || '').trim().toLowerCase();
    var hasKw = !!kw;

    // 图谱节点
    var nodeHits = data.nodes.filter(function (n) {
      if (!hasKw) return false;
      return [n.title, n.summary, (n.tags || []).join(' ')].join(' ').toLowerCase().indexOf(kw) !== -1;
    }).slice(0, 5);

    // 文献
    var artHits = articles.filter(function (a) {
      if (!hasKw) return false;
      return [a.title, a.abstract, a.journal, (a.authors || []).join(' ')].join(' ').toLowerCase().indexOf(kw) !== -1;
    }).slice(0, 5);

    // 专家
    var expHits = experts.filter(function (e) {
      if (!hasKw) return false;
      return [e.name_en, e.affiliation, (e.public_tags || []).join(' ')].join(' ').toLowerCase().indexOf(kw) !== -1;
    }).slice(0, 4);

    if (!hasKw) {
      elSearchResults.innerHTML = '<div class="kg-empty-hint">输入关键词检索知识图谱节点、文献、专家。聚焦检索请前往情报中心 / MSL 工作台。</div>';
      return;
    }

    var html = '';
    if (nodeHits.length) {
      html += '<div class="kg-detail-section"><h4>知识节点 (' + nodeHits.length + ')</h4><ul class="kg-study-list">' +
        nodeHits.map(function (n) {
          return '<li><a class="text-link" data-node="' + escapeHtml(n.id) + '">' + escapeHtml(n.title) + '</a></li>';
        }).join('') + '</ul></div>';
    }
    if (artHits.length) {
      html += '<div class="kg-detail-section"><h4>文献 (' + artHits.length + ')</h4><ul class="kg-study-list">' +
        artHits.map(function (a) {
          return '<li><a class="text-link" href="' + escapeHtml(a.url) + '" target="_blank">' + escapeHtml(a.title) + '</a><br><span style="color:var(--fg3);font-size:0.75rem">' + escapeHtml(a.journal || '') + ' · PMID ' + escapeHtml(a.pmid || '-') + '</span></li>';
        }).join('') + '</ul></div>';
    }
    if (expHits.length) {
      html += '<div class="kg-detail-section"><h4>专家 (' + expHits.length + ')</h4><ul class="kg-study-list">' +
        expHits.map(function (e) {
          return '<li><a class="text-link" href="/MA-MG-HUB/pages/msl.html">' + escapeHtml(e.name_en) + '</a><br><span style="color:var(--fg3);font-size:0.75rem">' + escapeHtml(e.affiliation || '') + '</span></li>';
        }).join('') + '</ul></div>';
    }

    elSearchResults.innerHTML = html || '<div class="kg-empty-hint">无匹配结果，换个关键词试试。</div>';

    // 绑定节点点击 → 跳到图谱并选中
    Array.prototype.forEach.call(elSearchResults.querySelectorAll('[data-node]'), function (a) {
      a.addEventListener('click', function () {
        var id = a.getAttribute('data-node');
        if (id && nodesById[id]) {
          selectNode(id);
          var wrap = document.querySelector('.kg-canvas-wrap');
          if (wrap) wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      });
    });
  }

  // ════════════════════════════════════════════════
  //  8. 折叠区开关
  // ════════════════════════════════════════════════
  function attachCollapse() {
    Array.prototype.forEach.call(document.querySelectorAll('.kg-collapse-head'), function (head) {
      head.addEventListener('click', function () {
        head.parentElement.classList.toggle('open');
      });
    });
  }

  // ════════════════════════════════════════════════
  //  init
  // ════════════════════════════════════════════════
  function init() {
    renderBadge();
    buildGraph();
    attachPanZoom();
    attachNodeInteraction();
    attachCollapse();
    renderQuestions();
    attachSearch();
    // 默认选中核心药物实体
    var defaultId = nodesById['efgartigimod'] ? 'efgartigimod' : (data.nodes[0] && data.nodes[0].id);
    if (defaultId) renderDetail(defaultId);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
