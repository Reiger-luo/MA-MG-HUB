/* MA-MG-HUB 诊治格局 */
(function() {
  'use strict';

  var hub = window.MgHub || {};
  var data = window.MG_LANDSCAPE_DATA || {};
  var chinaLandscape = data.china_landscape || {};
  var themeDivergence = chinaLandscape.theme_divergence || {};
  var guidelineDivergence = chinaLandscape.guideline_divergence || {};
  var curatedTopicPayload = window.MG_CURATED_TOPICS || { topics: [] };
  var curatedTopics = curatedTopicPayload.topics || [];
  var topicCoveragePayload = window.MG_WIKI_TOPIC_COVERAGE || { stats: {}, topic_coverage: [], community_coverage: [] };
  var topicById = {};
  var topicCoverageById = {};
  var activeTopicId = '';
  var tabController = null;
  curatedTopics.forEach(function(topic) { topicById[topic.id] = topic; });
  (topicCoveragePayload.topic_coverage || []).forEach(function(item) { topicCoverageById[item.topic_id] = item; });

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    if (hub.escapeText) return hub.escapeText(value);
    return String(value == null ? '' : value).replace(/[&<>"']/g, function(char) {
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

  function getQueryParam(name) {
    try {
      var params = new URLSearchParams(window.location.search || '');
      return params.get(name) || '';
    } catch (err) {
      return '';
    }
  }

  function compactNumber(value) {
    var num = Number(value || 0);
    return num >= 1000 ? (num / 1000).toFixed(1).replace(/\.0$/, '') + 'k' : String(num);
  }

  function confidenceLabel(value) {
    if (value === 'high') return '高置信';
    if (value === 'medium') return '中置信';
    if (value === 'low') return '低置信';
    return '待确认';
  }

  // 视图路由与标签的映射：视图 view 决定落到哪个标签
  var VIEW_TAB_MAP = { overview: 'overview', matrix: 'matrix', guide: 'guide', answers: 'answers' };

  function bindTabs() {
    var initialTab = getQueryParam('tab');
    var initialKey = VIEW_TAB_MAP[initialTab] || '';
    if (!initialKey && (getQueryParam('topic') || getQueryParam('community'))) initialKey = 'answers';
    if (hub.initTabs) {
      tabController = hub.initTabs({
        tabAttr: 'data-landscape-tab',
        initialKey: initialKey,
        panelFor: function(key) { return $('landscape-' + key); }
      });
      return;
    }
    var tabs = document.querySelectorAll('[data-landscape-tab]');
    var panels = document.querySelectorAll('.intel-tab-panel');
    Array.prototype.forEach.call(tabs, function(tab) {
      tab.addEventListener('click', function() {
        var key = tab.getAttribute('data-landscape-tab');
        Array.prototype.forEach.call(tabs, function(item) { item.classList.remove('active'); });
        Array.prototype.forEach.call(panels, function(panel) { panel.classList.remove('active'); });
        tab.classList.add('active');
        var panel = $('landscape-' + key);
        if (panel) panel.classList.add('active');
      });
    });
  }

  function activateLandscapeTab(key) {
    if (tabController) {
      tabController.activate(key, false);
      return;
    }
    var tab = document.querySelector('[data-landscape-tab="' + key + '"]');
    if (tab) tab.click();
  }

  // ---------------------------------------------------------------------------
  // 导出：竞品卡与指南差异对照表（Markdown，可直接粘进顾问会材料/培训包）
  // ---------------------------------------------------------------------------
  function cell(value) {
    var text = String(value == null ? '' : value).replace(/\r?\n/g, ' ').replace(/\|/g, '\\|').trim();
    return text || '—';
  }

  function buildMatrixBrief() {
    var rows = (data.approved_competitive_matrix || data.competitive_matrix || []);
    var lines = [];
    lines.push('# MA-MG-HUB 竞争定位（中国已获批）');
    lines.push('');
    lines.push('> 证据厚度按近一年 PubMed 滚动窗口统计；口径与站内竞争矩阵一致。窗口外的注册研究不计入。');
    lines.push('');
    for (var i = 0; i < rows.length; i++) {
      var item = rows[i];
      var reg = item.china_regulatory || {};
      var ev = item.evidence_summary || {};
      lines.push('## ' + (item.name || '') + (item.owner ? '（' + item.owner + '）' : ''));
      lines.push('');
      lines.push('| 项目 | 内容 |');
      lines.push('| --- | --- |');
      lines.push('| 靶点 / 给药 | ' + cell((item.mechanism || item.target || '') + ' · ' + (item.convenience || item.route || '')) + ' |');
      lines.push('| 中国状态 | ' + cell((reg.status_label || item.status || '') + (reg.status_date ? ' · ' + reg.status_date : '')) + ' |');
      lines.push('| 中国适应症 | ' + cell(reg.china_indication || '—') + ' |');
      lines.push('| 用药方案 | ' + cell(reg.dosing || reg.china_dosing || '—') + ' |');
      lines.push('| 起效 / 定位 | ' + cell((item.speed || '') + ' · ' + (item.positioning || '')) + ' |');
      lines.push('| 安全性要点 | ' + cell(item.safety || '') + ' |');
      lines.push('| 竞争关系 | ' + cell(item.competition || '') + ' |');
      lines.push('| 证据厚度 | ' + cell('总体 ' + (ev.overall_depth || item.evidence_maturity || '') + ' · 中国 ' + (ev.china_depth || '') +
        ' · 近一年 ' + (ev.abstract_count == null ? '—' : ev.abstract_count + ' 篇') + '（中国相关 ' + (ev.china_count == null ? '—' : ev.china_count + ' 篇') + '）') + ' |');
      lines.push('| 最高证据等级 | ' + cell(item.best_evidence_level || '—') + ' |');
      lines.push('');
    }
    return { title: 'MA-MG-HUB 竞争定位', md: lines.join('\n') };
  }

  function buildGuidelineBrief() {
    var guide = (data.china_landscape || {}).guideline_divergence || {};
    var items = guide.divergences || [];
    var lines = [];
    lines.push('# MA-MG-HUB 中外指南共识差异对照表');
    lines.push('');
    if (guide.corpus_count) {
      lines.push('> 语料 ' + (guide.corpus_count.total || 0) + ' 份（中国 ' + (guide.corpus_count.china || 0) +
        ' / 国际 ' + (guide.corpus_count.international || 0) + ' / 中国台湾 ' + (guide.corpus_count.taiwan || 0) + '）；' +
        (guide.quote_check && guide.quote_check.rate != null ? '引文回验率 ' + guide.quote_check.rate + '%。' : ''));
      lines.push('');
    }
    lines.push('| 维度 | 中国立场 | 国际立场 | 对医学部的含义 |');
    lines.push('| --- | --- | --- | --- |');
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      lines.push('| ' + cell(item.dimension || item.title) + ' | ' + cell(item.china) + ' | ' +
        cell(item.international) + ' | ' + cell(item.clinical_impact) + ' |');
    }
    lines.push('');
    lines.push('## 逐条引文与建议动作');
    lines.push('');
    for (var j = 0; j < items.length; j++) {
      var it = items[j];
      lines.push('### ' + (it.dimension || '') + ' — ' + (it.title || ''));
      lines.push('');
      lines.push('- 医学部动作：' + cell(it.msl_action));
      var evs = it.evidence || [];
      for (var k = 0; k < evs.length; k++) {
        var ev = evs[k];
        lines.push('- ' + cell(ev.short_name || ev.name) + '：「' + cell(ev.quote) + '」' +
          (ev.quote_match === 'exact' ? '（逐字命中）' : ev.quote_match === 'partial' ? '（部分命中）' : '（待核对）'));
      }
      lines.push('');
    }
    return { title: 'MA-MG-HUB 指南差异对照表', md: lines.join('\n') };
  }

  function briefModal(brief) {
    var d = document.createElement('div');
    d.className = 'modal-overlay open';
    var preId = 'landscape_brief_' + Date.now();
    d.innerHTML =
      '<div class="modal literature-brief-modal" role="dialog" aria-modal="true" aria-label="' + escapeHtml(brief.title) + '">' +
        '<button class="modal-close" type="button" data-brief-close="1">✕</button>' +
        '<h2>⬇ ' + escapeHtml(brief.title) + '</h2>' +
        '<div class="literature-brief-layout">' +
          '<div class="literature-brief-preview">' +
            '<div class="literature-brief-label">预览（Markdown）</div>' +
            '<pre id="' + preId + '" class="literature-brief-pre">' + escapeHtml(brief.md) + '</pre>' +
          '</div>' +
          '<div class="literature-brief-actions">' +
            '<div class="literature-brief-label">操作</div>' +
            '<button class="btn literature-brief-copy" type="button" data-brief-copy="' + preId + '">📋 复制</button>' +
            '<button class="btn" type="button" data-brief-download="' + preId + '">⬇ 下载 .md</button>' +
            '<p>复制后可粘进飞书 / 顾问会材料 / 培训包</p>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(d);
    function close() { if (d.parentNode) d.parentNode.removeChild(d); }
    d.addEventListener('click', function(ev) {
      if (ev.target === d || ev.target.getAttribute('data-brief-close')) close();
    });
    document.addEventListener('keydown', function onKey(ev) {
      if (ev.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); }
    });
    var copyBtn = d.querySelector('[data-brief-copy]');
    if (copyBtn) copyBtn.addEventListener('click', function() {
      var text = (document.getElementById(preId) || {}).textContent || '';
      if (navigator.clipboard) navigator.clipboard.writeText(text);
      copyBtn.textContent = '✓ 已复制';
    });
    var dlBtn = d.querySelector('[data-brief-download]');
    if (dlBtn) dlBtn.addEventListener('click', function() {
      var text = (document.getElementById(preId) || {}).textContent || '';
      var blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = brief.title.replace(/[\s/]+/g, '_') + '.md';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function() { URL.revokeObjectURL(a.href); }, 1000);
    });
  }

  function bindExports() {
    var matrixBtn = $('btnExportMatrix');
    if (matrixBtn) matrixBtn.addEventListener('click', function() { briefModal(buildMatrixBrief()); });
    var guideBtn = $('btnExportGuideline');
    if (guideBtn) guideBtn.addEventListener('click', function() { briefModal(buildGuidelineBrief()); });
  }

  function renderBadge() {
    var badge = $('landscapeBadge');
    var overview = data.overview || {};
    if (badge) {
      badge.textContent = (overview.guideline_divergence_count || 0) + ' 条指南差异 · ' +
        (overview.theme_divergence_count || 0) + ' 条主题差异';
    }
    var positioning = $('landscapePositioning');
    if (positioning && overview.positioning) positioning.textContent = overview.positioning;
  }

  function renderStats() {
    var overview = data.overview || {};
    var guideCount = (guidelineDivergence.divergences || []).length || overview.guideline_divergence_count || 0;
    var themeCount = (themeDivergence.divergences || []).length || overview.theme_divergence_count || 0;
    var quoteCheck = guidelineDivergence.quote_check || {};
    var stats = [
      ['指南共识差异', guideCount, (guidelineDivergence.corpus_count ? '语料 ' + guidelineDivergence.corpus_count.total + ' 份' : '待分析')],
      ['文献主题差异', themeCount, (themeDivergence.window_start ? themeDivergence.window_start + ' 起' : '待分析')],
      ['已获批对象', overview.competitive_count || (data.approved_competitive_matrix || data.competitive_matrix || []).length, '中国监管 + 证据厚度'],
      ['引文回验', (quoteCheck.rate == null ? '—' : quoteCheck.rate + '%'), '指南原文逐字核对']
    ];
    var box = $('landscapeStats');
    if (!box) return;
    box.innerHTML = stats.map(function(item) {
      var label = /^</.test(item[2]) ? item[2] : escapeHtml(item[2]);
      // 只有纯数值走紧凑格式；百分比/占位符原样输出，避免 Number('99.9%') 变成 NaN
      var value = typeof item[1] === 'number' ? compactNumber(item[1]) : item[1];
      return '<article class="landscape-stat-card"><span>' + escapeHtml(item[0]) + '</span><strong>' +
        escapeHtml(value) + '</strong><em>' + label + '</em></article>';
    }).join('');
  }

  function renderChipList(items, className, emptyText) {
    items = items || [];
    if (!items.length) return '<span class="muted-text">' + escapeHtml(emptyText || '暂无') + '</span>';
    return items.map(function(item) {
      var label = typeof item === 'string' ? item : (item.title || item.id || item.topic_id || '');
      var href = '';
      if (item.topic_id) href = topicHref(item.topic_id);
      else if (item.id) href = pageUrl('pages/knowledge.html?node=' + encodeURIComponent(item.id));
      if (item.community_id) href = pageUrl('pages/knowledge.html?community=' + encodeURIComponent(item.community_id));
      if (href) {
        return '<a class="' + escapeHtml(className || 'mini-chip') + '" href="' + escapeHref(href) + '">' + escapeHtml(label) + '</a>';
      }
      return '<span class="' + escapeHtml(className || 'mini-chip') + '">' + escapeHtml(label) + '</span>';
    }).join('');
  }

  function topicHref(topicId, communityId) {
    var communityQuery = communityId && communityId !== 'all' ? '&community=' + encodeURIComponent(communityId) : '';
    return pageUrl('pages/landscape.html?tab=answers&topic=' + encodeURIComponent(topicId || '') + communityQuery);
  }

  function toSet(items) {
    var output = {};
    (items || []).forEach(function(item) {
      if (item != null && item !== '') output[String(item)] = true;
    });
    return output;
  }

  function countShared(a, b) {
    var count = 0;
    Object.keys(a || {}).forEach(function(key) {
      if (b && b[key]) count += 1;
    });
    return count;
  }

  function answerSearchText(answer) {
    return [
      answer.question,
      answer.short_answer,
      (answer.key_points || []).join(' '),
      (answer.anchor_nodes || []).join(' '),
      (answer.source_pmids || []).join(' ')
    ].join(' ').toLowerCase();
  }

  function relatedTopicsForAnswer(answer) {
    var answerPmids = toSet(answer.source_pmids || []);
    (answer.references || []).forEach(function(ref) {
      if (ref.pmid) answerPmids[String(ref.pmid)] = true;
    });
    var answerNodes = toSet(answer.anchor_nodes || []);
    var text = answerSearchText(answer);
    return curatedTopics.map(function(topic) {
      var topicPmids = toSet(topic.evidence_pmids || []);
      var topicNodes = toSet(topic.anchor_nodes || []);
      var sharedPmids = countShared(answerPmids, topicPmids);
      var sharedNodes = countShared(answerNodes, topicNodes);
      var textHit = 0;
      [topic.title, topic.slug].forEach(function(value) {
        value = String(value || '').toLowerCase();
        if (value && text.indexOf(value) !== -1) textHit += 1;
      });
      var score = sharedPmids * 5 + sharedNodes * 2 + textHit;
      return {
        topic_id: topic.id,
        title: topic.title || topic.id,
        confidence: topic.confidence || 'unknown',
        updated: topic.updated || '',
        evidence_count: (topic.evidence_refs || []).length,
        shared_pmids: sharedPmids,
        shared_nodes: sharedNodes,
        impact_status: (topic.impact || {}).status || 'quiet',
        score: score
      };
    }).filter(function(item) {
      return item.score > 0;
    }).sort(function(a, b) {
      return b.score - a.score ||
        b.shared_pmids - a.shared_pmids ||
        b.shared_nodes - a.shared_nodes ||
        a.title.localeCompare(b.title);
    }).slice(0, 4);
  }

  function renderAnswerTopics(answer) {
    var topics = relatedTopicsForAnswer(answer);
    if (!topics.length) {
      return '<div class="answer-section"><span>相关专题证据包</span><span class="muted-text">暂无直接匹配专题</span></div>';
    }
    return '<div class="answer-section"><span>相关专题证据包</span><div class="kg-tags">' +
      topics.map(function(topic) {
        var meta = topic.shared_pmids ? topic.shared_pmids + ' PMID' : topic.shared_nodes + ' 锚点';
        if (topic.impact_status === 'updatedEvidence') meta = '本周新证据 · ' + meta;
        var cls = 'mini-chip chip-button' + (topic.topic_id === activeTopicId ? ' active' : '');
        return '<a class="' + cls + '" href="' + escapeHref(topicHref(topic.topic_id)) + '" data-answer-topic="' +
          escapeHtml(topic.topic_id) + '" title="' + escapeHtml(meta) + '">' + escapeHtml(topic.title) + '</a>';
      }).join('') + '</div></div>';
  }

  function getTopicCoverage(topicId) {
    return topicCoverageById[topicId] || { communities: [] };
  }

  function topicImpactForCommunity(topic, communityId) {
    if (!communityId || communityId === 'all') return topic.impact || { status: 'quiet', recent_articles: [] };
    var communityImpact = (getTopicCoverage(topic.id).community_impacts || {})[communityId];
    return communityImpact || { status: 'quiet', recent_articles: [] };
  }

  function topicHasCommunity(topicId, communityId) {
    if (!communityId || communityId === 'all') return true;
    return (getTopicCoverage(topicId).communities || []).some(function(community) {
      return community.community_id === communityId;
    });
  }

  function sourceTypeLabelForTopic(value) {
    return {
      concept: '概念专题',
      entity: '实体专题',
      dataPoint: '数据专题',
      comparison: '对比专题'
    }[value] || '专题';
  }

  function impactStatusLabel(value) {
    return value === 'updatedEvidence' ? '本周新证据' : '本周无明显变化';
  }

  function topicEvidenceCount(topic) {
    return (topic.evidence_refs || []).length || (topic.evidence_pmids || []).length || 0;
  }

  function renderReferenceItem(ref) {
    ref = ref || {};
    var pmid = ref.pmid || '';
    var meta = [
      ref.journal || '',
      ref.pub_date || '',
      ref.evidence_level ? 'Level ' + ref.evidence_level : '',
      (ref.study_types || []).slice(0, 2).join(' / ')
    ].filter(Boolean).join(' · ');
    var href = ref.url || (pmid ? 'https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/' : '#');
    return '<li><a class="text-link" href="' + escapeHref(href) + '" target="_blank" rel="noopener">PMID ' +
      escapeHtml(pmid || '-') + '</a> ' + escapeHtml(ref.title || '') +
      '<br><span class="kg-ref-meta">' + escapeHtml(meta || '待补充元数据') + '</span></li>';
  }

  function topicSearchText(topic) {
    var coverage = getTopicCoverage(topic.id);
    var communityText = (coverage.communities || []).map(function(community) {
      return community.title + ' ' + community.community_id;
    }).join(' ');
    return [
      topic.title,
      topic.summary,
      topic.source_type,
      (topic.anchor_nodes || []).join(' '),
      (topic.evidence_pmids || []).join(' '),
      (topic.msl_use || []).join(' '),
      communityText
    ].join(' ').toLowerCase();
  }

  function renderTopicCommunityBadges(topicId, limit, interactive) {
    var communities = (getTopicCoverage(topicId).communities || []).slice(0, limit || 4);
    if (!communities.length) return '<span class="kg-ref-meta">未连接社区</span>';
    return communities.map(function(community) {
      var label = (community.title || community.community_id) + (community.confidence ? ' · ' + community.confidence : '');
      if (interactive) {
        return '<button class="mini-chip chip-button topic-community-chip" type="button" data-topic-community="' +
          escapeHtml(community.community_id) + '">' + escapeHtml(label) + '</button>';
      }
      return '<span class="kg-badge community-badge mini">' + escapeHtml(community.title || community.community_id) + '</span>';
    }).join(' ');
  }

  function relatedAnswersForTopic(topicId) {
    return (data.living_answers || []).map(function(answer) {
      var match = relatedTopicsForAnswer(answer).filter(function(topic) {
        return topic.topic_id === topicId;
      })[0];
      if (!match) return null;
      var meta = match.shared_pmids ? match.shared_pmids + ' PMID' : match.shared_nodes + ' 锚点';
      return { answer: answer, score: match.score, meta: meta };
    }).filter(Boolean).sort(function(a, b) {
      return b.score - a.score || String(a.answer.question || '').localeCompare(String(b.answer.question || ''));
    });
  }

  function renderTopicAnswerLinks(topicId) {
    var related = relatedAnswersForTopic(topicId).slice(0, 5);
    if (!related.length) {
      return '<div class="kg-detail-section"><h4>对应 Living Answer</h4><div class="kg-empty-hint">当前专题还没有稳定匹配到 Living Answer。</div></div>';
    }
    return '<div class="kg-detail-section"><h4>对应 Living Answer</h4><div class="kg-relation-list">' +
      related.map(function(row) {
        return '<button class="kg-relation-row topic-answer-filter" type="button" data-answer-query="' +
          escapeHtml(row.answer.question || '') + '">' +
          '<span>' + escapeHtml(row.answer.category || 'Answer') + '</span>' +
          '<strong>' + escapeHtml(row.answer.question || '') + '</strong>' +
          '<em>' + escapeHtml(row.meta) + '</em>' +
        '</button>';
      }).join('') + '</div></div>';
  }

  function renderTopicCommunitySection(topicId) {
    var coverage = getTopicCoverage(topicId);
    var communities = coverage.communities || [];
    if (!communities.length) {
      return '<div class="kg-detail-section"><h4>覆盖社区</h4><div class="kg-empty-hint">该专题尚未稳定连接到医学事务社区。</div></div>';
    }
    return '<div class="kg-detail-section"><h4>覆盖社区</h4><div class="kg-tags">' +
      renderTopicCommunityBadges(topicId, 6, true) +
      '</div><div class="kg-ref-meta">依据专题锚点、PMID 归类和 taxonomy 关键词生成；点击社区可反筛专题列表。</div></div>';
  }

  function renderTopicDetail(topicId) {
    var detail = $('answerTopicDetail');
    if (!detail) return;
    var topic = topicById[topicId];
    if (!topic) {
      detail.innerHTML = '<div class="kg-empty-hint">选择一个专题查看详情。</div>';
      return;
    }
    var anchorHtml = (topic.anchor_nodes || []).length ? (topic.anchor_nodes || []).map(function(nodeId) {
      return '<a class="mini-chip chip-button" href="' + escapeHref(pageUrl('pages/knowledge.html?node=' + encodeURIComponent(nodeId))) + '">' +
        escapeHtml(nodeId) + '</a>';
    }).join('') : '<span class="muted-text">暂无图谱锚点</span>';
    var useHtml = (topic.msl_use || []).length ? (topic.msl_use || []).map(function(item) {
      return '<span class="mini-chip">' + escapeHtml(item) + '</span>';
    }).join('') : '<span class="muted-text">暂无 MSL 场景标注</span>';
    var claimHtml = (topic.claims || []).length ? (topic.claims || []).slice(0, 5).map(function(claim) {
      return '<article class="curated-claim">' +
        '<span>' + escapeHtml(claim.claim_type || 'claim') + (claim.section ? ' · ' + escapeHtml(claim.section) : '') + '</span>' +
        '<p>' + escapeHtml(claim.text || '') + '</p>' +
      '</article>';
    }).join('') : '<div class="kg-empty-hint">暂无结构化 claim。</div>';
    var refsHtml = (topic.evidence_refs || []).length ?
      topic.evidence_refs.slice(0, 8).map(renderReferenceItem).join('') :
      '<li>暂无可校验 PMID；可在 wiki 中补充 evidence_pmids。</li>';
    var communityFilter = (($('answerTopicCommunity') || {}).value || 'all');
    var scopedImpact = topicImpactForCommunity(topic, communityFilter);
    var impactItems = (scopedImpact.recent_articles || []).slice(0, 6);
    var impactHtml = impactItems.length ? impactItems.map(renderReferenceItem).join('') : '<li>本周未发现明确影响该专题的新入库 abstract。</li>';
    var impact = scopedImpact.status || 'quiet';
    var communitySelect = $('answerTopicCommunity');
    var selectedCommunityOption = communitySelect && communitySelect.options[communitySelect.selectedIndex];
    var impactScope = communityFilter !== 'all' && selectedCommunityOption ? ' · ' + selectedCommunityOption.textContent : '';

    detail.innerHTML =
      '<div class="kg-detail-type">' + escapeHtml(sourceTypeLabelForTopic(topic.source_type)) + '</div>' +
      '<h2>' + escapeHtml(topic.title || topic.id) + '</h2>' +
      '<div class="kg-badges">' +
        '<span class="kg-badge conf-' + escapeHtml(topic.confidence === 'high' ? 'high' : topic.confidence === 'medium' ? 'medium' : 'low') + '">' + escapeHtml(topic.confidence || 'unknown') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(topic.status || 'active') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(impactStatusLabel(impact) + impactScope) + '</span>' +
        '<span class="kg-badge">更新 ' + escapeHtml(topic.updated || '-') + '</span>' +
      '</div>' +
      '<div class="kg-detail-summary">' + escapeHtml(topic.summary || '') + '</div>' +
      renderTopicAnswerLinks(topic.id) +
      renderTopicCommunitySection(topic.id) +
      '<div class="kg-detail-section"><h4>全库锚点</h4><div class="kg-tags">' + anchorHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>MSL 使用场景</h4><div class="kg-tags">' + useHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>专题要点</h4>' + claimHtml + '</div>' +
      '<div class="kg-detail-section"><h4>本周新入库证据' + escapeHtml(impactScope) + '</h4><ul class="kg-study-list">' + impactHtml + '</ul></div>' +
      '<div class="kg-detail-section"><h4>专题 PMID（长期知识底座）</h4><ul class="kg-study-list">' + refsHtml + '</ul></div>' +
      '<div class="kg-detail-actions"><a class="kg-obsidian-btn" href="' + escapeHref(topic.obsidian_url || '#') + '">在 Obsidian 中打开</a></div>';

    Array.prototype.forEach.call(detail.querySelectorAll('[data-topic-community]'), function(button) {
      button.addEventListener('click', function() {
        openTopicCommunity(button.getAttribute('data-topic-community'));
      });
    });
    Array.prototype.forEach.call(detail.querySelectorAll('[data-answer-query]'), function(button) {
      button.addEventListener('click', function() {
        var input = $('answerSearch');
        if (input) input.value = button.getAttribute('data-answer-query') || '';
        renderAnswers();
        var answerList = $('answerList');
        if (answerList && answerList.scrollIntoView) answerList.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  function renderTopics(selectedId) {
    var list = $('answerTopicList');
    var detail = $('answerTopicDetail');
    if (!list || !detail) return;
    var keyword = (($('answerTopicSearch') || {}).value || '').trim().toLowerCase();
    var impactFilter = (($('answerTopicImpact') || {}).value || 'all');
    var communityFilter = (($('answerTopicCommunity') || {}).value || 'all');
    var filtered = curatedTopics.filter(function(topic) {
      var impact = topicImpactForCommunity(topic, communityFilter).status || 'quiet';
      return (!keyword || topicSearchText(topic).indexOf(keyword) !== -1) &&
        (impactFilter === 'all' || impact === impactFilter) &&
        topicHasCommunity(topic.id, communityFilter);
    }).sort(function(a, b) {
      var impactA = topicImpactForCommunity(a, communityFilter).status === 'updatedEvidence' ? 1 : 0;
      var impactB = topicImpactForCommunity(b, communityFilter).status === 'updatedEvidence' ? 1 : 0;
      return impactB - impactA ||
        topicEvidenceCount(b) - topicEvidenceCount(a) ||
        String(a.title || '').localeCompare(String(b.title || ''));
    });
    var topics = filtered.slice();
    if (selectedId && topicById[selectedId] && !topics.some(function(topic) { return topic.id === selectedId; })) {
      topics.unshift(topicById[selectedId]);
    }
    var count = $('answerTopicCount');
    if (count) count.textContent = filtered.length + ' 个专题';
    if (!topics.length) {
      activeTopicId = '';
      list.innerHTML = '<div class="kg-empty-hint">没有匹配的专题。</div>';
      detail.innerHTML = '<div class="kg-empty-hint">调整筛选条件查看专题。</div>';
      renderAnswers();
      return;
    }

    var activeId = selectedId && topicById[selectedId] ? selectedId : topics[0].id;
    activeTopicId = activeId;
    list.innerHTML = topics.map(function(topic) {
      var scopedImpact = topicImpactForCommunity(topic, communityFilter);
      var impactCount = (scopedImpact.recent_articles || []).length;
      var impact = scopedImpact.status || 'quiet';
      return '<button class="curated-topic-card' + (topic.id === activeId ? ' active' : '') + '" type="button" data-topic="' + escapeHtml(topic.id) + '">' +
        '<span>' + escapeHtml(sourceTypeLabelForTopic(topic.source_type)) + ' · ' + escapeHtml(impactStatusLabel(impact)) + '</span>' +
        '<strong>' + escapeHtml(topic.title || topic.id) + '</strong>' +
        '<div class="topic-community-row">' + renderTopicCommunityBadges(topic.id, 3, false) + '</div>' +
        '<em>' + escapeHtml(topicEvidenceCount(topic)) + ' PMID · ' + escapeHtml((topic.anchor_nodes || []).length) + ' 锚点' +
          (impactCount ? ' · 本周 ' + impactCount : '') + '</em>' +
      '</button>';
    }).join('');

    Array.prototype.forEach.call(list.querySelectorAll('[data-topic]'), function(button) {
      button.addEventListener('click', function() {
        openTopic(button.getAttribute('data-topic'));
      });
    });
    renderTopicDetail(activeId);
    renderAnswers();
  }

  function populateTopicFilters() {
    var select = $('answerTopicCommunity');
    if (!select || select.options.length > 1) return;
    (topicCoveragePayload.community_coverage || []).slice().sort(function(a, b) {
      return (b.topic_count || 0) - (a.topic_count || 0) || String(a.title || '').localeCompare(String(b.title || ''));
    }).forEach(function(community) {
      var option = document.createElement('option');
      option.value = community.community_id;
      option.textContent = (community.title || community.community_id) + ' · ' + (community.topic_count || 0);
      select.appendChild(option);
    });
  }

  function bindTopicFilters() {
    ['answerTopicSearch', 'answerTopicImpact', 'answerTopicCommunity'].forEach(function(id) {
      var el = $(id);
      if (el) el.addEventListener(id === 'answerTopicSearch' ? 'input' : 'change', function() { renderTopics(); });
    });
  }

  function openTopic(topicId, skipHistory) {
    if (!topicById[topicId]) return;
    activeTopicId = topicId;
    activateLandscapeTab('answers');
    renderTopics(topicId);
    if (!skipHistory && window.history && window.history.replaceState) {
      var communityId = (($('answerTopicCommunity') || {}).value || 'all');
      window.history.replaceState(null, '', topicHref(topicId, communityId));
    }
  }

  function openTopicCommunity(communityId) {
    var select = $('answerTopicCommunity');
    if (select) select.value = communityId || 'all';
    activateLandscapeTab('answers');
    renderTopics();
    if (window.history && window.history.replaceState) {
      var suffix = communityId ? '&community=' + encodeURIComponent(communityId) : '';
      window.history.replaceState(null, '', pageUrl('pages/landscape.html?tab=answers' + suffix));
    }
  }

  function renderRefLinks(refs, limit) {
    refs = refs || [];
    if (!refs.length) return '<span class="muted-text">暂无 PMID</span>';
    return refs.slice(0, limit || 3).map(function(ref) {
      var pmid = ref.pmid || '';
      return '<a class="pmid-chip" href="' + escapeHref(ref.url || ('https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/')) +
        '" target="_blank" rel="noopener">PMID ' + escapeHtml(pmid) + '</a>';
    }).join('');
  }

  function renderSourceLinks(regulatory) {
    regulatory = regulatory || {};
    var links = [];
    if (regulatory.source_url) {
      links.push('<a class="regulatory-source-link" href="' + escapeHref(regulatory.source_url) + '" target="_blank" rel="noopener">来源 1</a>');
    }
    if (regulatory.secondary_url) {
      links.push('<a class="regulatory-source-link" href="' + escapeHref(regulatory.secondary_url) + '" target="_blank" rel="noopener">来源 2</a>');
    }
    if (!links.length) return '<span class="muted-text">待核对</span>';
    return links.join('');
  }

  function renderEvidenceSummary(item) {
    var summary = item.evidence_summary || {};
    var abstractCount = Number(summary.abstract_count || 0);
    var rweCount = Number(summary.rwe_count || 0);
    var chinaCount = Number(summary.china_count || 0);
    return '<div class="evidence-density-row">' +
        '<span>总体 ' + escapeHtml(summary.overall_depth || item.evidence_maturity || '待补充') + '</span>' +
        '<span>中国 ' + escapeHtml(summary.china_depth || item.china_depth || '待补充') + '</span>' +
      '</div>' +
      '<div class="evidence-count-row">' +
        '<span>近一年 abstract ' + escapeHtml(abstractCount) + ' 篇</span>' +
        '<span>RWE/观察性 ' + escapeHtml(rweCount) + ' 篇</span>' +
        '<span>中国相关 ' + escapeHtml(chinaCount) + ' 篇</span>' +
      '</div>';
  }

  function renderCompetitiveMatrix() {
    var rows = data.approved_competitive_matrix || data.competitive_matrix || [];
    var box = $('competitiveMatrix');
    if (!box) return;
    var html = rows.map(function(item) {
      var regulatory = item.china_regulatory || {};
      var statusClass = regulatory.status_class || 'unknown';
      return '<tr>' +
        '<td><strong>' + escapeHtml(item.name) + '</strong><br><span>' + escapeHtml(item.owner || '') + '</span></td>' +
        '<td>' + escapeHtml(item.mechanism || item.target || '') + '<br><span>' + escapeHtml(item.convenience || item.route || '-') + '</span></td>' +
        '<td><em class="regulatory-status ' + escapeHtml(statusClass) + '">' + escapeHtml(regulatory.status_label || '待接入') + '</em>' +
          '<br><span>' + escapeHtml(regulatory.status_date || '-') + '</span><div class="regulatory-source-row">' + renderSourceLinks(regulatory) + '</div></td>' +
        '<td>' + escapeHtml(regulatory.china_indication || item.population || '-') + '</td>' +
        '<td>' + escapeHtml(regulatory.cde_status || '-') + '<br><span>' + escapeHtml(regulatory.source_type || '') + '</span><br><span>核对 ' + escapeHtml(regulatory.last_verified || '-') + '</span></td>' +
        '<td>' + renderEvidenceSummary(item) + '</td>' +
      '</tr>';
    }).join('');
    box.innerHTML = '<table><tr><th>药物</th><th>靶点/剂型</th><th>中国监管</th><th>中国适应症</th><th>CDE/NMPA</th><th>证据厚度</th></tr>' + html + '</table>';
  }

  function regionLabel(region) {
    if (region === 'china') return '中国';
    if (region === 'taiwan') return '中国台湾';
    return '国际';
  }

  function quoteCheckLabel(match) {
    if (match === 'exact') return { text: '逐字命中', cls: 'ok' };
    if (match === 'partial') return { text: '部分命中', cls: 'partial' };
    return { text: '待核对', cls: 'fail' };
  }

  /* ── PMID 弹窗：主题差异里的篇数可点开查看该侧全部 PMID ── */
  var lastModalTrigger = null;

  function openPmidModal(title, meta, refs) {
    var modal = $('pmidModal');
    var body = $('pmidModalBody');
    if (!modal || !body) return;
    refs = refs || [];
    var titleEl = $('pmidModalTitle');
    var metaEl = $('pmidModalMeta');
    if (titleEl) titleEl.textContent = title;
    if (metaEl) metaEl.textContent = meta || '';
    if (!refs.length) {
      body.innerHTML = '<p class="kg-empty-hint">该侧本窗口无文献。</p>';
    } else {
      body.innerHTML = '<ol class="pmid-modal-list">' + refs.map(function(ref) {
        var pmid = ref.pmid || '';
        var tags = [ref.angle, ref.journal].filter(Boolean).join(' · ');
        return '<li>' +
          '<a class="pmid-modal-link" href="' +
            escapeHref(ref.url || ('https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/')) +
            '" target="_blank" rel="noopener">PMID ' + escapeHtml(pmid) + '</a>' +
          '<strong>' + escapeHtml(ref.title || '') + '</strong>' +
          (tags ? '<span class="pmid-modal-tags">' + escapeHtml(tags) + '</span>' : '') +
        '</li>';
      }).join('') + '</ol>';
    }
    lastModalTrigger = document.activeElement;
    modal.hidden = false;
    document.body.classList.add('pmid-modal-open');
    var closeBtn = modal.querySelector('.pmid-modal-close');
    if (closeBtn) closeBtn.focus();
  }

  function closePmidModal() {
    var modal = $('pmidModal');
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.body.classList.remove('pmid-modal-open');
    if (lastModalTrigger && lastModalTrigger.focus) lastModalTrigger.focus();
    lastModalTrigger = null;
  }

  function bindPmidModal() {
    var modal = $('pmidModal');
    if (!modal) return;
    modal.addEventListener('click', function(event) {
      var target = event.target;
      if (target && target.hasAttribute && target.hasAttribute('data-pmid-modal-close')) closePmidModal();
    });
    document.addEventListener('keydown', function(event) {
      if (event.key === 'Escape') closePmidModal();
    });
    var list = $('themeDivergenceList');
    if (!list) return;
    // 事件委托：篇数按钮点击后弹窗展示该侧全部 PMID
    list.addEventListener('click', function(event) {
      var btn = event.target && event.target.closest ? event.target.closest('[data-pmid-side]') : null;
      if (!btn || btn.disabled) return;
      var id = btn.getAttribute('data-divergence') || '';
      var side = btn.getAttribute('data-pmid-side') || '';
      var item = (themeDivergence.divergences || []).filter(function(row) { return row.id === id; })[0];
      if (!item) return;
      var isChina = side === 'china';
      var refs = isChina ? (item.china_refs || []) : (item.non_china_refs || []);
      openPmidModal(
        (isChina ? '中国侧文献' : '国际侧文献') + ' · ' + (item.theme || ''),
        refs.length + ' 篇 · ' + (themeDivergence.window_start || '-') + ' 至 ' + (themeDivergence.window_end || '-'),
        refs
      );
    });
  }

  // 滚动模块的自检：窗口过期说明上周的自动重算没跑成，必须显性提示而不是静默显示旧数据
  function themeStaleness(windowEnd) {
    if (!windowEnd) return { stale: true, text: '窗口未知' };
    var end = new Date(windowEnd + 'T00:00:00');
    if (isNaN(end.getTime())) return { stale: true, text: '窗口未知' };
    var days = Math.floor((Date.now() - end.getTime()) / 86400000);
    if (days <= 14) return { stale: false, text: '' };
    return { stale: true, text: '窗口已 ' + days + ' 天未更新' };
  }

  // 两套差异模块的元信息行：窗口 / 语料 / 生成时间 / 触发条件
  function renderMetaRow(boxId, rows) {
    var box = $(boxId);
    if (!box) return;
    box.innerHTML = (rows || []).filter(function(row) {
      return row && row[1] !== '' && row[1] != null;
    }).map(function(row) {
      return '<span class="meta-chip"><em>' + escapeHtml(row[0]) + '</em>' + escapeHtml(row[1]) + '</span>';
    }).join('');
  }

  function renderRatioBar(item) {
    var china = Number(item.china_count || 0);
    var global = Number(item.non_china_count || 0);
    var total = china + global;
    if (!total) return '';
    var chinaPct = Math.round(china / total * 100);
    return '<div class="divergence-ratio" role="img" aria-label="中国 ' + china + ' 篇 / 非中国 ' + global + ' 篇">' +
      '<span class="ratio-china" style="width:' + chinaPct + '%"></span>' +
      '<span class="ratio-global" style="width:' + (100 - chinaPct) + '%"></span>' +
    '</div>';
  }

  function renderThemeDivergence() {
    var box = $('themeDivergenceList');
    var badge = $('themeDivergenceMeta');
    var note = $('themeDivergenceNote');
    var ready = themeDivergence.status === 'ready';
    var staleness = themeStaleness(themeDivergence.window_end);
    if (badge) {
      badge.textContent = ready
        ? (themeDivergence.total_count || 0) + ' 篇 · ' + (themeDivergence.window_end || '-') +
          (staleness.stale ? ' · ' + staleness.text : '')
        : '等待分析';
      if (staleness.stale && ready) badge.classList.add('is-stale');
      else badge.classList.remove('is-stale');
    }
    renderMetaRow('themeDivergenceMetaRow', [
      ['窗口', ready ? (themeDivergence.window_start || '') + ' 至 ' + (themeDivergence.window_end || '') : ''],
      ['中国 / 国际', ready ? (themeDivergence.china_total || 0) + ' / ' + (themeDivergence.non_china_total || 0) + ' 篇' : ''],
      ['生成时间', themeDivergence.generated_at || ''],
      ['更新方式', ready ? '随文献周更自动重算' : '']
    ]);
    if (note) {
      var parts = [];
      if (themeDivergence.scope_note) parts.push(themeDivergence.scope_note);
      if (themeDivergence.method) {
        parts.push('篇数与 PMID 由代码按受控主题表统计，模型自报的篇数会被删除；窗口口径：' +
          (themeDivergence.window_basis || '') + '。');
      }
      note.textContent = parts.join(' ');
    }
    if (!box) return;
    var items = themeDivergence.divergences || [];
    if (!items.length) {
      box.innerHTML = '<div class="kg-empty-hint">' + escapeHtml(themeDivergence.note || '暂无主题差异数据。') + '</div>';
      return;
    }
    box.innerHTML = items.map(function(item, index) {
      var chinaCount = Number(item.china_count || 0);
      var globalCount = Number(item.non_china_count || 0);
      function countBtn(side, label, count) {
        return '<button type="button" class="pmid-count-btn' + (count ? '' : ' is-empty') + '"' +
          ' data-pmid-side="' + side + '" data-divergence="' + escapeHtml(item.id || '') + '"' +
          (count ? '' : ' disabled') + '>' + label + ' ' + count + ' 篇' + (count ? ' ▸' : '') + '</button>';
      }
      return '<article class="theme-divergence-card">' +
        '<div class="theme-divergence-head">' +
          '<span class="divergence-index">' + escapeHtml(String(index + 1).padStart(2, '0')) + '</span>' +
          '<strong>' + escapeHtml(item.theme || '') + '</strong>' +
          '<span class="divergence-type">' + escapeHtml(item.divergence_type || '') + '</span>' +
          '<em class="insight-confidence ' + escapeHtml(item.confidence || 'unknown') + '">' +
            escapeHtml(confidenceLabel(item.confidence)) + '</em>' +
        '</div>' +
        renderRatioBar(item) +
        '<div class="theme-divergence-sides">' +
          '<div class="divergence-side china">' +
            countBtn('china', '中国', chinaCount) +
            '<p>' + escapeHtml(item.china_focus || '') + '</p>' +
          '</div>' +
          '<div class="divergence-side global">' +
            countBtn('non_china', '国际', globalCount) +
            '<p>' + escapeHtml(item.global_focus || '') + '</p>' +
          '</div>' +
        '</div>' +
        '<div class="divergence-impact"><span>对医学部意味着什么</span><p>' + escapeHtml(item.why_it_matters || '') + '</p></div>' +
        (item.msl_action
          ? '<div class="divergence-action"><span>可执行动作</span><p>' + escapeHtml(item.msl_action) + '</p></div>'
          : '') +
      '</article>';
    }).join('');
  }

  function renderGuidelineDivergence() {
    var badge = $('guidelineDivergenceMeta');
    var box = $('guidelineDivergenceList');
    var corpusBox = $('guidelineCorpusList');
    var ready = guidelineDivergence.status === 'ready';
    var counts = guidelineDivergence.corpus_count || {};
    var quoteCheck = guidelineDivergence.quote_check || {};
    var items = guidelineDivergence.divergences || [];
    if (badge) {
      badge.textContent = ready ? items.length + ' 条 · 语料 ' + (counts.total || 0) + ' 份' : '等待分析';
    }
    renderMetaRow('guidelineDivergenceMetaRow', [
      ['语料', ready ? '中国 ' + (counts.china || 0) + ' / 国际 ' + (counts.international || 0) +
        (counts.taiwan ? ' / 台湾 ' + counts.taiwan : '') + ' 份' : ''],
      ['引文回验', quoteCheck.total ? (quoteCheck.verified || 0) + ' / ' + quoteCheck.total +
        '（' + (quoteCheck.rate == null ? '—' : quoteCheck.rate + '%') + '）' : ''],
      ['生成时间', guidelineDivergence.generated_at || ''],
      ['更新方式', ready ? '新增指南/共识全文后手动重跑' : '']
    ]);
    var items = guidelineDivergence.divergences || [];
    if (box) {
      if (!items.length) {
        box.innerHTML = '<div class="kg-empty-hint">' + escapeHtml(guidelineDivergence.note || '暂无指南差异数据。') + '</div>';
      } else {
        box.innerHTML = items.map(function(item, index) {
          var evidence = item.evidence || [];
          var verified = evidence.filter(function(ev) { return ev.quote_verified; }).length;
          var evidenceHtml = evidence.map(function(ev) {
            var check = quoteCheckLabel(ev.quote_match);
            return '<li>' +
              '<blockquote>' + escapeHtml(ev.quote || '') + '</blockquote>' +
              '<div class="gd-source">' +
                '<span class="region-tag ' + escapeHtml(ev.region || '') + '">' + escapeHtml(regionLabel(ev.region)) + '</span>' +
                '<strong>' + escapeHtml(ev.short_name || ev.name || '') + '</strong>' +
                '<em>' + escapeHtml(ev.year || '') + '</em>' +
                '<i class="quote-check ' + check.cls + '">' + check.text + '</i>' +
              '</div>' +
            '</li>';
          }).join('');
          return '<article class="guideline-divergence-card">' +
            '<div class="gd-head">' +
              '<span class="divergence-index">' + escapeHtml(String(index + 1).padStart(2, '0')) + '</span>' +
              '<strong>' + escapeHtml(item.title || '') + '</strong>' +
              '<span class="gd-dimension">' + escapeHtml(item.dimension || '') + '</span>' +
              '<em class="insight-confidence ' + escapeHtml(item.confidence || 'unknown') + '">' +
                escapeHtml(confidenceLabel(item.confidence)) + '</em>' +
            '</div>' +
            '<div class="gd-sides">' +
              '<div class="gd-side china"><span>中国</span><p>' + escapeHtml(item.china || '') + '</p></div>' +
              '<div class="gd-side global"><span>国际</span><p>' + escapeHtml(item.international || '') + '</p></div>' +
            '</div>' +
            '<div class="gd-meta">' +
              '<div><span>为什么重要</span><p>' + escapeHtml(item.clinical_impact || '') + '</p></div>' +
              '<div><span>医学部动作</span><p>' + escapeHtml(item.msl_action || '') + '</p></div>' +
            '</div>' +
            (evidence.length
              ? '<details class="gd-evidence"><summary>证据原文 ' + evidence.length + ' 条 · 原文回验 ' +
                  verified + '/' + evidence.length + '</summary><ul>' + evidenceHtml + '</ul></details>'
              : '') +
          '</article>';
        }).join('');
      }
    }
    if (corpusBox) {
      var corpus = guidelineDivergence.corpus || [];
      var groups = { china: [], international: [], taiwan: [] };
      corpus.forEach(function(doc) {
        var key = groups[doc.region] ? doc.region : 'international';
        groups[key].push(doc);
      });
      var order = ['china', 'international', 'taiwan'];
      var groupsHtml = order.filter(function(key) { return groups[key].length; }).map(function(key) {
        return '<div class="corpus-group">' +
          '<span>' + escapeHtml(regionLabel(key)) + ' · ' + groups[key].length + ' 份</span>' +
          '<ul>' + groups[key].map(function(doc) {
            var label = doc.short_name || doc.name || '';
            return '<li><strong>' + escapeHtml(label) + '</strong>' +
              (doc.dims ? '<span>' + escapeHtml(doc.dims) + ' 个维度</span>' : '') + '</li>';
          }).join('') + '</ul>' +
        '</div>';
      }).join('');
      var checkHtml = quoteCheck.total
        ? '<p class="divergence-source-note">引文回验：' + (quoteCheck.verified || 0) + ' / ' + quoteCheck.total +
          ' 条在原文中命中（' + (quoteCheck.rate == null ? '—' : quoteCheck.rate + '%') + '）。' +
          '「部分命中」多为 PDF 跨页或上标引文序号导致的字符差异。</p>'
        : '';
      var triggerHtml = '<p class="divergence-source-note">更新触发：新增或替换指南/共识全文后，' +
        '按 <code>report/runbooks/monthlyDivergenceAnalysis.md</code> 重跑立场提取与差异归纳；' +
        '文献周更不会改动本模块。</p>';
      corpusBox.innerHTML = (corpus.length ? groupsHtml : '<p class="muted-text">暂无语料清单。</p>') +
        checkHtml + triggerHtml;
    }
  }

  function stanceClass(value) {
    if (value === '可积极回答') return 'positive';
    if (value === '可谨慎回答') return 'cautious';
    if (value === '证据不足') return 'limited';
    return 'outline';
  }

  function populateAnswerFilters() {
    var select = $('answerCategory');
    if (!select) return;
    var categories = {};
    (data.living_answers || []).forEach(function(answer) {
      categories[answer.category || '未分类'] = true;
    });
    Object.keys(categories).sort().forEach(function(category) {
      var option = document.createElement('option');
      option.value = category;
      option.textContent = category;
      select.appendChild(option);
    });
  }

  function renderAnswers() {
    var answers = data.living_answers || [];
    var keyword = (($('answerSearch') || {}).value || '').trim().toLowerCase();
    var category = (($('answerCategory') || {}).value || 'all');
    var stance = (($('answerStance') || {}).value || 'all');
    var filtered = answers.filter(function(answer) {
      var text = [
        answer.question,
        answer.short_answer,
        (answer.key_points || []).join(' '),
        (answer.source_pmids || []).join(' '),
        (answer.anchor_nodes || []).join(' '),
        relatedTopicsForAnswer(answer).map(function(topic) { return topic.title + ' ' + topic.topic_id; }).join(' ')
      ].join(' ').toLowerCase();
      return (!keyword || text.indexOf(keyword) !== -1) &&
        (category === 'all' || answer.category === category) &&
        (stance === 'all' || answer.stance === stance);
    });
    var count = $('answerCount');
    if (count) count.textContent = filtered.length + ' 个问题';
    var box = $('answerList');
    if (!box) return;
    if (!filtered.length) {
      box.innerHTML = '<div class="kg-empty-hint">没有匹配的 Living Answer。</div>';
      return;
    }
    box.innerHTML = filtered.map(function(answer) {
      var pointHtml = (answer.key_points || []).map(function(point) {
        return '<li>' + escapeHtml(point) + '</li>';
      }).join('');
      var addedHtml = (answer.added_papers || []).length ?
        '<div class="answer-added"><span>新增证据</span>' + renderRefLinks(answer.added_papers, 3) + '</div>' :
        '<div class="answer-added"><span>新增证据</span><em>本轮未发现明确新增 PMID</em></div>';
      var anchors = (answer.anchor_nodes || []).map(function(node) {
        return '<a class="mini-chip chip-button" href="' + escapeHref(pageUrl('pages/knowledge.html?node=' + encodeURIComponent(node))) + '">' + escapeHtml(node) + '</a>';
      }).join('');
      return '<article class="living-answer-card">' +
        '<div class="answer-head">' +
          '<span>' + escapeHtml(answer.category || '问题') + '</span>' +
          '<em class="stance ' + stanceClass(answer.stance) + '">' + escapeHtml(answer.stance || '仅供提纲') + '</em>' +
        '</div>' +
        '<h3>' + escapeHtml(answer.question) + '</h3>' +
        '<p class="answer-short">' + escapeHtml(answer.short_answer || '') + '</p>' +
        '<ul>' + pointHtml + '</ul>' +
        '<div class="answer-meta-row">' +
          '<span>证据强度 Level ' + escapeHtml(answer.evidence_strength || '-') + '</span>' +
          '<span>' + escapeHtml(answer.evidence_window || '-') + '</span>' +
          '<span>' + escapeHtml(answer.answer_version || '-') + '</span>' +
        '</div>' +
        addedHtml +
        '<div class="answer-section"><span>关键 PMID</span><div class="pmid-row">' + renderRefLinks(answer.references, 5) + '</div></div>' +
        '<div class="answer-section"><span>知识库锚点</span><div class="kg-tags">' + anchors + '</div></div>' +
        renderAnswerTopics(answer) +
        '<p class="answer-limitation">' + escapeHtml(answer.abstract_limitation || '') + '</p>' +
      '</article>';
    }).join('');
    Array.prototype.forEach.call(box.querySelectorAll('[data-answer-topic]'), function(link) {
      link.addEventListener('click', function(event) {
        event.preventDefault();
        openTopic(link.getAttribute('data-answer-topic'));
      });
    });
  }

  function bindAnswerFilters() {
    ['answerSearch', 'answerCategory', 'answerStance'].forEach(function(id) {
      var el = $(id);
      if (el) el.addEventListener(id === 'answerSearch' ? 'input' : 'change', renderAnswers);
    });
  }

  function applyInitialAnswerRoute() {
    var communityId = getQueryParam('community');
    var topicId = getQueryParam('topic');
    var communitySelect = $('answerTopicCommunity');
    if (communityId && communitySelect) communitySelect.value = communityId;
    if (topicId && topicById[topicId]) {
      openTopic(topicId, true);
      return;
    }
    renderTopics();
  }

  function init() {
    bindTabs();
    renderBadge();
    renderStats();
    renderCompetitiveMatrix();
    renderThemeDivergence();
    renderGuidelineDivergence();
    bindPmidModal();
    bindExports();
    populateAnswerFilters();
    populateTopicFilters();
    bindAnswerFilters();
    bindTopicFilters();
    renderAnswers();
    applyInitialAnswerRoute();
  }

  init();
})();
