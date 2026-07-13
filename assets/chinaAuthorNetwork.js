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
    drugFilter: document.getElementById('chinaNetworkDrugFilter'),
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
  var drugCatalog = [];
  var drugById = {};
  var nodesById = {};
  var payloadLoading = false;
  var filtersAttached = false;
  var activeNodeId = '';
  var activeEdgeId = '';
  var activeDetail = null;
  var chinaMapTemplate = null;
  var chinaMapLoading = false;
  var chinaMapCallbacks = [];

  function refreshData() {
    payload = window.MG_CHINA_AUTHOR_NETWORK || payload || null;
    nodes = payload && payload.nodes ? payload.nodes : [];
    edges = payload && payload.edges ? payload.edges : [];
    papers = payload && payload.papers ? payload.papers : {};
    heatmap = payload && payload.heatmap ? payload.heatmap : [];
    drugCatalog = payload && payload.drug_catalog ? payload.drug_catalog : [];
    drugById = {};
    drugCatalog.forEach(function (drug) { drugById[drug.id] = drug; });
    nodesById = nodeByIdMap(nodes);
    renderDrugFilterOptions();
  }

  refreshData();

  function currentGeoScope() {
    return el.geo ? el.geo.value || 'mainland' : 'mainland';
  }

  function currentEdgeMin() {
    return el.edgeWeight ? Number(el.edgeWeight.value || 1) : 1;
  }

  function currentQuery() {
    return el.search ? (el.search.value || '').trim().toLowerCase() : '';
  }

  function currentDrugId() {
    return el.drugFilter ? (el.drugFilter.value || '') : '';
  }

  function currentGlobalContext() {
    var geoLabel = currentGeoScope();
    if (el.geo && el.geo.options && el.geo.selectedIndex >= 0) {
      geoLabel = el.geo.options[el.geo.selectedIndex].text;
    }
    var drugId = currentDrugId();
    return {
      geoScope: currentGeoScope(),
      geoLabel: geoLabel,
      drugId: drugId,
      drugLabel: drugId ? ((drugById[drugId] || {}).label || drugId) : '全部药物标签'
    };
  }

  function renderDetailContext(sourceLabel, basis) {
    var context = currentGlobalContext();
    return '<div class="china-network-detail-context"><span class="kg-detail-type">' + escapeHtml(sourceLabel) +
      '</span><p>当前全局筛选：' + escapeHtml(context.geoLabel) + ' · ' + escapeHtml(context.drugLabel) +
      '</p><p>统计口径：' + escapeHtml(basis) + '</p></div>';
  }

  function renderContextEmpty(sourceLabel, basis, title, message) {
    if (!el.detail) return;
    el.detail.innerHTML = renderDetailContext(sourceLabel, basis) +
      '<div class="kg-detail-head"><h3>' + escapeHtml(title || '暂无匹配数据') + '</h3></div>' +
      '<div class="kg-empty-hint">当前全局筛选下暂无匹配数据。' + escapeHtml(message || '') + '</div>';
  }

  function nodeMatchesGlobalGeo(node) {
    return Boolean(node && nodeInGeo(node, currentGeoScope()));
  }

  function renderDrugFilterOptions() {
    if (!el.drugFilter) return;
    var selected = el.drugFilter.value || '';
    var options = '<option value="">全部药物标签</option>' + drugCatalog
      .filter(function (drug) { return Number(drug.article_count || 0) > 0; })
      .map(function (drug) {
        return '<option value="' + escapeHtml(drug.id) + '">' + escapeHtml(drug.label) + '</option>';
      }).join('');
    el.drugFilter.innerHTML = options;
    el.drugFilter.value = drugCatalog.some(function (drug) { return drug.id === selected; }) ? selected : '';
  }

  function paperHasDrug(pmid, drugId) {
    if (!drugId) return true;
    return Boolean(papers[pmid] && (papers[pmid].drug_tags || []).indexOf(drugId) !== -1);
  }

  function edgeDisplayWeight(edge) {
    var drugId = currentDrugId();
    if (!drugId) return Number(edge.edge_weight || edge.weight || 0);
    return Number((edge.drug_counts || {})[drugId] || 0);
  }

  function edgePaperIds(edge) {
    return (edge.paper_ids || []).filter(function (pmid) { return paperHasDrug(pmid, currentDrugId()); });
  }

  function edgeForDisplay(edge) {
    var displayWeight = edgeDisplayWeight(edge);
    if (!displayWeight) return null;
    return Object.assign({}, edge, { display_weight: displayWeight });
  }

  function graphNodePaperCount(node) {
    var drugId = currentDrugId();
    return drugId ? Number((node.drug_counts || {})[drugId] || 0) : Number(node.paper_count || 0);
  }

  function allAuthorNodePaperCount(node) {
    var drugId = currentDrugId();
    return drugId ? Number((node.all_author_drug_counts || {})[drugId] || 0) : Number(node.all_author_paper_count || 0);
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
        var displayEdge = edgeForDisplay(edge);
        if (displayEdge && (visibleNodeIds[edge.source] || visibleNodeIds[edge.target])) {
          visibleEdges.push(displayEdge);
          visibleNodeIds[edge.source] = true;
          visibleNodeIds[edge.target] = true;
        }
      });
    } else {
      edges.forEach(function (edge) {
        if (!edgeInGeo(edge, geoScope)) return;
        var displayEdge = edgeForDisplay(edge);
        if (!displayEdge || displayEdge.display_weight < minWeight) return;
        visibleEdges.push(displayEdge);
        visibleNodeIds[edge.source] = true;
        visibleNodeIds[edge.target] = true;
      });
    }

    var degreeById = {};
    visibleEdges.forEach(function (edge) {
      degreeById[edge.source] = (degreeById[edge.source] || 0) + edge.display_weight;
      degreeById[edge.target] = (degreeById[edge.target] || 0) + edge.display_weight;
    });
    var visibleNodes = nodes.filter(function (node) { return visibleNodeIds[node.id]; });
    if (!visibleNodes.length) {
      visibleNodes = nodes.filter(function (node) {
        return nodeInGeo(node, geoScope) && graphNodePaperCount(node) > 0;
      }).slice(0, 42);
    }
    visibleNodes.sort(function (a, b) {
      return (degreeById[b.id] || 0) - (degreeById[a.id] || 0) ||
        graphNodePaperCount(b) - graphNodePaperCount(a) ||
        Number(b.paper_count || 0) - Number(a.paper_count || 0) || a.label.localeCompare(b.label);
    });
    var maxNodes = query ? 72 : 64;
    if (visibleNodes.length > maxNodes) {
      var keep = {};
      visibleNodes.slice(0, maxNodes).forEach(function (node) { keep[node.id] = true; });
      visibleNodes = visibleNodes.slice(0, maxNodes);
      visibleEdges = visibleEdges.filter(function (edge) { return keep[edge.source] && keep[edge.target]; });
    }
    return { nodes: visibleNodes, edges: visibleEdges, degreeById: degreeById };
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
    var geoScope = currentGeoScope();
    var graphPaperIds = {};
    var allAuthorPaperIds = {};
    var graphNodes = nodes.filter(function (node) {
      if (!nodeInGeo(node, geoScope) || !graphNodePaperCount(node)) return false;
      var ids = currentDrugId() ? ((node.drug_paper_ids || {})[currentDrugId()] || []) : (node.paper_ids || []);
      ids.forEach(function (pmid) { graphPaperIds[pmid] = true; });
      return true;
    });
    var allAuthorNodes = nodes.filter(function (node) {
      if (!nodeInGeo(node, geoScope) || !allAuthorNodePaperCount(node)) return false;
      var ids = currentDrugId() ? ((node.all_author_drug_paper_ids || {})[currentDrugId()] || []) : (node.all_author_paper_ids || []);
      ids.forEach(function (pmid) { allAuthorPaperIds[pmid] = true; });
      return true;
    });
    var graphEdges = edges.filter(function (edge) {
      return edgeInGeo(edge, geoScope) && edgeDisplayWeight(edge) > 0;
    });
    var items = [
      { label: '联络作者文献', value: compactNumber(Object.keys(graphPaperIds).length), note: 'first/corresponding' },
      { label: '合作图医院', value: compactNumber(graphNodes.length), note: 'first/corresponding' },
      { label: '合作边', value: compactNumber(graphEdges.length), note: 'first/corresponding co-occurrence' },
      { label: '全作者文献', value: compactNumber(Object.keys(allAuthorPaperIds).length), note: 'all-author affiliations' },
      { label: '全作者医院', value: compactNumber(allAuthorNodes.length), note: 'province evidence map' }
    ];
    el.stats.innerHTML = items.map(function (item) {
      return '<article class="knowledge-stat-card"><span>' + escapeHtml(item.label) + '</span><strong>' +
        escapeHtml(item.value) + '</strong><em>' + escapeHtml(item.note) + '</em></article>';
    }).join('');
  }

  function layoutNodes(graphNodes, graphEdges) {
    var width = 1240;
    var height = 720;
    var cx = width / 2;
    var cy = height / 2;
    var count = graphNodes.length || 1;
    var positioned = {};
    graphNodes.forEach(function (node, index) {
      var ring = index < 8 ? 150 : (index < 24 ? 270 : 390);
      var ringIndex = index < 8 ? index : index < 24 ? index - 8 : index - 24;
      var ringCount = index < 8 ? 8 : index < 24 ? 16 : Math.max(1, count - 24);
      var angle = (Math.PI * 2 * ringIndex / ringCount) - Math.PI / 2;
      positioned[node.id] = Object.assign({}, node, {
        x: cx + Math.cos(angle) * ring,
        y: cy + Math.sin(angle) * ring * 0.7,
        vx: 0,
        vy: 0,
        r: Math.max(8, Math.min(24, 8 + Math.sqrt(graphNodePaperCount(node)) * 1.35))
      });
    });
    var links = (graphEdges || []).filter(function (edge) {
      return positioned[edge.source] && positioned[edge.target];
    });
    for (var iteration = 0; iteration < 90; iteration += 1) {
      graphNodes.forEach(function (node) {
        var point = positioned[node.id];
        point.vx += (cx - point.x) * 0.0008;
        point.vy += (cy - point.y) * 0.0008;
      });
      for (var i = 0; i < graphNodes.length; i += 1) {
        var a = positioned[graphNodes[i].id];
        for (var j = i + 1; j < graphNodes.length; j += 1) {
          var b = positioned[graphNodes[j].id];
          var dx = b.x - a.x;
          var dy = b.y - a.y;
          var distance = Math.max(24, Math.sqrt(dx * dx + dy * dy));
          var force = 1900 / (distance * distance);
          var fx = dx / distance * force;
          var fy = dy / distance * force;
          a.vx -= fx;
          a.vy -= fy;
          b.vx += fx;
          b.vy += fy;
        }
      }
      links.forEach(function (edge) {
        var source = positioned[edge.source];
        var target = positioned[edge.target];
        var dx = target.x - source.x;
        var dy = target.y - source.y;
        var distance = Math.max(24, Math.sqrt(dx * dx + dy * dy));
        var force = (distance - 170) * 0.0025 * Math.min(3, Number(edge.display_weight || edge.edge_weight || 1));
        var fx = dx / distance * force;
        var fy = dy / distance * force;
        source.vx += fx;
        source.vy += fy;
        target.vx -= fx;
        target.vy -= fy;
      });
      graphNodes.forEach(function (node) {
        var point = positioned[node.id];
        point.vx *= 0.86;
        point.vy *= 0.86;
        point.x = Math.max(45, Math.min(width - 45, point.x + point.vx));
        point.y = Math.max(42, Math.min(height - 42, point.y + point.vy));
      });
    }
    return positioned;
  }

  function edgeTitle(edge) {
    var source = nodesById[edge.source] || {};
    var target = nodesById[edge.target] || {};
    var weight = edge.display_weight == null ? edgeDisplayWeight(edge) : edge.display_weight;
    return (source.label || edge.source) + ' ↔ ' + (target.label || edge.target) + ' · ' + weight + ' papers' +
      (currentDrugId() ? ' · ' + ((drugById[currentDrugId()] || {}).label || currentDrugId()) : '');
  }

  function renderGraph() {
    if (!el.canvas) return;
    if (!payload) {
      el.canvas.innerHTML = '<text x="40" y="80" fill="#64748b">china-author-network.js 未生成</text>';
      return;
    }
    var graph = filteredGraph();
    var positioned = layoutNodes(graph.nodes, graph.edges);
    el.canvas.setAttribute('viewBox', '0 0 1240 720');
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
      var weight = Number(edge.display_weight || edge.edge_weight || edge.weight || 1);
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
      var hit = document.createElementNS(svgNs, 'line');
      setSvgAttrs(hit, {
        x1: source.x,
        y1: source.y,
        x2: target.x,
        y2: target.y,
        class: 'china-network-edge-hit',
        'data-edge-id': edge.id,
        stroke: 'transparent',
        'stroke-width': 16,
        'pointer-events': 'stroke',
        tabindex: 0,
        'aria-label': edgeTitle(edge)
      });
      edgeGroup.appendChild(hit);
    });

    graph.nodes.forEach(function (node) {
      var point = positioned[node.id];
      var group = document.createElementNS(svgNs, 'g');
      setSvgAttrs(group, {
        class: 'kg-node china-network-node' + (node.id === activeNodeId ? ' active' : ''),
        'data-node-id': node.id,
        tabindex: 0,
        role: 'button',
        'aria-label': node.label + ' · ' + (node.city || node.province || '')
      });
      var circle = document.createElementNS(svgNs, 'circle');
      setSvgAttrs(circle, { cx: point.x, cy: point.y, r: point.r });
      var text = document.createElementNS(svgNs, 'text');
      setSvgAttrs(text, { x: point.x, y: point.y + point.r + 13 });
      text.textContent = displayNodeLabel(node);
      var title = document.createElementNS(svgNs, 'title');
      title.textContent = node.label + ' · 当前上下文第一/通讯作者文献 ' + graphNodePaperCount(node);
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

  function displayNodeLabel(node) {
    var label = node.label || '';
    var generic = /first|second|third|fourth|fifth|affiliated|people|provincial|general|central/i.test(label);
    if (generic && node.city && label.toLowerCase().indexOf(String(node.city).toLowerCase()) === -1) {
      label += ' · ' + node.city;
    }
    return shortLabel(label);
  }

  function bindGraphEvents() {
    Array.prototype.forEach.call(el.canvas.querySelectorAll('[data-node-id]'), function (nodeEl) {
      nodeEl.addEventListener('click', function () {
        selectNode(nodeEl.getAttribute('data-node-id'));
      });
      nodeEl.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          selectNode(nodeEl.getAttribute('data-node-id'));
        }
      });
    });
    Array.prototype.forEach.call(el.canvas.querySelectorAll('[data-edge-id]'), function (edgeEl) {
      edgeEl.addEventListener('click', function () {
        selectEdge(edgeEl.getAttribute('data-edge-id'));
      });
      edgeEl.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          selectEdge(edgeEl.getAttribute('data-edge-id'));
        }
      });
    });
  }

  function renderLegend(graph) {
    if (!el.legend) return;
    var query = currentQuery();
    var minWeight = currentEdgeMin();
    var geoScope = currentGeoScope();
    var note = query ? '搜索模式：展开匹配医院的全部合作边' : '当前阈值：edge_weight ≥' + minWeight;
    note += '；线 = 第一/通讯作者医院共现 PMID，节点大小 = 第一/通讯作者文献量';
    if (currentDrugId()) note += '；当前按药物标签：' + ((drugById[currentDrugId()] || {}).label || currentDrugId());
    if (!graph.edges.length) {
      note += '；当前筛选无合作边，已显示该地区发文量最高的医院节点';
    }
    el.legend.innerHTML = '<span class="kg-legend-item"><span class="kg-legend-dot disease"></span>' +
      escapeHtml(geoScope === 'all' ? '大中华全部' : geoScope) + '</span>' +
      '<span class="kg-legend-item" style="color:var(--fg3)">' + escapeHtml(note) + '</span>';
  }

  function incidentEdges(nodeId) {
    return edges.filter(function (edge) {
      return (edge.source === nodeId || edge.target === nodeId) && edgeInGeo(edge, currentGeoScope());
    })
      .map(edgeForDisplay)
      .filter(Boolean)
      .sort(function (a, b) { return b.display_weight - a.display_weight; });
  }

  function selectNode(nodeId) {
    activeNodeId = nodeId;
    activeEdgeId = '';
    activeDetail = { type: 'node', id: nodeId };
    renderGraph();
    var node = nodesById[nodeId];
    if (!el.detail) return;
    if (!node || !nodeMatchesGlobalGeo(node)) {
      renderContextEmpty('医院联络视图', '第一作者 + 通讯作者医院', node ? node.label : nodeId, '所选医院不在当前地域范围内。');
      return;
    }
    var nodeDrugId = currentDrugId();
    var nodePaperIds = nodeDrugId
      ? ((node.drug_paper_ids || {})[nodeDrugId] || [])
      : (node.paper_ids || []);
    if (!nodePaperIds.length) {
      renderContextEmpty('医院联络视图', '第一作者 + 通讯作者医院', node.label, '所选医院没有符合当前药物标签的联络作者文献。');
      return;
    }
    var nodeEdges = incidentEdges(nodeId);
    var collaborators = nodeEdges.slice(0, 20).map(function (edge) {
      var otherId = edge.source === nodeId ? edge.target : edge.source;
      var other = nodesById[otherId] || { label: otherId };
      return '<li><button type="button" class="matrix-node-link" data-china-edge="' + escapeHtml(edge.id) + '">' +
        escapeHtml(other.label) + '</button><br><span class="kg-ref-meta">edge_weight ' +
        escapeHtml(edge.display_weight) + ' · PMID ' + escapeHtml(edgePaperIds(edge).slice(0, 4).join(', ')) + '</span></li>';
    }).join('');
    var contextPaperCount = nodeDrugId ? Number((node.drug_counts || {})[nodeDrugId] || 0) : Number(node.paper_count || 0);
    var nodeMetadata = nodeDrugId ? '' :
      '<div class="kg-detail-section"><h4>代表作者</h4>' + renderMiniTags(node.top_authors, 'label') + '</div>' +
      '<div class="kg-detail-section"><h4>主题</h4>' + renderMiniTags(node.top_topics, 'label') + '</div>';
    el.detail.innerHTML = renderDetailContext('医院联络视图', '第一作者 + 通讯作者医院；文献与合作边同口径') +
      '<div class="kg-detail-head"><h3>' + escapeHtml(node.label) + '</h3><span>' +
      escapeHtml(node.region || node.geo_scope || '') + '</span></div>' +
      '<div class="kg-detail-section"><h4>节点概况</h4><p>' +
      '当前上下文联络作者文献 ' + escapeHtml(contextPaperCount) + ' 篇 · 当前上下文合作医院 ' + escapeHtml(nodeEdges.length) + '</p></div>' +
      '<div class="kg-detail-section"><h4>合作医院</h4><ul class="kg-study-list">' +
      (collaborators || '<li class="kg-ref-meta">暂无合作边；可能是单中心或未达到当前图谱筛选阈值。</li>') + '</ul></div>' +
      nodeMetadata +
      '<div class="kg-detail-section"><h4>药物标签</h4>' + renderDrugCounts(node.drug_counts, '第一/通讯作者文献') + '</div>' +
      '<div class="kg-detail-section"><h4>文献 · 联络作者口径</h4>' + renderPaperList(nodePaperIds) + '</div>';
    bindDetailEdgeButtons();
  }

  function selectEdge(edgeId) {
    activeEdgeId = edgeId;
    activeNodeId = '';
    activeDetail = { type: 'edge', id: edgeId };
    renderGraph();
    var edge = edges.filter(function (item) { return item.id === edgeId; })[0];
    if (!el.detail) return;
    if (!edge || !edgeInGeo(edge, currentGeoScope())) {
      renderContextEmpty('医院合作', '第一作者 + 通讯作者医院共现', edgeId, '所选合作边不在当前地域范围内。');
      return;
    }
    var source = nodesById[edge.source] || { label: edge.source };
    var target = nodesById[edge.target] || { label: edge.target };
    var displayWeight = edgeDisplayWeight(edge);
    var paperIds = edgePaperIds(edge);
    if (!displayWeight || !paperIds.length) {
      renderContextEmpty('医院合作', '第一作者 + 通讯作者医院共现', source.label + ' ↔ ' + target.label, '所选合作边没有符合当前药物标签的文献。');
      return;
    }
    var edgeMetadata = currentDrugId() ? '' :
      '<div class="kg-detail-section"><h4>合作主题</h4>' + renderMiniTags(edge.top_topics, 'label') + '</div>' +
      '<div class="kg-detail-section"><h4>第一/通讯作者</h4>' + renderMiniTags(edge.top_authors, 'label') + '</div>';
    el.detail.innerHTML = renderDetailContext('医院合作', '第一作者 + 通讯作者医院共现；edge_weight 为去重 PMID 数') +
      '<div class="kg-detail-head"><h3>' + escapeHtml(source.label) + ' ↔ ' + escapeHtml(target.label) +
      '</h3><span>edge_weight ' + escapeHtml(displayWeight) + '</span></div>' +
      edgeMetadata +
      '<div class="kg-detail-section"><h4>药物标签</h4>' + renderDrugCounts(edge.drug_counts, '合作文献') + '</div>' +
      '<div class="kg-detail-section"><h4>合作 PMID</h4>' + renderPaperList(paperIds) + '</div>';
  }

  function renderMiniTags(items, key) {
    items = items || [];
    if (!items.length) return '<p class="kg-ref-meta">暂无</p>';
    return '<div class="signal-topic-row">' + items.slice(0, 10).map(function (item) {
      return '<span class="signal-topic">' + escapeHtml(item[key] || item.label || '') + ' ' + escapeHtml(item.count || '') + '</span>';
    }).join('') + '</div>';
  }

  function renderDrugCounts(counts, basis) {
    var items = Object.keys(counts || {}).map(function (id) {
      return { id: id, label: (drugById[id] || {}).label || id, count: Number(counts[id] || 0) };
    }).filter(function (item) { return item.count > 0 && (!currentDrugId() || item.id === currentDrugId()); })
      .sort(function (a, b) { return b.count - a.count || a.label.localeCompare(b.label); });
    if (!items.length) return '<p class="kg-ref-meta">暂无药物标签</p>';
    return '<div class="signal-topic-row">' + items.map(function (item) {
      return '<span class="signal-drug">' + escapeHtml(item.label) + ' · ' + escapeHtml(item.count) + '篇' +
        (basis ? ' · ' + escapeHtml(basis) : '') + '</span>';
    }).join('') + '</div>';
  }

  function renderPaperDrugTags(paper) {
    var tags = (paper.drug_tags || []).map(function (id) { return (drugById[id] || {}).label || id; });
    if (!tags.length) return '';
    return '<br><span class="kg-ref-meta">药物标签：' + escapeHtml(tags.join('；')) + '</span>';
  }

  function paperDateKey(pmid) {
    var paper = papers[pmid] || {};
    return String(paper.entry_date || paper.pub_date || '').replace(/\//g, '-');
  }

  function latestFirst(pmids) {
    return (pmids || []).slice().sort(function (a, b) {
      return paperDateKey(b).localeCompare(paperDateKey(a)) || String(b).localeCompare(String(a));
    });
  }

  function renderPaperList(pmids, limit, includeGraphAuthors) {
    pmids = latestFirst(pmids);
    if (limit != null) pmids = pmids.slice(0, limit);
    if (!pmids.length) return '<p class="kg-ref-meta">暂无 PMID</p>';
    return '<ul class="kg-study-list">' + pmids.map(function (pmid) {
      var paper = papers[pmid] || { pmid: pmid };
      var authorLine = includeGraphAuthors === false ? '' : renderPaperAuthors(paper);
      return '<li><a class="text-link" href="' + escapeHref(pubmedUrl(pmid)) + '" target="_blank" rel="noopener">' +
        escapeHtml(paper.title || ('PMID ' + pmid)) + '</a><br><span class="kg-ref-meta">PMID ' + escapeHtml(pmid) +
        ((paper.entry_date || paper.pub_date) ? ' · ' + escapeHtml(paper.entry_date || paper.pub_date) : '') +
        (paper.journal ? ' · ' + escapeHtml(paper.journal) : '') + (paper.evidence_level ? ' · Level ' + escapeHtml(paper.evidence_level) : '') +
        '</span>' + renderPaperDrugTags(paper) + authorLine + '</li>';
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

  var MAP_PROVINCE_BY_ID = {
    anhui: 'Anhui', beijing: 'Beijing', chongqing: 'Chongqing', fujian: 'Fujian',
    gansu: 'Gansu', guangdong: 'Guangdong', 'guangxi-zhuang': 'Guangxi', guizhou: 'Guizhou',
    hainan: 'Hainan', hebei: 'Hebei', heilongjiang: 'Heilongjiang', henan: 'Henan',
    'hong-kong': 'Hong Kong', hubei: 'Hubei', hunan: 'Hunan', jiangsu: 'Jiangsu',
    jiangxi: 'Jiangxi', jilin: 'Jilin', liaoning: 'Liaoning', macau: 'Macau',
    'nei-mongol': 'Inner Mongolia', 'ningxia-hui': 'Ningxia', quinghai: 'Qinghai',
    shaanxi: 'Shaanxi', shandong: 'Shandong', shanghai: 'Shanghai', shanxi: 'Shanxi',
    sichuan: 'Sichuan', tianjin: 'Tianjin', 'xinjiang-uygur': 'Xinjiang', xizang: 'Tibet',
    yunnan: 'Yunnan', zhejiang: 'Zhejiang'
  };
  var MAP_COLORS = ['#eef5fb', '#d7e8f6', '#b7d5ec', '#86b9de', '#4e91c4', '#1f659b'];

  function mapAssetUrl() {
    return hub.assetUrl ? hub.assetUrl('assets/china-provinces.svg') : 'assets/china-provinces.svg';
  }

  function loadChinaMap(callback) {
    if (chinaMapTemplate) { callback(true); return; }
    chinaMapCallbacks.push(callback);
    if (chinaMapLoading) return;
    chinaMapLoading = true;
    fetch(mapAssetUrl(), { cache: 'force-cache' }).then(function (response) {
      if (!response.ok) throw new Error('map HTTP ' + response.status);
      return response.text();
    }).then(function (text) {
      var doc = new DOMParser().parseFromString(text, 'image/svg+xml');
      var svg = doc.documentElement;
      if (!svg || svg.nodeName.toLowerCase() !== 'svg') throw new Error('invalid SVG map');
      chinaMapTemplate = svg;
      chinaMapLoading = false;
      var callbacks = chinaMapCallbacks.slice();
      chinaMapCallbacks = [];
      callbacks.forEach(function (cb) { if (cb) cb(true); });
    }).catch(function (error) {
      chinaMapLoading = false;
      chinaMapTemplate = null;
      var callbacks = chinaMapCallbacks.slice();
      chinaMapCallbacks = [];
      console.warn('China province map load failed:', error);
      callbacks.forEach(function (cb) { if (cb) cb(false); });
    });
  }

  function provinceHeatmapStats() {
    var stats = {};
    heatmap.forEach(function (row) {
      if (row.geo_scope !== 'mainland') return;
      var province = row.province || '';
      if (!province || province === 'Mainland China') return;
      var item = stats[province] || {
        province: province, paper_count: 0, hospital_count: 0,
        all_author_occurrences: 0, top_hospitals: {}, paper_ids: {}, drug_counts: {}
      };
      var rowPaperIds = currentDrugId() ? ((row.drug_paper_ids || {})[currentDrugId()] || []) : (row.paper_ids || []);
      rowPaperIds.forEach(function (pmid) { item.paper_ids[pmid] = true; });
      item.paper_count = Object.keys(item.paper_ids).length;
      item.hospital_count += Number(row.hospital_count || 0);
      item.all_author_occurrences += Number(row.all_author_occurrences || 0);
      Object.keys(row.drug_counts || {}).forEach(function (drugId) {
        item.drug_counts[drugId] = (item.drug_counts[drugId] || 0) + Number(row.drug_counts[drugId] || 0);
      });
      (row.top_hospitals || []).forEach(function (hospital) {
        var id = hospital.id || hospital.label;
        var previous = item.top_hospitals[id] || { id: id, label: hospital.label, count: 0 };
        previous.count += Number(hospital.count || 0);
        item.top_hospitals[id] = previous;
      });
      stats[province] = item;
    });
    Object.keys(stats).forEach(function (province) {
      stats[province].top_hospitals = Object.keys(stats[province].top_hospitals).map(function (id) {
        return stats[province].top_hospitals[id];
      }).sort(function (a, b) { return b.count - a.count || a.label.localeCompare(b.label); }).slice(0, 10);
      if (currentDrugId()) {
        stats[province].hospital_count = nodes.filter(function (node) {
          return node.geo_scope === 'mainland' && node.province === province && allAuthorNodePaperCount(node) > 0;
        }).length;
      }
      delete stats[province].paper_ids;
    });
    return stats;
  }

  function provinceHospitalRanking(province) {
    var drugId = currentDrugId();
    return nodes.filter(function (node) {
      return node.geo_scope === 'mainland' && node.province === province;
    }).map(function (node) {
      return {
        id: node.id,
        label: node.label,
        count: drugId ? Number((node.all_author_drug_counts || {})[drugId] || 0) : Number(node.all_author_paper_count || 0)
      };
    }).filter(function (item) { return item.count > 0; })
      .sort(function (a, b) { return b.count - a.count || a.label.localeCompare(b.label); })
      .slice(0, 10);
  }

  function mapFill(value, maximum) {
    if (!value || !maximum) return MAP_COLORS[0];
    var index = Math.min(MAP_COLORS.length - 1, Math.max(1, Math.ceil(value / maximum * (MAP_COLORS.length - 1))));
    return MAP_COLORS[index];
  }

  function heatmapRowPaperCount(row) {
    var drugId = currentDrugId();
    return drugId ? Number((row.drug_counts || {})[drugId] || 0) : Number(row.paper_count || 0);
  }

  function bindDetailHospitalButtons() {
    if (!el.detail) return;
    Array.prototype.forEach.call(el.detail.querySelectorAll('[data-china-hospital]'), function (button) {
      button.addEventListener('click', function () {
        showHospitalDetail(button.getAttribute('data-china-hospital'), button.getAttribute('data-china-province') || '');
      });
    });
  }

  function showHospitalDetail(hospitalId, province) {
    if (!el.detail) return;
    activeDetail = { type: 'mapHospital', id: hospitalId, province: province || '' };
    var node = nodesById[hospitalId];
    if (!node || !nodeMatchesGlobalGeo(node)) {
      renderContextEmpty('医院全作者文献', '全部作者 affiliation', node ? node.label : hospitalId, '所选医院不在当前地域范围内。');
      return;
    }
    var drugId = currentDrugId();
    var pmids = latestFirst(drugId
      ? ((node.all_author_drug_paper_ids || {})[drugId] || [])
      : (node.all_author_paper_ids || node.paper_ids || []));
    var drugLabel = drugId ? ((drugById[drugId] || {}).label || drugId) : '';
    if (!pmids.length) {
      renderContextEmpty('医院全作者文献', '全部作者 affiliation', node.label, '所选医院没有符合当前药物标签的全作者文献。');
      return;
    }
    var contextPaperCount = drugId ? Number((node.all_author_drug_counts || {})[drugId] || 0) : Number(node.all_author_paper_count || 0);
    el.detail.innerHTML = renderDetailContext('医院全作者文献', '全部作者 affiliation；医院文献按去重 PMID') +
      '<div class="kg-detail-head"><h3>' + escapeHtml(node.label) + '</h3><span>' +
      escapeHtml(province || node.province || node.region || '') + '</span></div>' +
      '<div class="kg-detail-section"><h4>医院文献概况</h4><p>当前上下文全作者文献 ' + escapeHtml(contextPaperCount) +
      (drugLabel ? ' 篇 · ' + escapeHtml(drugLabel) + '相关' : ' 篇') +
      ' · 以下按最新入库/发表信息倒序。</p></div>' +
      '<div class="kg-detail-section"><h4>药物标签</h4>' + renderDrugCounts(node.all_author_drug_counts, '全作者文献') + '</div>' +
      '<div class="kg-detail-section"><h4>文献清单</h4>' + renderPaperList(pmids, null, false) + '</div>';
  }

  function showProvinceDetail(province, row) {
    if (!el.detail) return;
    activeDetail = { type: 'province', province: province };
    if (currentGeoScope() !== 'mainland' && currentGeoScope() !== 'all') {
      renderContextEmpty('省级全作者分布', '全部作者 affiliation；省级文献按去重 PMID', province, '当前地域不使用中国大陆省级分布。');
      return;
    }
    row = row || { paper_count: 0, hospital_count: 0, all_author_occurrences: 0, top_hospitals: [] };
    if (!Number(row.paper_count || 0)) {
      renderContextEmpty('省级全作者分布', '全部作者 affiliation；省级文献按去重 PMID', province, '所选省份没有符合当前药物标签的文献。');
      return;
    }
    var top = provinceHospitalRanking(province).map(function (item) {
      return '<li><button type="button" class="matrix-node-link" data-china-hospital="' + escapeHtml(item.id || '') +
        '" data-china-province="' + escapeHtml(province) + '">' + escapeHtml(item.label) + '</button><br><span class="kg-ref-meta">' +
        escapeHtml(item.count) + ' 篇全作者 PMID</span></li>';
    }).join('');
    var drugLabel = currentDrugId() ? ((drugById[currentDrugId()] || {}).label || currentDrugId()) : '';
    var occurrenceText = currentDrugId() ? '' : ' · ' + escapeHtml(row.all_author_occurrences || 0) + ' 次 affiliation 出现';
    el.detail.innerHTML = renderDetailContext('省级全作者分布', '全部作者 affiliation；省级文献按去重 PMID') +
      '<div class="kg-detail-head"><h3>' + escapeHtml(province) + '</h3><span>全作者热力线索</span></div>' +
      '<div class="kg-detail-section"><h4>省级聚合</h4><p>' + escapeHtml(row.paper_count || 0) + ' 篇去重 PMID · ' +
      escapeHtml(row.hospital_count || 0) + ' 个医院节点' + occurrenceText + '</p></div>' +
      (drugLabel ? '<div class="kg-detail-section"><h4>当前药物标签</h4><p>' + escapeHtml(drugLabel) + ' · ' + escapeHtml((row.drug_counts || {})[currentDrugId()] || 0) + ' 篇文本命中文献</p></div>' : '') +
      '<div class="kg-detail-section"><h4>医院排名</h4><p class="kg-ref-meta">点击医院查看最新文献清单。</p><ul class="kg-study-list">' + (top || '<li>暂无</li>') + '</ul></div>';
    bindDetailHospitalButtons();
  }

  function renderProvinceMap() {
    var stats = provinceHeatmapStats();
    var values = Object.keys(stats).map(function (province) { return stats[province].paper_count; });
    var maximum = Math.max.apply(Math, values.concat([0]));
    var sorted = Object.keys(stats).sort(function (a, b) {
      return stats[b].paper_count - stats[a].paper_count || a.localeCompare(b);
    });
    var drugLabel = currentDrugId() ? ((drugById[currentDrugId()] || {}).label || currentDrugId()) : '';
    el.heatmap.innerHTML = '<div class="china-network-map-head"><div><h3>全作者医院热力线索 · 中国省级图</h3><p>颜色 = ' + (drugLabel ? escapeHtml(drugLabel) + '相关' : '省级') + '去重 PMID 数；点击省份查看医院排名，点击医院查看最新文献清单。</p></div>' +
      '<span class="china-network-map-source">单层可编辑省级 SVG · 审图号 GS（2016）2923号</span></div>' +
      '<div class="china-network-map-layout"><div class="china-network-map-canvas" id="chinaNetworkMapCanvas"></div><aside class="china-network-map-rank"><h4>省级排行</h4><ol>' +
      sorted.slice(0, 8).map(function (province) {
        return '<li><span>' + escapeHtml(province) + '</span><strong>' + escapeHtml(stats[province].paper_count) + ' 篇</strong></li>';
      }).join('') + '</ol></aside></div>' +
      '<div class="china-network-map-legend"><span>低</span><i style="background:' + MAP_COLORS[0] + '"></i><i style="background:' + MAP_COLORS[2] + '"></i><i style="background:' + MAP_COLORS[4] + '"></i><i style="background:' + MAP_COLORS[5] + '"></i><span>高</span></div>';

    var mapCanvas = document.getElementById('chinaNetworkMapCanvas');
    mapCanvas.innerHTML = '<div class="china-editable-map-shell"></div>';
    var mapShell = mapCanvas.querySelector('.china-editable-map-shell');
    var svg = chinaMapTemplate.cloneNode(true);
    svg.classList.add('china-province-map');
    svg.setAttribute('role', 'group');
    svg.setAttribute('aria-label', '中国省级医院情报热力图，审图号 GS（2016）2923号');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    Array.prototype.forEach.call(svg.querySelectorAll('path[id]'), function (path) {
      var province = MAP_PROVINCE_BY_ID[path.getAttribute('id')];
      if (!province) return;
      var row = stats[province];
      path.classList.add('china-province');
      path.style.fill = mapFill(row ? row.paper_count : 0, maximum);
      path.setAttribute('tabindex', '0');
      path.setAttribute('role', 'button');
      path.setAttribute('aria-label', province + ' · ' + (row ? row.paper_count : 0) + ' 篇');
      var title = document.createElementNS(svgNs, 'title');
      title.textContent = province + ' · ' + (row ? row.paper_count : 0) + ' 篇 · ' + (row ? row.hospital_count : 0) + ' 个医院节点';
      path.appendChild(title);
      path.addEventListener('click', function () { showProvinceDetail(province, row); });
      path.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          showProvinceDetail(province, row);
        }
      });
    });
    var auditText = document.createElementNS(svgNs, 'text');
    setSvgAttrs(auditText, { x: 14, y: 558, class: 'china-map-audit-label' });
    auditText.textContent = '审图号 GS（2016）2923号';
    svg.appendChild(auditText);
    mapShell.appendChild(svg);
  }

  function renderRegionalHeatmapCards() {
    var geoScope = currentGeoScope();
    var rows = heatmap.filter(function (row) { return geoScope === 'all' ? row.geo_scope !== 'mainland' : row.geo_scope === geoScope; })
      .sort(function (a, b) { return heatmapRowPaperCount(b) - heatmapRowPaperCount(a); }).slice(0, 8);
    var drugLabel = currentDrugId() ? ((drugById[currentDrugId()] || {}).label || currentDrugId()) : '';
    el.heatmap.innerHTML = '<div class="china-network-map-head"><div><h3>全作者医院热力线索</h3><p>该筛选层没有对应的省级底图，先按独立地区展示去重 PMID 与医院排行。</p></div></div>' +
      '<div class="china-network-heatmap-grid">' + rows.map(function (row) {
        var top = (row.top_hospitals || []).slice(0, 3).map(function (item) { return item.label + ' ' + item.count; }).join('；');
        return '<article class="china-network-heatmap-card"><span>' + escapeHtml(row.province || row.region || row.geo_scope) + '</span><strong>' +
          escapeHtml(heatmapRowPaperCount(row)) + ' 篇' + (drugLabel ? ' · ' + escapeHtml(drugLabel) : '') + '</strong><em>' + escapeHtml(row.hospital_count || 0) + ' hospitals · ' +
          escapeHtml(row.all_author_occurrences || 0) + ' affiliations</em><p>' + escapeHtml(top || '—') + '</p></article>';
      }).join('') + '</div>';
  }

  function renderHeatmap() {
    if (!el.heatmap || !payload) return;
    var geoScope = currentGeoScope();
    if (geoScope !== 'mainland' && geoScope !== 'all') {
      renderRegionalHeatmapCards();
      return;
    }
    if (!chinaMapTemplate) {
      el.heatmap.innerHTML = '<div class="kg-empty-hint">正在加载中国省级底图…</div>';
      loadChinaMap(function (ok) {
        if (ok) renderHeatmap();
        else el.heatmap.innerHTML = '<div class="kg-empty-hint">中国省级底图加载失败，已保留地区排行数据。</div>';
      });
      return;
    }
    renderProvinceMap();
  }

  function refresh() {
    refreshData();
    renderBadge();
    renderStats();
    renderGraph();
    renderHeatmap();
  }

  function rerenderActiveDetail() {
    if (!activeDetail) return;
    if (activeDetail.type === 'node') selectNode(activeDetail.id);
    else if (activeDetail.type === 'edge') selectEdge(activeDetail.id);
    else if (activeDetail.type === 'mapHospital') showHospitalDetail(activeDetail.id, activeDetail.province);
    else if (activeDetail.type === 'province') {
      var currentStats = provinceHeatmapStats();
      showProvinceDetail(activeDetail.province, currentStats[activeDetail.province]);
    }
  }

  function clearActiveDetail() {
    activeEdgeId = '';
    activeNodeId = '';
    activeDetail = null;
    if (el.detail) {
      el.detail.innerHTML = '<div class="kg-empty-hint">点击医院节点、合作边或地图省份查看筛选后的详情。</div>';
    }
  }

  function attachFilters() {
    if (filtersAttached) return;
    filtersAttached = true;
    var globalFilterInputs = [el.geo, el.drugFilter];
    var graphFilterInputs = [el.search, el.edgeWeight];
    globalFilterInputs.forEach(function (input) {
      if (!input) return;
      input.addEventListener('change', function () {
        if (!payload) {
          loadAndRender();
          return;
        }
        refresh();
        rerenderActiveDetail();
      });
    });
    graphFilterInputs.forEach(function (input) {
      if (!input) return;
      input.addEventListener(input.tagName === 'INPUT' ? 'input' : 'change', function () {
        if (!payload) {
          loadAndRender();
          return;
        }
        renderGraph();
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
      clearActiveDetail();
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
