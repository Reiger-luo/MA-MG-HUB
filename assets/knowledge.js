/* MA-MG-HUB 知识库
 * 数据来源: full PubMed abstract 派生知识图谱。
 * 关系代表标题、摘要与元数据层面的证据线索，不替代全文判断。
 */
(function () {
  'use strict';

  var hub = window.MgHub || {};
  var graphData = window.MG_KNOWLEDGE_GRAPH || {};
  var graphHealthData = window.MG_GRAPH_HEALTH || { summary: {}, health: {} };
  var nodes = graphData.nodes || [];
  var coreEdges = graphData.edges || [];
  var allEdges = graphData.all_edges || coreEdges;
  var edges = coreEdges;
  var nodeRefs = graphData.node_references || {};
  var matrixRows = graphData.evidence_matrix || [];
  var curatedData = window.MG_CURATED_TOPICS || { topics: [], bridge_by_node: {}, stats: {} };
  var curatedTopics = curatedData.topics || [];
  var topicsById = {};
  curatedTopics.forEach(function (topic) { topicsById[topic.id] = topic; });
  var communityTaxonomy = window.MG_COMMUNITY_TAXONOMY || { communities: [] };
  var communityCardsData = window.MG_COMMUNITY_CARDS || { cards: [] };
  var communityCards = communityCardsData.cards || [];
  var communityRows = [];
  var communityCardsById = {};
  var taxonomyById = {};
  (communityTaxonomy.communities || []).forEach(function (item) { taxonomyById[item.id] = item; });
  communityCards.forEach(function (card) { communityCardsById[card.id] = card; });
  communityCards.forEach(function (card) {
    communityRows.push(Object.assign({}, taxonomyById[card.id] || {}, card));
  });
  (communityTaxonomy.communities || []).forEach(function (item) {
    if (!communityCardsById[item.id]) communityRows.push(item);
  });

  var elBadge = document.getElementById('knowledgeBadge');
  var elStats = document.getElementById('knowledgeStats');
  var elCanvas = document.getElementById('knowledgeGraph');
  var elDetail = document.getElementById('knowledgeDetail');
  var elZoomLabel = document.getElementById('kgZoomLabel');
  var elNodeSearch = document.getElementById('knowledgeNodeSearch');
  var elTypeFilter = document.getElementById('knowledgeTypeFilter');
  var elGraphCommunityFilter = document.getElementById('knowledgeCommunityFilter');
  var elGraphDensity = document.getElementById('knowledgeGraphDensity');
  var elGraphColorMode = document.getElementById('knowledgeGraphColorMode');
  var elGraphLegend = document.getElementById('knowledgeGraphLegend');

  var svgNamespace = 'http://www.w3.org/2000/svg';
  var viewBox = { x: 0, y: 0, w: 1100, h: 720 };
  var zoomScale = 1;
  var scaleMin = 0.45;
  var scaleMax = 3.2;
  var activeNodeId = null;
  var activeCommunityId = null;
  var tabController = null;
  var communityAssignmentCache = {};
  var communityAssignmentLoading = {};
  var communityAssignmentErrors = {};
  var communityAssignmentCallbacks = {};
  var graphColorMode = 'type';
  var graphDensityMode = 'core';
  var communityPalette = [
    '#2563eb', '#0891b2', '#16a34a', '#ca8a04', '#7c3aed',
    '#dc2626', '#0f766e', '#4f46e5', '#9333ea', '#64748b'
  ];
  var communityColorById = {};

  var nodesById = {};
  var edgesById = {};
  var coreEdgeIds = {};
  var neighborMap = {};
  communityRows.forEach(function (community, index) {
    communityColorById[community.id] = communityPalette[index % communityPalette.length];
  });
  nodes.forEach(function (node) {
    nodesById[node.id] = node;
    neighborMap[node.id] = {};
  });
  coreEdges.forEach(function (edge) {
    coreEdgeIds[edge.id] = true;
  });
  allEdges.forEach(function (edge) {
    edgesById[edge.id] = edge;
  });

  function rebuildNeighborMap(edgeList) {
    neighborMap = {};
    nodes.forEach(function (node) {
      neighborMap[node.id] = {};
    });
    edgeList.forEach(function (edge) {
      if (!nodesById[edge.from] || !nodesById[edge.to]) return;
      neighborMap[edge.from] = neighborMap[edge.from] || {};
      neighborMap[edge.to] = neighborMap[edge.to] || {};
      neighborMap[edge.from][edge.to] = true;
      neighborMap[edge.to][edge.from] = true;
    });
  }

  rebuildNeighborMap(edges);

  var typeLabel = {
    disease: '疾病',
    drug: '药物/干预',
    mechanism: '机制',
    population: '人群/亚型',
    outcome: '结局',
    evidence: '证据类型'
  };

  var confidenceLabel = {
    high: '高覆盖',
    medium: '中覆盖',
    low: '低覆盖'
  };

  var sourceTypeLabel = {
    metadataConfirmed: '元数据确认',
    abstractMentioned: '摘要提及',
    llmInferred: '规则推断',
    curated: '人工策展'
  };

  var communitySignalLabel = {
    active: '高活跃',
    watch: '观察',
    quiet: '平稳',
    high: '高活跃',
    medium: '观察',
    low: '平稳'
  };

  function escapeHtml(value) {
    if (hub.escapeText) return hub.escapeText(value);
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }

  function escapeHref(value, fallback) {
    if (hub.safeUrl) return hub.safeUrl(value, fallback || '#');
    return escapeHtml(fallback || '#');
  }

  function assetUrl(path) {
    if (hub.assetUrl) return hub.assetUrl(path);
    if (/\/pages\/[^/]*$/.test(window.location.pathname || '') && /^(assets|data|pages)\//.test(String(path || ''))) {
      return '../' + path;
    }
    return path;
  }

  function pageUrl(path) {
    if (hub.pageUrl) return hub.pageUrl(path);
    if (/\/pages\/[^/]*$/.test(window.location.pathname || '') && /^(assets|data|pages)\//.test(String(path || ''))) {
      return '../' + path;
    }
    return path;
  }

  function topicHref(topicId, communityId) {
    var communityQuery = communityId ? '&community=' + encodeURIComponent(communityId) : '';
    return pageUrl('pages/knowledge.html?topic=' + encodeURIComponent(topicId || '') + communityQuery);
  }

  function safeClassToken(value, fallback) {
    return hub.safeClassToken ? hub.safeClassToken(value, fallback) : String(value || fallback || 'unknown').replace(/[^a-zA-Z0-9_-]+/g, '-');
  }

  function cssEscape(value) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(value);
    return String(value).replace(/"/g, '\\"');
  }

  function attrSelectorEscape(value) {
    return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  }

  function compactNumber(value) {
    var n = Number(value || 0);
    if (n >= 10000) return (n / 10000).toFixed(1).replace(/\.0$/, '') + '万';
    return String(n);
  }

  function communityColor(communityId) {
    return communityColorById[communityId] || '#64748b';
  }

  function populateCommunitySelect(selectEl, fallbackLabel) {
    if (!selectEl) return;
    selectEl.innerHTML = '<option value="all">' + escapeHtml(fallbackLabel) + '</option>' +
      communityRows.map(function (community) {
        return '<option value="' + escapeHtml(community.id) + '">' + escapeHtml(community.title || community.id) + '</option>';
      }).join('');
  }

  function renderGraphLegend() {
    if (!elGraphLegend) return;
    if (graphColorMode === 'community') {
      var activeCommunities = communityRows.filter(function (community) {
        return nodes.some(function (node) { return node.dominant_community_id === community.id; });
      });
      elGraphLegend.innerHTML = activeCommunities.map(function (community) {
        return '<span class="kg-legend-item"><span class="kg-legend-dot" style="background:' +
          escapeHtml(communityColor(community.id)) + '"></span>' + escapeHtml(community.title || community.id) + '</span>';
      }).join('') + '<span class="kg-legend-item"><span class="kg-legend-dot unmapped"></span>未映射</span>';
      return;
    }
    elGraphLegend.innerHTML =
      '<span class="kg-legend-item"><span class="kg-legend-dot disease"></span>疾病</span>' +
      '<span class="kg-legend-item"><span class="kg-legend-dot drug"></span>药物/干预</span>' +
      '<span class="kg-legend-item"><span class="kg-legend-dot mechanism"></span>机制</span>' +
      '<span class="kg-legend-item"><span class="kg-legend-dot population"></span>人群/亚型</span>' +
      '<span class="kg-legend-item"><span class="kg-legend-dot outcome"></span>结局</span>' +
      '<span class="kg-legend-item"><span class="kg-legend-dot evidence"></span>证据类型</span>' +
      '<span class="kg-legend-item" style="color:var(--fg3)">节点大小 = abstract 命中文献量</span>';
  }

  function initializeCommunityControls() {
    populateCommunitySelect(elGraphCommunityFilter, '全部医学社区');
    graphColorMode = (elGraphColorMode && elGraphColorMode.value) || 'type';
    renderGraphLegend();
  }

  function itemHasCommunity(item, communityId) {
    if (!communityId || communityId === 'all') return true;
    if (item.dominant_community_id === communityId) return true;
    return (item.community_profile || []).some(function (profile) {
      return profile.community_id === communityId;
    });
  }

  function svgEl(tag, attrs) {
    var el = document.createElementNS(svgNamespace, tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === 'text') el.textContent = attrs[key];
        else el.setAttribute(key, attrs[key]);
      });
    }
    return el;
  }

  function renderBadge() {
    if (!elBadge) return;
    var stats = graphData.stats || {};
    elBadge.textContent = compactNumber(stats.matched_articles) + ' 篇 abstract';
  }

  function renderStats() {
    if (!elStats) return;
    var stats = graphData.stats || {};
    var cards = [
      { label: '命中文献', value: compactNumber(stats.matched_articles), note: 'full PubMed abstract' },
      { label: '有证据等级', value: compactNumber(stats.evidence_articles), note: 'I-V 或已分级' }
    ];
    elStats.innerHTML = cards.map(function (card) {
      return '<article class="knowledge-stat-card">' +
        '<span>' + escapeHtml(card.label) + '</span>' +
        '<strong>' + escapeHtml(card.value) + '</strong>' +
        '<em>' + escapeHtml(card.note) + '</em>' +
      '</article>';
    }).join('');
  }

  function nodeRadius(node) {
    return 8 + Math.min(Math.log((node.article_count || 0) + 1) * 2.2, 17);
  }

  function edgeWidth(edge) {
    return 0.8 + Math.min(Math.log((edge.article_count || 0) + 1) * 0.26, 2.4);
  }

  function truncateLabel(title) {
    var text = String(title || '');
    if (text.length <= 20) return text;
    return text.slice(0, 19) + '…';
  }

  function edgesForDensity(mode) {
    if (mode === 'all') return allEdges;
    if (mode === 'bridge') {
      return allEdges.filter(function (edge) {
        return coreEdgeIds[edge.id] || edge.confidence === 'high';
      });
    }
    return coreEdges;
  }

  function refreshGraphDensity() {
    graphDensityMode = (elGraphDensity && elGraphDensity.value) || 'core';
    edges = edgesForDensity(graphDensityMode);
    rebuildNeighborMap(edges);
    buildGraph();
    attachGraphInteraction();
    applyNodeFilters();
    if (activeNodeId && nodesById[activeNodeId]) {
      var selectedId = activeNodeId;
      activeNodeId = null;
      selectNode(selectedId);
    }
  }

  function buildGraph() {
    if (!elCanvas) return;
    elCanvas.innerHTML = '';
    elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);
    elCanvas.classList.toggle('community-mode', graphColorMode === 'community');
    elCanvas.classList.toggle('density-all', graphDensityMode === 'all');
    elCanvas.classList.toggle('density-bridge', graphDensityMode === 'bridge');

    var edgeLayer = svgEl('g', { class: 'kg-edge-layer' });
    edges.forEach(function (edge) {
      var source = nodesById[edge.from];
      var target = nodesById[edge.to];
      if (!source || !target) return;
      var line = svgEl('line', {
        class: 'kg-edge source-' + safeClassToken(edge.source_type, 'unknown') + (coreEdgeIds[edge.id] ? ' core-edge' : ' secondary-edge'),
        x1: source.x,
        y1: source.y,
        x2: target.x,
        y2: target.y,
        'data-id': edge.id,
        'data-from': edge.from,
        'data-to': edge.to,
        'data-community': edge.dominant_community_id || '',
        'stroke-width': edgeWidth(edge)
      });
      edgeLayer.appendChild(line);
    });
    elCanvas.appendChild(edgeLayer);

    var nodeLayer = svgEl('g', { class: 'kg-node-layer' });
    nodes.forEach(function (node) {
      var group = svgEl('g', {
        class: 'kg-node type-' + safeClassToken(node.type, 'unknown') + ' conf-' + safeClassToken(node.confidence, 'low') + (node.dominant_community_id ? ' community-mapped' : ' community-unmapped'),
        'data-id': node.id,
        'data-type': node.type,
        'data-community': node.dominant_community_id || '',
        style: '--community-color:' + communityColor(node.dominant_community_id),
        transform: 'translate(' + node.x + ',' + node.y + ')'
      });
      var radius = nodeRadius(node);
      group.appendChild(svgEl('circle', { r: radius }));
      group.appendChild(svgEl('text', { y: radius + 13, text: truncateLabel(node.title) }));
      nodeLayer.appendChild(group);
    });
    elCanvas.appendChild(nodeLayer);
  }

  function applyViewBox() {
    var centerX = viewBox.x + viewBox.w / 2;
    var centerY = viewBox.y + viewBox.h / 2;
    viewBox.w = 1100 / zoomScale;
    viewBox.h = 720 / zoomScale;
    viewBox.x = centerX - viewBox.w / 2;
    viewBox.y = centerY - viewBox.h / 2;
    elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);
    if (elZoomLabel) elZoomLabel.textContent = Math.round(zoomScale * 100) + '%';
  }

  function zoomTo(newScale, focusX, focusY) {
    if (!elCanvas) return;
    newScale = Math.max(scaleMin, Math.min(scaleMax, newScale));
    if (focusX != null && focusY != null) {
      var worldX = viewBox.x + (focusX / elCanvas.clientWidth) * viewBox.w;
      var worldY = viewBox.y + (focusY / elCanvas.clientHeight) * viewBox.h;
      zoomScale = newScale;
      viewBox.w = 1100 / zoomScale;
      viewBox.h = 720 / zoomScale;
      viewBox.x = worldX - (focusX / elCanvas.clientWidth) * viewBox.w;
      viewBox.y = worldY - (focusY / elCanvas.clientHeight) * viewBox.h;
      elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);
    } else {
      zoomScale = newScale;
      applyViewBox();
    }
    if (elZoomLabel) elZoomLabel.textContent = Math.round(zoomScale * 100) + '%';
  }

  function resetView() {
    zoomScale = 1;
    viewBox = { x: 0, y: 0, w: 1100, h: 720 };
    if (elCanvas) elCanvas.setAttribute('viewBox', '0 0 1100 720');
    if (elZoomLabel) elZoomLabel.textContent = '100%';
  }

  function attachPanZoom() {
    if (!elCanvas) return;
    elCanvas.addEventListener('wheel', function (event) {
      event.preventDefault();
      var rect = elCanvas.getBoundingClientRect();
      var focusX = event.clientX - rect.left;
      var focusY = event.clientY - rect.top;
      zoomTo(zoomScale * (event.deltaY < 0 ? 1.15 : 1 / 1.15), focusX, focusY);
    }, { passive: false });

    var dragging = false;
    var start = { x: 0, y: 0, viewX: 0, viewY: 0 };

    elCanvas.addEventListener('mousedown', function (event) {
      if (event.target.closest('.kg-node')) return;
      dragging = true;
      start.x = event.clientX;
      start.y = event.clientY;
      start.viewX = viewBox.x;
      start.viewY = viewBox.y;
      elCanvas.classList.add('grabbing');
    });

    window.addEventListener('mousemove', function (event) {
      if (!dragging) return;
      var dx = event.clientX - start.x;
      var dy = event.clientY - start.y;
      viewBox.x = start.viewX - dx * (viewBox.w / elCanvas.clientWidth);
      viewBox.y = start.viewY - dy * (viewBox.h / elCanvas.clientHeight);
      elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);
    });

    window.addEventListener('mouseup', function () {
      dragging = false;
      elCanvas.classList.remove('grabbing');
    });

    var btnIn = document.getElementById('kgZoomIn');
    var btnOut = document.getElementById('kgZoomOut');
    var btnReset = document.getElementById('kgZoomReset');
    if (btnIn) btnIn.addEventListener('click', function () { zoomTo(zoomScale * 1.25); });
    if (btnOut) btnOut.addEventListener('click', function () { zoomTo(zoomScale / 1.25); });
    if (btnReset) btnReset.addEventListener('click', resetView);
  }

  function attachGraphInteraction() {
    if (!elCanvas) return;
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node'), function (nodeEl) {
      var id = nodeEl.getAttribute('data-id');
      nodeEl.addEventListener('mouseenter', function () {
        if (!activeNodeId) highlightNeighborhood(id);
      });
      nodeEl.addEventListener('mouseleave', function () {
        if (!activeNodeId) clearHighlight();
      });
      nodeEl.addEventListener('click', function (event) {
        event.stopPropagation();
        selectNode(id);
      });
    });

    elCanvas.onclick = function () {
      activeNodeId = null;
      clearActive();
      clearHighlight();
    };
  }

  function highlightNeighborhood(id) {
    if (!elCanvas) return;
    var neighbors = neighborMap[id] || {};
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge'), function (line) {
      var source = line.getAttribute('data-from');
      var target = line.getAttribute('data-to');
      if (source === id || target === id) line.classList.add('hl');
      else line.classList.add('dim');
    });
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node'), function (nodeEl) {
      var nodeId = nodeEl.getAttribute('data-id');
      if (nodeId !== id && !neighbors[nodeId]) nodeEl.classList.add('dim');
    });
  }

  function clearHighlight() {
    if (!elCanvas) return;
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge.hl,.kg-edge.dim,.kg-node.dim'), function (el) {
      el.classList.remove('hl');
      el.classList.remove('dim');
    });
  }

  function clearActive() {
    if (!elCanvas) return;
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node.active'), function (nodeEl) {
      nodeEl.classList.remove('active');
    });
  }

  function ensureNodeInView(id) {
    if (!elCanvas || !nodesById[id]) return;
    var node = nodesById[id];
    var marginX = viewBox.w * 0.18;
    var marginY = viewBox.h * 0.18;
    var nextX = viewBox.x;
    var nextY = viewBox.y;
    if (node.x < viewBox.x + marginX || node.x > viewBox.x + viewBox.w - marginX) {
      nextX = node.x - viewBox.w / 2;
    }
    if (node.y < viewBox.y + marginY || node.y > viewBox.y + viewBox.h - marginY) {
      nextY = node.y - viewBox.h / 2;
    }
    if (nextX !== viewBox.x || nextY !== viewBox.y) {
      viewBox.x = nextX;
      viewBox.y = nextY;
      elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);
    }
  }

  function selectNode(id) {
    if (!nodesById[id]) return;
    activeNodeId = id;
    clearActive();
    clearHighlight();
    ensureNodeInView(id);
    var nodeEl = elCanvas.querySelector('.kg-node[data-id="' + cssEscape(id) + '"]');
    if (nodeEl) nodeEl.classList.add('active');
    highlightNeighborhood(id);
    renderDetail(id);
  }

  function renderDetail(id) {
    if (!elDetail) return;
    var node = nodesById[id];
    if (!node) {
      elDetail.innerHTML = '<div class="kg-empty-hint">点击图谱节点查看详情</div>';
      return;
    }
    var refs = nodeRefs[id] || [];
    var relatedEdges = allEdges.filter(function (edge) {
      return edge.from === id || edge.to === id;
    }).sort(function (a, b) {
      return (b.evidence_score || 0) - (a.evidence_score || 0);
    });

    var levelHtml = Object.keys(node.evidence_levels || {}).map(function (level) {
      return '<span class="mini-chip">Level ' + escapeHtml(level) + ' · ' + escapeHtml(node.evidence_levels[level]) + '</span>';
    }).join('');

    var relatedHtml = relatedEdges.map(function (edge) {
      var otherId = edge.from === id ? edge.to : edge.from;
      var otherNode = nodesById[otherId] || {};
      return '<button class="kg-relation-row" type="button" data-node="' + escapeHtml(otherId) + '">' +
        '<span>' + escapeHtml(edge.relation) + '</span>' +
        '<strong>' + escapeHtml(otherNode.title || otherId) + '</strong>' +
        '<em>' + escapeHtml(edge.article_count || 0) + ' 篇</em>' +
      '</button>';
    }).join('');

    var refsHtml = refs.length ? refs.map(renderReferenceItem).join('') : '<li>暂无 PMID 引用</li>';
    var topicHtml = renderRelatedTopics(id);
    var communityHtml = renderCommunityProfileBlock(node, '社区映射');
    var communityBadge = node.dominant_community_id ?
      '<span class="kg-badge community-badge" style="--community-color:' + escapeHtml(communityColor(node.dominant_community_id)) + '">' + escapeHtml(node.dominant_community_title || getCommunityTitle(node.dominant_community_id)) + '</span>' :
      '<span class="kg-badge">未映射社区</span>';

    elDetail.innerHTML =
      '<div class="kg-detail-type">' + escapeHtml(typeLabel[node.type] || node.type) + '</div>' +
      '<h2>' + escapeHtml(node.title) + '</h2>' +
      '<div class="kg-badges">' +
        '<span class="kg-badge conf-' + escapeHtml(node.confidence || 'low') + '">' + escapeHtml(confidenceLabel[node.confidence] || '覆盖未知') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(node.article_count || 0) + ' 篇 abstract</span>' +
        '<span class="kg-badge">' + escapeHtml(sourceTypeLabel[node.source_type] || '摘要提及') + '</span>' +
        communityBadge +
      '</div>' +
      '<div class="kg-detail-summary">' + escapeHtml(node.summary || '') + '</div>' +
      communityHtml +
      topicHtml +
      '<div class="kg-detail-section"><h4>证据等级分布</h4><div class="kg-tags">' + levelHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>关联关系 (' + escapeHtml(relatedEdges.length) + ')</h4><div class="kg-relation-list">' + relatedHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>代表 PMID</h4><ul class="kg-study-list">' + refsHtml + '</ul></div>';

    Array.prototype.forEach.call(elDetail.querySelectorAll('[data-node]'), function (button) {
      button.addEventListener('click', function () {
        selectNode(button.getAttribute('data-node'));
      });
    });
    Array.prototype.forEach.call(elDetail.querySelectorAll('[data-topic]'), function (button) {
      button.addEventListener('click', function () {
        openTopic(button.getAttribute('data-topic'));
      });
    });
    Array.prototype.forEach.call(elDetail.querySelectorAll('[data-community]'), function (button) {
      button.addEventListener('click', function () {
        openCommunity(button.getAttribute('data-community'));
      });
    });
  }

  function renderRelatedTopics(nodeId) {
    var ids = (curatedData.bridge_by_node && curatedData.bridge_by_node[nodeId]) || [];
    var topics = ids.map(function (id) { return topicsById[id]; }).filter(Boolean).slice(0, 5);
    if (!topics.length) return '';
    return '<div class="kg-detail-section"><h4>相关专题</h4><div class="kg-relation-list">' +
      topics.map(function (topic) {
        var impact = topic.impact && topic.impact.status === 'updatedEvidence' ? '本周新证据' : '专题';
        return '<button class="kg-relation-row" type="button" data-topic="' + escapeHtml(topic.id) + '">' +
          '<span>' + escapeHtml(impact) + '</span>' +
          '<strong>' + escapeHtml(topic.title) + '</strong>' +
          '<em>' + escapeHtml((topic.evidence_refs || []).length) + ' PMID</em>' +
        '</button>';
      }).join('') + '</div></div>';
  }

  function renderCommunityProfileBlock(item, title) {
    var profile = item.community_profile || [];
    if (!profile.length) {
      return '<div class="kg-detail-section"><h4>' + escapeHtml(title) + '</h4><div class="kg-empty-hint">当前图谱关系尚未映射到稳定医学事务社区。</div></div>';
    }
    var rows = profile.map(function (community) {
      return '<button class="kg-relation-row community-profile-link" type="button" data-community="' + escapeHtml(community.community_id) + '">' +
        '<span><i style="background:' + escapeHtml(communityColor(community.community_id)) + '"></i>' + escapeHtml(Math.round((community.total_ratio || 0) * 100)) + '%</span>' +
        '<strong>' + escapeHtml(community.title || community.community_id) + '</strong>' +
        '<em>' + escapeHtml(community.count || 0) + ' PMID</em>' +
      '</button>';
    }).join('');
    return '<div class="kg-detail-section"><h4>' + escapeHtml(title) + '</h4>' +
      '<div class="kg-relation-list">' + rows + '</div></div>';
  }

  function renderReferenceItem(ref) {
    var meta = [
      ref.journal || '',
      ref.pub_date || '',
      ref.evidence_level ? 'Level ' + ref.evidence_level : '',
      (ref.study_types || []).slice(0, 2).join(' / ')
    ].filter(Boolean).join(' · ');
    return '<li><a class="text-link" href="' + escapeHref(ref.url) + '" target="_blank" rel="noopener">PMID ' +
      escapeHtml(ref.pmid) + '</a> ' + escapeHtml(ref.title || '') +
      '<br><span class="kg-ref-meta">' + escapeHtml(meta) + '</span></li>';
  }

  function attachNodeFilters() {
    if (elNodeSearch) elNodeSearch.addEventListener('input', applyNodeFilters);
    if (elTypeFilter) elTypeFilter.addEventListener('change', applyNodeFilters);
    if (elGraphCommunityFilter) elGraphCommunityFilter.addEventListener('change', applyNodeFilters);
    if (elGraphDensity) elGraphDensity.addEventListener('change', refreshGraphDensity);
    if (elGraphColorMode) elGraphColorMode.addEventListener('change', function () {
      graphColorMode = elGraphColorMode.value || 'type';
      if (elCanvas) elCanvas.classList.toggle('community-mode', graphColorMode === 'community');
      renderGraphLegend();
    });
    applyNodeFilters();
  }

  function applyNodeFilters() {
    if (!elCanvas) return;
    var keyword = (elNodeSearch && elNodeSearch.value || '').trim().toLowerCase();
    var type = (elTypeFilter && elTypeFilter.value) || 'all';
    var communityId = (elGraphCommunityFilter && elGraphCommunityFilter.value) || 'all';
    var visible = {};
    var seeds = {};
    var hasFocusFilter = !!keyword || type !== 'all';

    nodes.forEach(function (node) {
      var communityText = (node.community_profile || []).map(function (profile) {
        return profile.title + ' ' + profile.community_id;
      }).join(' ');
      var text = [node.id, node.title, node.summary, node.type, node.dominant_community_title, communityText, (node.top_study_types || []).join(' ')].join(' ').toLowerCase();
      var okKeyword = !keyword || text.indexOf(keyword) !== -1;
      var okType = type === 'all' || node.type === type;
      var okCommunity = itemHasCommunity(node, communityId);
      if (!hasFocusFilter) {
        visible[node.id] = okCommunity;
        return;
      }
      if (okKeyword && okType && okCommunity) {
        visible[node.id] = true;
        seeds[node.id] = true;
      }
    });

    if (hasFocusFilter) {
      Object.keys(seeds).forEach(function (id) {
        Object.keys(neighborMap[id] || {}).forEach(function (neighborId) {
          var neighbor = nodesById[neighborId];
          if (neighbor && itemHasCommunity(neighbor, communityId)) visible[neighborId] = true;
        });
      });
    }

    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node'), function (nodeEl) {
      var id = nodeEl.getAttribute('data-id');
      nodeEl.classList.toggle('filtered-out', !visible[id]);
    });
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge'), function (line) {
      var source = line.getAttribute('data-from');
      var target = line.getAttribute('data-to');
      var edgeVisible = visible[source] && visible[target] && (!hasFocusFilter || seeds[source] || seeds[target]);
      line.classList.toggle('filtered-out', !edgeVisible);
    });
  }

  function loadScriptOnce(src, callback) {
    var finalSrc = hub.withReleaseVersion ? hub.withReleaseVersion(src) : src;
    var existing = document.querySelector('script[src="' + attrSelectorEscape(finalSrc) + '"]');
    if (existing && existing.getAttribute('data-loaded') === '1') {
      callback(true);
      return;
    }
    if (existing && existing.getAttribute('data-loading') === '1') {
      existing.addEventListener('load', function () { callback(true); }, { once: true });
      existing.addEventListener('error', function () { callback(false); }, { once: true });
      return;
    }
    if (existing) existing.remove();
    var script = document.createElement('script');
    script.src = finalSrc;
    script.setAttribute('data-loading', '1');
    script.onload = function () {
      script.setAttribute('data-loaded', '1');
      script.removeAttribute('data-loading');
      callback(true);
    };
    script.onerror = function () {
      script.removeAttribute('data-loading');
      callback(false);
    };
    if (!existing) document.head.appendChild(script);
  }

  function loadCommunityAssignmentShard(communityId, callback) {
    if (communityAssignmentCache[communityId]) {
      callback(true, communityAssignmentCache[communityId]);
      return;
    }
    if (communityAssignmentLoading[communityId]) {
      communityAssignmentCallbacks[communityId].push(callback);
      return;
    }
    communityAssignmentLoading[communityId] = true;
    communityAssignmentCallbacks[communityId] = [callback];
    loadScriptOnce(assetUrl('data/communityAssignments-' + encodeURIComponent(communityId) + '.js'), function (ok) {
      var shards = window.MG_COMMUNITY_ASSIGNMENT_SHARDS || {};
      var payload = shards[communityId] || null;
      if (ok && payload) {
        communityAssignmentCache[communityId] = payload;
        delete communityAssignmentErrors[communityId];
      } else {
        communityAssignmentErrors[communityId] = true;
      }
      communityAssignmentLoading[communityId] = false;
      var callbacks = communityAssignmentCallbacks[communityId] || [];
      delete communityAssignmentCallbacks[communityId];
      for (var i = 0; i < callbacks.length; i++) {
        callbacks[i](ok && !!payload, payload);
      }
    });
  }

  function assignmentFlagLabel(flag) {
    return {
      lowConfidence: '低置信度',
      crossCommunityConflict: '跨社区冲突'
    }[flag] || flag;
  }

  function assignmentConfidenceLabel(value) {
    return {
      high: '高',
      medium: '中',
      low: '低',
      unassigned: '未归类'
    }[value] || value || '未知';
  }

  function renderAssignmentFlags(flags) {
    return (flags || []).map(function (flag) {
      return '<span class="community-assignment-flag">' + escapeHtml(assignmentFlagLabel(flag)) + '</span>';
    }).join('');
  }

  function renderAssignmentSummary(items) {
    var counts = { high: 0, medium: 0, low: 0, conflict: 0, china: 0 };
    for (var i = 0; i < items.length; i++) {
      var item = items[i] || {};
      if (counts[item.confidence] !== undefined) counts[item.confidence]++;
      if ((item.flags || []).indexOf('crossCommunityConflict') !== -1) counts.conflict++;
      if (item.china_related) counts.china++;
    }
    return '<div class="community-assignment-summary">' +
      '<span>全量 ' + escapeHtml(compactNumber(items.length)) + '</span>' +
      '<span>高 ' + escapeHtml(counts.high) + '</span>' +
      '<span>中 ' + escapeHtml(counts.medium) + '</span>' +
      '<span>低 ' + escapeHtml(counts.low) + '</span>' +
      '<span>冲突 ' + escapeHtml(counts.conflict) + '</span>' +
      '<span>中国 ' + escapeHtml(counts.china) + '</span>' +
    '</div>';
  }

  function renderAssignmentList(communityId, payload) {
    var panel = document.getElementById('communityAssignmentPanel');
    if (!panel || panel.getAttribute('data-community') !== communityId) return;
    var items = (payload && payload.items) || [];
    if (!items.length) {
      panel.innerHTML = '<div class="kg-empty-hint">该社区分片暂无归类记录。</div>';
      return;
    }
    var rows = items.map(function (item) {
      var flags = renderAssignmentFlags(item.flags || []);
      var secondary = (item.secondary || []).slice(0, 2).map(function (entry) {
        var title = getCommunityTitle(entry.community_id);
        return title + ' ' + Number(entry.score || 0).toFixed(1).replace(/\.0$/, '');
      }).join(' / ');
      return '<li class="community-assignment-row">' +
        '<a href="' + escapeHref('https://pubmed.ncbi.nlm.nih.gov/' + encodeURIComponent(item.pmid || '') + '/') + '" target="_blank" rel="noopener">PMID ' + escapeHtml(item.pmid) + '</a>' +
        '<span class="kg-badge conf-' + escapeHtml(item.confidence === 'high' ? 'high' : item.confidence === 'medium' ? 'medium' : 'low') + '">' + escapeHtml(assignmentConfidenceLabel(item.confidence)) + '</span>' +
        '<span>' + escapeHtml(item.entry_date || item.pub_date || '-') + '</span>' +
        '<span>' + escapeHtml(item.evidence_level ? 'Level ' + item.evidence_level : '未分级') + '</span>' +
        (item.china_related ? '<span class="community-assignment-flag china">中国</span>' : '') +
        flags +
        (secondary ? '<em>' + escapeHtml(secondary) + '</em>' : '') +
      '</li>';
    }).join('');
    panel.innerHTML = renderAssignmentSummary(items) +
      '<ul class="community-assignment-list">' + rows + '</ul>';
  }

  function getCommunityTitle(communityId) {
    var card = communityCardsById[communityId] || {};
    var taxonomy = taxonomyById[communityId] || {};
    return card.title || taxonomy.title || communityId;
  }

  function getInitialKnowledgeCommunityId() {
    try {
      var params = new URLSearchParams(window.location.search || '');
      var communityId = params.get('community') || '';
      if (communityId && taxonomyById[communityId]) return communityId;
      return '';
    } catch (err) {
      return '';
    }
  }

  function getInitialKnowledgeTab() {
    try {
      var params = new URLSearchParams(window.location.search || '');
      return params.get('tab') || '';
    } catch (err) {
      return '';
    }
  }

  function getInitialKnowledgeNodeId() {
    try {
      var params = new URLSearchParams(window.location.search || '');
      var nodeId = params.get('node') || '';
      if (nodeId && nodesById[nodeId]) return nodeId;
      return '';
    } catch (err) {
      return '';
    }
  }

  function openTopic(topicId, communityId) {
    // 专题详情视图已由诊治格局「诊疗现状」承接
    window.location.href = pageUrl('pages/landscape.html?tab=chapters');
  }

  function openCommunity(communityId) {
    openCommunityGraph(communityId);
  }

  function openCommunityGraph(communityId) {
    activateTab('graph');
    if (elGraphCommunityFilter) elGraphCommunityFilter.value = communityId;
    if (elGraphColorMode) elGraphColorMode.value = 'community';
    graphColorMode = 'community';
    if (elCanvas) elCanvas.classList.add('community-mode');
    renderGraphLegend();
    applyNodeFilters();
    var firstNode = nodes.find(function (node) { return itemHasCommunity(node, communityId); });
    if (firstNode) selectNode(firstNode.id);
  }

  function activateTab(key) {
    if (tabController) {
      tabController.activate(key, false);
      return;
    }
    var tabs = document.querySelectorAll('[data-knowledge-tab]');
    var panels = document.querySelectorAll('.intel-tab-panel');
    Array.prototype.forEach.call(tabs, function (tab) {
      tab.classList.toggle('active', tab.getAttribute('data-knowledge-tab') === key);
    });
    Array.prototype.forEach.call(panels, function (panel) {
      panel.classList.remove('active');
    });
    var panel = document.getElementById('knowledge-' + key + '-panel');
    if (panel) panel.classList.add('active');
  }

  function attachTabs() {
    if (hub.initTabs) {
      tabController = hub.initTabs({
        tabAttr: 'data-knowledge-tab',
        panelFor: function(key) { return document.getElementById('knowledge-' + key + '-panel'); }
      });
      return;
    }
    Array.prototype.forEach.call(document.querySelectorAll('[data-knowledge-tab]'), function (tab) {
      tab.addEventListener('click', function () {
        activateTab(tab.getAttribute('data-knowledge-tab'));
      });
    });
  }

  function init() {
    renderBadge();
    renderStats();
    initializeCommunityControls();
    buildGraph();
    attachPanZoom();
    attachGraphInteraction();
    attachNodeFilters();
    attachTabs();
    selectNode(nodesById.fcrnInhibition ? 'fcrnInhibition' : (nodes[0] && nodes[0].id));
    var initialCommunityId = getInitialKnowledgeCommunityId();
    var initialNodeId = getInitialKnowledgeNodeId();
    var initialTab = getInitialKnowledgeTab();
    if (initialNodeId) {
      activateTab('graph');
      selectNode(initialNodeId);
    } else if (initialCommunityId) {
      openCommunityGraph(initialCommunityId);
    } else if (['graph', 'china-network'].indexOf(initialTab) !== -1) {
      activateTab(initialTab);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
