/* MA-MG-HUB MSL 工作台 */
(function() {
  'use strict';

  var hub = window.MgHub || {};
  var expertPayload = window.MG_EXPERT_PROFILES || {};
  var profiles = expertPayload.experts || [];
  var chinaExpertIndex = ((window.MG_EXPERT_PROFILE_CHINA || {}).items) || expertPayload.china_expert_index || [];
  var internationalExpertIndex = ((window.MG_EXPERT_PROFILE_INTERNATIONAL || {}).items) || expertPayload.international_expert_index || [];
  var quickExpertIds = expertPayload.quick_expert_ids || {};
  var expertIndex = [];
  var expertPool = [];
  var expertById = {};
  var internationalExpertsLoaded = internationalExpertIndex.length > 0;
  var internationalExpertsLoading = false;
  var internationalExpertCallbacks = [];
  var signals = (window.MG_SIGNALS_DATA && window.MG_SIGNALS_DATA.signals) || [];
  var landscapeInsights = (window.MG_LANDSCAPE_INSIGHTS && window.MG_LANDSCAPE_INSIGHTS.insights) || [];
  var landscapeInsightSummary = (window.MG_LANDSCAPE_INSIGHTS && window.MG_LANDSCAPE_INSIGHTS.summary) || {};
  var contentPayload = window.MG_CONTENT_MODULES || { modules: [], templates: [], compliance_rules: [] };
  var modules = contentPayload.modules || [];
  var templates = contentPayload.templates || [];
  var selectedProfileExpertId = '';
  var selectedVisitExpertId = '';
  var selectedTopic = 'all';
  var selectedRegion = 'china';
  var selectedLocation = 'all';
  var selectedProductivity = 'all';
  var selectedActive = 'all';
  var selectedModuleIds = initialModuleIds();
  var expertResultLimit = 20;

  var researchTopicOrder = [
    '真实世界', '疗效', '安全性', '机制', '抗体分型',
    'FcRn', '补体', 'B细胞', '诊疗策略'
  ];

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
    institutionFilter: document.getElementById('institutionFilter'),
    institutionOptions: document.getElementById('institutionOptions'),
    locationFilterLabel: document.getElementById('locationFilterLabel'),
    provinceFilter: document.getElementById('provinceFilter'),
    productivityFilter: document.getElementById('productivityFilter'),
    activeFilter: document.getElementById('activeFilter'),
    expertCount: document.getElementById('expertCount'),
    expertResultMeta: document.getElementById('expertResultMeta'),
    expertList: document.getElementById('expertList'),
    expertDetail: document.getElementById('expertDetail'),
    visitSearch: document.getElementById('visitExpertSearch'),
    visitMeta: document.getElementById('visitExpertMeta'),
    visitChinaMatches: document.getElementById('visitChinaMatches'),
    moduleMeta: document.getElementById('moduleMeta'),
    moduleList: document.getElementById('visitModuleList'),
    compliance: document.getElementById('visitCompliance'),
    landscapeActionMeta: document.getElementById('landscapeActionMeta'),
    landscapeActionList: document.getElementById('landscapeActionList'),
    selectedExpertLine: document.getElementById('selectedExpertLine'),
    visitBrief: document.getElementById('visitBrief')
  };

  function escapeHtml(text) {
    if (hub.escapeText) return hub.escapeText(text);
    return String(text == null ? '' : text).replace(/[&<>"']/g, function(char) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
    });
  }

  function escapeHref(value, fallback) {
    if (hub.safeUrl) return hub.safeUrl(value, fallback || '#');
    return escapeHtml(fallback || '#');
  }

  function initialModuleIds() {
    return [];
  }

  function buildExpertPool() {
    return expertIndex.slice();
  }

  function buildExpertById() {
    var map = {};
    expertPool.forEach(function(expert) {
      if (expert.id) map[expert.id] = expert;
    });
    profiles.forEach(function(expert) {
      if (expert.id) map[expert.id] = expert;
    });
    return map;
  }

  function refreshExpertCollections() {
    expertIndex = chinaExpertIndex.concat(internationalExpertIndex);
    expertPool = buildExpertPool();
    expertById = buildExpertById();
  }

  function expertShardPath(region) {
    var shards = expertPayload.shards || [];
    for (var i = 0; i < shards.length; i++) {
      if (shards[i].id === region && shards[i].path) return shards[i].path;
    }
    return region === 'international' ? 'data/expert-profiles-international.js' : 'data/expert-profiles-china.js';
  }

  function loadScript(src, callback) {
    if (hub.loadScript) {
      hub.loadScript(src, callback);
      return;
    }
    var script = document.createElement('script');
    script.src = src.indexOf('data/') === 0 ? '../' + src : src;
    script.onload = function() { callback(true); };
    script.onerror = function() { callback(false); };
    document.head.appendChild(script);
  }

  function updateInternationalShard() {
    var shard = window.MG_EXPERT_PROFILE_INTERNATIONAL || {};
    internationalExpertIndex = shard.items || internationalExpertIndex || [];
    internationalExpertsLoaded = internationalExpertIndex.length > 0;
    refreshExpertCollections();
  }

  function loadInternationalExperts(callback) {
    if (internationalExpertsLoaded) {
      if (callback) callback(true);
      return;
    }
    if (callback) internationalExpertCallbacks.push(callback);
    if (internationalExpertsLoading) return;
    internationalExpertsLoading = true;
    loadScript(expertShardPath('international'), function(ok) {
      if (ok) updateInternationalShard();
      internationalExpertsLoading = false;
      var callbacks = internationalExpertCallbacks.slice();
      internationalExpertCallbacks = [];
      callbacks.forEach(function(fn) { fn(Boolean(ok && internationalExpertsLoaded)); });
      updateExpertBadge();
    });
  }

  function needsInternationalExperts(region) {
    return region === 'international' || region === 'all';
  }

  function renderAfterExpertLoad() {
    renderTopicFilters();
    renderExpertFilterOptions();
    renderExperts();
    renderVisitExpertMatches();
    renderSelectedExpertLine();
    renderBriefPreview();
  }

  refreshExpertCollections();

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

  function expertMetrics(expert) {
    var metrics = (expert && expert.metrics) || {};
    if (Array.isArray(metrics)) {
      return {
        total_publications: metrics[0] || 0,
        recent_3y_publications: metrics[1] || 0,
        highest_if: metrics[2] || 0,
        journal_count: metrics[3] || 0,
        china_related: metrics[4] || 0
      };
    }
    return metrics;
  }

  function namedCountItems(items, nameKey) {
    return (items || []).map(function(item) {
      if (Array.isArray(item)) return { term: item[0], name: item[0], count: item[1] || 0 };
      if (typeof item === 'string') return { term: item, name: item, count: 1 };
      return {
        term: item.term || item[nameKey] || item.name || '',
        name: item.name || item.term || item[nameKey] || '',
        count: item.count || 0
      };
    }).filter(function(item) {
      return item.term || item.name;
    });
  }

  function expertTags(expert) {
    if (expert.public_tags && expert.public_tags.length) return expert.public_tags;
    return namedCountItems(expert.interests, 'term').slice(0, 4).map(function(item) {
      return item.term;
    });
  }

  function expertTimeline(expert) {
    var timeline = expert.timeline || [];
    if (!timeline.length) return [];
    if (Array.isArray(timeline[0])) {
      return timeline.filter(function(item) { return item && item[0]; }).map(function(item) {
        return {
          pmid: item[0] || '',
          title: item[1] || '',
          journal: item[2] || '',
          pub_date: item[3] || '',
          url: item[4] || ''
        };
      });
    }
    if (typeof timeline[0] === 'string') {
      if (!timeline[0] && !timeline[1]) return [];
      return [{
        pmid: timeline[0] || '',
        title: timeline[1] || '',
        journal: timeline[2] || '',
        pub_date: timeline[3] || '',
        url: timeline[4] || ''
      }];
    }
    return timeline;
  }

  function isDefaultProfileQuery(keyword, institutionKeyword) {
    return !keyword &&
      !institutionKeyword &&
      selectedTopic === 'all' &&
      selectedLocation === 'all' &&
      selectedProductivity === 'all' &&
      selectedActive === 'all';
  }

  function quickExperts(region) {
    var ids = quickExpertIds[region] || quickExpertIds.all || [];
    return ids.map(function(id) { return expertById[id]; }).filter(Boolean);
  }

  function debounce(fn, wait) {
    var timer = null;
    return function() {
      clearTimeout(timer);
      timer = setTimeout(fn, wait);
    };
  }

  function hasChinaInstitution(expert) {
    var text = normalizeText(expert.affiliation || '');
    return chinaInstitutionTerms.some(function(term) {
      return text.indexOf(term) !== -1;
    });
  }

  function isChinaExpert(expert) {
    var metrics = expertMetrics(expert);
    var region = normalizeText(expert.region || expert.country || expert.group || '');
    if (region === 'international' || expert.profile_scope === 'international_author_identity_index') return false;
    if (region === 'china' || region === 'cn' || region === '中国') return true;
    if (expert.profile_scope === 'china_author_identity' || expert.profile_scope === 'china_author_identity_index' || expert.profile_scope === 'china_author_institution') return true;
    return Boolean(expert.name_zh) || hasChinaInstitution(expert) || (metrics.china_related || 0) >= 8;
  }

  function identityStatus(expert) {
    var metrics = expertMetrics(expert);
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
    return { label: '国外画像', className: 'foreign', note: '基于 PubMed 作者-机构聚合的国外作者画像' };
  }

  function displayName(expert) {
    if (!expert) return '';
    return expert.name_zh ? expert.name_zh + ' · ' + expert.name_en : expert.name_en;
  }

  function expertSearchBlob(expert) {
    if (expert._search_blob) return expert._search_blob;
    var interests = namedCountItems(expert.interests, 'term').map(function(item) { return item.term; }).join(' ');
    var aliases = (expert.aliases || expert.name_aliases || []).join(' ');
    var institutionAliases = (expert.institution_aliases || []).map(function(item) {
      return typeof item === 'string' ? item : item.name || '';
    }).join(' ');
    expert._search_blob = normalizeText([
      expert.name_en,
      compactName(expert.name_en),
      expert.name_zh,
      aliases,
      expert.affiliation,
      expert.country,
      expert.region,
      institutionAliases,
      expert.province,
      expert.city,
      expertTags(expert).join(' '),
      interests
    ].join(' '));
    return expert._search_blob;
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
    var metrics = expertMetrics(expert);
    var status = identityStatus(expert);
    var identityBonus = status.className === 'high' ? 40 : status.className === 'medium' ? 24 : status.className === 'low' ? 12 : 0;
    return identityBonus + (metrics.china_related || 0) * 2 + (metrics.recent_3y_publications || 0) + (metrics.total_publications || 0) / 8;
  }

  function sortedExperts(query, region) {
    return expertPool.map(function(expert) {
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

  function expertLocationValue(expert) {
    if (isChinaExpert(expert)) return expert.province || '未识别';
    return expert.country || '未识别';
  }

  function expertLocationText(expert) {
    if (isChinaExpert(expert)) return [expert.province, expert.city].filter(Boolean).join(' · ');
    return expert.country || '国家未识别';
  }

  function matchesRegion(expert, region) {
    if (region === 'china') return isChinaExpert(expert);
    if (region === 'international') return !isChinaExpert(expert);
    return true;
  }

  function findExpertById(id) {
    if (!id) return null;
    return expertById[id] || null;
  }

  function bindTabs() {
    if (hub.initTabs) {
      hub.initTabs({
        tabAttr: 'data-msl-tab',
        panelFor: function(key) { return document.getElementById('msl-' + key); }
      });
      return;
    }
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
    for (var i = 0; i < expertPool.length; i++) {
      if (!matchesRegion(expertPool[i], selectedRegion)) continue;
      var tags = expertTags(expertPool[i]);
      for (var j = 0; j < tags.length; j++) counts[tags[j]] = (counts[tags[j]] || 0) + 1;
    }
    return researchTopicOrder.filter(function(topic) { return counts[topic]; });
  }

  function renderTopicFilters() {
    var topics = topTopics();
    var html = '<label class="filter-checkbox-item"><input type="radio" name="topic" value="all" checked> 全部</label>';
    for (var i = 0; i < topics.length; i++) {
      html += '<label class="filter-checkbox-item"><input type="radio" name="topic" value="' + escapeHtml(topics[i]) + '"> ' + escapeHtml(topics[i]) + '</label>';
    }
    el.topicFilters.innerHTML = html;
  }

  function renderExpertFilterOptions() {
    if (el.provinceFilter) {
      var locationCounts = {};
      expertPool.forEach(function(expert) {
        if (!matchesRegion(expert, selectedRegion)) return;
        var location = expertLocationValue(expert);
        locationCounts[location] = (locationCounts[location] || 0) + 1;
      });
      var locations = Object.keys(locationCounts).sort(function(a, b) {
        if (a === '未识别') return 1;
        if (b === '未识别') return -1;
        return locationCounts[b] - locationCounts[a] || a.localeCompare(b, 'zh-Hans-CN');
      });
      var locationLabel = selectedRegion === 'international' ? '国家' : selectedRegion === 'all' ? '省份 / 国家' : '省份';
      if (el.locationFilterLabel) el.locationFilterLabel.textContent = locationLabel;
      el.provinceFilter.innerHTML = '<option value="all">全部</option>' + locations.map(function(location) {
        return '<option value="' + escapeHtml(location) + '">' + escapeHtml(location) + ' · ' + locationCounts[location] + '</option>';
      }).join('');
      el.provinceFilter.value = selectedLocation;
    }
    if (el.institutionOptions) {
      var institutionCounts = {};
      expertPool.forEach(function(expert) {
        if (!matchesRegion(expert, selectedRegion) || !expert.affiliation) return;
        institutionCounts[expert.affiliation] = (institutionCounts[expert.affiliation] || 0) + 1;
      });
      var institutions = Object.keys(institutionCounts).sort(function(a, b) {
        return institutionCounts[b] - institutionCounts[a] || a.localeCompare(b);
      }).slice(0, 120);
      el.institutionOptions.innerHTML = institutions.map(function(name) {
        return '<option value="' + escapeHtml(name) + '">';
      }).join('');
    }
  }

  function bindTopicFilters() {
    el.topicFilters.addEventListener('change', function(e) {
      if (e.target && e.target.name === 'topic') {
        selectedTopic = e.target.value;
        renderExperts();
      }
    });
    if (el.regionFilters) {
      el.regionFilters.addEventListener('change', function(e) {
        if (e.target && e.target.name === 'region') {
          selectedRegion = e.target.value;
          selectedTopic = 'all';
          selectedLocation = 'all';
          if (needsInternationalExperts(selectedRegion) && !internationalExpertsLoaded) {
            renderExperts();
            loadInternationalExperts(renderAfterExpertLoad);
            return;
          }
          renderAfterExpertLoad();
        }
      });
    }
    if (el.institutionFilter) el.institutionFilter.addEventListener('input', renderExperts);
    if (el.provinceFilter) {
      el.provinceFilter.addEventListener('change', function() {
        selectedLocation = el.provinceFilter.value || 'all';
        renderExperts();
      });
    }
    if (el.productivityFilter) {
      el.productivityFilter.addEventListener('change', function() {
        selectedProductivity = el.productivityFilter.value || 'all';
        renderExperts();
      });
    }
    if (el.activeFilter) {
      el.activeFilter.addEventListener('change', function() {
        selectedActive = el.activeFilter.value || 'all';
        renderExperts();
      });
    }
  }

  function filteredExperts() {
    var keyword = el.search ? (el.search.value || '').trim() : '';
    var institutionKeyword = el.institutionFilter ? (el.institutionFilter.value || '').trim() : '';
    if (isDefaultProfileQuery(keyword, institutionKeyword)) {
      return quickExperts(selectedRegion);
    }
    var list = sortedExperts(keyword, selectedRegion);
    if (selectedTopic !== 'all') {
      list = list.filter(function(expert) {
        var text = expertSearchBlob(expert);
        return text.indexOf(normalizeText(selectedTopic)) !== -1;
      });
    }
    if (institutionKeyword) {
      var institutionQuery = normalizeText(institutionKeyword);
      list = list.filter(function(expert) {
        return normalizeText([
          expert.affiliation,
          expert.primary_institution,
          (expert.institution_aliases || []).map(function(item) {
            return typeof item === 'string' ? item : item.name || '';
          }).join(' ')
        ].join(' ')).indexOf(institutionQuery) !== -1;
      });
    }
    if (selectedLocation !== 'all') {
      list = list.filter(function(expert) {
        return expertLocationValue(expert) === selectedLocation;
      });
    }
    list = list.filter(matchesProductivityFilter).filter(matchesActiveFilter);
    var exactMatches = exactNameMatches(list, keyword);
    if (exactMatches.length) return exactMatches;
    return list;
  }

  function exactNameMatches(list, keyword) {
    var query = normalizeText(keyword);
    var compactQuery = compactName(keyword);
    if (!query || query.length < 3) return [];
    return list.filter(function(expert) {
      var names = [
        normalizeText(expert.name_en),
        compactName(expert.name_en),
        normalizeText(expert.name_zh)
      ];
      return names.indexOf(query) !== -1 || names.indexOf(compactQuery) !== -1;
    });
  }

  function matchesProductivityFilter(expert) {
    var total = expertMetrics(expert).total_publications || 0;
    if (selectedProductivity === 'ge20') return total >= 20;
    if (selectedProductivity === 'ge10') return total >= 10 && total < 20;
    if (selectedProductivity === 'lt10') return total < 10;
    return true;
  }

  function matchesActiveFilter(expert) {
    var recent = expertMetrics(expert).recent_3y_publications || 0;
    if (selectedActive === 'ge10') return recent >= 10;
    if (selectedActive === 'ge5') return recent >= 5 && recent < 10;
    if (selectedActive === 'lt5') return recent < 5;
    return true;
  }

  function renderExperts() {
    if (needsInternationalExperts(selectedRegion) && !internationalExpertsLoaded) {
      if (el.expertCount) el.expertCount.textContent = expertPool.length;
      if (el.expertResultMeta) el.expertResultMeta.textContent = internationalExpertsLoading ? '正在加载国际作者索引...' : '国际作者索引按需加载';
      el.expertList.innerHTML = '<div class="empty-state"><h3>正在加载专家索引</h3><p>国际作者索引按需加载，稍后自动刷新结果。</p></div>';
      el.expertDetail.innerHTML = '<div class="empty-state"><h3>等待索引加载</h3></div>';
      loadInternationalExperts(renderAfterExpertLoad);
      return;
    }
    var keyword = el.search ? (el.search.value || '').trim() : '';
    var institutionKeyword = el.institutionFilter ? (el.institutionFilter.value || '').trim() : '';
    var defaultMode = isDefaultProfileQuery(keyword, institutionKeyword);
    var list = filteredExperts();
    el.expertCount.textContent = list.length;
    if (!list.length) {
      el.expertList.innerHTML = '<div class="empty-state"><h3>暂无匹配专家</h3></div>';
      el.expertDetail.innerHTML = '<div class="empty-state"><h3>暂无专家数据</h3></div>';
      if (el.expertResultMeta) el.expertResultMeta.textContent = '无匹配结果';
      return;
    }
    if (!selectedProfileExpertId) selectedProfileExpertId = list[0].id;
    if (!list.some(function(item) { return item.id === selectedProfileExpertId; })) selectedProfileExpertId = list[0].id;
    var visibleList = list.slice(0, expertResultLimit);
    el.expertList.innerHTML = visibleList.map(renderExpertRow).join('');
    if (el.expertResultMeta) {
      el.expertResultMeta.textContent = defaultMode
        ? '快速候选 ' + visibleList.length + ' 位 · 搜索可查全部'
        : list.length > visibleList.length
        ? '显示前 ' + visibleList.length + ' / 共 ' + list.length + ' 位'
        : '共 ' + list.length + ' 位';
    }
    var cards = el.expertList.querySelectorAll('.expert-row');
    for (var i = 0; i < cards.length; i++) {
      cards[i].addEventListener('click', function() {
        selectedProfileExpertId = this.getAttribute('data-expert-id');
        selectedVisitExpertId = selectedProfileExpertId;
        renderExperts();
        renderVisitExpertMatches();
        renderSelectedExpertLine();
        renderBriefPreview();
      });
    }
    renderExpertDetail();
  }

  function renderExpertRow(expert) {
    var metrics = expertMetrics(expert);
    var status = identityStatus(expert);
    var tags = expertTags(expert).slice(0, 3).map(function(tag) {
      return '<span class="mini-chip">' + escapeHtml(tag) + '</span>';
    }).join('');
    var location = expertLocationText(expert);
    return '<article class="expert-row ' + (expert.id === selectedProfileExpertId ? 'active' : '') + '" data-expert-id="' + escapeHtml(expert.id) + '">' +
      '<div class="expert-row-head"><strong>' + escapeHtml(displayName(expert)) + '</strong><span class="expert-row-badges"><span class="identity-badge ' + status.className + '">' + escapeHtml(status.label) + '</span></span></div>' +
      '<div>' + escapeHtml(expert.affiliation || '机构待识别') + '</div>' +
      '<div class="metric-line">发文 ' + (metrics.total_publications || 0) + ' · 近3年 ' + (metrics.recent_3y_publications || 0) + (location ? ' · ' + escapeHtml(location) : '') + '</div>' +
      '<div class="chip-row">' + tags + '</div>' +
    '</article>';
  }

  function getSelectedProfileExpert() {
    return findExpertById(selectedProfileExpertId) || expertPool[0] || profiles[0];
  }

  function getSelectedVisitExpert() {
    return findExpertById(selectedVisitExpertId) || sortedVisitExperts('')[0] || expertPool[0] || profiles[0];
  }

  function renderExpertDetail() {
    var expert = getSelectedProfileExpert();
    if (!expert) {
      el.expertDetail.innerHTML = '<div class="empty-state"><h3>暂无专家数据</h3></div>';
      return;
    }
    var metrics = expertMetrics(expert);
    var status = identityStatus(expert);
    var location = expertLocationText(expert);
    var interests = namedCountItems(expert.interests, 'term').slice(0, 8).map(function(item) {
      var width = Math.min(100, Math.max(12, item.count * 8));
      return '<div class="interest-bar"><span>' + escapeHtml(item.term) + '</span><div><i style="width:' + width + '%"></i></div><strong>' + item.count + '</strong></div>';
    }).join('');
    var timeline = expertTimeline(expert).slice(0, 6).map(function(item) {
      return '<li><a href="' + escapeHref(item.url) + '" target="_blank" rel="noopener">' + escapeHtml(item.title) + '</a><span>' + escapeHtml(item.pub_date || item.entry_date || '') + ' · PMID ' + escapeHtml(item.pmid) + '</span></li>';
    }).join('');
    var collaborators = (expert.collaborators || []).slice(0, 6).map(function(item) {
      return '<span class="mini-chip">' + escapeHtml(item.name) + ' ' + item.count + '</span>';
    }).join('');
    var journals = namedCountItems(expert.top_journals, 'name').slice(0, 4).map(function(item) {
      return '<span class="mini-chip">' + escapeHtml(item.name) + ' ' + item.count + '</span>';
    }).join('');
    var compactNote = '<div class="identity-note foreign"><strong>PubMed 作者-机构画像</strong><span>该模板来自全量轻量索引，展示公开发文聚合摘要；后台保留更完整的作者、机构和归一化索引。</span></div>';
    el.expertDetail.innerHTML =
      '<div class="detail-title">' +
        '<h2>' + escapeHtml(displayName(expert)) + '</h2>' +
        '<p>' + escapeHtml(expert.affiliation || '机构待识别') + '</p>' +
        (location ? '<p>' + escapeHtml(location) + '</p>' : '') +
      '</div>' +
      '<div class="identity-note ' + status.className + '"><strong>' + escapeHtml(status.label) + '</strong><span>' + escapeHtml(status.note) + '</span></div>' +
      compactNote +
      '<div class="metric-grid">' +
        '<div><span>总发文</span><strong>' + (metrics.total_publications || 0) + '</strong></div>' +
        '<div><span>近3年</span><strong>' + (metrics.recent_3y_publications || 0) + '</strong></div>' +
        '<div><span>最高IF</span><strong>' + (metrics.highest_if || 0) + '</strong></div>' +
        '<div><span>期刊数</span><strong>' + (metrics.journal_count || 0) + '</strong></div>' +
      '</div>' +
      '<h3>研究兴趣向量</h3>' + (interests || '<div class="muted">暂无主题</div>') +
      '<h3>主要期刊</h3><div class="chip-row">' + (journals || '<span class="muted">暂无数据</span>') + '</div>' +
      '<h3>主要合作者</h3><div class="chip-row">' + (collaborators || '<span class="muted">暂无数据</span>') + '</div>' +
      '<h3>近期文献时间线</h3>' + (timeline ? '<ol class="timeline-list">' + timeline + '</ol>' : '<div class="muted">暂无近期文献</div>');
  }

  function renderVisitExpertMatches() {
    var query = (el.visitSearch.value || '').trim();
    if (query && !internationalExpertsLoaded) {
      if (el.visitMeta) el.visitMeta.textContent = '正在加载国际作者索引，以便搜索全部作者。';
      el.visitChinaMatches.innerHTML = '<div class="empty-state small"><h3>正在加载专家索引</h3><p>加载完成后会自动刷新搜索结果。</p></div>';
      loadInternationalExperts(renderVisitExpertMatches);
      return;
    }
    var matches = sortedVisitExperts(query);
    var visitExperts = matches.slice(0, 10);
    var totalExperts = expertPool.length;
    var note = query
      ? '搜索结果 ' + matches.length + ' 位，显示前 ' + visitExperts.length + ' 位；点击专家卡片后才会切换右侧建议。'
      : '快速候选：按近 3 年活跃度展示前 10 位作者；可输入姓名、拼音、机构、国家或研究方向搜索全部 ' + totalExperts + ' 位作者画像。';
    if (el.visitMeta) el.visitMeta.textContent = note;
    el.visitChinaMatches.innerHTML =
      '<div class="visit-result-note">' + escapeHtml(note) + '</div>' +
      (visitExperts.map(renderVisitExpertCard).join('') || '<div class="empty-state small"><h3>暂无专家匹配</h3><p>请尝试姓名拼音、英文名、机构或国家关键词。</p></div>');
    bindVisitExpertCards();
    renderSelectedExpertLine();
    renderBriefPreview();
  }

  function sortedVisitExperts(query) {
    var normalizedQuery = normalizeText(query);
    if (!normalizedQuery) {
      var region = selectedRegion === 'international' ? 'international' : selectedRegion === 'all' ? 'all' : 'china';
      return quickExperts(region);
    }
    return expertPool.filter(function(expert) {
      return expertScore(expert, query) >= 0;
    }).sort(function(a, b) {
      var metricsA = expertMetrics(a);
      var metricsB = expertMetrics(b);
      var totalDiff = (metricsB.total_publications || 0) - (metricsA.total_publications || 0);
      if (totalDiff) return totalDiff;
      return (metricsB.recent_3y_publications || 0) - (metricsA.recent_3y_publications || 0);
    });
  }

  function renderVisitExpertCard(expert) {
    var metrics = expertMetrics(expert);
    var status = identityStatus(expert);
    var active = expert.id === selectedVisitExpertId ? ' active' : '';
    var action = active ? '已选择' : '点击选择';
    var location = expertLocationText(expert);
    var tags = expertTags(expert).slice(0, 3).map(function(tag) {
      return '<span class="mini-chip">' + escapeHtml(tag) + '</span>';
    }).join('');
    return '<button class="visit-expert-card' + active + '" type="button" data-expert-id="' + escapeHtml(expert.id) + '" aria-pressed="' + (active ? 'true' : 'false') + '">' +
      '<span class="visit-expert-top"><strong>' + escapeHtml(displayName(expert)) + '</strong><span class="visit-card-badges"><em class="identity-badge ' + status.className + '">' + escapeHtml(status.label) + '</em><em class="visit-card-action">' + escapeHtml(action) + '</em></span></span>' +
      '<span>' + escapeHtml(expert.affiliation || '机构待识别') + '</span>' +
      '<span class="visit-expert-meta">发文 ' + (metrics.total_publications || 0) + ' · 近3年 ' + (metrics.recent_3y_publications || 0) + (location ? ' · ' + escapeHtml(location) : '') + '</span>' +
      '<span class="chip-row">' + tags + '</span>' +
    '</button>';
  }

  function bindVisitExpertCards() {
    var cards = document.querySelectorAll('.visit-expert-card');
    for (var i = 0; i < cards.length; i++) {
      cards[i].addEventListener('click', function() {
        selectedVisitExpertId = this.getAttribute('data-expert-id');
        renderVisitExpertMatches();
        renderExperts();
        renderBriefPreview();
      });
    }
  }

  function renderSelectedExpertLine() {
    var expert = getSelectedVisitExpert();
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
      var active = checked ? ' selected' : '';
      var categoryClass = module.category === '纯学术探讨' ? ' academic' : ' product';
      var state = checked ? '已纳入' : '点击纳入';
      var claims = (module.claims || []).slice(0, 2).map(function(claim) {
        return '<li>' + escapeHtml(claim.text) + '<span>PMID ' + escapeHtml(claim.pmid || '-') + ' · ' + escapeHtml(claim.evidence_level || '未分类') + '</span></li>';
      }).join('');
      return '<label class="module-card compact visit-module-card' + active + '" data-module-id="' + escapeHtml(module.id) + '">' +
        '<span class="module-check"><input type="checkbox" value="' + escapeHtml(module.id) + '" ' + checked + '> <span><strong>' + escapeHtml(module.title) + '</strong><small>' + escapeHtml(module.type) + '</small></span><em>' + escapeHtml(state) + '</em></span>' +
        '<div class="module-meta"><span class="module-category' + categoryClass + '">' + escapeHtml(module.category || '内容模块') + '</span><span>更新 ' + escapeHtml(module.updated_at || '-') + '</span></div>' +
        '<p class="module-purpose">' + escapeHtml(module.purpose || module.summary || '') + '</p>' +
        '<p class="module-boundary">边界：' + escapeHtml(module.boundary || '正式使用前需核对原文。') + '</p>' +
        '<ul>' + claims + '</ul>' +
      '</label>';
    }).join('');
    var inputs = el.moduleList.querySelectorAll('input[type="checkbox"]');
    for (var i = 0; i < inputs.length; i++) {
      inputs[i].addEventListener('change', function() {
        selectedModuleIds = Array.from(el.moduleList.querySelectorAll('input[type="checkbox"]:checked')).map(function(input) {
          return input.value;
        });
        renderModulePicker();
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
      ? '<span>' + selected.length + ' 个模块已纳入话题建议；纯学术与产品相关内容会分别处理。</span>'
      : '<span>点击上方模块卡片纳入建议；至少选择 1 个模块后，下方会即时生成话题和文献清单。</span>';
  }

  function shortText(value, maxLength) {
    var text = String(value || '').replace(/\s+/g, ' ').trim();
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength - 1) + '…';
  }

  function uniqueItems(values) {
    var seen = {};
    return values.filter(function(value) {
      if (!value || seen[value]) return false;
      seen[value] = true;
      return true;
    });
  }

  function expertInterestItems(expert) {
    return namedCountItems(expert.interests, 'term').filter(function(item) {
      return item && item.term;
    }).sort(function(a, b) {
      return (b.count || 0) - (a.count || 0);
    });
  }

  function expertContext(expert) {
    var metrics = expertMetrics(expert);
    var interests = expertInterestItems(expert);
    var timeline = expertTimeline(expert);
    var collaborators = expert.collaborators || [];
    return {
      topInterest: interests[0] || { term: 'MG 研究', count: 0 },
      secondInterest: interests[1] || null,
      thirdInterest: interests[2] || null,
      recentArticle: timeline[0] || null,
      secondArticle: timeline[1] || null,
      collaborator: collaborators[0] || null,
      metrics: metrics
    };
  }

  function moduleSearchText(module) {
    return normalizeText([
      module.title,
      module.type,
      module.category,
      module.summary,
      module.purpose,
      (module.keywords || []).join(' ')
    ].join(' '));
  }

  function moduleFitScore(module, expert) {
    var text = moduleSearchText(module);
    var score = 0;
    expertInterestItems(expert).slice(0, 8).forEach(function(item, index) {
      var term = normalizeText(item.term);
      if (term && text.indexOf(term) !== -1) score += Math.max(1, 8 - index) + (item.count || 0) / 12;
    });
    expertTags(expert).forEach(function(tag) {
      var term = normalizeText(tag);
      if (term && text.indexOf(term) !== -1) score += 2;
    });
    return score;
  }

  function matchedExpertInterest(module, expert) {
    var text = moduleSearchText(module);
    var matched = expertInterestItems(expert).slice(0, 8).find(function(item) {
      var term = normalizeText(item.term);
      return term && text.indexOf(term) !== -1;
    });
    if (matched) return matched.term;
    return expertTags(expert).find(function(tag) {
      var term = normalizeText(tag);
      return term && text.indexOf(term) !== -1;
    }) || '';
  }

  function rankModulesForExpert(expert, moduleList) {
    return moduleList.slice().sort(function(a, b) {
      return moduleFitScore(b, expert) - moduleFitScore(a, expert);
    });
  }

  function moduleFitReason(module, expert) {
    var matched = matchedExpertInterest(module, expert);
    if (matched) {
      return '与该专家兴趣谱中的“' + matched + '”有连接';
    }
    if (module.category === '纯学术探讨') {
      return '适合作为非产品化开放式探访入口';
    }
    return '适合作为产品相关证据补充入口';
  }

  function relatedSignalsForExpert(expert, moduleList) {
    var weightedKeys = [];
    expertInterestItems(expert).slice(0, 8).forEach(function(item, index) {
      weightedKeys.push({
        key: normalizeText(item.term),
        weight: Math.max(2, 8 - index) + Math.min(4, (item.count || 0) / 12)
      });
    });
    expertTags(expert).forEach(function(tag) {
      weightedKeys.push({ key: normalizeText(tag), weight: 2 });
    });
    (moduleList || []).forEach(function(module) {
      (module.keywords || []).forEach(function(keyword) {
        weightedKeys.push({ key: normalizeText(keyword), weight: module.category === '产品相关' ? 1.8 : 1.3 });
      });
    });
    var recentText = normalizeText(expertTimeline(expert).slice(0, 3).map(function(article) {
      return article.title || '';
    }).join(' '));
    var scored = signals.map(function(signal) {
      var text = normalizeText([
        signal.summary,
        (signal.keywords || []).join(' '),
        (signal.drugs || []).join(' ')
      ].join(' '));
      var hits = weightedKeys.reduce(function(total, item) {
        return total + (item.key && text.indexOf(item.key) !== -1 ? item.weight : 0);
      }, 0);
      if (recentText && text && recentText.indexOf(text.split(' ')[0]) !== -1) hits += 1.5;
      var strengthBonus = signal.strength === '强' ? 3 : signal.strength === '中' ? 2 : 1;
      return { signal: signal, score: hits * 3 + strengthBonus + (signal.score || 0) / 12 };
    }).filter(function(item) {
      return item.score > 2;
    });
    scored.sort(function(a, b) { return b.score - a.score; });
    return scored.slice(0, 4).map(function(item) { return item.signal; });
  }

  function insightSearchText(insight) {
    return normalizeText([
      insight.title,
      insight.change_type || insight.type,
      insight.selection_reason,
      insight.what_is_new,
      insight.msl_action,
      (insight.community_titles || []).join(' '),
      (insight.knowledge_nodes || []).map(function(node) { return node.title || node.id || ''; }).join(' ')
    ].join(' '));
  }

  function relatedLandscapeInsightsForExpert(expert, moduleList) {
    if (!landscapeInsights.length) return [];
    var weightedKeys = [];
    expertInterestItems(expert).slice(0, 8).forEach(function(item, index) {
      weightedKeys.push({
        key: normalizeText(item.term),
        weight: Math.max(2, 8 - index) + Math.min(4, (item.count || 0) / 12)
      });
    });
    expertTags(expert).forEach(function(tag) {
      weightedKeys.push({ key: normalizeText(tag), weight: 2 });
    });
    (moduleList || []).forEach(function(module) {
      (module.keywords || []).forEach(function(keyword) {
        weightedKeys.push({ key: normalizeText(keyword), weight: 1.5 });
      });
    });
    var scored = landscapeInsights.map(function(insight, index) {
      var text = insightSearchText(insight);
      var hits = weightedKeys.reduce(function(total, item) {
        return total + (item.key && text.indexOf(item.key) !== -1 ? item.weight : 0);
      }, 0);
      var confidenceBonus = insight.confidence === 'high' ? 4 : insight.confidence === 'medium' ? 2 : 0;
      var evidence = insight.evidence_summary || {};
      return {
        insight: insight,
        score: hits * 3 + confidenceBonus + (Number(evidence.high_evidence_count || 0) * 1.8) + Math.max(0, 6 - index) * 0.2
      };
    });
    scored.sort(function(a, b) { return b.score - a.score; });
    return scored.slice(0, 3).map(function(item) { return item.insight; });
  }

  function renderLandscapeActions() {
    if (!el.landscapeActionList) return;
    var items = landscapeInsights.slice(0, 3);
    if (el.landscapeActionMeta) {
      el.landscapeActionMeta.textContent = landscapeInsights.length ?
        '动态洞察 ' + landscapeInsights.length + ' 条 · 高置信 ' + (landscapeInsightSummary.high_confidence_count || 0) + ' 条' :
        '等待 landscapeInsights.js';
    }
    if (!items.length) {
      el.landscapeActionList.innerHTML = '<div class="visit-result-note">暂无动态诊治格局洞察；拜访助手将回退到近期信号和内容模块。</div>';
      return;
    }
    el.landscapeActionList.innerHTML = items.map(function(insight) {
      var refs = (insight.references || []).slice(0, 2).map(function(ref) {
        return ref.pmid ? '<a class="pmid-chip" href="' + escapeHref(ref.url || ('https://pubmed.ncbi.nlm.nih.gov/' + ref.pmid + '/')) + '" target="_blank" rel="noopener">PMID ' + escapeHtml(ref.pmid) + '</a>' : '';
      }).join('');
      return '<article class="landscape-action-card">' +
        '<span>' + escapeHtml(insight.change_type || insight.type || '格局洞察') + '</span>' +
        '<strong>' + escapeHtml(insight.title || '') + '</strong>' +
        '<p>' + escapeHtml(insight.msl_action || '') + '</p>' +
        '<div class="pmid-row">' + refs + '</div>' +
      '</article>';
    }).join('');
  }

  function articleKey(article) {
    return article && article.pmid ? 'pmid:' + article.pmid : 'title:' + normalizeText(article && article.title);
  }

  function collectReferences(expert, moduleList, signalList, insightList) {
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
    expertTimeline(expert).slice(0, 4).forEach(function(article) { add(article, '专家近期发文'); });
    signalList.forEach(function(signal) { add(signal.article, '近期信号'); });
    (insightList || []).forEach(function(insight) {
      (insight.references || []).slice(0, 4).forEach(function(article) { add(article, '动态格局洞察'); });
    });
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
    var expert = getSelectedVisitExpert();
    var selected = selectedModules();
    if (!expert || !selected.length) {
      el.visitBrief.innerHTML =
        '<div class="empty-state">' +
          '<h3>选择专家和内容模块后生成建议</h3>' +
          '<p>左侧选择 1 位专家，并勾选至少 1 个学术或产品模块；右侧会即时生成拜访话题和对应文献清单。</p>' +
        '</div>';
      return;
    }
    generateBrief();
  }

  function generateBrief() {
    var expert = getSelectedVisitExpert();
    var selected = selectedModules();
    if (!expert) return;
    var expertTopics = expertTags(expert).slice(0, 4);
    var moduleTypes = selected.map(function(module) { return (module.category || '内容') + ' / ' + module.type; });
    var signalList = relatedSignalsForExpert(expert, selected);
    if (!signalList.length) signalList = signals.slice(0, 3);
    var insightList = relatedLandscapeInsightsForExpert(expert, selected);
    var references = collectReferences(expert, selected, signalList, insightList);
    var profileCues = buildProfileCues(expert);
    var openingTopics = buildOpeningTopics(expert, selected, signalList, insightList);
    var bridgeItems = buildBridgeItems(expert, selected);
    var questions = buildQuestions(expert, selected, signalList, insightList);

    el.visitBrief.innerHTML =
      '<div class="brief-section">' +
        '<h3>' + escapeHtml(displayName(expert)) + ' · 拜访话题建议</h3>' +
        '<p><strong>研究兴趣：</strong>' + escapeHtml(expertTopics.join('、') || 'MG 研究') + '</p>' +
        '<p><strong>本次内容：</strong>' + escapeHtml(moduleTypes.join('、') || '未选择内容模块') + '</p>' +
      '</div>' +
      '<div class="brief-section">' +
        '<h4>个体化依据</h4>' +
        '<ul>' + profileCues.map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') + '</ul>' +
      '</div>' +
      '<div class="brief-section">' +
        '<h4>建议切入点</h4>' +
        '<ol>' + openingTopics.map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') + '</ol>' +
      '</div>' +
      '<div class="brief-section">' +
        '<h4>内容模块接入</h4>' +
        '<ul>' + bridgeItems.map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') + '</ul>' +
      '</div>' +
      '<div class="brief-section">' +
        '<h4>可追问问题</h4>' +
        '<ul>' + questions.map(function(item) { return '<li>' + escapeHtml(item) + '</li>'; }).join('') + '</ul>' +
      '</div>' +
      (insightList.length ? '<div class="brief-section">' +
        '<h4>本月格局行动</h4>' +
        '<ul>' + insightList.map(function(insight) {
          return '<li>' + escapeHtml((insight.change_type || insight.type || '格局') + ' · ' + insight.title + '：' + (insight.msl_action || '准备对应 PMID 和限制说明。')) + '</li>';
        }).join('') + '</ul>' +
      '</div>' : '') +
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

  function buildProfileCues(expert) {
    var ctx = expertContext(expert);
    var cues = [
      '发文结构：总发文 ' + (ctx.metrics.total_publications || 0) + ' 篇，近 3 年 ' + (ctx.metrics.recent_3y_publications || 0) + ' 篇；最高频兴趣为“' + ctx.topInterest.term + '”（' + (ctx.topInterest.count || 0) + ' 次）。'
    ];
    if (ctx.secondInterest) {
      cues.push('兴趣组合：' + ctx.topInterest.term + ' + ' + ctx.secondInterest.term + '，适合先做问题探访，再决定是否进入具体产品证据。');
    }
    if (ctx.recentArticle) {
      cues.push('近期证据锚点：' + shortText(ctx.recentArticle.title, 92) + '（PMID ' + (ctx.recentArticle.pmid || '-') + '）。');
    }
    if (ctx.collaborator) {
      cues.push('合作网络：与 ' + ctx.collaborator.name + ' 等共同发文较多，可追问该团队正在形成的研究问题。');
    }
    return cues.slice(0, 4);
  }

  function buildOpeningTopics(expert, selected, signalList, insightList) {
    var ctx = expertContext(expert);
    var rankedModules = rankModulesForExpert(expert, selected);
    var practiceFrame = isChinaExpert(expert) ? '本土患者和本中心实践' : '目标患者和所在中心实践';
    var topics = [];
    if (ctx.recentArticle) {
      topics.push('从其近期文章“' + shortText(ctx.recentArticle.title, 78) + '”切入，先询问该研究背后的临床问题是否仍是当前团队优先级。');
    }
    if (ctx.topInterest && ctx.secondInterest) {
      topics.push('围绕“' + ctx.topInterest.term + ' / ' + ctx.secondInterest.term + '”这组高频兴趣，确认专家更希望讨论机制解释、患者选择还是实践路径。');
    }
    if (rankedModules[0]) {
      topics.push('把“' + rankedModules[0].title + '”作为本次主线：' + moduleFitReason(rankedModules[0], expert) + '，先界定讨论边界再进入文献。');
    }
    if (signalList[0]) {
      topics.push('结合近期信号“' + shortText(signalList[0].summary, 82) + '”，追问其对' + practiceFrame + '的可转化性判断。');
    }
    if ((insightList || [])[0]) {
      topics.push('连接本月格局洞察“' + shortText(insightList[0].title, 76) + '”，请专家判断其是否会改变' + practiceFrame + '中的治疗路径或证据需求。');
    }
    topics.push('最后收束到下一次沟通需要补充的证据类型：机制、真实世界、安全性管理、特殊人群或治疗格局。');
    return topics.slice(0, 4);
  }

  function buildBridgeItems(expert, selected) {
    if (!selected.length) return ['暂未选择内容模块，可先围绕专家兴趣和近期信号做开放式探访。'];
    return rankModulesForExpert(expert, selected).slice(0, 6).map(function(module) {
      var claim = (module.claims || [])[0];
      var anchor = claim && claim.pmid ? 'PMID ' + claim.pmid : 'PMID 待补';
      var prefix = module.category === '纯学术探讨' ? '学术入口' : '产品相关';
      return prefix + '｜' + module.title + '：' + moduleFitReason(module, expert) + '。以 ' + anchor + ' 作为证据锚点；边界是“' + (module.boundary || '正式使用前核对原文') + '”。';
    });
  }

  function buildQuestions(expert, selected, signalList, insightList) {
    var ctx = expertContext(expert);
    var top = ctx.topInterest.term;
    var second = ctx.secondInterest ? ctx.secondInterest.term : '临床实践';
    var questions = [];
    if (top === '真实世界') {
      questions.push('您近期真实世界相关发文较多，目前最想补齐的是患者选择、疗程管理、结局指标，还是本土多中心数据？');
    } else if (top === '机制') {
      questions.push('围绕机制研究，您更希望看到抗体功能、补体/FcRn 通路，还是免疫细胞谱系变化与临床应答的连接？');
    } else if (top === '安全性') {
      questions.push('在安全性讨论中，您最关注感染、IgG 变化、合并用药，还是长期随访中的风险识别？');
    } else if (top === '抗体分型') {
      questions.push('抗体分型相关证据中，您认为哪些指标最可能影响治疗路径或患者分层？');
    } else {
      questions.push('您在“' + top + '”方向最希望下一步补充哪类可用于临床讨论的证据？');
    }
    questions.push('如果把“' + top + '”和“' + second + '”合并成一次沟通主线，您会建议先谈未满足需求，还是先谈近期证据？');
    if (selected.some(function(module) { return module.category === '纯学术探讨'; })) {
      questions.push('纯学术部分是否适合作为非产品化开场？哪些表述会更容易引出专家真实观点？');
    }
    if (selected.some(function(module) { return module.id === 'module_product_efg_efficacy'; })) {
      questions.push('关于 efgartigimod 疗效和适用人群，您更希望看到哪类亚组、应答预测或真实世界补充数据？');
    }
    if (selected.some(function(module) { return module.id === 'module_product_efg_safety'; })) {
      questions.push('如果进入用药管理讨论，哪些安全性监测点最值得在材料中提前准备？');
    }
    if (selected.some(function(module) { return module.id === 'module_product_landscape'; })) {
      questions.push('面对 FcRn、补体和其他靶向治疗并行发展，您更认可按机制、患者分层还是证据层级来做定位讨论？');
    }
    if (signalList.length) {
      questions.push('近期信号中哪一类最可能影响您下一阶段的研究或临床讨论重点？');
    }
    if ((insightList || []).length) {
      questions.push('本月动态诊治格局里，哪条洞察最值得转化成下一次专家会或中心内讨论？还需要补哪类证据？');
    }
    return uniqueItems(questions).slice(0, 5);
  }

  function renderReferenceTable(references) {
    if (!references.length) return '<div class="muted">暂无可关联文献</div>';
    return '<div class="msl-reference-table"><table><thead><tr><th>PMID</th><th>文献</th><th>证据</th><th>来源</th></tr></thead><tbody>' +
      references.map(function(ref) {
        var link = ref.url ? '<a href="' + escapeHref(ref.url) + '" target="_blank" rel="noopener">' + escapeHtml(ref.pmid || '-') + '</a>' : escapeHtml(ref.pmid || '-');
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
    var profileExperts = sortedExperts('', selectedRegion);
    var visitExperts = sortedVisitExperts('');
    selectedProfileExpertId = (profileExperts[0] || expertPool[0] || profiles[0] || {}).id || '';
    selectedVisitExpertId = (visitExperts[0] || profileExperts[0] || expertPool[0] || profiles[0] || {}).id || '';
  }

  function updateExpertBadge() {
    if (!el.update) return;
    var summary = expertPayload.summary || {};
    var chinaCount = summary.indexed_china_experts || chinaExpertIndex.length;
    var internationalCount = summary.indexed_international_experts || internationalExpertIndex.length;
    var totalCount = summary.indexed_experts || (chinaCount + internationalCount) || expertPool.length;
    var loadedNote = internationalExpertsLoaded ? '' : ' · 国际按需加载';
    el.update.textContent = '作者索引 ' + totalCount + ' 位 · 中国 ' + chinaCount + ' · 国外 ' + internationalCount + ' · 快捷候选 ' + (quickExpertIds.china || []).length + ' 位' + loadedNote;
  }

  function init() {
    bindTabs();
    initSelectedExpert();
    renderTopicFilters();
    renderExpertFilterOptions();
    bindTopicFilters();
    renderLandscapeActions();
    renderExperts();
    renderVisitExpertMatches();
    renderModulePicker();
    renderSelectedExpertLine();
    if (el.search) el.search.addEventListener('input', debounce(renderExperts, 160));
    if (el.visitSearch) el.visitSearch.addEventListener('input', debounce(renderVisitExpertMatches, 160));
    updateExpertBadge();
    if (el.moduleMeta) {
      var academicCount = modules.filter(function(module) { return module.category === '纯学术探讨'; }).length;
      var productCount = modules.filter(function(module) { return module.category === '产品相关'; }).length;
      el.moduleMeta.textContent = modules.length + ' 个模块：' + academicCount + ' 个纯学术探讨 + ' + productCount + ' 个产品相关；点击卡片纳入建议。';
    }
    renderBriefPreview();
  }

  init();
})();
