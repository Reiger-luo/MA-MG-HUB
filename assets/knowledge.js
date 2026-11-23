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
  // 关系详情索引：evidence_matrix 每行是一条"节点对"的交叉证据（含 references/limitation）。
  // 共 180 行，不是全量边；没有矩阵记录的边回退用 edge.pmids。
  var matrixByPairKey = {};
  function pairKey(a, b) { return [a, b].sort().join('::'); }
  matrixRows.forEach(function (row) {
    if (row.source_id && row.target_id) matrixByPairKey[pairKey(row.source_id, row.target_id)] = row;
  });
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
  var elWorkbenchTitle = document.getElementById('kgWorkbenchTitle');
  var elWorkbenchNote = document.getElementById('kgWorkbenchNote');
  var elRelationList = document.getElementById('kgRelationList');
  var elCurationPanel = document.getElementById('kgCurationPanel');
  var elEvidencePane = document.getElementById('kgEvidencePane');
  var elEvidenceBody = document.getElementById('kgEvidenceBody');
  var elEvidenceTitle = document.getElementById('kgEvidenceTitle');
  var elEvidenceMeta = document.getElementById('kgEvidenceMeta');
  var activeTopicId = '';
  var activeEdgeId = ''; // 选边模式：非空表示正在看"主节点 × 关联节点"这条关系

  var svgNamespace = 'http://www.w3.org/2000/svg';
  var viewBox = { x: 0, y: 0, w: 1100, h: 720 };
  var zoomScale = 1;
  var scaleMin = 0.45;
  var scaleMax = 3.2;
  var activeNodeId = null;
  var activeCommunityId = null;
  var tabController = null;
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

  function pageUrl(path) {
    if (hub.pageUrl) return hub.pageUrl(path);
    if (/\/pages\/[^/]*$/.test(window.location.pathname || '') && /^(assets|data|pages)\//.test(String(path || ''))) {
      return '../' + path;
    }
    return path;
  }

  function safeClassToken(value, fallback) {
    return hub.safeClassToken ? hub.safeClassToken(value, fallback) : String(value || fallback || 'unknown').replace(/[^a-zA-Z0-9_-]+/g, '-');
  }

  function cssEscape(value) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(value);
    return String(value).replace(/"/g, '\\"');
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
    populateCommunitySelect(elGraphCommunityFilter, '全部主题分类');
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

  // 更新时间按 zh-CN 本地时区显示为「月/日 时:分」，与首页「数据截至」口径一致
  function formatUpdatedAt(value) {
    if (!value) return '时间待确认';
    var rawValue = String(value).trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(rawValue)) return rawValue.slice(5).replace('-', '/');
    var normalized = rawValue.indexOf('T') === -1 ? rawValue.replace(' ', 'T') : rawValue;
    var parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) return rawValue;
    return new Intl.DateTimeFormat('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    }).format(parsed);
  }

  function renderBadge() {
    if (!elBadge) return;
    // 徽标回答「这份数据什么时候更新的」：优先跟随站点发布节奏（release-manifest），
    // 图谱未随本次发布重算时也不至于把旧时间当成本次更新；发布清单缺失才回退图谱生成时间。
    var release = window.MG_RELEASE_MANIFEST || {};
    var releasedAt = release.released_at || '';
    var generatedAt = graphData.generated_at || (graphHealthData && graphHealthData.generated_at) || '';
    var updatedAt = releasedAt || generatedAt;
    elBadge.textContent = '数据更新 ' + formatUpdatedAt(updatedAt);
    if (releasedAt) {
      elBadge.title = '数据发布时间 ' + releasedAt + (release.run_id ? '（发布编号 ' + release.run_id + '）' : '');
    } else {
      elBadge.title = generatedAt ? '知识图谱生成时间 ' + generatedAt : '数据更新时间待确认';
    }
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
      activeEdgeId = '';
      activeTopicId = '';
      clearActive();
      clearHighlight();
      renderDetail(null);
      renderWorkbench(null);
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

  function selectNode(id, options) {
    if (!nodesById[id]) return;
    activeNodeId = id;
    activeTopicId = '';
    activeEdgeId = '';
    clearActive();
    clearHighlight();
    ensureNodeInView(id);
    var nodeEl = elCanvas.querySelector('.kg-node[data-id="' + cssEscape(id) + '"]');
    if (nodeEl) nodeEl.classList.add('active');
    highlightNeighborhood(id);
    renderDetail(id);
    renderWorkbench(id);
    // 深链进入专题时，选中锚点后在右栏策展区显示该专题；用 options.topicId 传递，避免再次解析 URL。
    if (options && options.topicId) {
      openTopic(options.topicId);
    }
  }

  // ===== 选边模式：主节点 × 关联节点 =====
  // 图谱里"边"是一等公民：点下方共现关系中的某行，即选中主节点与该节点之间的边。
  // 图谱与主节点身份卡保持锁定；右侧切换为关联节点的解读，下方给出该边的交叉证据文献。

  function edgeById(id) {
    return allEdges.find(function (edge) { return edge.id === id; }) || null;
  }

  // 返回一条边相对于主节点的"另一端"节点 id；找不到主节点时取边的 to。
  function edgeOtherId(edge, primaryId) {
    if (!edge) return '';
    if (edge.from === primaryId) return edge.to;
    if (edge.to === primaryId) return edge.from;
    return edge.to;
  }

  // 从 evidence_matrix 取这条节点对的交叉证据；无矩阵记录时回退到边上的代表 PMID。
  function crossEvidenceFor(edge, primaryId) {
    var otherId = edgeOtherId(edge, primaryId);
    var row = matrixByPairKey[pairKey(primaryId, otherId)] || null;
    if (row) {
      return {
        references: row.references || [],
        key_pmids: row.key_pmids || [],
        article_count: row.article_count || edge.article_count || 0,
        level: row.best_evidence_level || edge.best_evidence_level || '',
        relation: row.relation || edge.relation || '',
        limitation: row.limitation || '',
        hasMatrix: true
      };
    }
    var refs = (edge.pmids || []).map(function (pmid) {
      return { pmid: String(pmid), title: '（摘要级代表文献，标题请回 PMID 原文核对）', url: 'https://pubmed.ncbi.nlm.nih.gov/' + encodeURIComponent(pmid) + '/' };
    });
    return {
      references: refs,
      key_pmids: edge.pmids || [],
      article_count: edge.article_count || 0,
      level: edge.best_evidence_level || '',
      relation: edge.relation || '',
      limitation: '这条关系未进入证据矩阵明细，仅提供摘要级代表 PMID，不能作为完整文献清单。',
      hasMatrix: false
    };
  }

  function selectEdge(edgeId) {
    var edge = edgeById(edgeId);
    if (!edge || !activeNodeId) return;
    activeEdgeId = edgeId;
    activeTopicId = '';
    // 图谱：主节点仍 active，同时把这条边单独高亮，让"选中的关系"可见。
    clearHighlight();
    highlightNeighborhood(activeNodeId);
    var line = elCanvas.querySelector('.kg-edge[data-id="' + cssEscape(edgeId) + '"]');
    if (line) line.classList.add('edge-selected');
    var otherEl = elCanvas.querySelector('.kg-node[data-id="' + cssEscape(edgeOtherId(edge, activeNodeId)) + '"]');
    if (otherEl) otherEl.classList.add('edge-peer');

    // 左栏高亮选中的关系
    Array.prototype.forEach.call(elRelationList ? elRelationList.querySelectorAll('[data-edge]') : [], function (button) {
      button.classList.toggle('selected', button.getAttribute('data-edge') === edgeId);
    });
    // 右栏策展 + 下方文献清单
    renderCuration(activeEdgeId);
    renderCrossEvidence(activeEdgeId);
  }

  // 右侧身份卡：只回答「这个节点是什么」。所有可交互的清单统一移到下方工作台，
  // 避免右侧既做身份说明又做导航，造成点击行为不一致。
  function renderDetail(id) {
    if (!elDetail) return;
    var node = nodesById[id];
    if (!node) {
      elDetail.innerHTML = '<div class="kg-empty-hint">点击图谱节点查看详情</div>';
      return;
    }

    var levelHtml = Object.keys(node.evidence_levels || {}).map(function (level) {
      return '<span class="mini-chip">Level ' + escapeHtml(level) + ' · ' + escapeHtml(node.evidence_levels[level]) + '</span>';
    }).join('');

    // 主主题静态呈现，不设点击。要按主题筛选请用顶部「主题分类」下拉或下方工作台。
    var communityBadge = node.dominant_community_id ?
      '<span class="kg-badge community-badge" style="--community-color:' + escapeHtml(communityColor(node.dominant_community_id)) + '">' + escapeHtml(node.dominant_community_title || getCommunityTitle(node.dominant_community_id)) + '</span>' :
      '<span class="kg-badge">未归入主题分类</span>';

    elDetail.innerHTML =
      '<div class="kg-detail-type">' + escapeHtml(typeLabel[node.type] || node.type) + '</div>' +
      '<h2>' + escapeHtml(node.title) + '</h2>' +
      '<div class="kg-badges">' +
        '<span class="kg-badge conf-' + escapeHtml(node.confidence || 'low') + '">' + escapeHtml(confidenceLabel[node.confidence] || '覆盖未知') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(node.article_count || 0) + ' 篇 abstract</span>' +
        communityBadge +
      '</div>' +
      '<div class="kg-detail-summary">' + escapeHtml(node.summary || '') + '</div>' +
      '<div class="kg-detail-section"><h4>证据等级分布</h4><div class="kg-tags">' + levelHtml + '</div></div>' +
      '<p class="kg-detail-note">在下方工作台选择一条关系，可查看关联节点的策展解读与两者的交叉文献。</p>';
  }

  // ===== 下方工作台：左=关系选择(1) / 右=策展解读(3) / 下=证据文献清单 =====
  // 选边交互完全收进工作台内部：选一条关系 → 右侧看关联节点策展 → 下方看这条关系的文献。
  // 页面右侧身份卡始终锁定主节点，图谱也保持主节点高亮。
  // 统一点击契约：除 PMID 原文是外链外，工作台内所有点击都是页内状态更新。

  function renderWorkbench(id) {
    var node = nodesById[id];
    if (!elRelationList) return;
    if (!node) {
      if (elWorkbenchTitle) elWorkbenchTitle.textContent = '尚未选中节点';
      if (elWorkbenchNote) elWorkbenchNote.textContent = '点击图谱中的节点开始';
      elRelationList.innerHTML = '<div class="kg-empty-hint">点击图谱节点后列出它的共现关系。</div>';
      if (elCurationPanel) elCurationPanel.innerHTML = '<div class="kg-empty-hint">选择左侧一条关系后，这里显示关联节点的策展解读。</div>';
      hideEvidencePane();
      return;
    }
    if (elWorkbenchTitle) elWorkbenchTitle.textContent = node.title;
    if (elWorkbenchNote) elWorkbenchNote.textContent = (node.article_count || 0) + ' 篇 abstract · 摘要级证据线索';

    var relatedEdges = allEdges.filter(function (edge) {
      return edge.from === id || edge.to === id;
    }).sort(function (a, b) {
      return (b.article_count || 0) - (a.article_count || 0);
    });

    if (!relatedEdges.length) {
      elRelationList.innerHTML = '<div class="kg-empty-hint">这个节点暂无共现关系。</div>';
    } else {
      elRelationList.innerHTML = '<p class="kg-detail-note">共 ' + relatedEdges.length + ' 条关系。点选一条，右侧看策展、下方看文献。</p>' +
        relatedEdges.map(function (edge) {
          var otherId = edge.from === id ? edge.to : edge.from;
          var otherNode = nodesById[otherId] || {};
          var level = edge.best_evidence_level ? '证据 ' + escapeHtml(edge.best_evidence_level) : '';
          var inMatrix = !!matrixByPairKey[pairKey(id, otherId)];
          var selected = edge.id === activeEdgeId ? ' selected' : '';
          return '<button class="kg-relation-pick' + selected + '" type="button" data-edge="' + escapeHtml(edge.id) + '">' +
            '<strong>' + escapeHtml(otherNode.title || otherId) + '</strong>' +
            '<span>' + escapeHtml(edge.article_count || 0) + ' 篇' + (level ? ' · ' + level : '') + (inMatrix ? ' · 有明细' : '') + '</span>' +
          '</button>';
        }).join('');
      Array.prototype.forEach.call(elRelationList.querySelectorAll('[data-edge]'), function (button) {
        button.addEventListener('click', function () {
          selectEdge(button.getAttribute('data-edge'));
        });
      });
    }

    if (activeEdgeId) {
      // 切换节点后若仍有选边，重渲染右栏与下方
      renderCuration(activeEdgeId);
      renderCrossEvidence(activeEdgeId);
    } else {
      if (elCurationPanel) elCurationPanel.innerHTML = '<div class="kg-empty-hint">选择左侧一条关系后，这里显示关联节点的策展解读。</div>';
      hideEvidencePane();
    }
  }

  // 右栏：关联节点的策展解读（身份 + 该节点自己的策展专题）
  function renderCuration(edgeId) {
    if (!elCurationPanel) return;
    var edge = edgeById(edgeId);
    if (!edge || !activeNodeId) return;
    var otherId = edgeOtherId(edge, activeNodeId);
    var other = nodesById[otherId] || {};
    var primary = nodesById[activeNodeId] || {};
    var otherTopics = (curatedData.bridge_by_node && curatedData.bridge_by_node[otherId]) || [];
    var topicHtml = otherTopics.length
      ? otherTopics.map(function (tid) {
          var t = topicsById[tid];
          return t ? '<div class="kg-curation-topic"><strong>' + escapeHtml(t.title) + '</strong>' +
            (t.summary ? '<p>' + escapeHtml(t.summary) + '</p>' : '') + '</div>' : '';
        }).join('')
      : '<div class="kg-empty-hint">该关联节点暂无策展专题（专题只覆盖部分核心节点）。</div>';

    elCurationPanel.innerHTML =
      '<div class="kg-curation-head">' +
        '<div class="kg-detail-type">关联节点</div>' +
        '<h4>' + escapeHtml(other.title || otherId) + '</h4>' +
        '<div class="kg-badges">' +
          '<span class="kg-badge">' + escapeHtml(typeLabel[other.type] || other.type || '') + '</span>' +
          '<span class="kg-badge">' + escapeHtml(other.article_count || 0) + ' 篇 abstract</span>' +
          '<span class="kg-badge relation-peer-badge">与 ' + escapeHtml(primary.title) + ' 共现</span>' +
        '</div>' +
        (other.summary ? '<p class="kg-detail-summary">' + escapeHtml(other.summary) + '</p>' : '') +
      '</div>' +
      '<div class="kg-curation-section"><h5>策展解读</h5>' + topicHtml + '</div>' +
      '<p class="kg-detail-note">策展专题为观点性整理、非实时证据；引用前请核对 PMID 原文。</p>';
  }

  function hideEvidencePane() {
    if (elEvidencePane) elEvidencePane.hidden = true;
    // 收起即退出选边：右栏回到提示态、左栏取消关系高亮、图谱取消边高亮。
    activeEdgeId = '';
    if (elCurationPanel) elCurationPanel.innerHTML = '<div class="kg-empty-hint">选择左侧一条关系后，这里显示关联节点的策展解读。</div>';
    if (elRelationList) {
      Array.prototype.forEach.call(elRelationList.querySelectorAll('[data-edge]'), function (button) {
        button.classList.remove('selected');
      });
    }
    if (elCanvas) {
      Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge.edge-selected,.kg-node.edge-peer'), function (el) {
        el.classList.remove('edge-selected', 'edge-peer');
      });
    }
  }

  // 下方文献清单：这条"节点对"在 evidence_matrix 中的交叉证据。
  function renderCrossEvidence(edgeId) {
    if (!elEvidencePane || !elEvidenceBody) return;
    var edge = edgeById(edgeId);
    if (!edge || !activeNodeId) return;
    var primary = nodesById[activeNodeId] || {};
    var otherId = edgeOtherId(edge, activeNodeId);
    var other = nodesById[otherId] || {};
    var x = crossEvidenceFor(edge, activeNodeId);

    if (elEvidenceTitle) elEvidenceTitle.textContent = (primary.title || '') + ' × ' + (other.title || '');
    if (elEvidenceMeta) elEvidenceMeta.textContent = x.article_count + ' 篇共现 abstract · ' + (x.level ? '最佳证据 ' + x.level : '证据等级未标注');

    var refsHtml = x.references.length
      ? '<ul class="kg-study-list">' + x.references.slice(0, 20).map(renderReferenceItem).join('') + '</ul>'
      : '<div class="kg-empty-hint">这条关系没有可展示的代表文献。</div>';
    var limitHtml = x.limitation
      ? '<p class="kg-detail-note">' + escapeHtml(x.limitation) + '</p>'
      : '';

    elEvidenceBody.innerHTML =
      '<div class="cross-evidence-head">' +
        '<span class="kg-badge">' + escapeHtml(x.relation || '共现关系') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(x.key_pmids.length) + ' 条代表 PMID</span>' +
        (x.hasMatrix ? '' : '<span class="kg-badge conf-low">非完整清单</span>') +
      '</div>' +
      limitHtml +
      '<p class="kg-detail-note">以下为两者在同一批文献中共同出现时被抽到的代表文献（PMID 标题可点回原文）。共现不代表疗效或因果。</p>' +
      refsHtml;
    elEvidencePane.hidden = false;
  }

  // 专题来源类型：策展层沿用旧 wiki 分类，这里只作标签，不参与图谱节点类型语义。
  var topicSourceTypeLabel = {
    concept: '概念专题',
    entity: '事实专题',
    dataPoint: '数据专题',
    comparison: '对比专题'
  };

  // 策展快照日期：来自 curated-topics.js 的 generated_at，只取日期部分。
  // 它不等于 topic.updated（各 wiki 正文的更新日期），两者都展示以避免误导。
  var topicSnapshotDate = (function () {
    var raw = curatedData.generated_at || '';
    return raw ? String(raw).slice(0, 10) : '未知';
  })();

  // 右栏渲染一个完整策展专题（供 ?topic= 深链使用）。
  // 数据已在内存（knowledge.html 已加载 curated-topics.js），标注为静态策展快照。
  function renderTopicCuration(topicId) {
    if (!elCurationPanel) return;
    var topic = topicsById[topicId];
    if (!topic) {
      elCurationPanel.innerHTML = '<div class="kg-empty-hint">未找到该策展专题。</div>';
      return;
    }
    var kind = topicSourceTypeLabel[topic.source_type] || '策展专题';
    var updated = topic.updated || '未知';

    var claimsHtml = (topic.claims || []).slice(0, 5).map(function (claim) {
      var meta = [claim.claim_type, claim.section].filter(Boolean).join(' · ');
      return '<div class="curated-claim">' +
        (meta ? '<span>' + escapeHtml(meta) + '</span>' : '') +
        '<p>' + escapeHtml(claim.text || '') + '</p>' +
      '</div>';
    }).join('');

    var sceneHtml = (topic.msl_use || []).map(function (scene) {
      return '<span class="mini-chip">' + escapeHtml(scene) + '</span>';
    }).join('');

    var anchorHtml = (topic.anchor_nodes || []).filter(function (id) { return nodesById[id]; }).map(function (id) {
      return '<button class="kg-relation-row" type="button" data-node="' + escapeHtml(id) + '">' +
        '<span>锚点节点</span><strong>' + escapeHtml(nodesById[id].title || id) + '</strong><em>跳转图谱</em>' +
      '</button>';
    }).join('');

    var refs = topic.evidence_refs || [];
    var refsHtml = refs.length
      ? '<ul class="kg-study-list">' + refs.slice(0, 8).map(renderReferenceItem).join('') + '</ul>'
      : '<div class="kg-empty-hint">暂无可校验 PMID；本专题观点无法据摘要级文献直接溯源。</div>';

    var recent = (topic.impact && topic.impact.recent_articles) || [];
    var recentHtml = recent.length
      ? '<div class="kg-detail-section"><h4>快照新增证据（' + escapeHtml(topicSnapshotDate) + '）</h4>' +
        '<ul class="kg-study-list">' + recent.slice(0, 5).map(renderReferenceItem).join('') + '</ul></div>'
      : '';

    var obsidianLink = topic.obsidian_url
      ? '<a class="text-link" href="' + escapeHref(topic.obsidian_url) + '">在本地 Obsidian 打开原文</a>（需安装 Obsidian 与 efgartigimod-wiki 库）'
      : '';

    elCurationPanel.innerHTML =
      '<div class="topic-freshness-note">静态策展快照 · 数据截至 ' + escapeHtml(topicSnapshotDate) +
        ' · 正文更新 ' + escapeHtml(updated) + '。为观点性整理，非实时证据；引用前请核对 PMID 原文。</div>' +
      '<div class="curated-topic-detail">' +
        '<h2>' + escapeHtml(topic.title) + '</h2>' +
        '<div class="kg-badges">' +
          '<span class="kg-badge">' + escapeHtml(kind) + '</span>' +
          '<span class="kg-badge">' + escapeHtml(topic.confidence || '未标注') + '</span>' +
          '<span class="kg-badge">' + escapeHtml(topic.status || '') + '</span>' +
        '</div>' +
        '<div class="kg-detail-summary">' + escapeHtml(topic.summary || '') + '</div>' +
        (sceneHtml ? '<div class="kg-detail-section"><h4>沟通场景</h4><div class="kg-tags">' + sceneHtml + '</div></div>' : '') +
        (claimsHtml ? '<div class="kg-detail-section"><h4>策展要点（EFG 视角观点，非证据结论）</h4>' + claimsHtml + '</div>' : '') +
        (anchorHtml ? '<div class="kg-detail-section"><h4>关联节点</h4><div class="kg-relation-list">' + anchorHtml + '</div></div>' : '') +
        '<div class="kg-detail-section"><h4>长期知识底座 PMID</h4>' + refsHtml + '</div>' +
        recentHtml +
        (obsidianLink || topic.rel_path
          ? '<div class="kg-detail-section"><h4>原始笔记</h4><div class="kg-detail-summary">' +
            (topic.rel_path ? '<code>' + escapeHtml(topic.rel_path) + '</code><br>' : '') + obsidianLink +
            '</div></div>'
          : '') +
      '</div>';

    // 专题内的锚点按钮：图谱内选中该节点。
    Array.prototype.forEach.call(elCurationPanel.querySelectorAll('[data-node]'), function (button) {
      button.addEventListener('click', function () {
        selectNode(button.getAttribute('data-node'));
      });
    });
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

  // 深链 ?topic=<id>：专题来自策展层，有文档契约（operationsManual）但此前无实现。
  // 非法 id 安全降级为空，不报错。
  function getInitialKnowledgeTopicId() {
    try {
      var params = new URLSearchParams(window.location.search || '');
      var topicId = params.get('topic') || '';
      if (topicId && topicsById[topicId]) return topicId;
      return '';
    } catch (err) {
      return '';
    }
  }

  function openTopic(topicId) {
    // 深链 ?topic=：在右栏策展区显示该专题完整内容，页内不跳页。
    activeTopicId = topicId;
    renderTopicCuration(topicId);
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
    var closeEvidenceBtn = document.getElementById('kgEvidenceClose');
    if (closeEvidenceBtn) closeEvidenceBtn.addEventListener('click', hideEvidencePane);

    renderBadge();
    renderStats();
    initializeCommunityControls();
    buildGraph();
    attachPanZoom();
    attachGraphInteraction();
    attachNodeFilters();
    attachTabs();

    var initialCommunityId = getInitialKnowledgeCommunityId();
    var initialNodeId = getInitialKnowledgeNodeId();
    var initialTopicId = getInitialKnowledgeTopicId();
    var initialTab = getInitialKnowledgeTab();
    var defaultNodeId = nodesById.fcrnInhibition ? 'fcrnInhibition' : (nodes[0] && nodes[0].id);

    if (initialTopicId) {
      // 专题深链：选一个锚点节点作为身份卡上下文，并在工作台展开该专题。
      var topic = topicsById[initialTopicId];
      var anchors = (topic.anchor_nodes || []).filter(function (id) { return nodesById[id]; });
      var anchorNodeId = anchors[0] || defaultNodeId;
      activateTab('graph');
      selectNode(anchorNodeId, { topicId: initialTopicId });
    } else if (initialNodeId) {
      activateTab('graph');
      selectNode(initialNodeId);
    } else if (initialCommunityId) {
      openCommunityGraph(initialCommunityId);
    } else {
      selectNode(defaultNodeId);
      if (['graph', 'china-network'].indexOf(initialTab) !== -1) activateTab(initialTab);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
