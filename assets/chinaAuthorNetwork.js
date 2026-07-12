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
  var chinaMapTemplate = null;
  var chinaMapLoading = false;
  var chinaMapCallbacks = [];

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

    var degreeById = {};
    visibleEdges.forEach(function (edge) {
      degreeById[edge.source] = (degreeById[edge.source] || 0) + Number(edge.edge_weight || edge.weight || 0);
      degreeById[edge.target] = (degreeById[edge.target] || 0) + Number(edge.edge_weight || edge.weight || 0);
    });
    var visibleNodes = nodes.filter(function (node) { return visibleNodeIds[node.id]; });
    if (!visibleNodes.length) {
      visibleNodes = nodes.filter(function (node) { return nodeInGeo(node, geoScope); }).slice(0, 42);
    }
    visibleNodes.sort(function (a, b) {
      return (degreeById[b.id] || 0) - (degreeById[a.id] || 0) ||
        Number(b.all_author_paper_count || 0) - Number(a.all_author_paper_count || 0) ||
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
        r: Math.max(8, Math.min(24, 8 + Math.sqrt(Number(node.all_author_paper_count || node.paper_count || 0)) * 1.35))
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
        var force = (distance - 170) * 0.0025 * Math.min(3, Number(edge.edge_weight || 1));
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
    return (source.label || edge.source) + ' ↔ ' + (target.label || edge.target) + ' · ' + (edge.edge_weight || edge.weight || 0) + ' papers';
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
      title.textContent = node.label + ' · 联络作者文献 ' + (node.paper_count || 0) +
        ' · 全作者文献 ' + (node.all_author_paper_count || 0);
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
    var note = query ? '搜索模式：展开匹配医院的全部合作边' : '默认阈值：edge_weight ≥' + minWeight;
    note += '；线 = 第一/通讯作者医院共现 PMID，节点大小 = 全作者文献量';
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
      '联络作者文献 ' + escapeHtml(node.paper_count || 0) + ' 篇 · 全作者文献 ' + escapeHtml(node.all_author_paper_count || 0) +
      ' 篇 · 第一作者 ' + escapeHtml(node.first_author_paper_count || 0) +
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

  function paperDateKey(pmid) {
    var paper = papers[pmid] || {};
    return String(paper.entry_date || paper.pub_date || '').replace(/\//g, '-');
  }

  function latestFirst(pmids) {
    return (pmids || []).slice().sort(function (a, b) {
      return paperDateKey(b).localeCompare(paperDateKey(a)) || String(b).localeCompare(String(a));
    });
  }

  function renderPaperList(pmids, limit) {
    pmids = latestFirst(pmids).slice(0, limit || 10);
    if (!pmids.length) return '<p class="kg-ref-meta">暂无 PMID</p>';
    return '<ul class="kg-study-list">' + pmids.map(function (pmid) {
      var paper = papers[pmid] || { pmid: pmid };
      var authorLine = renderPaperAuthors(paper);
      return '<li><a class="text-link" href="' + escapeHref(pubmedUrl(pmid)) + '" target="_blank" rel="noopener">' +
        escapeHtml(paper.title || ('PMID ' + pmid)) + '</a><br><span class="kg-ref-meta">PMID ' + escapeHtml(pmid) +
        ((paper.entry_date || paper.pub_date) ? ' · ' + escapeHtml(paper.entry_date || paper.pub_date) : '') +
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

  function standardMapAssetUrl() {
    return hub.assetUrl ? hub.assetUrl('assets/china-standard-map-gs-2016-2923.jpg') : 'assets/china-standard-map-gs-2016-2923.jpg';
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
        all_author_occurrences: 0, top_hospitals: {}
      };
      item.paper_count += Number(row.paper_count || 0);
      item.hospital_count += Number(row.hospital_count || 0);
      item.all_author_occurrences += Number(row.all_author_occurrences || 0);
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
    });
    return stats;
  }

  function mapFill(value, maximum) {
    if (!value || !maximum) return MAP_COLORS[0];
    var index = Math.min(MAP_COLORS.length - 1, Math.max(1, Math.ceil(value / maximum * (MAP_COLORS.length - 1))));
    return MAP_COLORS[index];
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
    var node = nodesById[hospitalId];
    if (!node) {
      el.detail.innerHTML = '<div class="kg-empty-hint">医院节点未找到。</div>';
      return;
    }
    var pmids = latestFirst(node.all_author_paper_ids || node.paper_ids || []);
    el.detail.innerHTML = '<div class="kg-detail-head"><h3>' + escapeHtml(node.label) + '</h3><span>' +
      escapeHtml(province || node.province || node.region || '') + '</span></div>' +
      '<div class="kg-detail-section"><h4>医院文献概况</h4><p>全作者文献 ' + escapeHtml(node.all_author_paper_count || 0) +
      ' 篇 · 联络作者文献 ' + escapeHtml(node.paper_count || 0) + ' 篇 · 以下按最新入库/发表信息倒序。</p></div>' +
      '<div class="kg-detail-section"><h4>文献清单</h4>' + renderPaperList(pmids, 30) + '</div>';
  }

  function showProvinceDetail(province, row) {
    if (!el.detail) return;
    row = row || { paper_count: 0, hospital_count: 0, all_author_occurrences: 0, top_hospitals: [] };
    var top = (row.top_hospitals || []).map(function (item) {
      return '<li><button type="button" class="matrix-node-link" data-china-hospital="' + escapeHtml(item.id || '') +
        '" data-china-province="' + escapeHtml(province) + '">' + escapeHtml(item.label) + '</button><br><span class="kg-ref-meta">' +
        escapeHtml(item.count) + ' 篇全作者 PMID</span></li>';
    }).join('');
    el.detail.innerHTML = '<div class="kg-detail-head"><h3>' + escapeHtml(province) + '</h3><span>全作者热力线索</span></div>' +
      '<div class="kg-detail-section"><h4>省级聚合</h4><p>' + escapeHtml(row.paper_count || 0) + ' 篇去重 PMID · ' +
      escapeHtml(row.hospital_count || 0) + ' 个医院节点 · ' + escapeHtml(row.all_author_occurrences || 0) + ' 次 affiliation 出现</p></div>' +
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
    el.heatmap.innerHTML = '<div class="china-network-map-head"><div><h3>全作者医院热力线索 · 中国省级图</h3><p>颜色 = 省级去重 PMID 数；点击省份查看医院排名，点击医院查看最新文献清单。颜色叠加是情报数据层，底图边界与标注来自规范标准地图。</p></div>' +
      '<span class="china-network-map-source">标准地图：自然资源部 · 审图号 GS（2016）2923号</span></div>' +
      '<div class="china-network-map-layout"><div class="china-network-map-canvas" id="chinaNetworkMapCanvas"></div><aside class="china-network-map-rank"><h4>省级排行</h4><ol>' +
      sorted.slice(0, 8).map(function (province) {
        return '<li><span>' + escapeHtml(province) + '</span><strong>' + escapeHtml(stats[province].paper_count) + ' 篇</strong></li>';
      }).join('') + '</ol></aside></div>' +
      '<div class="china-network-map-legend"><span>低</span><i style="background:' + MAP_COLORS[0] + '"></i><i style="background:' + MAP_COLORS[2] + '"></i><i style="background:' + MAP_COLORS[4] + '"></i><i style="background:' + MAP_COLORS[5] + '"></i><span>高</span></div>';

    var mapCanvas = document.getElementById('chinaNetworkMapCanvas');
    mapCanvas.innerHTML = '<div class="china-standard-map-shell"><img class="china-standard-map-image" src="' + escapeHref(standardMapAssetUrl()) + '" alt="中国地图，审图号 GS（2016）2923号"><svg class="china-standard-map-overlay" viewBox="0 0 1000 707" preserveAspectRatio="none" role="group" aria-label="中国省级情报数据交互层"></svg></div>';
    var overlay = mapCanvas.querySelector('.china-standard-map-overlay');
    var overlayGroup = document.createElementNS(svgNs, 'g');
    overlayGroup.setAttribute('transform', 'translate(80 48) scale(0.995 1)');
    overlay.appendChild(overlayGroup);
    var svg = chinaMapTemplate.cloneNode(true);
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
      overlayGroup.appendChild(path);
    });
  }

  function renderRegionalHeatmapCards() {
    var geoScope = currentGeoScope();
    var rows = heatmap.filter(function (row) { return geoScope === 'all' ? row.geo_scope !== 'mainland' : row.geo_scope === geoScope; })
      .sort(function (a, b) { return b.paper_count - a.paper_count; }).slice(0, 8);
    el.heatmap.innerHTML = '<div class="china-network-map-head"><div><h3>全作者医院热力线索</h3><p>该筛选层没有对应的省级底图，先按独立地区展示去重 PMID 与医院排行。</p></div></div>' +
      '<div class="china-network-heatmap-grid">' + rows.map(function (row) {
        var top = (row.top_hospitals || []).slice(0, 3).map(function (item) { return item.label + ' ' + item.count; }).join('；');
        return '<article class="china-network-heatmap-card"><span>' + escapeHtml(row.province || row.region || row.geo_scope) + '</span><strong>' +
          escapeHtml(row.paper_count || 0) + ' 篇</strong><em>' + escapeHtml(row.hospital_count || 0) + ' hospitals · ' +
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
