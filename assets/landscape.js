/* MA-MG-HUB 诊治格局 */
(function() {
  'use strict';

  var hub = window.MgHub || {};
  var data = window.MG_LANDSCAPE_DATA || {};
  var insightPayload = window.MG_LANDSCAPE_INSIGHTS || { insights: [], summary: {} };
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

  function activeInsights() {
    var dynamic = insightPayload.insights || [];
    return dynamic.length ? dynamic : (data.monthly_changes || []);
  }

  function confidenceLabel(value) {
    if (value === 'high') return '高置信';
    if (value === 'medium') return '中置信';
    if (value === 'low') return '低置信';
    return '待确认';
  }

  function bindTabs() {
    var initialTab = getQueryParam('tab');
    var initialKey = (initialTab === 'answers' || getQueryParam('topic') || getQueryParam('community')) ? 'answers' : '';
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

  function renderBadge() {
    var badge = $('landscapeBadge');
    var overview = data.overview || {};
    var insights = activeInsights();
    if (badge) {
      badge.textContent = insights.length + ' 条动态洞察 · ' +
        (overview.living_answer_count || 0) + ' 个 Living Answer';
    }
    var positioning = $('landscapePositioning');
    if (positioning && overview.positioning) positioning.textContent = overview.positioning;
    var insightMeta = $('landscapeInsightMeta');
    if (insightMeta) {
      var summary = insightPayload.summary || {};
      if ((insightPayload.insights || []).length) {
        insightMeta.textContent = (insightPayload.method || 'dynamic') + ' · ' +
          (summary.high_confidence_count || 0) + ' 条高置信';
      } else {
        insightMeta.textContent = 'fallback · 固定框架';
      }
    }
  }

  function renderStats() {
    var overview = data.overview || {};
    var insights = activeInsights();
    var insightSummary = insightPayload.summary || {};
    var stats = [
      ['动态洞察', insights.length, (insightPayload.insights || []).length ? '社区/图谱驱动' : '固定框架回退'],
      ['已获批对象', overview.competitive_count || (data.approved_competitive_matrix || data.competitive_matrix || []).length, '中国监管 + 证据厚度'],
      ['临床管线', overview.clinical_pipeline_count || (data.clinical_pipeline_matrix || []).length, '<a href="literature.html?tab=trials" class="stat-link">→ 情报中心</a>'],
      ['PMID 锚点', insightSummary.reference_count || 0, '动态洞察引用']
    ];
    var box = $('landscapeStats');
    if (!box) return;
    box.innerHTML = stats.map(function(item) {
      var label = /^</.test(item[2]) ? item[2] : escapeHtml(item[2]);
      return '<article class="landscape-stat-card"><span>' + escapeHtml(item[0]) + '</span><strong>' +
        escapeHtml(compactNumber(item[1])) + '</strong><em>' + label + '</em></article>';
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

  function topicHref(topicId) {
    return pageUrl('pages/landscape.html?tab=answers&topic=' + encodeURIComponent(topicId || ''));
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
    var impactItems = ((topic.impact && topic.impact.recent_articles) || []).slice(0, 6);
    var impactHtml = impactItems.length ? impactItems.map(renderReferenceItem).join('') : '<li>本周未发现明确影响该专题的新 abstract。</li>';
    var impact = (topic.impact && topic.impact.status) || 'quiet';

    detail.innerHTML =
      '<div class="kg-detail-type">' + escapeHtml(sourceTypeLabelForTopic(topic.source_type)) + '</div>' +
      '<h2>' + escapeHtml(topic.title || topic.id) + '</h2>' +
      '<div class="kg-badges">' +
        '<span class="kg-badge conf-' + escapeHtml(topic.confidence === 'high' ? 'high' : topic.confidence === 'medium' ? 'medium' : 'low') + '">' + escapeHtml(topic.confidence || 'unknown') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(topic.status || 'active') + '</span>' +
        '<span class="kg-badge">' + escapeHtml(impactStatusLabel(impact)) + '</span>' +
        '<span class="kg-badge">更新 ' + escapeHtml(topic.updated || '-') + '</span>' +
      '</div>' +
      '<div class="kg-detail-summary">' + escapeHtml(topic.summary || '') + '</div>' +
      renderTopicAnswerLinks(topic.id) +
      renderTopicCommunitySection(topic.id) +
      '<div class="kg-detail-section"><h4>全库锚点</h4><div class="kg-tags">' + anchorHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>MSL 使用场景</h4><div class="kg-tags">' + useHtml + '</div></div>' +
      '<div class="kg-detail-section"><h4>专题要点</h4>' + claimHtml + '</div>' +
      '<div class="kg-detail-section"><h4>专题 PMID</h4><ul class="kg-study-list">' + refsHtml + '</ul></div>' +
      '<div class="kg-detail-section"><h4>本周自动影响提示</h4><ul class="kg-study-list">' + impactHtml + '</ul></div>' +
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
      var impact = (topic.impact && topic.impact.status) || 'quiet';
      return (!keyword || topicSearchText(topic).indexOf(keyword) !== -1) &&
        (impactFilter === 'all' || impact === impactFilter) &&
        topicHasCommunity(topic.id, communityFilter);
    }).sort(function(a, b) {
      var impactA = (a.impact && a.impact.status) === 'updatedEvidence' ? 1 : 0;
      var impactB = (b.impact && b.impact.status) === 'updatedEvidence' ? 1 : 0;
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
      var impactCount = ((topic.impact && topic.impact.recent_articles) || []).length;
      var impact = (topic.impact && topic.impact.status) || 'quiet';
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
      window.history.replaceState(null, '', topicHref(topicId));
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

  function renderInsightEvidence(change) {
    var summary = change.evidence_summary || {};
    var parts = [
      '新增 ' + (summary.recent_count || 0) + ' 篇',
      '高等级 ' + (summary.high_evidence_count || 0) + ' 篇',
      '中国相关 ' + (summary.china_count || 0) + ' 篇'
    ];
    if (summary.signal_level) parts.push('信号 ' + summary.signal_level);
    return parts.join(' · ');
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

  function renderMonthlyChanges() {
    var changes = activeInsights();
    var box = $('monthlyChangeList');
    if (!box) return;
    if (!changes.length) {
      box.innerHTML = '<div class="kg-empty-hint">暂无格局变化数据。</div>';
      return;
    }
    box.innerHTML = changes.map(function(change) {
      var communities = (change.community_titles || []).map(function(title, index) {
        return { title: title, community_id: (change.community_ids || [])[index] || '' };
      });
      var nodes = change.knowledge_nodes || [];
      var topics = change.wiki_topics || [];
      var confidence = change.confidence || '';
      return '<article class="landscape-change-card">' +
        '<div class="change-card-head"><span>' + escapeHtml(change.change_type || change.type || '变化') + '</span><em class="insight-confidence ' + escapeHtml(confidence || 'unknown') + '">' + escapeHtml(confidenceLabel(confidence)) + '</em></div>' +
        '<strong class="change-title">' + escapeHtml(change.title) + '</strong>' +
        '<p>' + escapeHtml(change.selection_reason || change.why_it_matters || '') + '</p>' +
        (change.what_is_new ? '<div class="insight-new"><span>新在哪里</span><strong>' + escapeHtml(change.what_is_new) + '</strong></div>' : '') +
        '<div class="insight-chip-row">' + renderChipList(communities, 'mini-chip chip-button', '暂无社区') + '</div>' +
        '<div class="insight-evidence-line">' + escapeHtml(renderInsightEvidence(change)) + '</div>' +
        '<div class="change-meta-grid">' +
          '<div><span>影响位置</span><strong>' + escapeHtml(change.treatment_position || '-') + '</strong></div>' +
          '<div><span>竞争叙事</span><strong>' + escapeHtml(change.competitive_narrative || '-') + '</strong></div>' +
          '<div><span>MSL 准备</span><strong>' + escapeHtml(change.msl_action || '-') + '</strong></div>' +
        '</div>' +
        '<div class="insight-support-grid">' +
          '<div><span>图谱节点</span><div class="kg-tags">' + renderChipList(nodes, 'mini-chip chip-button', '暂无节点') + '</div></div>' +
          '<div><span>wiki 专题</span><div class="kg-tags">' + renderChipList(topics, 'mini-chip', '暂无专题') + '</div></div>' +
        '</div>' +
        '<div class="pmid-row">' + renderRefLinks(change.references, 3) + '</div>' +
        '<p class="answer-limitation">' + escapeHtml(change.limitations || '基于 abstract 和元数据；正式使用前需阅读全文。') + '</p>' +
      '</article>';
    }).join('');
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

  function renderGuidelineSlot(china) {
    var slot = china.guideline_consensus_slot || {};
    var box = $('guidelineConsensusSlot');
    if (!box) return;
    var inputs = (slot.expected_inputs || []).map(function(item) {
      return '<li>' + escapeHtml(item) + '</li>';
    }).join('');
    box.innerHTML = '<article class="guideline-slot">' +
      '<div class="guideline-slot-head"><strong>' + escapeHtml(slot.title || '指南/共识与路径差异') + '</strong>' +
      '<span>' + escapeHtml(slot.status_label || '等待接口') + '</span></div>' +
      '<p>' + escapeHtml(slot.note || '') + '</p>' +
      '<ul>' + inputs + '</ul>' +
    '</article>';
  }

  function renderEvidenceDirections(china) {
    var comparison = china.evidence_direction_comparison || {};
    var directions = comparison.directions || [];
    var box = $('chinaEvidenceDirections');
    if (!box) return;
    var meta = $('chinaEvidenceMeta');
    if (meta) {
      meta.textContent = (comparison.window_start || '-') + ' 至 ' + (comparison.window_end || '-') + ' · ' + (comparison.source || 'PubMed abstract');
    }
    if (!directions.length) {
      box.innerHTML = '<div class="kg-empty-hint">暂无证据方向统计。</div>';
      return;
    }
    box.innerHTML = directions.map(function(item) {
      var total = (Number(item.china_count) || 0) + (Number(item.non_china_count) || 0);
      var chinaCount = Number(item.china_count) || 0;
      var nonChinaCount = Number(item.non_china_count) || 0;
      var chinaWidth = total ? Math.round(chinaCount / total * 100) : 0;
      var nonChinaWidth = total ? 100 - chinaWidth : 0;
      if (chinaCount > 0 && chinaWidth < 3) chinaWidth = 3;
      if (nonChinaCount > 0 && nonChinaWidth < 3) nonChinaWidth = 3;
      return '<article class="evidence-direction-card">' +
        '<div class="evidence-direction-head"><strong>' + escapeHtml(item.dimension || '-') + '</strong><span>中国 ' + escapeHtml(item.china_count || 0) + ' / 非中国 ' + escapeHtml(item.non_china_count || 0) + '</span></div>' +
        '<div class="direction-bar" aria-hidden="true">' +
          '<span class="china-fill" style="width:' + escapeHtml(chinaWidth) + '%"></span>' +
          '<span class="global-fill" style="width:' + escapeHtml(nonChinaWidth) + '%"></span>' +
        '</div>' +
        '<p>' + escapeHtml(item.analysis_angle || '') + '</p>' +
        '<em>' + escapeHtml(item.signal || '') + '</em>' +
        '<div class="direction-ref-grid">' +
          '<div><span>中国 PMID</span><div class="pmid-row">' + renderRefLinks(item.china_refs, 2) + '</div></div>' +
          '<div><span>非中国 PMID</span><div class="pmid-row">' + renderRefLinks(item.non_china_refs, 2) + '</div></div>' +
        '</div>' +
      '</article>';
    }).join('');
  }

  function renderChinaLandscape() {
    var china = data.china_landscape || {};
    var principle = $('chinaLandscapePrinciple');
    if (principle) principle.innerHTML = '<p>' + escapeHtml(china.principle || '') + '</p>';
    renderGuidelineSlot(china);
    renderEvidenceDirections(china);
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
    renderMonthlyChanges();
    renderCompetitiveMatrix();
    renderChinaLandscape();
    populateAnswerFilters();
    populateTopicFilters();
    bindAnswerFilters();
    bindTopicFilters();
    renderAnswers();
    applyInitialAnswerRoute();
  }

  init();
})();
