/* MA-MG-HUB MSL 工作台 */
(function() {
  'use strict';

  var profiles = (window.MG_EXPERT_PROFILES && window.MG_EXPERT_PROFILES.experts) || [];
  var signals = (window.MG_SIGNALS_DATA && window.MG_SIGNALS_DATA.signals) || [];
  var contentPayload = window.MG_CONTENT_MODULES || { modules: [], templates: [], compliance_rules: [] };
  var modules = contentPayload.modules || [];
  var templates = contentPayload.templates || [];
  var selectedExpertId = '';
  var selectedTopic = 'all';
  var selectedRegion = 'china';
  var selectedModuleIds = initialModuleIds();

  var chinaInstitutionTerms = [
    'china', 'chinese', 'taiwan', 'hong kong', 'macau', 'beijing', 'shanghai',
    'guangzhou', 'nanjing', 'tianjin', 'xian', 'changsha', 'wuhan', 'jinan',
    'fudan', 'peking', 'xiangya', 'huashan', 'xuanwu', 'tangdu', 'tongji',
    'xuzhou', 'shandong', 'sichuan', 'zhejiang', 'sun yat', 'capital medical',
    'west china', 'pla general', 'first affiliated hospital'
  ];

  var el = {
    update: document.getElementById('mslUpdate'),
    search: document.getElementById('expertSearch'),
    topicFilters: document.getElementById('topicFilters'),
    regionFilters: document.getElementById('regionFilters'),
    expertCount: document.getElementById('expertCount'),
    expertList: document.getElementById('expertList'),
    expertDetail: document.getElementById('expertDetail'),
    visitSearch: document.getElementById('visitExpertSearch'),
    visitMeta: document.getElementById('visitExpertMeta'),
    visitChinaMatches: document.getElementById('visitChinaMatches'),
    moduleMeta: document.getElementById('moduleMeta'),
    moduleList: document.getElementById('visitModuleList'),
    compliance: document.getElementById('visitCompliance'),
    selectedExpertLine: document.getElementById('selectedExpertLine'),
    visitBrief: document.getElementById('visitBrief')
  };

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  function initialModuleIds() {
    var visitTemplate = templates.find(function(template) {
      return template.id === 'visit_material';
    }) || templates[0] || { modules: [] };
    return (visitTemplate.modules || []).slice();
  }

  function normalizeText(value) {
    return String(value || '')
      .toLowerCase()
      .replace(/[·.,;:()（）\[\]\-_/]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function compactName(value) {
    return normalizeText(value).replace(/\s+/g, '');
  }

  function hasChinaInstitution(expert) {
    var text = normalizeText(expert.affiliation || '');
    return chinaInstitutionTerms.some(function(term) {
      return text.indexOf(term) !== -1;
    });
  }

  function isChinaExpert(expert) {
    var metrics = expert.metrics || {};
    var region = normalizeText(expert.region || expert.country || expert.group || '');
    if (expert.profile_scope === 'china_author_identity' || expert.profile_scope === 'china_author_institution') return true;
    return region === 'china' || region === 'cn' || Boolean(expert.name_zh) || hasChinaInstitution(expert) || (metrics.china_related || 0) >= 8;
  }

  function identityStatus(expert) {
    var metrics = expert.metrics || {};
    var manualStatus = normalizeText(expert.identity_status || '');
    if (manualStatus === 'confirmed' || expert.identity_verified) {
      return { label: '已确认', className: 'high', note: '中文名与公开发文身份已绑定' };
    }
    if (manualStatus === 'candidate') {
      return { label: '待确认', className: 'low', note: '需人工确认中文名和唯一身份' };
    }
    if (expert.name_zh && isChinaExpert(expert)) {
      return { label: '已确认', className: 'high', note: '中文名与公开发文身份已绑定' };
    }
    if (isChinaExpert(expert) && ((metrics.china_related || 0) >= 20 || hasChinaInstitution(expert))) {
      return { label: '高置信', className: 'medium', note: '基于作者名、机构和发文聚合' };
    }
    if (isChinaExpert(expert)) {
      return { label: '待确认', className: 'low', note: '需人工确认中文名和唯一身份' };
    }
    return { label: '其他画像', className: 'foreign', note: '非中国机构作者画像' };
  }

  function displayName(expert) {
    if (!expert) return '';
    return expert.name_zh ? expert.name_zh + ' · ' + expert.name_en : expert.name_en;
  }

  function expertSearchBlob(expert) {
    var interests = (expert.interests || []).map(function(item) { return item.term; }).join(' ');
    var aliases = (expert.aliases || expert.name_aliases || []).join(' ');
    return normalizeText([
      expert.name_en,
      compactName(expert.name_en),
      expert.name_zh,
      aliases,
      expert.affiliation,
      (expert.public_tags || []).join(' '),
      interests
    ].join(' '));
  }

  function expertScore(expert, query) {
    var blob = expertSearchBlob(expert);
    var normalizedQuery = normalizeText(query);
    var compactQuery = compactName(query);
    if (!normalizedQuery) return baseExpertScore(expert);
    var parts = normalizedQuery.split(/\s+/).filter(Boolean);
    var hits = 0;
    for (var i = 0; i < parts.length; i++) {
      if (blob.indexOf(parts[i]) !== -1) hits += 1;
    }
    if (compactQuery && blob.indexOf(compactQuery) !== -1) hits += 2;
    if (normalizeText(expert.name_en).indexOf(normalizedQuery) === 0) hits += 3;
    if (expert.name_zh && normalizeText(expert.name_zh).indexOf(normalizedQuery) !== -1) hits += 4;
    if (!hits) return -1;
    return hits * 100 + baseExpertScore(expert);
  }

  function baseExpertScore(expert) {
    var metrics = expert.metrics || {};
    var status = identityStatus(expert);
    var identityBonus = status.className === 'high' ? 40 : status.className === 'medium' ? 24 : status.className === 'low' ? 12 : 0;
    return identityBonus + (metrics.china_related || 0) * 2 + (metrics.recent_3y_publications || 0) + (metrics.total_publications || 0) / 8;
  }

  function sortedExperts(query, region) {
    return profiles.map(function(expert) {
      return { expert: expert, score: expertScore(expert, query) };
    }).filter(function(item) {
      if (item.score < 0) return false;
      if (region === 'china') return isChinaExpert(item.expert);
      if (region === 'international') return !isChinaExpert(item.expert);
      return true;
    }).sort(function(a, b) {
      return b.score - a.score;
    }).map(function(item) {
      return item.expert;
    });
  }

  function bindTabs() {
    var tabs = document.querySelectorAll('[data-msl-tab]');
    var panels = document.querySelectorAll('.intel-tab-panel');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener('click', function() {
        var key = this.getAttribute('data-msl-tab');
        for (var t = 0; t < tabs.length; t++) tabs[t].classList.remove('active');
        for (var p = 0; p < panels.length; p++) panels[p].classList.remove('active');
        this.classList.add('active');
        document.getElementById('msl-' + key).classList.add('active');
      });
    }
  }

  function topTopics() {
    var counts = {};
    for (var i = 0; i < profiles.length; i++) {
      var regionOk = selectedRegion === 'all' ||
        (selectedRegion === 'china' && isChinaExpert(profiles[i])) ||
        (selectedRegion === 'international' && !isChinaExpert(profiles[i]));
      if (!regionOk) continue;
      var tags = profiles[i].public_tags || [];
      for (var j = 0; j < tags.length; j++) counts[tags[j]] = (counts[tags[j]] || 0) + 1;
    }
    return Object.keys(counts).sort(function(a, b) { return counts[b] - counts[a]; }).slice(0, 10);
  }

  function renderTopicFilters() {
    var topics = topTopics();
    var html = '<label class="filter-checkbox-item"><input type="radio" name="topic" value="all" checked> 全部</label>';
    for (var i = 0; i < topics.length; i++) {
      html += '<label class="filter-checkbox-item"><input type="radio" name="topic" value="' + escapeHtml(topics[i]) + '"> ' + escapeHtml(topics[i]) + '</label>';
    }
    el.topicFilters.innerHTML = html;
  }

  function bindTopicFilters() {
    el.topicFilters.addEventListener('change', function(e) {
      if (e.target && e.target.name === 'topic') {
        selectedTopic = e.target.value;
        renderExperts();
      }
    });
    if (!el.regionFilters) return;
    el.regionFilters.addEventListener('change', function(e) {
      if (e.target && e.target.name === 'region') {
        selectedRegion = e.target.value;
        selectedTopic = 'all';
        renderTopicFilters();
        renderExperts();
      }
    });
  }

  function filteredExperts() {
    var keyword = el.search ? (el.search.value || '').trim() : '';
    var list = sortedExperts(keyword, selectedRegion);
    if (selectedTopic !== 'all') {
      list = list.filter(function(expert) {
        var text = expertSearchBlob(expert);
        return text.indexOf(normalizeText(selectedTopic)) !== -1;
      });
    }
    return list;
  }

  function renderExperts() {
    var list = filteredExperts();
    el.expertCount.textContent = list.length;
    if (!list.length) {
      el.expertList.innerHTML = '<div class="empty-state"><h3>暂无匹配专家</h3></div>';
      el.expertDetail.innerHTML = '<div class="empty-state"><h3>暂无专家数据</h3></div>';
      return;
    }
    if (!list.some(function(item) { return item.id === selectedExpertId; })) selectedExpertId = list[0].id;
    el.expertList.innerHTML = list.slice(0, 80).map(renderExpertRow).join('');
    var cards = el.expertList.querySelectorAll('.expert-row');
    for (var i = 0; i < cards.length; i++) {
      cards[i].addEventListener('click', function() {
        selectedExpertId = this.getAttribute('data-expert-id');
        renderExperts();
        renderVisitExpertMatches();
        renderSelectedExpertLine();
        renderBriefPreview();
      });
    }
    renderExpertDetail();
  }

  function renderExpertRow(expert) {
    var metrics = expert.metrics || {};
    var status = identityStatus(expert);
    var tags = (expert.public_tags || []).slice(0, 3).map(function(tag) {
      return '<span class="mini-chip">' + escapeHtml(tag) + '</span>';
    }).join('');
    return '<article class="expert-row ' + (expert.id === selectedExpertId ? 'active' : '') + '" data-expert-id="' + escapeHtml(expert.id) + '">' +
      '<div class="expert-row-head"><strong>' + escapeHtml(displayName(expert)) + '</strong><span class="identity-badge ' + status.className + '">' + escapeHtml(status.label) + '</span></div>' +
      '<div>' + escapeHtml(expert.affiliation || '机构待识别') + '</div>' +
      '<div class="metric-line">发文 ' + (metrics.total_publications || 0) + ' · 近3年 ' + (metrics.recent_3y_publications || 0) + '</div>' +
      '<div class="chip-row">' + tags + '</div>' +
    '</article>';
  }

  function getSelectedExpert() {
    return profiles.find(function(item) { return item.id === selectedExpertId; }) || profiles[0];
  }

  function renderExpertDetail() {
    var expert = getSelectedExpert();
    if (!expert) {
      el.expertDetail.innerHTML = '<div class="empty-state"><h3>暂无专家数据</h3></div>';
      return;
    }
    var metrics = expert.metrics || {};
    var status = identityStatus(expert);
    var interests = (expert.interests || []).slice(0, 8).map(function(item) {
      var width = Math.min(100, Math.max(12, item.count * 8));
      return '<div class="interest-bar"><span>' + escapeHtml(item.term) + '</span><div><i style="width:' + width + '%"></i></div><strong>' + item.count + '</strong></div>';
    }).join('');
    var timeline = (expert.timeline || []).slice(0, 6).map(function(item) {
      return '<li><a href="' + escapeHtml(item.url || '#') + '" target="_blank">' + escapeHtml(item.title) + '</a><span>' + escapeHtml(item.pub_date || item.entry_date || '') + ' · PMID ' + escapeHtml(item.pmid) + '</span></li>';
    }).join('');
    var collaborators = (expert.collaborators || []).slice(0, 6).map(function(item) {
      return '<span class="mini-chip">' + escapeHtml(item.name) + ' ' + item.count + '</span>';
    }).join('');
    el.expertDetail.innerHTML =
      '<div class="detail-title">' +
        '<h2>' + escapeHtml(displayName(expert)) + '</h2>' +
        '<p>' + escapeHtml(expert.affiliation || '机构待识别') + '</p>' +
      '</div>' +
      '<div class="identity-note ' + status.className + '"><strong>' + escapeHtml(status.label) + '</strong><span>' + escapeHtml(status.note) + '</span></div>' +
      '<div class="metric-grid">' +
        '<div><span>总发文</span><strong>' + (metrics.total_publications || 0) + '</strong></div>' +
        '<div><span>近3年</span><strong>' + (metrics.recent_3y_publications || 0) + '</strong></div>' +
        '<div><span>最高IF</span><strong>' + (metrics.highest_if || 0) + '</strong></div>' +
        '<div><span>期刊数</span><strong>' + (metrics.journal_count || 0) + '</strong></div>' +
      '</div>' +
      '<h3>研究兴趣向量</h3>' + (interests || '<div class="muted">暂无主题</div>') +
      '<h3>主要合作者</h3><div class="chip-row">' + (collaborators || '<span class="muted">暂无数据</span>') + '</div>' +
      '<h3>近期文献时间线</h3><ol class="timeline-list">' + timeline + '</ol>';
  }

  function renderVisitExpertMatches() {
    var query = (el.visitSearch.value || '').trim();
    var chinaExperts = sortedVisitExperts(query).slice(0, 10);
    if (chinaExperts.length && !chinaExperts.some(function(item) { return item.id === selectedExpertId; })) {
      selectedExpertId = chinaExperts[0].id;
    }
    el.visitChinaMatches.innerHTML = chinaExperts.map(renderVisitExpertCard).join('') || '<div class="empty-state small"><h3>暂无中国专家匹配</h3></div>';
    bindVisitExpertCards();
    renderSelectedExpertLine();
    renderBriefPreview();
  }

  function sortedVisitExperts(query) {
    var normalizedQuery = normalizeText(query);
    return profiles.filter(function(expert) {
      if (!isChinaExpert(expert)) return false;
      if (!normalizedQuery) return true;
      return expertScore(expert, query) >= 0;
    }).sort(function(a, b) {
      var metricsA = a.metrics || {};
      var metricsB = b.metrics || {};
      var totalDiff = (metricsB.total_publications || 0) - (metricsA.total_publications || 0);
      if (totalDiff) return totalDiff;
      return (metricsB.recent_3y_publications || 0) - (metricsA.recent_3y_publications || 0);
    });
  }

  function renderVisitExpertCard(expert) {
    var metrics = expert.metrics || {};
    var status = identityStatus(expert);
    var active = expert.id === selectedExpertId ? ' active' : '';
    var tags = (expert.public_tags || []).slice(0, 3).map(function(tag) {
      return '<span class="mini-chip">' + escapeHtml(tag) + '</span>';
    }).join('');
    return '<button class="visit-expert-card' + active + '" type="button" data-expert-id="' + escapeHtml(expert.id) + '">' +
      '<span class="visit-expert-top"><strong>' + escapeHtml(displayName(expert)) + '</strong><em class="identity-badge ' + status.className + '">' + escapeHtml(status.label) + '</em></span>' +
      '<span>' + escapeHtml(expert.affiliation || '机构待识别') + '</span>' +
      '<span class="visit-expert-meta">发文 ' + (metrics.total_publications || 0) + ' · 近3年 ' + (metrics.recent_3y_publications || 0) + '</span>' +
      '<span class="chip-row">' + tags + '</span>' +
    '</button>';
  }

  function bindVisitExpertCards() {
    var cards = document.querySelectorAll('.visit-expert-card');
    for (var i = 0; i < cards.length; i++) {
      cards[i].addEventListener('click', function() {
        selectedExpertId = this.getAttribute('data-expert-id');
        renderVisitExpertMatches();
        renderExperts();
        renderBriefPreview();
      });
    }
  }

  function renderSelectedExpertLine() {
    var expert = getSelectedExpert();
    if (!expert) {
      el.selectedExpertLine.textContent = '请选择专家';
      return;
    }
    var status = identityStatus(expert);
    el.selectedExpertLine.textContent = displayName(expert) + ' · ' + (expert.affiliation || '机构待识别') + ' · ' + status.label;
  }

  function renderModulePicker() {
    if (!modules.length) {
      el.moduleList.innerHTML = '<div class="empty-state small"><h3>暂无内容模块</h3></div>';
      return;
    }
    el.moduleList.innerHTML = modules.map(function(module) {
      var checked = selectedModuleIds.indexOf(module.id) !== -1 ? 'checked' : '';
      var claims = (module.claims || []).slice(0, 2).map(function(claim) {
        return '<li>' + escapeHtml(claim.text) + '<span>PMID ' + escapeHtml(claim.pmid || '-') + ' · ' + escapeHtml(claim.evidence_level || '未分类') + '</span></li>';
      }).join('');
      return '<article class="module-card compact">' +
        '<label class="module-check"><input type="checkbox" value="' + escapeHtml(module.id) + '" ' + checked + '> <strong>' + escapeHtml(module.title) + '</strong></label>' +
        '<div class="module-meta">' + escapeHtml(module.type) + ' · 更新 ' + escapeHtml(module.updated_at || '-') + '</div>' +
        '<ul>' + claims + '</ul>' +
      '</article>';
    }).join('');
    var inputs = el.moduleList.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < inputs.length; i++) {
      inputs[i].addEventListener('change', function() {
        selectedModuleIds = Array.from(el.moduleList.querySelectorAll('input[type="checkbox"]:checked')).map(function(input) {
          return input.value;
        });
        renderCompliance();
        renderBriefPreview();
      });
    }
    renderCompliance();
  }

  function selectedModules() {
    return modules.filter(function(module) {
      return selectedModuleIds.indexOf(module.id) !== -1;
    });
  }

  function renderCompliance() {
    var selected = selectedModules();
    if (!el.compliance) return;
    el.compliance.innerHTML = selected.length
      ? '<span>' + selected.length + ' 个产品研究信息已纳入右侧话题建议</span>'
      : '<span>请选择产品研究信息，右侧建议会自动更新</span>';
  }

  function relatedSignalsForExpert(expert) {
    var tags = (expert.public_tags || []).map(normalizeText);
    var interests = (expert.interests || []).slice(0, 6).map(function(item) {
      return normalizeText(item.term);
    });
    var keys = tags.concat(interests);
    var scored = signals.map(function(signal) {
      var text = normalizeText([
        signal.summary,
        (signal.keywords || []).join(' '),
        (signal.drugs || []).join(' ')
      ].join(' '));
      var hits = keys.filter(function(key) { return key && text.indexOf(key) !== -1; }).length;
      var strengthBonus = signal.strength === '强' ? 3 : signal.strength === '中' ? 2 : 1;
      return { signal: signal, score: hits * 4 + strengthBonus + (signal.score || 0) / 10 };
    }).filter(function(item) {
      return item.score > 1;
    });
    scored.sort(function(a, b) { return b.score - a.score; });
    return scored.slice(0, 4).map(function(item) { return item.signal; });
  }

  function articleKey(article) {
    return article && article.pmid ? 'pmid:' + article.pmid : 'title:' + normalizeText(article && article.title);
  }

  function collectReferences(expert, moduleList, signalList) {
    var map = {};
    function add(article, source) {
      if (!article) return;
      var key = articleKey(article);
      if (!map[key]) {
        map[key] = {
          pmid: article.pmid || '',
          title: article.title || '',
          journal: article.journal || '',
          pub_date: article.pub_date || article.entry_date || '',
          url: article.url || '',
          evidence_level: article.evidence_level || '',
          china_related: Boolean(article.china_related),
          sources: []
        };
      }
      if (map[key].sources.indexOf(source) === -1) map[key].sources.push(source);
    }
    (expert.timeline || []).slice(0, 4).forEach(function(article) { add(article, '专家近期发文'); });
    signalList.forEach(function(signal) { add(signal.article, '近期信号'); });
    moduleList.forEach(function(module) {
      (module.references || []).slice(0, 5).forEach(function(article) { add(article, module.title); });
    });
    var rows = Object.keys(map).map(function(key) { return map[key]; });
    rows.sort(function(a, b) {
      var scoreA = a.evidence_level === 'I' ? 6 : a.evidence_level === 'II' ? 5 : a.evidence_level === 'III' ? 4 : 1;
      var scoreB = b.evidence_level === 'I' ? 6 : b.evidence_level === 'II' ? 5 : b.evidence_level === 'III' ? 4 : 1;
      return scoreB - scoreA;
    });
    return rows.slice(0, 12);
  }

  function renderBriefPreview() {
    var expert = getSelectedExpert();
    var selected = selectedModules();
    if (!expert || !selected.length) {
      el.visitBrief.innerHTML =
        '<div class="empty-state">' +
          '<h3>选择专家和产品研究信息后生成建议</h3>' +
          '<p>左侧选择 1 位专家，并勾选至少 1 个产品研究信息；右侧会即时生成拜访话题和对应文献清单。</p>' +
        '</div>';
      return;
    }
    generateBrief();
  }

  function generateBrief() {
    var expert = getSelectedExpert();
    var selected = selectedModules();
    if (!expert) return;
    var expertTopics = (expert.public_tags || []).slice(0, 4);
    var moduleTypes = selected.map(function(module) { return module.type; });
    var signalList = relatedSignalsForExpert(expert);
    if (!signalList.length) signalList = signals.slice(0, 3);
    var references = collectReferences(expert, selected, signalList);
    var openingTopics = buildOpeningTopics(expert, selected, signalList);
    var bridgeItems = buildBridgeItems(selected);
    var questions = buildQuestions(expert, selected, signalList);

    el.visitBrief.innerHTML =
      '<div class="brief-section">' +
        '<h3>' + escapeHtml(displayName(expert)) + ' · 拜访话题建议</h3>' +
        '<p><strong>研究兴趣：</strong>' + escapeHtml(expertTopics.join('、') || 'MG 研究') + '</p>' +
        '<p><strong>本次内容：</strong>' + escapeHtml(moduleTypes.join('、') || '未选择产品研究信息') + '</p>' +
      '</div>' +
      '<div class="brief-section">' +
        '<h4>建议切入点</h4>' +
        '<ol>' + openingTopics.map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') + '</ol>' +
      '</div>' +
      '<div class="brief-section">' +
        '<h4>产品研究信息接入</h4>' +
        '<ul>' + bridgeItems.map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') + '</ul>' +
      '</div>' +
      '<div class="brief-section">' +
        '<h4>可追问问题</h4>' +
        '<ul>' + questions.map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') + '</ul>' +
      '</div>' +
      '<div class="brief-section">' +
        '<h4>近期信号</h4>' +
        '<ul>' + signalList.map(function(signal) {
          return '<li>' + escapeHtml(signal.strength + '信号 · ' + signal.summary) + '</li>';
        }).join('') + '</ul>' +
      '</div>' +
      '<div class="brief-section">' +
        '<h4>对应文献清单</h4>' +
        renderReferenceTable(references) +
      '</div>' +
      '<div class="brief-compliance">自动生成内容仅作拜访准备草稿；疗效、安全性、适应症和比较性表述需核对 PMID 原文后使用。</div>';
  }

  function buildOpeningTopics(expert, selected, signalList) {
    var interests = (expert.public_tags || []).slice(0, 3);
    var topics = [];
    if (interests.length) {
      topics.push('从专家近期关注的 ' + interests.join('、') + ' 切入，确认当前临床证据缺口。');
    }
    if (signalList[0]) {
      topics.push('结合近期信号“' + signalList[0].summary + '”，询问其对中国患者实践的可转化性判断。');
    }
    if (selected[0]) {
      topics.push('围绕“' + selected[0].title + '”中的关键 PMID，讨论哪些数据最适合进入后续材料。');
    }
    topics.push('最后收束到专家希望补充的证据类型：RCT、真实世界、安全性、特殊人群或竞品比较。');
    return topics.slice(0, 4);
  }

  function buildBridgeItems(selected) {
    if (!selected.length) return ['暂未选择产品研究信息，可先围绕专家兴趣和近期信号做开放式探访。'];
    return selected.slice(0, 4).map(function(module) {
      var claim = (module.claims || [])[0];
      var pmid = claim && claim.pmid ? 'PMID ' + claim.pmid : 'PMID 待补';
      return module.title + '：以 ' + pmid + ' 作为证据锚点，先确认专家对该方向的关注度，再展开材料。';
    });
  }

  function buildQuestions(expert, selected, signalList) {
    var interests = (expert.public_tags || []).slice(0, 2).join('、') || 'MG 靶向治疗';
    var questions = [
      '您目前在 ' + interests + ' 方向最希望看到哪类中国本土证据？',
      '对于近期新证据，您会优先关注疗效终点、安全性监测还是患者选择？',
      '在真实世界使用中，哪些患者特征最影响治疗路径选择？'
    ];
    if (selected.some(function(module) { return module.type === '竞品对比'; })) {
      questions.push('面对 FcRn、补体和 B 细胞方向的并行证据，您更认可怎样的机制区隔口径？');
    } else if (signalList.length) {
      questions.push('这些近期信号是否会改变您对下一次材料沟通重点的期待？');
    }
    return questions.slice(0, 4);
  }

  function renderReferenceTable(references) {
    if (!references.length) return '<div class="muted">暂无可关联文献</div>';
    return '<div class="msl-reference-table"><table><thead><tr><th>PMID</th><th>文献</th><th>证据</th><th>来源</th></tr></thead><tbody>' +
      references.map(function(ref) {
        var link = ref.url ? '<a href="' + escapeHtml(ref.url) + '" target="_blank">' + escapeHtml(ref.pmid || '-') + '</a>' : escapeHtml(ref.pmid || '-');
        return '<tr>' +
          '<td>' + link + '</td>' +
          '<td><strong>' + escapeHtml(ref.title || '-') + '</strong><span>' + escapeHtml(ref.journal || '') + ' · ' + escapeHtml(ref.pub_date || '') + '</span></td>' +
          '<td>' + escapeHtml(ref.evidence_level || '未分类') + '</td>' +
          '<td>' + escapeHtml(ref.sources.join(' / ')) + '</td>' +
        '</tr>';
      }).join('') +
      '</tbody></table></div>';
  }

  function initSelectedExpert() {
    var chinaExperts = sortedExperts('', 'china');
    selectedExpertId = (chinaExperts[0] || profiles[0] || {}).id || '';
  }

  function init() {
    bindTabs();
    initSelectedExpert();
    renderTopicFilters();
    bindTopicFilters();
    renderExperts();
    renderVisitExpertMatches();
    renderModulePicker();
    renderSelectedExpertLine();
    if (el.search) el.search.addEventListener('input', renderExperts);
    if (el.visitSearch) el.visitSearch.addEventListener('input', renderVisitExpertMatches);
    if (el.update) {
      var chinaCount = profiles.filter(isChinaExpert).length;
      el.update.textContent = '中国专家 ' + chinaCount + ' 位 · 专家画像 ' + profiles.length + ' 位 · 内容模块 ' + modules.length + ' 个';
    }
    if (el.visitMeta) {
      el.visitMeta.textContent = '按总发文量降序显示前 10 位中国专家';
    }
    if (el.moduleMeta) {
      el.moduleMeta.textContent = modules.length + ' 个模块可选';
    }
    renderBriefPreview();
  }

  init();
})();
