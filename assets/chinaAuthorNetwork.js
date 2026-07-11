/* MA-MG-HUB 中国作者医院联络图
 * 数据来源: data/china-author-network.js
 */
(function () {
  'use strict';

  var hub = window.MgHub || {};
  var payload = window.MG_CHINA_AUTHOR_NETWORK || null;
  var svgNs = 'http://www.w3.org/2000/svg';

  var el = {
    badge: document.getElementById('chinaNetworkBadge'),
    stats: document.getElementById('chinaNetworkStats'),
    search: document.getElementById('chinaNetworkSearch'),
    geo: document.getElementById('chinaNetworkGeoScope'),
    edgeWeight: document.getElementById('chinaNetworkEdgeWeight'),
    canvas: document.getElementById('chinaAuthorNetworkGraph'),
    legend: document.getElementById('chinaNetworkLegend'),
    heatmap: document.getElementById('chinaNetworkHeatmap'),
    detail: document.getElementById('chinaNetworkDetail')
  };

  if (!el.canvas) return;

  function escapeHtml(value) {
    if (hub.escapeText) return hub.escapeText(value);
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }

  function escapeHref(value, fallback) {
    if (hub.safeUrl) return hub.safeUrl(value, fallback || '#');
    return escapeHtml(value || fallback || '#');
  }

  function compactNumber(value) {
    var n = Number(value || 0);
    if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
    return String(n);
  }

  function pubmedUrl(pmid) {
    return pmid ? 'https://pubmed.ncbi.nlm.nih.gov/' + encodeURIComponent(pmid) + '/' : '#';
  }

  function setSvgAttrs(node, attrs) {
    Object.keys(attrs).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
  }

  function nodeByIdMap(nodes) {
    var map = {};
    nodes.forEach(function (node) { map[node.id] = node; });
    return map;
  }

  var nodes = [];
  var edges = [];
  var papers = {};
  var heatmap = [];
  var nodesById = {};
  var payloadLoading = false;
  var filtersAttached = false;
  var activeNodeId = '';
  var activeEdgeId = '';

  function refreshData() {
    payload = window.MG_CHINA_AUTHOR_NETWORK || payload || null;
    nodes = payload && payload.nodes ? payload.nodes : [];
    edges = payload && payload.edges ? payload.edges : [];
    papers = payload && payload.papers ? payload.papers : {};
    heatmap = payload && payload.heatmap ? payload.heatmap : [];
    nodesById = nodeByIdMap(nodes);
  }

  refreshData();

  function currentGeoScope() {
    return el.geo ? el.geo.value || 'mainland' : 'mainland';
  }

  function currentEdgeMin() {
    return el.edgeWeight ? Number(el.edgeWeight.value || 5) : 5;
  }

  function currentQuery() {
    return el.search ? (el.search.value || '').trim().toLowerCase() : '';
  }

  function nodeInGeo(node, geoScope) {
    return geoScope === 'all' || node.geo_scope === geoScope;
  }

  function edgeInGeo(edge, geoScope) {
    if (geoScope === 'all') return true;
    var source = nodesById[edge.source];
    var target = nodesById[edge.target];
    return Boolean(source && target && source.geo_scope === geoScope && target.geo_scope === geoScope);
  }

  function labelMatches(node, query) {
    if (!query) return false;
    return [node.label, node.province, node.city, node.region].join(' ').toLowerCase().indexOf(query) !== -1;
  }

  function filteredGraph() {
    var geoScope = currentGeoScope();
    var minWeight = currentEdgeMin();
    var query = currentQuery();
    var visibleNodeIds = {};
    var visibleEdges = [];

    if (query) {
      nodes.forEach(function (node) {
        if (nodeInGeo(node, geoScope) && labelMatches(node, query)) visibleNodeIds[node.id] = true;
      });
      edges.forEach(function (edge) {
        if (!edgeInGeo(edge, geoScope)) return;
        if (visibleNodeIds[edge.source] || visibleNodeIds[edge.target]) {
          visibleEdges.push(edge);
          visibleNodeIds[edge.source] = true;
          visibleNodeIds[edge.target] = true;
        }
      });
    } else {
      edges.forEach(function (edge) {
        if (!edgeInGeo(edge, geoScope)) return;
        if ((Number(edge.edge_weight || edge.weight || 0)) < minWeight) return;
        visibleEdges.push(edge);
        visibleNodeIds[edge.source] = true;
        visibleNodeIds[edge.target] = true;
      });
    }

    var visibleNodes = nodes.filter(function (node) { return visibleNodeIds[node.id]; });
    if (!visibleNodes.length) {
      visibleNodes = nodes.filter(function (node) { return nodeInGeo(node, geoScope); }).slice(0, 42);
    }
    if (visibleNodes.length > 72) {
      var keep = {};
      visibleNodes.slice(0, 72).forEach(function (node) { keep[node.id] = true; });
      visibleNodes = visibleNodes.slice(0, 72);
      visibleEdges = visibleEdges.filter(function (edge) { return keep[edge.source] && keep[edge.target]; });
    }
    return { nodes: visibleNodes, edges: visibleEdges };
  }

  function renderBadge() {
    if (!el.badge) return;
    if (!payload) {
      el.badge.textContent = '未生成';
      return;
    }
    el.badge.textContent = (payload.generated_at || '—') + ' · ' + compactNumber((payload.summary || {}).hospitals) + ' hospitals';
  }

  function renderStats() {
    if (!el.stats) return;
    var summary = payload && payload.summary ? payload.summary : {};
    var items = [
      { label: '中国相关文献', value: compactNumber(summary.china_related_papers), note: payload ? payload.source_scope : 'missing' },
      { label: '医院节点', value: compactNumber(summary.hospitals), note: compactNumber(summary.mainland_hospitals) + ' mainland' },
      { label: '合作边', value: compactNumber(summary.edges), note: 'data edge ≥1' },
      { label: '默认核心边', value: compactNumber(summary.mainland_default_edges), note: 'mainland edge ≥5' },
      { label: '作者机构解析率', value: Math.round(Number(summary.graph_author_hospital_parse_rate || 0) * 100) + '%', note: 'first/corresponding' }
    ];
    el.stats.innerHTML = items.map(function (item) {
      return '<article class="knowledge-stat-card"><span>' + escapeHtml(item.label) + '</span><strong>' +
        escapeHtml(item.value) + '</strong><em>' + escapeHtml(item.note) + '</em></article>';
    }).join('');
  }

  function layoutNodes(graphNodes) {
    var count = graphNodes.length || 1;
    var cx = 550;
    var cy = 320;
    var rx = count < 8 ? 210 : 360;
    var ry = count < 8 ? 150 : 230;
    var positioned = {};
    graphNodes.forEach(function (node, index) {
      var angle = (Math.PI * 2 * index / count) - Math.PI / 2;
      var ring = index < 12 ? 0.82 : 1;
      positioned[node.id] = Object.assign({}, node, {
        x: cx + Math.cos(angle) * rx * ring,
        y: cy + Math.sin(angle) * ry * ring,
        r: Math.max(7, Math.min(24, 7 + Math.sqrt(Number(node.paper_count || 0)) * 1.8))
      });
    });
    return positioned;
  }

  function edgeTitle(edge) {
    var source = nodesById[edge.source] || {};
    var target = nodesById[edge.target] || {};
    return (source.label || edge.source) + ' ↔ ' + (target.label || edge.target) + ' · ' + (edge.edge_weight || edge.weight || 0) + ' papers';
  }

  function renderGraph() {
    if (!el.canvas) return;
    if (!payload) {
      el.canvas.innerHTML = '<text x="40" y="80" fill="#64748b">china-author-network.js 未生成</text>';
      return;
    }
    var graph = filteredGraph();
    var positioned = layoutNodes(graph.nodes);
    el.canvas.setAttribute('viewBox', '0 0 1100 660');
    el.canvas.innerHTML = '';

    var edgeGroup = document.createElementNS(svgNs, 'g');
    var nodeGroup = document.createElementNS(svgNs, 'g');
    el.canvas.appendChild(edgeGroup);
    el.canvas.appendChild(nodeGroup);

    graph.edges.forEach(function (edge) {
      var source = positioned[edge.source];
      var target = positioned[edge.target];
      if (!source || !target) return;
      var line = document.createElementNS(svgNs, 'line');
      var weight = Number(edge.edge_weight || edge.weight || 1);
      setSvgAttrs(line, {
        x1: source.x,
        y1: source.y,
        x2: target.x,
        y2: target.y,
        class: 'kg-edge china-network-edge' + (edge.id === activeEdgeId ? ' hl' : ''),
        'data-edge-id': edge.id,
        'stroke-width': Math.max(1.1, Math.min(7, 0.8 + weight * 0.75))
      });
      var title = document.createElementNS(svgNs, 'title');
      title.textContent = edgeTitle(edge);
      line.appendChild(title);
      edgeGroup.appendChild(line);
    });

    graph.nodes.forEach(function (node) {
      var point = positioned[node.id];
      var group = document.createElementNS(svgNs, 'g');
      setSvgAttrs(group, { class: 'kg-node china-network-node' + (node.id === activeNodeId ? ' active' : ''), 'data-node-id': node.id });
      var circle = document.createElementNS(svgNs, 'circle');
      setSvgAttrs(circle, { cx: point.x, cy: point.y, r: point.r });
      var text = document.createElementNS(svgNs, 'text');
      setSvgAttrs(text, { x: point.x, y: point.y + point.r + 13 });
      text.textContent = shortLabel(node.label);
      var title = document.createElementNS(svgNs, 'title');
      title.textContent = node.label + ' · ' + (node.paper_count || 0) + ' papers';
      group.appendChild(circle);
      group.appendChild(text);
      group.appendChild(title);
      nodeGroup.appendChild(group);
    });

    bindGraphEvents();
    renderLegend(graph);
  }

  function shortLabel(label) {
    if (!label) return '';
    return label.length > 28 ? label.slice(0, 26) + '…' : label;
  }

  function bindGraphEvents() {
    Array.prototype.forEach.call(el.canvas.querySelectorAll('[data-node-id]'), function (nodeEl) {
      nodeEl.addEventListener('click', function () {
        selectNode(nodeEl.getAttribute('data-node-id'));
      });
    });
    Array.prototype.forEach.call(el.canvas.querySelectorAll('[data-edge-id]'), function (edgeEl) {
      edgeEl.addEventListener('click', function () {
        selectEdge(edgeEl.getAttribute('data-edge-id'));
      });
    });
  }

  function renderLegend(graph) {
    if (!el.legend) return;
    var query = currentQuery();
    var minWeight = currentEdgeMin();
    var geoScope = currentGeoScope();
    var note = query ? '搜索模式：展开匹配医院的全部合作边' : '默认阈值：edge_weight ≥' + minWeight;
    if (!graph.edges.length) {
      note += '；当前筛选无合作边，已显示该地区发文量最高的医院节点';
    }
    el.legend.innerHTML = '<span class="kg-legend-item"><span class="kg-legend-dot disease"></span>' +
      escapeHtml(geoScope === 'all' ? '大中华全部' : geoScope) + '</span>' +
      '<span class="kg-legend-item" style="color:var(--fg3)">' + escapeHtml(note) + '</span>';
  }

  function incidentEdges(nodeId) {
    return edges.filter(function (edge) { return edge.source === nodeId || edge.target === nodeId; })
      .sort(function (a, b) { return Number(b.edge_weight || 0) - Number(a.edge_weight || 0); });
  }

  function selectNode(nodeId) {
    activeNodeId = nodeId;
    activeEdgeId = '';
    renderGraph();
    var node = nodesById[nodeId];
    if (!node || !el.detail) return;
    var nodeEdges = incidentEdges(nodeId);
    var collaborators = nodeEdges.slice(0, 20).map(function (edge) {
      var otherId = edge.source === nodeId ? edge.target : edge.source;
      var other = nodesById[otherId] || { label: otherId };
      return '<li><button type="button" class="matrix-node-link" data-china-edge="' + escapeHtml(edge.id) + '">' +
        escapeHtml(other.label) + '</button><br><span class="kg-ref-meta">edge_weight ' +
        escapeHtml(edge.edge_weight || edge.weight || 0) + ' · PMID ' + escapeHtml((edge.paper_ids || []).slice(0, 4).join(', ')) + '</span></li>';
    }).join('');
    el.detail.innerHTML = '<div class="kg-detail-head"><h3>' + escapeHtml(node.label) + '</h3><span>' +
      escapeHtml(node.region || node.geo_scope || '') + '</span></div>' +
      '<div class="kg-detail-section"><h4>节点概况</h4><p>' +
      '文献 ' + escapeHtml(node.paper_count || 0) + ' 篇 · 第一作者 ' + escapeHtml(node.first_author_paper_count || 0) +
      ' · 通讯作者 ' + escapeHtml(node.corresponding_author_paper_count || 0) + ' · 合作医院 ' + escapeHtml(node.collaborator_count || 0) + '</p></div>' +
      '<div class="kg-detail-section"><h4>合作医院</h4><ul class="kg-study-list">' +
      (collaborators || '<li class="kg-ref-meta">暂无合作边；可能是单中心或未达到当前图谱筛选阈值。</li>') + '</ul></div>' +
      '<div class="kg-detail-section"><h4>代表作者</h4>' + renderMiniTags(node.top_authors, 'label') + '</div>' +
      '<div class="kg-detail-section"><h4>主题</h4>' + renderMiniTags(node.top_topics, 'label') + '</div>' +
      '<div class="kg-detail-section"><h4>文献</h4>' + renderPaperList(node.paper_ids || [], 8) + '</div>';
    bindDetailEdgeButtons();
  }

  function selectEdge(edgeId) {
    activeEdgeId = edgeId;
    activeNodeId = '';
    renderGraph();
    var edge = edges.filter(function (item) { return item.id === edgeId; })[0];
    if (!edge || !el.detail) return;
    var source = nodesById[edge.source] || { label: edge.source };
    var target = nodesById[edge.target] || { label: edge.target };
    el.detail.innerHTML = '<div class="kg-detail-head"><h3>' + escapeHtml(source.label) + ' ↔ ' + escapeHtml(target.label) +
      '</h3><span>edge_weight ' + escapeHtml(edge.edge_weight || edge.weight || 0) + '</span></div>' +
      '<div class="kg-detail-section"><h4>合作主题</h4>' + renderMiniTags(edge.top_topics, 'label') + '</div>' +
      '<div class="kg-detail-section"><h4>第一/通讯作者</h4>' + renderMiniTags(edge.top_authors, 'label') + '</div>' +
      '<div class="kg-detail-section"><h4>合作 PMID</h4>' + renderPaperList(edge.paper_ids || [], 20) + '</div>';
  }

  function renderMiniTags(items, key) {
    items = items || [];
    if (!items.length) return '<p class="kg-ref-meta">暂无</p>';
    return '<div class="signal-topic-row">' + items.slice(0, 10).map(function (item) {
      return '<span class="signal-topic">' + escapeHtml(item[key] || item.label || '') + ' ' + escapeHtml(item.count || '') + '</span>';
    }).join('') + '</div>';
  }

  function renderPaperList(pmids, limit) {
    pmids = (pmids || []).slice(0, limit || 10);
    if (!pmids.length) return '<p class="kg-ref-meta">暂无 PMID</p>';
    return '<ul class="kg-study-list">' + pmids.map(function (pmid) {
      var paper = papers[pmid] || { pmid: pmid };
      var authorLine = renderPaperAuthors(paper);
      return '<li><a class="text-link" href="' + escapeHref(pubmedUrl(pmid)) + '" target="_blank" rel="noopener">' +
        escapeHtml(paper.title || ('PMID ' + pmid)) + '</a><br><span class="kg-ref-meta">PMID ' + escapeHtml(pmid) +
        (paper.journal ? ' · ' + escapeHtml(paper.journal) : '') + (paper.evidence_level ? ' · Level ' + escapeHtml(paper.evidence_level) : '') +
        '</span>' + authorLine + '</li>';
    }).join('') + '</ul>';
  }

  function renderPaperAuthors(paper) {
    var authors = paper.authors_graph || [];
    if (!authors.length) return '';
    var lines = authors.slice(0, 4).map(function (author) {
      var hospitalLabels = (author.hospitals || []).map(function (id) {
        return nodesById[id] ? nodesById[id].label : id;
      }).join(' / ');
      return author.name + '（' + author.role + '；' + hospitalLabels + '）';
    });
    return '<br><span class="kg-ref-meta">' + escapeHtml(lines.join('；')) + '</span>';
  }

  function bindDetailEdgeButtons() {
    if (!el.detail) return;
    Array.prototype.forEach.call(el.detail.querySelectorAll('[data-china-edge]'), function (button) {
      button.addEventListener('click', function () {
        selectEdge(button.getAttribute('data-china-edge'));
      });
    });
  }

  function renderHeatmap() {
    if (!el.heatmap) return;
    var geoScope = currentGeoScope();
    var rows = heatmap.filter(function (row) { return geoScope === 'all' || row.geo_scope === geoScope; }).slice(0, 8);
    el.heatmap.innerHTML = '<h3>全作者医院热力线索</h3><div class="china-network-heatmap-grid">' + rows.map(function (row) {
      var top = (row.top_hospitals || []).slice(0, 3).map(function (item) { return item.label + ' ' + item.count; }).join('；');
      return '<article class="china-network-heatmap-card"><span>' + escapeHtml(row.province || row.region || row.geo_scope) + '</span><strong>' +
        escapeHtml(row.paper_count || 0) + ' 篇</strong><em>' + escapeHtml(row.hospital_count || 0) + ' hospitals · ' +
        escapeHtml(row.all_author_occurrences || 0) + ' affiliations</em><p>' + escapeHtml(top || '—') + '</p></article>';
    }).join('') + '</div>';
  }

  function refresh() {
    refreshData();
    renderBadge();
    renderStats();
    renderGraph();
    renderHeatmap();
  }

  function attachFilters() {
    if (filtersAttached) return;
    filtersAttached = true;
    [el.search, el.geo, el.edgeWeight].forEach(function (input) {
      if (!input) return;
      input.addEventListener(input.tagName === 'INPUT' ? 'input' : 'change', function () {
        activeEdgeId = '';
        activeNodeId = '';
        if (!payload) {
          loadAndRender();
          return;
        }
        refresh();
      });
    });
  }

  function renderLoadingShell(message) {
    if (el.badge) el.badge.textContent = message || 'Lazy loading…';
    if (el.stats && !payload) el.stats.innerHTML = '';
    if (el.canvas && !payload) {
      el.canvas.setAttribute('viewBox', '0 0 1100 660');
      el.canvas.innerHTML = '<text x="40" y="80" fill="#64748b">' + escapeHtml(message || '点击标签后加载中国作者医院联络图数据') + '</text>';
    }
    if (el.legend && !payload) el.legend.innerHTML = '<span class="kg-ref-meta">data/china-author-network.js 按需加载，避免拖慢知识库首屏。</span>';
    if (el.heatmap && !payload) el.heatmap.innerHTML = '';
  }

  function isChinaTabActive() {
    var tab = document.querySelector('[data-knowledge-tab="china-network"]');
    return Boolean(tab && (tab.getAttribute('aria-selected') === 'true' || tab.classList.contains('active')));
  }

  function loadAndRender() {
    refreshData();
    if (payload) {
      refresh();
      if (nodes.length && !activeNodeId && !activeEdgeId) selectNode(nodes[0].id);
      return;
    }
    if (payloadLoading) return;
    payloadLoading = true;
    renderLoadingShell('Loading china-author-network.js…');
    var loader = hub.loadScript;
    var onLoaded = function (ok) {
      payloadLoading = false;
      if (!ok || !window.MG_CHINA_AUTHOR_NETWORK) {
        renderLoadingShell('china-author-network.js 加载失败');
        return;
      }
      payload = window.MG_CHINA_AUTHOR_NETWORK;
      activeEdgeId = '';
      activeNodeId = '';
      refresh();
      if (nodes.length) selectNode(nodes[0].id);
    };
    if (loader) {
      loader('data/china-author-network.js', onLoaded);
      return;
    }
    var script = document.createElement('script');
    script.src = 'data/china-author-network.js';
    script.onload = function () { onLoaded(true); };
    script.onerror = function () { onLoaded(false); };
    document.head.appendChild(script);
  }

  function init() {
    attachFilters();
    renderBadge();
    renderLoadingShell('点击“中国作者联络图”后按需加载数据');
    var tab = document.querySelector('[data-knowledge-tab="china-network"]');
    if (tab) tab.addEventListener('click', loadAndRender);
    if (isChinaTabActive()) loadAndRender();
  }

  init();
})();
