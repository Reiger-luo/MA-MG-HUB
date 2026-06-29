/* MA-MG-HUB 知识库
 * 数据来源: full PubMed abstract 派生知识图谱。
 * 关系代表标题、摘要与元数据层面的证据线索，不替代全文判断。
 */
(function () {
  'use strict';

  var graphData = window.MG_KNOWLEDGE_GRAPH || {};
  var nodes = graphData.nodes || [];
  var edges = graphData.edges || [];
  var nodeRefs = graphData.node_references || {};
  var edgeRefs = graphData.edge_references || {};
  var matrixRows = graphData.evidence_matrix || [];
  var curatedData = window.MG_CURATED_TOPICS || { topics: [], bridge_by_node: {}, stats: {} };
  var curatedTopics = curatedData.topics || [];
  var topicsById = {};
  curatedTopics.forEach(function (topic) { topicsById[topic.id] = topic; });
  var communityTaxonomy = window.MG_COMMUNITY_TAXONOMY || { communities: [] };
  var communityCardsData = window.MG_COMMUNITY_CARDS || { cards: [] };
  var communityWeeklyData = window.MG_COMMUNITY_WEEKLY || { communities: [] };
  var communityAuditData = window.MG_COMMUNITY_AUDIT || { summary: {}, health: {} };
  var communityCards = communityCardsData.cards || [];
  var communityRows = [];
  var communityCardsById = {};
  var taxonomyById = {};
  var weeklyByCommunityId = {};
  (communityTaxonomy.communities || []).forEach(function (item) { taxonomyById[item.id] = item; });
  (communityWeeklyData.communities || []).forEach(function (item) { weeklyByCommunityId[item.community_id] = item; });
  communityCards.forEach(function (card) { communityCardsById[card.id] = card; });
  communityCards.forEach(function (card) {
    communityRows.push(Object.assign({}, taxonomyById[card.id] || {}, card));
  });
  (communityTaxonomy.communities || []).forEach(function (item) {
    if (!communityCardsById[item.id]) communityRows.push(item);
  });
  var articles = window.MG_LITERATURE_DATA || [];
  var experts = (window.MG_EXPERT_PROFILES && window.MG_EXPERT_PROFILES.experts) || [];
  var searchDepsLoaded = !!(articles.length || experts.length);

  function loadSearchDeps(callback) {
    if (searchDepsLoaded) { callback(); return; }
    var remaining = 2;
    function done() { if (--remaining === 0) { searchDepsLoaded = true; callback(); } }
    var s1 = document.createElement('script');
    s1.src = '/MA-MG-HUB/data/literature-recent.js';
    s1.onload = done;
    s1.onerror = done;
    document.head.appendChild(s1);
    var s2 = document.createElement('script');
    s2.src = '/MA-MG-HUB/data/expert-profiles.js';
    s2.onload = done;
    s2.onerror = done;
    document.head.appendChild(s2);
  }

  var elBadge = document.getElementById('knowledgeBadge');
  var elStats = document.getElementById('knowledgeStats');
  var elCanvas = document.getElementById('knowledgeGraph');
  var elDetail = document.getElementById('knowledgeDetail');
  var elZoomLabel = document.getElementById('kgZoomLabel');
  var elNodeSearch = document.getElementById('knowledgeNodeSearch');
  var elTypeFilter = document.getElementById('knowledgeTypeFilter');
  var elMatrix = document.getElementById('knowledgeMatrix');
  var elMatrixCount = document.getElementById('matrixCount');
  var elMatrixSearch = document.getElementById('knowledgeMatrixSearch');
  var elMatrixType = document.getElementById('knowledgeMatrixType');
  var elMatrixLevel = document.getElementById('knowledgeMatrixLevel');
  var elTopicCount = document.getElementById('topicCount');
  var elTopicSearch = document.getElementById('curatedTopicSearch');
  var elTopicImpact = document.getElementById('curatedTopicImpact');
  var elTopicList = document.getElementById('curatedTopicList');
  var elTopicDetail = document.getElementById('curatedTopicDetail');
  var elCommunityCount = document.getElementById('communityCount');
  var elCommunitySearch = document.getElementById('communitySearch');
  var elCommunitySignal = document.getElementById('communitySignalFilter');
  var elCommunityAuditStrip = document.getElementById('communityAuditStrip');
  var elCommunityList = document.getElementById('communityList');
  var elCommunityDetail = document.getElementById('communityDetail');
  var elSearch = document.getElementById('knowledgeSearch');
  var elSearchResults = document.getElementById('knowledgeSearchResults');

  var svgNamespace = 'http://www.w3.org/2000/svg';
  var viewBox = { x: 0, y: 0, w: 1100, h: 720 };
  var zoomScale = 1;
  var scaleMin = 0.45;
  var scaleMax = 3.2;
  var activeNodeId = null;
  var activeCommunityId = null;
  var communityAssignmentCache = {};
  var communityAssignmentLoading = {};
  var communityAssignmentErrors = {};
  var communityAssignmentCallbacks = {};

  var nodesById = {};
  var edgesById = {};
  var neighborMap = {};
  nodes.forEach(function (node) {
    nodesById[node.id] = node;
    neighborMap[node.id] = {};
  });
  edges.forEach(function (edge) {
    edgesById[edge.id] = edge;
    neighborMap[edge.from] = neighborMap[edge.from] || {};
    neighborMap[edge.to] = neighborMap[edge.to] || {};
    neighborMap[edge.from][edge.to] = true;
    neighborMap[edge.to][edge.from] = true;
  });

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
    llmInferred: '模型推断',
    curated: '人工策展'
  };

  var communitySignalLabel = {
    active: '活跃',
    watch: '观察',
    quiet: '平稳',
    high: '高活跃',
    medium: '中活跃',
    low: '低活跃'
  };

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
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
    elBadge.textContent = compactNumber(stats.matched_articles) + ' 篇 abstract · ' +
      (stats.total_nodes || 0) + ' 节点 · ' +
      (stats.edges || 0) + ' 关系';
  }

  function renderStats() {
    if (!elStats) return;
    var stats = graphData.stats || {};
    var cards = [
      { label: '命中文献', value: compactNumber(stats.matched_articles), note: 'full PubMed abstract' },
      { label: '有证据等级', value: compactNumber(stats.evidence_articles), note: 'I-VI 或已分级' },
      { label: '图谱节点', value: stats.total_nodes || 0, note: '疾病/药物/机制/结局' },
      { label: '证据矩阵', value: stats.evidence_matrix_rows || 0, note: '可回链 PMID 的关系' },
      { label: '医学社区', value: communityRows.length || 0, note: '全 MG 语义层' },
      { label: '专题', value: (curatedData.stats && curatedData.stats.topics) || 0, note: 'wiki 自动同步' }
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

  function buildGraph() {
    if (!elCanvas) return;
    elCanvas.innerHTML = '';
    elCanvas.setAttribute('viewBox', viewBox.x + ' ' + viewBox.y + ' ' + viewBox.w + ' ' + viewBox.h);

    var edgeLayer = svgEl('g', { class: 'kg-edge-layer' });
    edges.forEach(function (edge) {
      var source = nodesById[edge.from];
      var target = nodesById[edge.to];
      if (!source || !target) return;
      var line = svgEl('line', {
        class: 'kg-edge source-' + edge.source_type,
        x1: source.x,
        y1: source.y,
        x2: target.x,
        y2: target.y,
        'data-id': edge.id,
        'data-from': edge.from,
        'data-to': edge.to,
        'stroke-width': edgeWidth(edge)
      });
      edgeLayer.appendChild(line);
    });
    elCanvas.appendChild(edgeLayer);

    var nodeLayer = svgEl('g', { class: 'kg-node-layer' });
    nodes.forEach(function (node) {
      var group = svgEl('g', {
        class: 'kg-node type-' + node.type + ' conf-' + node.confidence,
        'data-id': node.id,
        'data-type': node.type,
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

    elCanvas.addEventListener('click', function () {
      activeNodeId = null;
      clearActive();
      clearHighlight();
    });
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

  function selectNode(id) {
    if (!nodesById[id]) return;
    activeNodeId = id;
    clearActive();
    clearHighlight();
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
    var relatedEdges = edges.filter(function (edge) {
      return edge.from === id || edge.to === id;
    }).sort(function (a, b) {
      return (b.article_count || 0) - (a.article_count || 0);
    }).slice(0, 8);

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

    elDetail.innerHTML =
      '<div class="kg-detail-type">' + escapeHtml(typeLabel[node.type] || node.type) + '</div>' +
      '<h2>' + escapeHtml(node.title) + '</h2>' +
      '<div class="kg-badges">' +
        '<span class="kg-badge conf-' + escapeHtml(node.confidence || 'low') + '">' + escapeHtml(confidenceLabel[node.confidence] || '覆盖未知') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(node.article_count || 0) + ' 篇 abstract</span>' +
        '<span class="kg-badge">' + escapeHtml(sourceTypeLabel[node.source_type] || '摘要提及') + '</span>' +
      '</div>' +
      '<div class="kg-detail-summary">' + escapeHtml(node.summary || '') + '</div>' +
      topicHtml +
      '<div class="kg-detail-section"><h4>证据等级分布</h4><div class="kg-tags">' + levelHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>关联关系</h4><div class="kg-relation-list">' + relatedHtml + '</div></div>' +
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

  function renderReferenceItem(ref) {
    var meta = [
      ref.journal || '',
      ref.pub_date || '',
      ref.evidence_level ? 'Level ' + ref.evidence_level : '',
      (ref.study_types || []).slice(0, 2).join(' / ')
    ].filter(Boolean).join(' · ');
    return '<li><a class="text-link" href="' + escapeHtml(ref.url) + '" target="_blank" rel="noopener">PMID ' +
      escapeHtml(ref.pmid) + '</a> ' + escapeHtml(ref.title || '') +
      '<br><span class="kg-ref-meta">' + escapeHtml(meta) + '</span></li>';
  }

  function attachNodeFilters() {
    if (elNodeSearch) elNodeSearch.addEventListener('input', applyNodeFilters);
    if (elTypeFilter) elTypeFilter.addEventListener('change', applyNodeFilters);
    applyNodeFilters();
  }

  function applyNodeFilters() {
    if (!elCanvas) return;
    var keyword = (elNodeSearch && elNodeSearch.value || '').trim().toLowerCase();
    var type = (elTypeFilter && elTypeFilter.value) || 'all';
    var visible = {};

    nodes.forEach(function (node) {
      var text = [node.title, node.summary, node.type, (node.top_study_types || []).join(' ')].join(' ').toLowerCase();
      var okKeyword = !keyword || text.indexOf(keyword) !== -1;
      var okType = type === 'all' || node.type === type;
      visible[node.id] = okKeyword && okType;
    });

    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-node'), function (nodeEl) {
      var id = nodeEl.getAttribute('data-id');
      nodeEl.classList.toggle('filtered-out', !visible[id]);
    });
    Array.prototype.forEach.call(elCanvas.querySelectorAll('.kg-edge'), function (line) {
      var source = line.getAttribute('data-from');
      var target = line.getAttribute('data-to');
      line.classList.toggle('filtered-out', !visible[source] || !visible[target]);
    });
  }

  function renderMatrix() {
    if (!elMatrix) return;
    var keyword = (elMatrixSearch && elMatrixSearch.value || '').trim().toLowerCase();
    var type = (elMatrixType && elMatrixType.value) || 'all';
    var level = (elMatrixLevel && elMatrixLevel.value) || 'all';
    var rows = matrixRows.filter(function (row) {
      var text = [
        row.source, row.target, row.relation, row.best_evidence_level,
        (row.key_pmids || []).join(' ')
      ].join(' ').toLowerCase();
      var typeMatch = type === 'all' || row.source_type === type || row.target_type === type;
      var levelMatch = level === 'all' || row.best_evidence_level === level;
      return (!keyword || text.indexOf(keyword) !== -1) && typeMatch && levelMatch;
    });
    if (elMatrixCount) elMatrixCount.textContent = rows.length + ' 行';

    if (!rows.length) {
      elMatrix.innerHTML = '<div class="kg-empty-hint">没有匹配的证据关系。</div>';
      return;
    }

    var tableRows = rows.map(function (row) {
      var pmids = (row.references || []).map(function (ref) {
        return '<a class="kg-pmid-link" href="' + escapeHtml(ref.url) + '" target="_blank" rel="noopener">' +
          escapeHtml(ref.pmid) + '</a>';
      }).join(' ');
      return '<tr>' +
        '<td><button class="matrix-node-link" type="button" data-node="' + escapeHtml(row.source_id) + '">' + escapeHtml(row.source) + '</button></td>' +
        '<td>' + escapeHtml(row.relation) + '</td>' +
        '<td><button class="matrix-node-link" type="button" data-node="' + escapeHtml(row.target_id) + '">' + escapeHtml(row.target) + '</button></td>' +
        '<td><span class="kg-badge conf-' + escapeHtml(row.confidence || 'low') + '">' + escapeHtml(confidenceLabel[row.confidence] || row.confidence || '未知') + '</span></td>' +
        '<td>' + escapeHtml(row.article_count || 0) + '</td>' +
        '<td>' + escapeHtml(row.best_evidence_level || '未分级') + '</td>' +
        '<td>' + pmids + '</td>' +
      '</tr>';
    }).join('');

    elMatrix.innerHTML = '<table><thead><tr>' +
      '<th>来源节点</th><th>关系</th><th>目标节点</th><th>覆盖</th><th>文献量</th><th>最高等级</th><th>PMID</th>' +
      '</tr></thead><tbody>' + tableRows + '</tbody></table>';

    Array.prototype.forEach.call(elMatrix.querySelectorAll('[data-node]'), function (button) {
      button.addEventListener('click', function () {
        activateTab('graph');
        selectNode(button.getAttribute('data-node'));
      });
    });
  }

  function attachMatrixFilters() {
    [elMatrixSearch, elMatrixType, elMatrixLevel].forEach(function (el) {
      if (el) el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', renderMatrix);
    });
    renderMatrix();
  }

  function renderTopics(selectedId) {
    if (!elTopicList || !elTopicDetail) return;
    var keyword = (elTopicSearch && elTopicSearch.value || '').trim().toLowerCase();
    var impactFilter = (elTopicImpact && elTopicImpact.value) || 'all';
    var topics = curatedTopics.filter(function (topic) {
      var text = [
        topic.title,
        topic.summary,
        topic.source_type,
        (topic.anchor_nodes || []).join(' '),
        (topic.evidence_pmids || []).join(' '),
        (topic.msl_use || []).join(' ')
      ].join(' ').toLowerCase();
      var impact = (topic.impact && topic.impact.status) || 'quiet';
      return (!keyword || text.indexOf(keyword) !== -1) &&
        (impactFilter === 'all' || impact === impactFilter);
    });
    if (elTopicCount) elTopicCount.textContent = topics.length + ' 个专题';
    if (!topics.length) {
      elTopicList.innerHTML = '<div class="kg-empty-hint">没有匹配的专题。</div>';
      elTopicDetail.innerHTML = '<div class="kg-empty-hint">调整筛选条件查看专题。</div>';
      return;
    }

    var activeId = selectedId && topicsById[selectedId] ? selectedId : topics[0].id;
    elTopicList.innerHTML = topics.map(function (topic) {
      var impactCount = ((topic.impact && topic.impact.recent_articles) || []).length;
      return '<button class="curated-topic-card' + (topic.id === activeId ? ' active' : '') + '" type="button" data-topic="' + escapeHtml(topic.id) + '">' +
        '<span>' + escapeHtml(sourceTypeLabelForTopic(topic.source_type)) + '</span>' +
        '<strong>' + escapeHtml(topic.title) + '</strong>' +
        '<em>' + escapeHtml((topic.evidence_refs || []).length) + ' PMID · ' + escapeHtml((topic.anchor_nodes || []).length) + ' 锚点' +
          (impactCount ? ' · 本周 ' + impactCount : '') + '</em>' +
      '</button>';
    }).join('');

    Array.prototype.forEach.call(elTopicList.querySelectorAll('[data-topic]'), function (button) {
      button.addEventListener('click', function () {
        renderTopicDetail(button.getAttribute('data-topic'));
        Array.prototype.forEach.call(elTopicList.querySelectorAll('.curated-topic-card'), function (item) {
          item.classList.toggle('active', item === button);
        });
      });
    });
    renderTopicDetail(activeId);
  }

  function sourceTypeLabelForTopic(value) {
    return {
      concept: '概念专题',
      entity: '实体专题',
      dataPoint: '数据专题',
      comparison: '对比专题'
    }[value] || '专题';
  }

  function renderTopicDetail(topicId) {
    if (!elTopicDetail) return;
    var topic = topicsById[topicId];
    if (!topic) {
      elTopicDetail.innerHTML = '<div class="kg-empty-hint">选择一个专题查看详情。</div>';
      return;
    }
    var anchorHtml = (topic.anchor_nodes || []).map(function (nodeId) {
      var node = nodesById[nodeId] || {};
      return '<button class="mini-chip chip-button" type="button" data-node="' + escapeHtml(nodeId) + '">' +
        escapeHtml(node.title || nodeId) + '</button>';
    }).join('');
    var useHtml = (topic.msl_use || []).map(function (item) {
      return '<span class="mini-chip">' + escapeHtml(item) + '</span>';
    }).join('');
    var claimHtml = (topic.claims || []).slice(0, 5).map(function (claim) {
      return '<article class="curated-claim">' +
        '<span>' + escapeHtml(claim.claim_type || 'claim') + (claim.section ? ' · ' + escapeHtml(claim.section) : '') + '</span>' +
        '<p>' + escapeHtml(claim.text || '') + '</p>' +
      '</article>';
    }).join('');
    var refsHtml = (topic.evidence_refs || []).length ?
      topic.evidence_refs.slice(0, 8).map(renderReferenceItem).join('') :
      '<li>暂无可校验 PMID；可在 wiki 中补充 evidence_pmids。</li>';
    var impactItems = ((topic.impact && topic.impact.recent_articles) || []).slice(0, 6);
    var impactHtml = impactItems.length ? impactItems.map(renderReferenceItem).join('') : '<li>本周未发现明确影响该专题的新 abstract。</li>';

    elTopicDetail.innerHTML =
      '<div class="kg-detail-type">' + escapeHtml(sourceTypeLabelForTopic(topic.source_type)) + '</div>' +
      '<h2>' + escapeHtml(topic.title) + '</h2>' +
      '<div class="kg-badges">' +
        '<span class="kg-badge conf-' + escapeHtml(topic.confidence === 'high' ? 'high' : topic.confidence === 'medium' ? 'medium' : 'low') + '">' + escapeHtml(topic.confidence || 'unknown') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(topic.status || 'active') + '</span>' +
        '<span class="kg-badge">更新 ' + escapeHtml(topic.updated || '-') + '</span>' +
      '</div>' +
      '<div class="kg-detail-summary">' + escapeHtml(topic.summary || '') + '</div>' +
      '<div class="kg-detail-section"><h4>全库锚点</h4><div class="kg-tags">' + anchorHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>MSL 使用场景</h4><div class="kg-tags">' + useHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>专题要点</h4>' + claimHtml + '</div>' +
      '<div class="kg-detail-section"><h4>专题 PMID</h4><ul class="kg-study-list">' + refsHtml + '</ul></div>' +
      '<div class="kg-detail-section"><h4>本周自动影响提示</h4><ul class="kg-study-list">' + impactHtml + '</ul></div>' +
      '<div class="kg-detail-actions"><a class="kg-obsidian-btn" href="' + escapeHtml(topic.obsidian_url || '#') + '">在 Obsidian 中打开</a></div>';

    Array.prototype.forEach.call(elTopicDetail.querySelectorAll('[data-node]'), function (button) {
      button.addEventListener('click', function () {
        activateTab('graph');
        selectNode(button.getAttribute('data-node'));
      });
    });
  }

  function attachTopicFilters() {
    if (elTopicSearch) elTopicSearch.addEventListener('input', function () { renderTopics(); });
    if (elTopicImpact) elTopicImpact.addEventListener('change', function () { renderTopics(); });
    renderTopics();
  }

  function communitySignalClass(value) {
    if (value === 'active' || value === 'high') return 'high';
    if (value === 'watch' || value === 'medium') return 'medium';
    return 'low';
  }

  function communitySignalText(value) {
    return communitySignalLabel[value] || value || '平稳';
  }

  function communityFilterSignal(value) {
    if (value === 'high') return 'active';
    if (value === 'medium') return 'watch';
    if (value === 'low') return 'quiet';
    return value || 'quiet';
  }

  function communityTermsText(terms) {
    if (!terms) return '';
    return ['strong', 'normal', 'weak'].map(function (key) {
      return (terms[key] || []).join(' ');
    }).join(' ');
  }

  function loadScriptOnce(src, callback) {
    var existing = document.querySelector('script[src="' + attrSelectorEscape(src) + '"]');
    if (existing && existing.getAttribute('data-loaded') === '1') {
      callback(true);
      return;
    }
    if (existing && existing.getAttribute('data-loading') === '1') {
      existing.addEventListener('load', function () { callback(true); }, { once: true });
      existing.addEventListener('error', function () { callback(false); }, { once: true });
      return;
    }
    var script = existing || document.createElement('script');
    script.src = src;
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
    loadScriptOnce('/MA-MG-HUB/data/communityAssignments-' + encodeURIComponent(communityId) + '.js', function (ok) {
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
        '<a href="https://pubmed.ncbi.nlm.nih.gov/' + escapeHtml(item.pmid) + '/" target="_blank" rel="noopener">PMID ' + escapeHtml(item.pmid) + '</a>' +
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

  function renderCommunityAuditStrip() {
    if (!elCommunityAuditStrip) return;
    var summary = communityAuditData.summary || {};
    var total = Number(summary.total_articles || 0);
    if (!total) {
      elCommunityAuditStrip.innerHTML = '<div class="community-audit-item"><span>社区层</span><strong>未生成</strong><em>等待周更管线</em></div>';
      return;
    }
    function rate(value) {
      return (Number(value || 0) / total * 100).toFixed(1).replace(/\.0$/, '') + '%';
    }
    var items = [
      { label: '全库文献', value: compactNumber(total), note: '社区归类基线' },
      { label: '已归类', value: compactNumber(summary.assigned_articles), note: rate(summary.assigned_articles) },
      { label: '未归类', value: compactNumber(summary.unassigned_articles), note: rate(summary.unassigned_articles) },
      { label: '低置信度', value: compactNumber(summary.low_confidence_articles), note: rate(summary.low_confidence_articles) },
      { label: '冲突归类', value: compactNumber(summary.conflict_articles), note: rate(summary.conflict_articles) }
    ];
    elCommunityAuditStrip.innerHTML = items.map(function (item) {
      return '<div class="community-audit-item">' +
        '<span>' + escapeHtml(item.label) + '</span>' +
        '<strong>' + escapeHtml(item.value) + '</strong>' +
        '<em>' + escapeHtml(item.note) + '</em>' +
      '</div>';
    }).join('');
  }

  function renderCommunities(selectedId) {
    if (!elCommunityList || !elCommunityDetail) return;
    var keyword = (elCommunitySearch && elCommunitySearch.value || '').trim().toLowerCase();
    var signalFilter = (elCommunitySignal && elCommunitySignal.value) || 'all';
    var rows = communityRows.filter(function (row) {
      var taxonomy = taxonomyById[row.id] || {};
      var text = [
        row.title,
        row.definition,
        row.boundary,
        row.summary,
        (row.representative_nodes || taxonomy.representative_nodes || []).join(' '),
        (row.msl_use_cases || taxonomy.msl_use_cases || []).join(' '),
        (row.facets || taxonomy.facets || []).join(' '),
        communityTermsText(taxonomy.terms || row.terms)
      ].join(' ').toLowerCase();
      var signal = communityFilterSignal(row.signal_level);
      return (!keyword || text.indexOf(keyword) !== -1) &&
        (signalFilter === 'all' || signal === signalFilter);
    }).sort(function (a, b) {
      return (b.recent_14d_count || 0) - (a.recent_14d_count || 0) ||
        (b.article_count || 0) - (a.article_count || 0);
    });

    if (elCommunityCount) elCommunityCount.textContent = rows.length + ' / ' + communityRows.length + ' 个社区';
    if (!rows.length) {
      elCommunityList.innerHTML = '<div class="kg-empty-hint">没有匹配的社区。</div>';
      elCommunityDetail.innerHTML = '<div class="kg-empty-hint">调整筛选条件查看社区。</div>';
      return;
    }

    var wantedId = selectedId || activeCommunityId;
    var activeRow = rows.find(function (row) { return row.id === wantedId; }) || rows[0];
    activeCommunityId = activeRow.id;
    elCommunityList.innerHTML = rows.map(function (row) {
      var weekly = weeklyByCommunityId[row.id] || {};
      var signal = row.signal_level || communityFilterSignal(weekly.signal_level);
      var meta = compactNumber(row.article_count || 0) + ' 篇 · 本周 ' + compactNumber(row.recent_14d_count || weekly.recent_count || 0) +
        ' · 高等级 ' + compactNumber(row.high_evidence_count || weekly.high_evidence_count || 0);
      return '<button class="curated-topic-card community-card' + (row.id === activeCommunityId ? ' active' : '') + '" type="button" data-community="' + escapeHtml(row.id) + '">' +
        '<span class="community-signal">' + escapeHtml(communitySignalText(signal)) + '</span>' +
        '<strong>' + escapeHtml(row.title || row.id) + '</strong>' +
        '<em>' + escapeHtml(meta) + '</em>' +
      '</button>';
    }).join('');

    Array.prototype.forEach.call(elCommunityList.querySelectorAll('[data-community]'), function (button) {
      button.addEventListener('click', function () {
        renderCommunityDetail(button.getAttribute('data-community'));
        Array.prototype.forEach.call(elCommunityList.querySelectorAll('.community-card'), function (item) {
          item.classList.toggle('active', item === button);
        });
      });
    });
    renderCommunityDetail(activeCommunityId);
  }

  function renderCommunityProfileBox(title, rows) {
    rows = Array.isArray(rows) ? rows.slice(0, 6) : [];
    if (!rows.length) return '';
    var max = rows.reduce(function (memo, row) { return Math.max(memo, Number(row[1] || 0)); }, 1);
    return '<div class="community-profile-box"><h5>' + escapeHtml(title) + '</h5>' +
      rows.map(function (row) {
        var percent = Math.max(4, Math.round(Number(row[1] || 0) / max * 100));
        return '<div class="community-profile-row">' +
          '<span>' + escapeHtml(row[0]) + '</span><em>' + escapeHtml(row[1]) + '</em>' +
          '<div class="community-meter" style="--meter-value:' + escapeHtml(percent) + '%"><i></i></div>' +
        '</div>';
      }).join('') + '</div>';
  }

  function renderCommunityDetail(communityId) {
    if (!elCommunityDetail) return;
    var card = communityCardsById[communityId] || {};
    var taxonomy = taxonomyById[communityId] || {};
    var weekly = weeklyByCommunityId[communityId] || {};
    var row = Object.assign({}, taxonomy, card);
    if (!row.id) {
      elCommunityDetail.innerHTML = '<div class="kg-empty-hint">选择一个社区查看详情。</div>';
      return;
    }
    activeCommunityId = row.id;

    var signal = row.signal_level || communityFilterSignal(weekly.signal_level);
    var nodeIds = row.representative_nodes || taxonomy.representative_nodes || [];
    var nodeHtml = nodeIds.map(function (nodeId) {
      var node = nodesById[nodeId] || {};
      return '<button class="mini-chip chip-button" type="button" data-node="' + escapeHtml(nodeId) + '">' +
        escapeHtml(node.title || nodeId) + '</button>';
    }).join('');
    var useHtml = (row.msl_use_cases || taxonomy.msl_use_cases || []).map(function (item) {
      return '<span class="mini-chip">' + escapeHtml(item) + '</span>';
    }).join('');
    var facetHtml = (row.facets || taxonomy.facets || []).map(function (item) {
      return '<span class="mini-chip">' + escapeHtml(item) + '</span>';
    }).join('');
    var terms = taxonomy.terms || row.terms || {};
    var termHtml = ['strong', 'normal', 'weak'].map(function (key) {
      return (terms[key] || []).slice(0, 10).map(function (term) {
        return '<span class="mini-chip">' + escapeHtml(term) + '</span>';
      }).join('');
    }).join('');
    var refsHtml = (row.representative_refs || []).length ?
      row.representative_refs.slice(0, 6).map(renderReferenceItem).join('') :
      '<li>暂无代表 PMID；等待社区层下一轮重建。</li>';
    var recentRefs = (weekly.top_refs && weekly.top_refs.length) ? weekly.top_refs : (row.recent_refs || []);
    var recentHtml = recentRefs.length ?
      recentRefs.slice(0, 6).map(renderReferenceItem).join('') :
      '<li>本周未发现明确进入该社区的新 abstract。</li>';
    var profileHtml = renderCommunityProfileBox('证据等级', row.evidence_profile) +
      renderCommunityProfileBox('研究类型', row.study_type_profile);

    elCommunityDetail.innerHTML =
      '<div class="kg-detail-type">医学事务社区 · ' + escapeHtml(communitySignalText(signal)) + '</div>' +
      '<h2>' + escapeHtml(row.title || row.id) + '</h2>' +
      '<div class="kg-badges">' +
        '<span class="kg-badge conf-' + escapeHtml(communitySignalClass(signal)) + '">' + escapeHtml(communitySignalText(signal)) + '</span>' +
        '<span class="kg-badge">' + escapeHtml(compactNumber(row.article_count || 0)) + ' 篇</span>' +
        '<span class="kg-badge">本周 ' + escapeHtml(compactNumber(row.recent_14d_count || weekly.recent_count || 0)) + '</span>' +
        '<span class="kg-badge">中国 ' + escapeHtml(compactNumber(row.china_count || weekly.china_count || 0)) + '</span>' +
      '</div>' +
      '<div class="kg-detail-summary">' + escapeHtml(row.summary || row.definition || '') + '</div>' +
      (row.boundary ? '<div class="community-boundary">边界：' + escapeHtml(row.boundary) + '</div>' : '') +
      '<div class="kg-detail-section"><h4>代表节点</h4><div class="kg-tags">' + nodeHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>MSL 使用场景</h4><div class="kg-tags">' + useHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>Facet 与关键词</h4><div class="kg-tags">' + facetHtml + termHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>证据结构</h4><div class="community-profile-grid">' + profileHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>代表 PMID</h4><ul class="kg-study-list">' + refsHtml + '</ul></div>' +
      '<div class="kg-detail-section"><h4>本周动态</h4><ul class="kg-study-list">' + recentHtml + '</ul></div>' +
      '<div class="kg-detail-section"><h4>全量归类文献</h4><div class="community-assignment-panel" id="communityAssignmentPanel" data-community="' + escapeHtml(row.id) + '">' +
        '<button class="kg-obsidian-btn" type="button" data-load-community-assignments="' + escapeHtml(row.id) + '">加载全量 PMID</button>' +
        '<span>按需加载该社区 assignment 分片；显示 primary community 的 PMID、置信度和质量标记。</span>' +
      '</div></div>' +
      '<div class="kg-detail-section"><h4>限制</h4><div class="kg-detail-summary">' + escapeHtml(row.limitations || '当前为 title/abstract/metadata 规则基线，后续需要 taxonomy review、LLM 仲裁和人工校准。') + '</div></div>' +
      '<div class="kg-detail-actions"><a class="kg-obsidian-btn" href="/MA-MG-HUB/pages/literature.html?community=' + encodeURIComponent(row.id) + '">在情报中心查看近一年文献</a></div>';

    Array.prototype.forEach.call(elCommunityDetail.querySelectorAll('[data-node]'), function (button) {
      button.addEventListener('click', function () {
        activateTab('graph');
        selectNode(button.getAttribute('data-node'));
      });
    });

    if (communityAssignmentCache[row.id]) {
      renderAssignmentList(row.id, communityAssignmentCache[row.id]);
    } else {
      var loadButton = elCommunityDetail.querySelector('[data-load-community-assignments]');
      if (loadButton) {
        loadButton.addEventListener('click', function () {
          var communityId = loadButton.getAttribute('data-load-community-assignments');
          var panel = document.getElementById('communityAssignmentPanel');
          if (panel) panel.innerHTML = '<div class="kg-empty-hint">正在加载社区 assignment 分片...</div>';
          loadCommunityAssignmentShard(communityId, function (ok, payload) {
            var currentPanel = document.getElementById('communityAssignmentPanel');
            if (!currentPanel || currentPanel.getAttribute('data-community') !== communityId) return;
            if (!ok || !payload) {
              currentPanel.innerHTML = '<div class="kg-empty-hint">该社区分片加载失败，请稍后重试。</div>';
              return;
            }
            renderAssignmentList(communityId, payload);
          });
        });
      }
    }
  }

  function attachCommunityFilters() {
    if (elCommunitySearch) elCommunitySearch.addEventListener('input', function () { renderCommunities(); });
    if (elCommunitySignal) elCommunitySignal.addEventListener('change', function () { renderCommunities(); });
    renderCommunityAuditStrip();
    renderCommunities();
  }

  function openTopic(topicId) {
    activateTab('topics');
    renderTopics(topicId);
  }

  function openCommunity(communityId) {
    activateTab('communities');
    if (elCommunitySearch) elCommunitySearch.value = '';
    if (elCommunitySignal) elCommunitySignal.value = 'all';
    renderCommunities(communityId);
  }

  function activateTab(key) {
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
    Array.prototype.forEach.call(document.querySelectorAll('[data-knowledge-tab]'), function (tab) {
      tab.addEventListener('click', function () {
        activateTab(tab.getAttribute('data-knowledge-tab'));
      });
    });
  }

  function attachSearch() {
    if (!elSearch || !elSearchResults) return;
    elSearch.addEventListener('input', function () {
      if (!searchDepsLoaded) {
        elSearchResults.innerHTML = '<div class="kg-empty-hint">正在加载跨库数据…</div>';
        loadSearchDeps(function () {
          articles = window.MG_LITERATURE_DATA || [];
          experts = (window.MG_EXPERT_PROFILES && window.MG_EXPERT_PROFILES.experts) || [];
          renderSearch();
        });
      } else {
        renderSearch();
      }
    });
    renderSearch();
  }

  function renderSearch() {
    var keyword = (elSearch.value || '').trim().toLowerCase();
    if (!keyword) {
      elSearchResults.innerHTML = '<div class="kg-empty-hint">输入关键词检索知识图谱节点、近一年文献和专家公开画像。</div>';
      return;
    }

    var nodeHits = nodes.filter(function (node) {
      return [node.title, node.summary, node.type, (node.top_study_types || []).join(' ')].join(' ').toLowerCase().indexOf(keyword) !== -1;
    }).slice(0, 8);
    var articleHits = articles.filter(function (article) {
      return [article.title, article.abstract, article.journal, (article.authors || []).join(' ')].join(' ').toLowerCase().indexOf(keyword) !== -1;
    }).slice(0, 8);
    var expertHits = experts.filter(function (expert) {
      return [expert.name_en, expert.name_zh, expert.affiliation, (expert.public_tags || []).join(' ')].join(' ').toLowerCase().indexOf(keyword) !== -1;
    }).slice(0, 5);
    var topicHits = curatedTopics.filter(function (topic) {
      return [
        topic.title,
        topic.summary,
        (topic.anchor_nodes || []).join(' '),
        (topic.evidence_pmids || []).join(' '),
        (topic.msl_use || []).join(' ')
      ].join(' ').toLowerCase().indexOf(keyword) !== -1;
    }).slice(0, 6);
    var communityHits = communityRows.filter(function (row) {
      var taxonomy = taxonomyById[row.id] || {};
      return [
        row.title,
        row.definition,
        row.boundary,
        row.summary,
        (row.representative_nodes || taxonomy.representative_nodes || []).join(' '),
        (row.msl_use_cases || taxonomy.msl_use_cases || []).join(' '),
        communityTermsText(taxonomy.terms || row.terms)
      ].join(' ').toLowerCase().indexOf(keyword) !== -1;
    }).slice(0, 6);

    var html = '';
    html += renderSearchGroup('知识节点', nodeHits, function (node) {
      return '<li><button class="matrix-node-link" type="button" data-node="' + escapeHtml(node.id) + '">' +
        escapeHtml(node.title) + '</button><br><span class="kg-ref-meta">' + escapeHtml(typeLabel[node.type]) +
        ' · ' + escapeHtml(node.article_count) + ' 篇 abstract</span></li>';
    });
    html += renderSearchGroup('专题', topicHits, function (topic) {
      return '<li><button class="matrix-node-link" type="button" data-topic="' + escapeHtml(topic.id) + '">' +
        escapeHtml(topic.title) + '</button><br><span class="kg-ref-meta">' +
        escapeHtml(sourceTypeLabelForTopic(topic.source_type)) + ' · ' + escapeHtml((topic.evidence_refs || []).length) + ' PMID</span></li>';
    });
    html += renderSearchGroup('医学事务社区', communityHits, function (community) {
      return '<li><button class="matrix-node-link" type="button" data-community="' + escapeHtml(community.id) + '">' +
        escapeHtml(community.title || community.id) + '</button><br><span class="kg-ref-meta">' +
        escapeHtml(communitySignalText(community.signal_level)) + ' · ' + escapeHtml(compactNumber(community.article_count || 0)) + ' 篇</span></li>';
    });
    html += renderSearchGroup('近一年文献', articleHits, function (article) {
      return '<li><a class="text-link" href="' + escapeHtml(article.url) + '" target="_blank" rel="noopener">' +
        escapeHtml(article.title) + '</a><br><span class="kg-ref-meta">' +
        escapeHtml(article.journal || '') + ' · PMID ' + escapeHtml(article.pmid || '-') + '</span></li>';
    });
    html += renderSearchGroup('专家公开画像', expertHits, function (expert) {
      return '<li><a class="text-link" href="/MA-MG-HUB/pages/msl.html">' + escapeHtml(expert.name_en || expert.name_zh || '') +
        '</a><br><span class="kg-ref-meta">' + escapeHtml(expert.affiliation || '') + '</span></li>';
    });

    elSearchResults.innerHTML = html || '<div class="kg-empty-hint">无匹配结果。</div>';
    Array.prototype.forEach.call(elSearchResults.querySelectorAll('[data-node]'), function (button) {
      button.addEventListener('click', function () {
        activateTab('graph');
        selectNode(button.getAttribute('data-node'));
      });
    });
    Array.prototype.forEach.call(elSearchResults.querySelectorAll('[data-topic]'), function (button) {
      button.addEventListener('click', function () {
        openTopic(button.getAttribute('data-topic'));
      });
    });
    Array.prototype.forEach.call(elSearchResults.querySelectorAll('[data-community]'), function (button) {
      button.addEventListener('click', function () {
        openCommunity(button.getAttribute('data-community'));
      });
    });
  }

  function renderSearchGroup(title, items, renderer) {
    if (!items.length) return '';
    return '<div class="kg-detail-section"><h4>' + escapeHtml(title) + ' (' + items.length + ')</h4>' +
      '<ul class="kg-study-list">' + items.map(renderer).join('') + '</ul></div>';
  }

  function init() {
    renderBadge();
    renderStats();
    attachTabs();
    buildGraph();
    attachPanZoom();
    attachGraphInteraction();
    attachNodeFilters();
    attachMatrixFilters();
    attachTopicFilters();
    attachCommunityFilters();
    attachSearch();
    selectNode(nodesById.fcrnInhibition ? 'fcrnInhibition' : (nodes[0] && nodes[0].id));
    var initialCommunityId = getInitialKnowledgeCommunityId();
    if (initialCommunityId) {
      openCommunity(initialCommunityId);
    } else if (getInitialKnowledgeTab() === 'communities') {
      activateTab('communities');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
