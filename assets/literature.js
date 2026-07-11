/* MA-MG-HUB 文献情报页面 JS */
(function() {
  'use strict';

  var hub = window.MgHub || {};
  let allArticles = [];
  let filteredResults = [];
  let signalItems = [];
  let signalFilter = 'all';
  let signalTopicFilter = null;
  let chinaMonthlyChart = null;
  let chinaEvidenceChart = null;
  let chinaQuartileChart = null;
  let communityTaxonomy = window.MG_COMMUNITY_TAXONOMY || { communities: [] };
  let communityAssignmentsById = {};
  let communityAssignmentLoading = {};
  let communityAssignmentCallbacks = {};
  let communityAssignmentErrors = {};
  let articleCommunityByPmid = {};
  let communityOptionById = {};
  let currentPage = 0;
  const PAGE_SIZE = 10;
  const SIGNAL_WINDOW_DAYS = 14;
  var echartsLoading = false;
  var chinaDataLoading = false;
  var echartsCallbacks = [];
  var chinaDataCallbacks = [];
  var chinaInsightsStarted = false;
  var conferenceLoading = false;
  var conferenceStarted = false;
  var conferenceCallbacks = [];

  function loadScript(src, callback) {
    if (hub.loadScript) {
      hub.loadScript(src, callback);
      return;
    }
    var s = document.createElement('script');
    s.src = src;
    s.onload = function() { if (callback) callback(true); };
    s.onerror = function() { if (callback) callback(false); };
    document.head.appendChild(s);
  }

  function loadEcharts(cb) {
    if (typeof echarts !== 'undefined') { cb(true); return; }
    echartsCallbacks.push(cb);
    if (echartsLoading) return;
    echartsLoading = true;
    loadScript('https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js', function () {
      echartsLoading = false;
      var callbacks = echartsCallbacks.slice();
      echartsCallbacks = [];
      var ok = typeof echarts !== 'undefined';
      callbacks.forEach(function(callback) { if (callback) callback(ok); });
    });
  }

  function loadChinaData(cb) {
    if (window.MG_CHINA_DATA) { cb(true); return; }
    chinaDataCallbacks.push(cb);
    if (chinaDataLoading) return;
    chinaDataLoading = true;
    loadScript('data/china-intelligence.js', function (ok) {
      chinaDataLoading = false;
      var callbacks = chinaDataCallbacks.slice();
      chinaDataCallbacks = [];
      callbacks.forEach(function(callback) { if (callback) callback(ok && !!window.MG_CHINA_DATA); });
    });
  }

  function loadConferenceModule(cb) {
    if (conferenceStarted) { if (cb) cb(true); return; }
    conferenceCallbacks.push(cb);
    if (conferenceLoading) return;
    conferenceLoading = true;

    function finish(ok) {
      conferenceLoading = false;
      conferenceStarted = ok;
      var callbacks = conferenceCallbacks.slice();
      conferenceCallbacks = [];
      callbacks.forEach(function(callback) { if (callback) callback(ok); });
    }

    loadScript('data/conference-data.js', function(dataOk) {
      if (!dataOk) { finish(false); return; }
      loadScript('assets/conference.js', finish);
    });
  }

  function ensureChinaInsights() {
    if (chinaInsightsStarted) {
      resizeChinaCharts();
      return;
    }
    chinaInsightsStarted = true;
    renderChinaInsights();
  }

  const $ = id => document.getElementById(id);
  const el = {
    loading: $('loading'),
    results: $('results'),
    filterCount: $('filterCount'),
    filterKeyword: $('filterKeyword'),
    sortMode: $('sortMode'),
    filterTimeList: $('filterTimeList'),
    chinaAll: $('chinaAll'),
    chinaOnly: $('chinaOnly'),
    filterIFList: $('filterIFList'),
    filterQuartileList: $('filterQuartileList'),
    filterEvidenceList: $('filterEvidenceList'),
    filterCommunityList: $('filterCommunityList'),
    communityFilterSummary: $('communityFilterSummary'),
    communityFilterStatus: $('communityFilterStatus'),
    btnExport: $('btnExport'),
    signalSummary: $('signalSummary'),
    signalList: $('signalList'),
    signalKeywords: $('signalKeywords'),
    chinaBadge: $('chinaBadge'),
    chinaSourceList: $('chinaSourceList'),
  };

  function parseDate(dateStr) {
    if (!dateStr) return null;
    var m = dateStr.match(/(\d{4})\/(\d{2})\/(\d{2})/);
    if (m) return new Date(+m[1], +m[2]-1, +m[3]);
    var d = new Date(dateStr);
    return isNaN(d) ? null : d;
  }

  function toNumber(value) {
    var number = Number(value);
    return isNaN(number) ? 0 : number;
  }

  function formatImpactFactor(value) {
    if (value === null || value === undefined || value === '') return '';
    var number = Number(value);
    if (isNaN(number)) return '';
    return number.toFixed(1).replace(/\.0$/, '');
  }

  function evidenceRank(level) {
    return { I: 6, II: 5, III: 4, IV: 3, V: 2 }[level || ''] || 0;
  }

  function articleTimeValue(article) {
    var date = parseDate(article.entry_date);
    return date ? date.getTime() : 0;
  }

  function sortFilteredResults() {
    var mode = el.sortMode ? el.sortMode.value : 'date';
    filteredResults.sort(function(a, b) {
      if (mode === 'if') {
        var ifDiff = toNumber(b.journal_if) - toNumber(a.journal_if);
        if (ifDiff !== 0) return ifDiff;
        var ifEvidenceDiff = evidenceRank(b.evidence_level) - evidenceRank(a.evidence_level);
        if (ifEvidenceDiff !== 0) return ifEvidenceDiff;
      }
      if (mode === 'evidence') {
        var evidenceDiff = evidenceRank(b.evidence_level) - evidenceRank(a.evidence_level);
        if (evidenceDiff !== 0) return evidenceDiff;
        var evidenceIfDiff = toNumber(b.journal_if) - toNumber(a.journal_if);
        if (evidenceIfDiff !== 0) return evidenceIfDiff;
      }
      return articleTimeValue(b) - articleTimeValue(a);
    });
  }

  function getSelectedMonths() {
    var cbs = el.filterTimeList.querySelectorAll('input[type="checkbox"]');
    var checked = [];
    for (var i = 0; i < cbs.length; i++) {
      if (cbs[i].checked) checked.push(cbs[i].value);
    }
    return checked;
  }

  function getCheckedValues(container) {
    var cbs = container.querySelectorAll('input[type="checkbox"]');
    var vals = [];
    for (var i = 0; i < cbs.length; i++) {
      if (cbs[i].checked && cbs[i].value !== 'all') vals.push(cbs[i].value);
    }
    var allCb = container.querySelector('input[value="all"]');
    return { values: vals, isAll: allCb ? allCb.checked : false };
  }

  function normalizePmid(value) {
    return String(value || '').trim();
  }

  function getCommunityTitle(communityId) {
    var item = communityOptionById[communityId] || {};
    return item.title || communityId;
  }

  function getInitialCommunityIds() {
    var requested = [];
    try {
      var params = new URLSearchParams(window.location.search || '');
      var value = params.get('community') || '';
      requested = value.split(',').map(function(item) { return item.trim(); }).filter(Boolean);
    } catch (err) {
      requested = [];
    }
    return requested.filter(function(communityId) { return !!communityOptionById[communityId]; });
  }

  function getSelectedCommunityIds() {
    if (!el.filterCommunityList) return [];
    var allCb = el.filterCommunityList.querySelector('input[value="all"]');
    if (allCb && allCb.checked) return [];
    var checked = el.filterCommunityList.querySelectorAll('input[type="checkbox"]:checked:not([value="all"])');
    var ids = [];
    for (var i = 0; i < checked.length; i++) ids.push(checked[i].value);
    return ids;
  }

  function updateCommunityFilterSummary() {
    if (!el.communityFilterSummary) return;
    var ids = getSelectedCommunityIds();
    if (!ids.length) {
      el.communityFilterSummary.textContent = '全部社区';
      return;
    }
    if (ids.length === 1) {
      el.communityFilterSummary.textContent = getCommunityTitle(ids[0]);
      return;
    }
    el.communityFilterSummary.textContent = ids.length + ' 个社区';
  }

  function updateCommunityFilterStatus(selectedIds, resultCount) {
    if (!el.communityFilterStatus) return;
    var ids = selectedIds || getSelectedCommunityIds();
    if (!ids.length) {
      el.communityFilterStatus.textContent = '按需加载社区分片，不增加首屏负担。';
      return;
    }
    var loading = [];
    var failed = [];
    for (var i = 0; i < ids.length; i++) {
      if (communityAssignmentLoading[ids[i]]) loading.push(getCommunityTitle(ids[i]));
      if (communityAssignmentErrors[ids[i]]) failed.push(getCommunityTitle(ids[i]));
    }
    if (loading.length) {
      el.communityFilterStatus.textContent = '正在加载：' + loading.join('、');
      return;
    }
    if (failed.length) {
      el.communityFilterStatus.textContent = '部分社区分片加载失败：' + failed.join('、');
      return;
    }
    var text = '已加载 ' + ids.length + ' 个社区分片，按 primary community 筛选';
    if (typeof resultCount === 'number') text += ' · 当前 ' + resultCount + ' 篇';
    el.communityFilterStatus.textContent = text;
  }

  function buildCommunityAssignmentCache(communityId, payload) {
    var items = payload && Array.isArray(payload.items) ? payload.items : [];
    var pmids = new Set();
    for (var i = 0; i < items.length; i++) {
      var item = items[i] || {};
      var pmid = normalizePmid(item.pmid);
      if (!pmid) continue;
      pmids.add(pmid);
      articleCommunityByPmid[pmid] = item;
    }
    communityAssignmentsById[communityId] = {
      pmids: pmids,
      items: items
    };
  }

  function loadCommunityAssignments(communityId, callback) {
    if (!communityOptionById[communityId]) {
      if (callback) callback(false);
      return;
    }
    if (communityAssignmentsById[communityId]) {
      if (callback) callback(true);
      return;
    }
    if (communityAssignmentLoading[communityId]) {
      communityAssignmentCallbacks[communityId].push(callback);
      return;
    }

    communityAssignmentLoading[communityId] = true;
    communityAssignmentCallbacks[communityId] = [callback];
    updateCommunityFilterStatus();
    loadScript('data/communityAssignments-' + encodeURIComponent(communityId) + '.js', function(ok) {
      var shards = window.MG_COMMUNITY_ASSIGNMENT_SHARDS || {};
      var payload = shards[communityId];
      if (ok && payload) {
        buildCommunityAssignmentCache(communityId, payload);
        delete communityAssignmentErrors[communityId];
      } else {
        communityAssignmentErrors[communityId] = true;
        buildCommunityAssignmentCache(communityId, { items: [] });
      }
      communityAssignmentLoading[communityId] = false;
      var callbacks = communityAssignmentCallbacks[communityId] || [];
      delete communityAssignmentCallbacks[communityId];
      for (var i = 0; i < callbacks.length; i++) {
        if (callbacks[i]) callbacks[i](ok && !!payload);
      }
      updateCommunityFilterStatus();
    });
  }

  function areCommunityAssignmentsReady(communityIds) {
    for (var i = 0; i < communityIds.length; i++) {
      if (!communityAssignmentsById[communityIds[i]]) return false;
    }
    return true;
  }

  function ensureSelectedCommunityAssignments(communityIds, callback) {
    var pending = [];
    for (var i = 0; i < communityIds.length; i++) {
      if (!communityAssignmentsById[communityIds[i]]) pending.push(communityIds[i]);
    }
    if (!pending.length) {
      callback();
      return;
    }
    var remaining = pending.length;
    function done() {
      remaining--;
      if (remaining === 0) callback();
    }
    for (var j = 0; j < pending.length; j++) {
      loadCommunityAssignments(pending[j], done);
    }
  }

  function matchesCommunityFilter(article, communityIds) {
    if (!communityIds.length) return true;
    var pmid = normalizePmid(article.pmid);
    if (!pmid) return false;
    for (var i = 0; i < communityIds.length; i++) {
      var assignment = communityAssignmentsById[communityIds[i]];
      if (assignment && assignment.pmids.has(pmid)) return true;
    }
    return false;
  }

  function renderArticleCommunityBadge(article) {
    var selectedIds = getSelectedCommunityIds();
    if (!selectedIds.length) return '';
    var assignment = articleCommunityByPmid[normalizePmid(article.pmid)];
    if (!assignment || selectedIds.indexOf(assignment.primary) === -1) return '';
    return '<span class="badge-community">社区 ' + escapeHtml(getCommunityTitle(assignment.primary)) + '</span>';
  }

  function populateCommunityFilters() {
    if (!el.filterCommunityList) return;
    var communities = communityTaxonomy.communities || [];
    communityOptionById = {};
    for (var i = 0; i < communities.length; i++) {
      communityOptionById[communities[i].id] = communities[i];
    }
    if (!communities.length) {
      el.filterCommunityList.innerHTML = '<div class="filter-hint">社区 taxonomy 尚未生成。</div>';
      updateCommunityFilterSummary();
      return;
    }

    var initialIds = getInitialCommunityIds();
    var html = '<label class="filter-checkbox-item"><input type="checkbox" value="all"' + (initialIds.length ? '' : ' checked') + '> <span>全部社区</span></label>';
    for (var j = 0; j < communities.length; j++) {
      var community = communities[j];
      var checked = initialIds.indexOf(community.id) !== -1 ? ' checked' : '';
      html += '<label class="filter-checkbox-item"><input type="checkbox" value="' + escapeHtml(community.id) + '"' + checked + '> <span>' + escapeHtml(community.title || community.id) + '</span></label>';
    }
    el.filterCommunityList.innerHTML = html;
    el.filterCommunityList.addEventListener('change', function(event) {
      var cb = event.target;
      if (!cb || cb.type !== 'checkbox') return;
      var allCb = el.filterCommunityList.querySelector('input[value="all"]');
      var others = el.filterCommunityList.querySelectorAll('input[type="checkbox"]:not([value="all"])');
      if (cb.value === 'all') {
        if (cb.checked) {
          for (var k = 0; k < others.length; k++) others[k].checked = false;
        } else {
          var anySelected = false;
          for (var m = 0; m < others.length; m++) {
            if (others[m].checked) { anySelected = true; break; }
          }
          if (!anySelected) cb.checked = true;
        }
      } else {
        if (cb.checked && allCb) allCb.checked = false;
        var hasSelected = false;
        for (var x = 0; x < others.length; x++) {
          if (others[x].checked) { hasSelected = true; break; }
        }
        if (!hasSelected && allCb) allCb.checked = true;
      }
      updateCommunityFilterSummary();
      applyFilters();
    });
    updateCommunityFilterSummary();
  }

  // checkbox 全选联动（通用）
  function wireCheckboxAll(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    container.addEventListener('change', function(e) {
      var cb = e.target;
      if (!cb || cb.type !== 'checkbox') return;
      var allCb = container.querySelector('input[value="all"]');
      var others = container.querySelectorAll('input[type="checkbox"]:not([value="all"])');
      if (cb.value === 'all') {
        for (var k = 0; k < others.length; k++) others[k].checked = cb.checked;
      } else {
        // 检查是否所有非all都被选中
        var allChecked = true;
        for (var k = 0; k < others.length; k++) {
          if (!others[k].checked) { allChecked = false; break; }
        }
        if (allCb) allCb.checked = allChecked;
        // 如果取消了全部，至少有一个勾着就行
      }
      applyFilters();
    });
  }

  function populateMonths(articles) {
    var ymSet = {};
    for (var i = 0; i < articles.length; i++) {
      var ed = articles[i].entry_date || '';
      var m = ed.match(/^(\d{4})\/(\d{2})/);
      if (m) ymSet[m[1] + '-' + m[2]] = true;
    }
    var sorted = Object.keys(ymSet).sort().reverse();
    var html = '';
    html += '<label class="filter-checkbox-item"><input type="checkbox" value="all" checked> 全部月份</label>';
    var lastYear = '';
    for (var j = 0; j < sorted.length; j++) {
      var ym = sorted[j], parts = ym.split('-'), y = parts[0], mm = parts[1];
      if (y !== lastYear) {
        html += '<label class="filter-checkbox-item" style="color:var(--fg3);font-size:0.75rem;pointer-events:none">── ' + y + '年 ──</label>';
        lastYear = y;
      }
      html += '<label class="filter-checkbox-item"><input type="checkbox" value="' + ym + '"> ' + y + '/' + parseInt(mm) + ' 月</label>';
    }
    el.filterTimeList.innerHTML = html;

    el.filterTimeList.addEventListener('change', function(e) {
      var cb = e.target;
      if (!cb || cb.type !== 'checkbox') return;
      if (cb.value === 'all') {
        var allCbs = el.filterTimeList.querySelectorAll('input[type="checkbox"]');
        for (var k = 0; k < allCbs.length; k++) {
          if (allCbs[k].value !== 'all') allCbs[k].checked = cb.checked;
        }
      } else {
        var checkedItems = el.filterTimeList.querySelectorAll('input[type="checkbox"]:checked');
        var allCheckbox = el.filterTimeList.querySelector('input[value="all"]');
        if (checkedItems.length === el.filterTimeList.querySelectorAll('input[type="checkbox"]').length - 1) {
          allCheckbox.checked = true;
        } else {
          allCheckbox.checked = false;
        }
      }
      applyFilters();
    });
  }

  function matchesMulti(container, articleValue) {
    var state = getCheckedValues(container);
    if (state.isAll) return true;
    if (state.values.length === 0) return true;
    for (var v = 0; v < state.values.length; v++) {
      if (articleValue === state.values[v]) return true;
    }
    return false;
  }

  function ifRangeMatch(rangeStr, ifVal) {
    if (ifVal === null || ifVal === undefined) return false;
    var parts = rangeStr.split('-').map(Number);
    if (rangeStr === '10') return ifVal >= 10;
    return ifVal >= parts[0] && ifVal < parts[1];
  }

  function applyFilters(resetPage) {
    if (resetPage === undefined) resetPage = true;
    var keyword = (el.filterKeyword.value || '').toLowerCase().trim();
    var selectedCommunityIds = getSelectedCommunityIds();
    if (selectedCommunityIds.length && !areCommunityAssignmentsReady(selectedCommunityIds)) {
      ensureSelectedCommunityAssignments(selectedCommunityIds, function() {
        applyFilters(resetPage);
      });
      return;
    }
    var selectedMonths = getSelectedMonths();
    var chinaVal = el.chinaOnly.checked ? 'china' : 'all';

    var ifState = getCheckedValues(el.filterIFList);
    var quartileState = getCheckedValues(el.filterQuartileList);
    var evState = getCheckedValues(el.filterEvidenceList);

    var allSelected = false;
    for (var s = 0; s < selectedMonths.length; s++) {
      if (selectedMonths[s] === 'all') { allSelected = true; break; }
    }

    function matchesTime(a) {
      if (allSelected || selectedMonths.length === 0) return true;
      var ed = a.entry_date || '';
      var m = ed.match(/^(\d{4})\/(\d{2})/);
      if (!m) return true;
      var ym = m[1] + '-' + m[2];
      for (var t = 0; t < selectedMonths.length; t++) {
        if (selectedMonths[t] === ym) return true;
      }
      return false;
    }

    filteredResults = [];
    for (var i = 0; i < allArticles.length; i++) {
      var a = allArticles[i];

      if (!matchesCommunityFilter(a, selectedCommunityIds)) continue;

      if (keyword) {
        var inTitle = (a.title || '').toLowerCase().indexOf(keyword) !== -1;
        var inAuthors = false;
        var aus = a.authors || [];
        for (var auIdx = 0; auIdx < aus.length; auIdx++) {
          if (aus[auIdx].toLowerCase().indexOf(keyword) !== -1) { inAuthors = true; break; }
        }
        var inJournal = (a.journal || '').toLowerCase().indexOf(keyword) !== -1;
        var inPmid = a.pmid === keyword;
        if (!inTitle && !inAuthors && !inJournal && !inPmid) continue;
      }

      if (!matchesTime(a)) continue;
      if (chinaVal === 'china' && !a.china_related) continue;

      // IF 多选
      if (!ifState.isAll && ifState.values.length > 0) {
        var ifMatch = false;
        for (var vi = 0; vi < ifState.values.length; vi++) {
          if (ifRangeMatch(ifState.values[vi], a.journal_if)) { ifMatch = true; break; }
        }
        if (!ifMatch) continue;
      }

      // 分区多选
      if (!quartileState.isAll && quartileState.values.length > 0) {
        var q = a.journal_quartile;
        var qMatch = false;
        for (var qi = 0; qi < quartileState.values.length; qi++) {
          if (q && String(q).charAt(0) === quartileState.values[qi]) { qMatch = true; break; }
        }
        if (!qMatch) continue;
      }

      // 证据等级多选
      if (!evState.isAll && evState.values.length > 0) {
        var evMatch = false;
        for (var ei = 0; ei < evState.values.length; ei++) {
          if (a.evidence_level === evState.values[ei]) { evMatch = true; break; }
        }
        if (!evMatch) continue;
      }

      filteredResults.push(a);
    }

    sortFilteredResults();
    el.filterCount.textContent = filteredResults.length;
    updateCommunityFilterStatus(selectedCommunityIds, filteredResults.length);
    if (resetPage) currentPage = 0;
    renderResults();
  }

  function renderResults() {
    var articles = filteredResults;
    el.results.innerHTML = '';
    if (articles.length === 0) {
      el.results.innerHTML = '<div class="empty-state"><h3>暂无匹配文献</h3><p>试试调整筛选条件</p></div>';
      return;
    }
    var totalPages = Math.ceil(articles.length / PAGE_SIZE);
    var start = currentPage * PAGE_SIZE;
    var pageArticles = articles.slice(start, start + PAGE_SIZE);

    var fragment = document.createDocumentFragment();
    for (var i = 0; i < pageArticles.length; i++) {
      fragment.appendChild(renderArticle(pageArticles[i]));
    }
    el.results.appendChild(fragment);

    var nav = document.createElement('div');
    nav.className = 'pagination';

    var prevBtn = document.createElement('button');
    prevBtn.className = 'btn';
    prevBtn.textContent = '‹ 上一页';
    prevBtn.disabled = currentPage === 0;
    prevBtn.addEventListener('click', function() { if (currentPage > 0) { currentPage--; renderResults(); window.scrollTo(0,0); } });
    nav.appendChild(prevBtn);

    var pageInfo = document.createElement('span');
    pageInfo.style.cssText = 'font-size:0.85rem;color:var(--fg3)';
    pageInfo.textContent = (currentPage + 1) + ' / ' + totalPages + ' 页 (' + articles.length + ' 篇)';
    nav.appendChild(pageInfo);

    var nextBtn = document.createElement('button');
    nextBtn.className = 'btn';
    nextBtn.textContent = '下一页 ›';
    nextBtn.disabled = currentPage >= totalPages - 1;
    nextBtn.addEventListener('click', function() { if (currentPage < totalPages - 1) { currentPage++; renderResults(); window.scrollTo(0,0); } });
    nav.appendChild(nextBtn);

    el.results.appendChild(nav);
  }

  function renderArticle(article) {
    var entryDate = parseDate(article.entry_date);
    var dateStr = entryDate ? entryDate.toLocaleDateString('zh-CN') : (article.pub_date || '');
    var china = article.china_related;
    var evLevel = article.evidence_level;
    var studyTypes = article.study_types || [];

    var div = document.createElement('div');
    div.className = 'article-card';

    var metaParts = [escapeHtml(article.journal || 'Unknown')];
    if (dateStr) metaParts.push(escapeHtml(dateStr));
    metaParts.push('PMID ' + escapeHtml(article.pmid || '-'));

    var tagsHTML = '';
    if (china) tagsHTML += '<span class="badge-china">🇨🇳 中国</span>';
    if (evLevel) tagsHTML += '<span class="badge-evidence">证据等级 ' + escapeHtml(evLevel) + '</span>';
    else if (studyTypes.length > 0 && studyTypes[0] !== 'Unclassified')
      tagsHTML += '<span class="badge-pending">' + escapeHtml(studyTypes[0]) + '</span>';
    var impactFactor = formatImpactFactor(article.journal_if);
    if (impactFactor) tagsHTML += '<span class="badge-metric">IF ' + impactFactor + '</span>';
    if (article.journal_quartile) tagsHTML += '<span class="badge-metric">CAS ' + escapeHtml(String(article.journal_quartile)) + '</span>';
    tagsHTML += renderArticleCommunityBadge(article);

    var pmidToken = safeIdToken(article.pmid || 'unknown');
    var abstractId = 'abs-' + pmidToken;
    div.innerHTML =
      '<a class="article-card-title" href="' + escapeHref(article.url) + '" target="_blank" rel="noopener">' + escapeHtml(article.title || '(无标题)') + '</a>' +
      '<div class="article-card-meta">' + metaParts.join(' · ') + '</div>' +
      (article.abstract
        ? '<button class="abstract-toggle" data-pmid="' + escapeHtml(normalizePmid(article.pmid)) + '">显示摘要</button>' +
          '<div class="article-card-abstract" id="' + abstractId + '">' + escapeHtml(article.abstract.slice(0, 300)) + (article.abstract.length > 300 ? '…' : '') + '</div>'
        : '') +
      '<div class="article-card-links">' +
        (article.doi ? '<a href="' + doiHref(article.doi) + '" target="_blank" rel="noopener">DOI</a>' : '') +
        tagsHTML +
      '</div>';

    var toggle = div.querySelector('.abstract-toggle');
    if (toggle) {
      (function(targetId, abstract) {
        toggle.addEventListener('click', function() {
          var abs = document.getElementById(targetId);
          if (abs) {
            if (abs.getAttribute('data-fulltext') !== '1') {
              abs.innerHTML = escapeHtml(abstract);
              abs.setAttribute('data-fulltext', '1');
            }
            abs.classList.toggle('open');
            this.textContent = abs.classList.contains('open') ? '收起摘要' : '显示摘要';
          }
        });
      })(abstractId, article.abstract);
    }
    return div;
  }

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

  function safeIdToken(value) {
    return hub.safeIdToken ? hub.safeIdToken(value, 'pmid') : String(value || 'pmid').replace(/[^a-zA-Z0-9_-]+/g, '-');
  }

  function doiHref(doi) {
    var value = String(doi || '').trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, '');
    if (!value) return '#';
    return escapeHref('https://doi.org/' + value);
  }

  function buildArticleMeta(article, dateStr) {
    var meta = [escapeHtml(article.journal || 'Unknown')];
    if (dateStr) meta.push(escapeHtml(dateStr));
    meta.push('PMID ' + escapeHtml(article.pmid || '-'));
    if (article.evidence_level) meta.push('证据等级 ' + escapeHtml(article.evidence_level));
    var impactFactor = formatImpactFactor(article.journal_if);
    if (impactFactor) meta.push('IF ' + escapeHtml(impactFactor));
    if (article.journal_quartile) meta.push('CAS ' + escapeHtml(String(article.journal_quartile)));
    return meta.join(' · ');
  }

  function bindTabs() {
    function handleTabChange(key) {
      if (key === 'china') {
        ensureChinaInsights();
        resizeChinaCharts();
      }
      if (key === 'conference') {
        loadConferenceModule(function(ok) {
          if (!ok) {
            var badge = document.getElementById('conferenceBadge');
            if (badge) badge.textContent = '会议数据加载失败';
          }
        });
      }
      if (el.btnExport) el.btnExport.style.display = key === 'conference' ? 'none' : '';
    }
    if (hub.initTabs) {
      hub.initTabs({
        tabAttr: 'data-tab',
        panelFor: function(key) { return document.getElementById('tab-' + key); },
        onChange: handleTabChange
      });
      return;
    }
    var tabs = document.querySelectorAll('.intel-tab');
    var panels = document.querySelectorAll('.intel-tab-panel');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener('click', function() {
        var key = this.getAttribute('data-tab');
        for (var t = 0; t < tabs.length; t++) tabs[t].classList.remove('active');
        for (var p = 0; p < panels.length; p++) panels[p].classList.remove('active');
        this.classList.add('active');
        var panel = document.getElementById('tab-' + key);
        if (panel) panel.classList.add('active');
        handleTabChange(key);
      });
    }
    var activeTab = document.querySelector('.intel-tab.active');
    handleTabChange(activeTab ? activeTab.getAttribute('data-tab') : 'literature');
  }

  function bindSignalFilters() {
    var btns = document.querySelectorAll('.signal-filter-btn');
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener('click', function() {
        for (var b = 0; b < btns.length; b++) btns[b].classList.remove('active');
        this.classList.add('active');
        signalFilter = this.getAttribute('data-signal-filter') || 'all';
        renderSignals();
      });
    }
  }

  function maxEntryDate(articles) {
    var max = null;
    for (var i = 0; i < articles.length; i++) {
      var d = parseDate(articles[i].entry_date);
      if (d && (!max || d > max)) max = d;
    }
    return max || new Date();
  }

  function rollingCutoffDate(articles, days) {
    var latest = maxEntryDate(articles);
    var cutoff = new Date(latest.getTime());
    cutoff.setDate(cutoff.getDate() - days);
    return cutoff;
  }

  function daysApart(a, b) {
    return Math.floor((a - b) / 86400000);
  }

  function hasAny(text, words) {
    for (var i = 0; i < words.length; i++) {
      if (text.indexOf(words[i]) !== -1) return true;
    }
    return false;
  }

  function inferTopics(article) {
    var text = ((article.title || '') + ' ' + (article.abstract || '')).toLowerCase();
    var defs = [
      { label: 'FcRn', words: ['fcrn', 'efgartigimod', 'rozanolixizumab', 'nipocalimab', 'batoclimab'] },
      { label: '补体', words: ['complement', 'zilucoplan', 'ravulizumab', 'eculizumab', 'c5 inhibitor'] },
      { label: '抗体分型', words: ['seronegative', 'musk', 'achr', 'lrp4', 'autoantibody'] },
      { label: '真实世界', words: ['real-world', 'registry', 'observational', 'retrospective'] },
      { label: '安全性', words: ['safety', 'adverse', 'infection', 'tolerability'] },
      { label: '疗效', words: ['efficacy', 'outcome', 'improvement', 'response'] },
      { label: '机制', words: ['pathogenesis', 'mechanism', 'biomarker', 'cytokine', 'b cell', 't cell'] },
      { label: '诊疗策略', words: ['guideline', 'consensus', 'recommendation', 'treatment strategy'] }
    ];
    var topics = [];
    for (var i = 0; i < defs.length; i++) {
      if (hasAny(text, defs[i].words)) topics.push(defs[i].label);
    }
    if (topics.length === 0 && article.study_types && article.study_types.length) {
      topics.push(article.study_types[0]);
    }
    return topics.slice(0, 4);
  }

  var DRUG_NAMES = [
    { name: 'efgartigimod', words: ['efgartigimod', 'vyvgart'] },
    { name: 'rozanolixizumab', words: ['rozanolixizumab'] },
    { name: 'ravulizumab', words: ['ravulizumab'] },
    { name: 'eculizumab', words: ['eculizumab'] },
    { name: 'zilucoplan', words: ['zilucoplan'] },
    { name: 'nipocalimab', words: ['nipocalimab'] },
    { name: 'batoclimab', words: ['batoclimab'] },
    { name: 'rituximab', words: ['rituximab'] }
  ];

  function matchDrugs(text) {
    var drugs = [];
    for (var i = 0; i < DRUG_NAMES.length; i++) {
      if (hasAny(text, DRUG_NAMES[i].words)) drugs.push(DRUG_NAMES[i].name);
    }
    return drugs.sort();
  }

  function inferSignal(article, latestDate) {
    var entryDate = parseDate(article.entry_date);
    if (!entryDate) return null;
    var age = daysApart(latestDate, entryDate);
    if (age < 0 || age > SIGNAL_WINDOW_DAYS) return null;

    var title = article.title || '';
    var text = (title + ' ' + (article.abstract || '') + ' ' + (article.pub_types || []).join(' ')).toLowerCase();
    var ev = article.evidence_level || '';
    if (!ev) return null;
    var ifVal = Number(article.journal_if || 0);
    var topics = inferTopics(article);
    var type = '新证据';

    if (hasAny(text, ['guideline', 'consensus', 'recommendation', 'review', 'meta-analysis'])) type = '新观点';
    if (hasAny(text, ['pathogenesis', 'mechanism', 'biomarker', 'cytokine', 'receptor', 'autoantibody'])) type = '新机制';
    if (hasAny(text, ['trial', 'randomized', 'phase 2', 'phase 3', 'cohort', 'efficacy', 'safety', 'real-world'])) type = '新证据';

    var drugs = matchDrugs(text);

    if (topics.length === 0 && drugs.length === 0 && !article.china_related) return null;

    var strength = '弱';
    if (ev === 'I' || ev === 'II' || (ifVal >= 10 && ev !== 'V')) strength = '强';
    else if (ifVal >= 5 || ev === 'III' || ev === 'IV' || article.china_related) strength = '中';

    var score = ifVal + evidenceRank(ev) + (article.china_related ? 1.5 : 0) + (SIGNAL_WINDOW_DAYS - age) / 3;
    if (strength === '强') score += 10;
    if (strength === '中') score += 4;

    return {
      article: article,
      date: entryDate,
      type: type,
      strength: strength,
      topics: topics,
      drugs: drugs,
      score: score,
      age: age
    };
  }

  function signalStrengthRank(strength) {
    return { '强': 3, '中': 2, '弱': 1 }[strength || ''] || 0;
  }

  function compareSignals(a, b) {
    var strengthDiff = signalStrengthRank(b.strength) - signalStrengthRank(a.strength);
    if (strengthDiff !== 0) return strengthDiff;
    if (b.score !== a.score) return b.score - a.score;
    return (b.date || 0) - (a.date || 0);
  }

  function buildSignals() {
    if (window.MG_SIGNALS_DATA && window.MG_SIGNALS_DATA.signals) {
      signalItems = window.MG_SIGNALS_DATA.signals.map(function(signal) {
        return {
          article: signal.article || {},
          date: parseDate(signal.date),
          type: signal.type || '新证据',
          strength: signal.strength || '弱',
          topics: signal.keywords || [],
          drugs: signal.drugs || [],
          score: signal.score || 0,
          age: 0,
          signal_to_kol: signal.signal_to_kol || null,
          kol_leads: signal.kol_leads || [],
          institution_leads: signal.institution_leads || [],
          medical_affairs: signal.medical_affairs || {},
          medical_affairs_implication: signal.medical_affairs_implication || (signal.medical_affairs && signal.medical_affairs.implication) || ''
        };
      });
      signalItems.sort(compareSignals);
      return;
    }
    var latest = maxEntryDate(allArticles);
    signalItems = [];
    for (var i = 0; i < allArticles.length; i++) {
      var item = inferSignal(allArticles[i], latest);
      if (item) signalItems.push(item);
    }
    signalItems.sort(compareSignals);
  }

  function renderSignals() {
    if (!el.signalList || !el.signalSummary) return;
    var counts = { all: signalItems.length, '强': 0, '中': 0, '弱': 0, china: 0 };
    var typeCounts = {};
    var topicCounts = {};

    for (var i = 0; i < signalItems.length; i++) {
      var s = signalItems[i];
      counts[s.strength]++;
      if (s.article.china_related) counts.china++;
      typeCounts[s.type] = (typeCounts[s.type] || 0) + 1;
      for (var k = 0; k < s.topics.length; k++) {
        topicCounts[s.topics[k]] = (topicCounts[s.topics[k]] || 0) + 1;
      }
    }

    el.signalSummary.innerHTML =
      '<div class="signal-stat-card"><span>14 天信号</span><strong>' + counts.all + '</strong></div>' +
      '<div class="signal-stat-card strong"><span>强信号</span><strong>' + counts['强'] + '</strong></div>' +
      '<div class="signal-stat-card medium"><span>中信号</span><strong>' + counts['中'] + '</strong></div>' +
      '<div class="signal-stat-card china"><span>中国相关</span><strong>' + counts.china + '</strong></div>';

    var filtered = [];
    for (var j = 0; j < signalItems.length; j++) {
      var ok = signalFilter === 'all' || signalItems[j].strength === signalFilter;
      if (ok && signalTopicFilter) {
        var hasTopic = false;
        for (var t = 0; t < signalItems[j].topics.length; t++) {
          if (signalItems[j].topics[t] === signalTopicFilter) { hasTopic = true; break; }
        }
        ok = hasTopic;
      }
      if (ok) filtered.push(signalItems[j]);
    }

    if (filtered.length === 0) {
      el.signalList.innerHTML = '<div class="empty-state"><h3>近 14 天暂无信号</h3><p>切换筛选条件或等待下一轮数据更新</p></div>';
    } else {
      var html = '';
      for (var n = 0; n < Math.min(filtered.length, 24); n++) {
        html += renderSignalCard(filtered[n]);
      }
      el.signalList.innerHTML = html;
    }

    var topics = Object.keys(topicCounts).sort(function(a, b) { return topicCounts[b] - topicCounts[a]; });
    var keywordHtml = '';
    for (var x = 0; x < Math.min(topics.length, 12); x++) {
      var isActive = topics[x] === signalTopicFilter;
      keywordHtml += '<button type="button" class="keyword-pill' + (isActive ? ' active' : '') + '" data-signal-topic="' + escapeHtml(topics[x]) + '" aria-pressed="' + (isActive ? 'true' : 'false') + '" title="筛选主题：' + escapeHtml(topics[x]) + '">' + escapeHtml(topics[x]) + '<strong>' + topicCounts[topics[x]] + '</strong></button>';
    }
    el.signalKeywords.innerHTML = keywordHtml || '<span class="muted">暂无主题</span>';

    var topicBtns = el.signalKeywords.querySelectorAll('.keyword-pill');
    for (var b = 0; b < topicBtns.length; b++) {
      topicBtns[b].addEventListener('click', function() {
        var topic = this.getAttribute('data-signal-topic');
        signalTopicFilter = (signalTopicFilter === topic) ? null : topic;
        renderSignals();
      });
    }
  }

  function renderSignalCard(item) {
    var a = item.article;
    var dateStr = item.date ? item.date.toLocaleDateString('zh-CN') : (a.pub_date || '');
    var topicHtml = '';
    for (var i = 0; i < item.topics.length; i++) {
      topicHtml += '<span class="signal-topic">' + escapeHtml(item.topics[i]) + '</span>';
    }
    var drugHtml = '';
    for (var d = 0; d < item.drugs.length; d++) {
      drugHtml += '<span class="signal-drug">' + escapeHtml(item.drugs[d]) + '</span>';
    }
    var tagHtml = topicHtml + drugHtml + (a.china_related ? '<span class="signal-topic china">中国相关</span>' : '');
    var kolHtml = renderSignalToKol(item);
    return '' +
      '<article class="signal-card signal-' + escapeHtml(item.strength) + '">' +
        '<div class="signal-card-head">' +
          '<span class="signal-strength">' + escapeHtml(item.strength) + '信号</span>' +
          '<span class="signal-type">' + escapeHtml(item.type) + '</span>' +
        '</div>' +
        '<a class="signal-title" href="' + escapeHref(a.url) + '" target="_blank" rel="noopener">' + escapeHtml(a.title || '(无标题)') + '</a>' +
        '<div class="signal-meta">' + buildArticleMeta(a, dateStr) + '</div>' +
        kolHtml +
        '<div class="signal-topic-row">' + tagHtml + '</div>' +
      '</article>';
  }

  function renderSignalToKol(item) {
    var leads = item.kol_leads || [];
    var institutions = item.institution_leads || [];
    var ma = item.medical_affairs || {};
    var implication = item.medical_affairs_implication || ma.implication || '';
    if (!item.signal_to_kol && !leads.length && !institutions.length && !implication) return '';
    var leadHtml = leads.slice(0, 2).map(function(lead) {
      var roles = (lead.roles || []).join('/');
      var meta = [roles, lead.institution, lead.country || lead.region].filter(Boolean).join(' · ');
      return '<span class="signal-kol-chip"><strong>' + escapeHtml(lead.name || 'Unknown KOL') + '</strong><em>' + escapeHtml(meta) + '</em></span>';
    }).join('');
    var institutionHtml = institutions.slice(0, 2).map(function(inst) {
      var meta = [inst.country || inst.region, (inst.article_author_count ? inst.article_author_count + ' authors' : '')].filter(Boolean).join(' · ');
      return '<span class="signal-kol-chip institution"><strong>' + escapeHtml(inst.name || 'Unknown institution') + '</strong><em>' + escapeHtml(meta) + '</em></span>';
    }).join('');
    var actionHtml = ma.msl_action ? '<p><strong>MSL action</strong>：' + escapeHtml(ma.msl_action) + '</p>' : '';
    var questionHtml = ma.suggested_kol_question ? '<p><strong>KOL question</strong>：' + escapeHtml(ma.suggested_kol_question) + '</p>' : '';
    return '<div class="signal-kol-bridge">' +
      '<div class="signal-kol-kicker">Signal → KOL</div>' +
      (implication ? '<p>' + escapeHtml(implication) + '</p>' : '') +
      (leadHtml ? '<div class="signal-kol-row">' + leadHtml + '</div>' : '') +
      (institutionHtml ? '<div class="signal-kol-row institutions">' + institutionHtml + '</div>' : '') +
      actionHtml + questionHtml +
    '</div>';
  }

  function groupByMonth(articles) {
    var months = {};
    for (var i = 0; i < articles.length; i++) {
      var ed = articles[i].entry_date || '';
      var m = ed.match(/^(\d{4})\/(\d{2})/);
      if (!m) continue;
      var key = m[1] + '-' + m[2];
      months[key] = (months[key] || 0) + 1;
    }
    return months;
  }

  function renderChinaInsights() {
    if (!el.chinaSourceList) return;
    loadChinaData(function (ok) {
      if (!ok) {
        el.chinaSourceList.innerHTML = '<div class="empty-state"><h3>中国情报加载失败</h3><p>请稍后重试或检查数据产物。</p></div>';
        return;
      }
      var chinaPayload = window.MG_CHINA_DATA || null;
      var chinaArticles = chinaPayload && chinaPayload.pubmed_articles ? chinaPayload.pubmed_articles.slice() : [];
      if (chinaArticles.length === 0) {
        for (var i = 0; i < allArticles.length; i++) {
          if (allArticles[i].china_related) chinaArticles.push(allArticles[i]);
        }
      }
      chinaArticles.sort(function(a, b) {
        return (parseDate(b.entry_date) || 0) - (parseDate(a.entry_date) || 0);
      });

      if (el.chinaBadge) {
        var label = chinaPayload && chinaPayload.summary ? '近1年证据文献 ' : '近1年 ';
        var chinaTotal = chinaPayload && chinaPayload.summary ? chinaPayload.summary.recent_year_articles : chinaArticles.length;
        el.chinaBadge.textContent = label + chinaTotal + ' 篇';
      }

      var sourceHtml = '';
      if (chinaPayload && chinaPayload.top_journals && chinaPayload.top_journals.length) {
        sourceHtml += '<div class="source-block"><h4>主要期刊</h4>' + renderRankItems(chinaPayload.top_journals, 10, 'journal') + '</div>';
        sourceHtml += '<div class="source-block"><h4>机构线索（第一作者机构出现频次排序）</h4>' + renderRankItems(chinaPayload.top_institutions || [], 8, 'institution') + '</div>';
      } else {
        var journalCounts = {};
        var institutionCounts = {};
        for (var j = 0; j < chinaArticles.length; j++) {
          var art = chinaArticles[j];
          var journal = art.journal || 'Unknown';
          journalCounts[journal] = (journalCounts[journal] || 0) + 1;
          var affs = art.affiliations || [];
          for (var k = 0; k < affs.length; k++) {
            var inst = normalizeInstitution(affs[k]);
            if (inst) institutionCounts[inst] = (institutionCounts[inst] || 0) + 1;
          }
        }
        sourceHtml += '<div class="source-block"><h4>主要期刊</h4>' + renderRankList(journalCounts, 10) + '</div>';
        sourceHtml += '<div class="source-block"><h4>机构线索（第一作者机构出现频次排序）</h4>' + renderRankList(institutionCounts, 8) + '</div>';
      }
      el.chinaSourceList.innerHTML = sourceHtml;
      bindRankLinks();

      loadEcharts(function (chartOk) {
        if (chartOk) renderChinaCharts(chinaArticles, chinaPayload);
      });
    });
  }

  function renderCompactArticle(article) {
    var d = parseDate(article.entry_date);
    var dateStr = d ? d.toLocaleDateString('zh-CN') : (article.pub_date || '');
    return '' +
      '<article class="compact-article">' +
        '<a href="' + escapeHref(article.url) + '" target="_blank" rel="noopener">' + escapeHtml(article.title || '(无标题)') + '</a>' +
        '<div>' + buildArticleMeta(article, dateStr) + '</div>' +
      '</article>';
  }

  function normalizeInstitution(affiliation) {
    if (!affiliation) return '';
    var parts = affiliation.split(',');
    var candidates = [];
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i].trim();
      if (!part) continue;
      if (/department|school|faculty|laboratory|center/i.test(part) && !/hospital|university/i.test(part)) continue;
      if (/china|province|district|road|street|email|@/i.test(part)) continue;
      candidates.push(part);
    }
    var inst = candidates.length ? candidates[0] : parts[0].trim();
    inst = inst.replace(/^the\s+/i, '').replace(/\.$/, '');
    if (inst.length > 70) inst = inst.slice(0, 70) + '...';
    return inst;
  }

  function renderRankList(counts, limit) {
    var keys = Object.keys(counts).sort(function(a, b) { return counts[b] - counts[a]; });
    if (!keys.length) return '<div class="muted">暂无数据</div>';
    var html = '<ol class="rank-list">';
    for (var i = 0; i < Math.min(keys.length, limit); i++) {
      html += '<li><span>' + escapeHtml(keys[i]) + '</span><strong>' + counts[keys[i]] + '</strong></li>';
    }
    html += '</ol>';
    return html;
  }

  function renderRankItems(items, limit, groupType) {
    if (!items || !items.length) return '<div class="muted">暂无数据</div>';
    var html = '<ol class="rank-list">';
    for (var i = 0; i < Math.min(items.length, limit); i++) {
      var item = items[i];
      var articles = item.articles || [];
      var payloadId = 'rank-payload-' + groupType + '-' + i;
      html += '<li class="rank-list-item">' +
        '<span class="rank-name">' + escapeHtml(item.name || '') + '</span>' +
        '<button class="rank-count-link" type="button" data-rank-target="' + payloadId + '" data-rank-title="' + escapeHtml(item.name || '') + '" data-rank-count="' + (item.count || 0) + '">' +
          (item.count || 0) +
        '</button>' +
        '<div class="rank-modal-payload" id="' + payloadId + '" hidden>' + renderRankArticles(articles) + '</div>' +
      '</li>';
    }
    html += '</ol>';
    return html;
  }

  function renderRankArticles(articles) {
    if (!articles || !articles.length) return '<div class="muted">暂无关联文献</div>';
    var html = '';
    for (var i = 0; i < articles.length; i++) {
      html += renderCompactArticle(articles[i]);
    }
    return html;
  }

  function bindRankLinks() {
    if (!el.chinaSourceList) return;
    var links = el.chinaSourceList.querySelectorAll('.rank-count-link');
    for (var i = 0; i < links.length; i++) {
      links[i].addEventListener('click', function() {
        var targetId = this.getAttribute('data-rank-target');
        var panel = targetId ? document.getElementById(targetId) : null;
        if (!panel) return;
        openRankModal(this, panel.innerHTML);
      });
    }
  }

  function openRankModal(trigger, contentHtml) {
    var title = trigger.getAttribute('data-rank-title') || '';
    var count = trigger.getAttribute('data-rank-count') || '0';
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML =
      '<div class="modal rank-modal" role="dialog" aria-modal="true">' +
        '<button class="modal-close" type="button" data-modal-close="1">\u2715</button>' +
        '<div class="rank-modal-head">' +
          '<h2>' + escapeHtml(title) + '</h2>' +
          '<span>' + escapeHtml(count) + ' 篇中国证据文献</span>' +
        '</div>' +
        '<div class="rank-modal-list">' + contentHtml + '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    function closeModal() {
      document.removeEventListener('keydown', handleKeydown);
      overlay.remove();
    }

    function handleKeydown(event) {
      if (event.key === 'Escape') closeModal();
    }

    overlay.addEventListener('click', function(event) {
      if (event.target === overlay || event.target.getAttribute('data-modal-close') === '1') {
        closeModal();
      }
    });
    document.addEventListener('keydown', handleKeydown);
  }

  function renderChinaCharts(chinaArticles, chinaPayload) {
    if (typeof echarts === 'undefined') return;

    var allMonths = groupByMonth(allArticles);
    var chinaMonths = {};
    if (chinaPayload && chinaPayload.monthly && chinaPayload.monthly.length) {
      for (var m = 0; m < chinaPayload.monthly.length; m++) {
        chinaMonths[chinaPayload.monthly[m].month] = chinaPayload.monthly[m].count;
      }
    } else {
      chinaMonths = groupByMonth(chinaArticles);
    }
    var monthKeys = Object.keys(allMonths).sort();
    if (monthKeys.length > 12) monthKeys = monthKeys.slice(monthKeys.length - 12);
    var monthLabels = [];
    var allValues = [];
    var chinaValues = [];
    for (var i = 0; i < monthKeys.length; i++) {
      monthLabels.push(monthKeys[i].replace('-', '\n'));
      allValues.push(allMonths[monthKeys[i]] || 0);
      chinaValues.push(chinaMonths[monthKeys[i]] || 0);
    }

    var monthlyEl = document.getElementById('chinaMonthlyChart');
    if (monthlyEl) {
      chinaMonthlyChart = chinaMonthlyChart || echarts.init(monthlyEl);
      chinaMonthlyChart.setOption({
        color: ['#93c5fd', '#22c55e'],
        tooltip: { trigger: 'axis' },
        legend: { top: 0, textStyle: { color: '#6b7280' } },
        grid: { left: 36, right: 16, top: 42, bottom: 42 },
        xAxis: { type: 'category', data: monthLabels, axisLabel: { color: '#6b7280', interval: 0, fontSize: 9, lineHeight: 11 } },
        yAxis: { type: 'value', axisLabel: { color: '#6b7280' }, splitLine: { lineStyle: { color: '#e5e7eb' } } },
        series: [
          { name: '全部文献', type: 'line', smooth: true, data: allValues, symbolSize: 6 },
          { name: '中国相关', type: 'bar', data: chinaValues, barMaxWidth: 18 }
        ]
      });
    }

    var evidenceCounts = {};
    if (chinaPayload && chinaPayload.evidence && chinaPayload.evidence.length) {
      for (var evIdx = 0; evIdx < chinaPayload.evidence.length; evIdx++) {
        evidenceCounts[chinaPayload.evidence[evIdx].level] = chinaPayload.evidence[evIdx].count;
      }
    } else {
      for (var j = 0; j < chinaArticles.length; j++) {
        var ev = chinaArticles[j].evidence_level;
        if (ev) evidenceCounts[ev] = (evidenceCounts[ev] || 0) + 1;
      }
    }
    var evOrder = ['I', 'II', 'III', 'IV', 'V'];
    var evValues = [];
    for (var e = 0; e < evOrder.length; e++) evValues.push(evidenceCounts[evOrder[e]] || 0);

    var evidenceEl = document.getElementById('chinaEvidenceChart');
    if (evidenceEl) {
      chinaEvidenceChart = chinaEvidenceChart || echarts.init(evidenceEl);
      chinaEvidenceChart.setOption({
        color: ['#60a5fa'],
        tooltip: { trigger: 'axis' },
        grid: { left: 36, right: 16, top: 20, bottom: 28 },
        xAxis: { type: 'category', data: evOrder, axisLabel: { color: '#6b7280' } },
        yAxis: { type: 'value', axisLabel: { color: '#6b7280' }, splitLine: { lineStyle: { color: '#e5e7eb' } } },
        series: [{ name: '篇数', type: 'bar', data: evValues, barMaxWidth: 22 }]
      });
    }

    var quartileCounts = {};
    if (chinaPayload && chinaPayload.quartile && chinaPayload.quartile.length) {
      for (var qIdx = 0; qIdx < chinaPayload.quartile.length; qIdx++) {
        quartileCounts[chinaPayload.quartile[qIdx].level] = chinaPayload.quartile[qIdx].count;
      }
    } else {
      for (var qArticleIdx = 0; qArticleIdx < chinaArticles.length; qArticleIdx++) {
        var quartile = chinaArticles[qArticleIdx].journal_quartile;
        if (!quartile) continue;
        var quartileKey = String(quartile).charAt(0) + '区';
        if (['1区', '2区', '3区', '4区'].indexOf(quartileKey) !== -1) {
          quartileCounts[quartileKey] = (quartileCounts[quartileKey] || 0) + 1;
        }
      }
    }
    var quartileOrder = ['1区', '2区', '3区', '4区'];
    var quartileValues = [];
    for (var q = 0; q < quartileOrder.length; q++) quartileValues.push(quartileCounts[quartileOrder[q]] || 0);

    var quartileEl = document.getElementById('chinaQuartileChart');
    if (quartileEl) {
      chinaQuartileChart = chinaQuartileChart || echarts.init(quartileEl);
      chinaQuartileChart.setOption({
        color: ['#38bdf8'],
        tooltip: { trigger: 'axis' },
        grid: { left: 36, right: 16, top: 20, bottom: 28 },
        xAxis: { type: 'category', data: quartileOrder, axisLabel: { color: '#6b7280', interval: 0 } },
        yAxis: { type: 'value', axisLabel: { color: '#6b7280' }, splitLine: { lineStyle: { color: '#e5e7eb' } } },
        series: [{ name: '篇数', type: 'bar', data: quartileValues, barMaxWidth: 22 }]
      });
    }
  }

  function resizeChinaCharts() {
    setTimeout(function() {
      if (chinaMonthlyChart) chinaMonthlyChart.resize();
      if (chinaEvidenceChart) chinaEvidenceChart.resize();
      if (chinaQuartileChart) chinaQuartileChart.resize();
    }, 60);
  }

  function init() {
    bindTabs();
    bindSignalFilters();
    el.loading.innerHTML = '';

    try {
      if (typeof window.MG_LITERATURE_DATA === 'undefined') {
        el.loading.innerHTML = '<div class="empty-state"><h3>⚠️ 数据加载失败</h3><p>全局变量 MG_LITERATURE_DATA 未定义</p></div>';
        return;
      }
      allArticles = window.MG_LITERATURE_DATA;
      if (allArticles.length === 0) {
        el.loading.innerHTML = '<div class="empty-state"><h3>暂无数据</h3></div>';
        return;
      }

      el.loading.style.display = 'none';
      populateMonths(allArticles);
      populateCommunityFilters();

      // 事件监听
      el.filterKeyword.addEventListener('input', applyFilters);
      if (el.sortMode) el.sortMode.addEventListener('change', applyFilters);
      el.chinaAll.addEventListener('change', applyFilters);
      el.chinaOnly.addEventListener('change', applyFilters);
      wireCheckboxAll('filterIFList');
      wireCheckboxAll('filterQuartileList');
      wireCheckboxAll('filterEvidenceList');

      // 统计
      document.getElementById('statYear').textContent = allArticles.length;

      var chinaYear = 0;
      for (var i = 0; i < allArticles.length; i++) {
        if (allArticles[i].china_related) chinaYear++;
      }
      document.getElementById('statChinaYear').textContent = chinaYear;

      var cutoff = rollingCutoffDate(allArticles, 30);
      var recent30 = [];
      for (var i = 0; i < allArticles.length; i++) {
        var d = parseDate(allArticles[i].entry_date);
        if (d && d >= cutoff) recent30.push(allArticles[i]);
      }
      document.getElementById('stat30d').textContent = recent30.length;

      var china30d = 0;
      for (var i = 0; i < recent30.length; i++) {
        if (recent30[i].china_related) china30d++;
      }
      document.getElementById('statChina30d').textContent = china30d;

      var evCounts = {};
      var evTotal = 0;
      for (var i = 0; i < allArticles.length; i++) {
        var ev = allArticles[i].evidence_level;
        if (ev) { evCounts[ev] = (evCounts[ev] || 0) + 1; evTotal++; }
      }
      var evOrder = ['I','II','III','IV','V'];
      var evParts = [];
      for (var k = 0; k < evOrder.length; k++) {
        var key = evOrder[k];
        if (evCounts[key]) {
          var pct = (evCounts[key] / evTotal * 100).toFixed(1);
          evParts.push(key + '级 ' + evCounts[key] + '篇（' + pct + '%）');
        }
      }
      document.getElementById('statEvDist').textContent = evParts.join(' · ');

      applyFilters();
      buildSignals();
      renderSignals();
      window.addEventListener('resize', resizeChinaCharts);
      document.getElementById('updateBadge').textContent = '数据: ' + allArticles.length + ' 篇';

    } catch (err) {
      el.loading.innerHTML = '<div class="empty-state"><h3>⚠️ 数据加载失败</h3><p>' + err.message + '</p></div>';
      console.error('Literature page init error:', err);
    }
  }

  el.btnExport.addEventListener('click', function() {
    var articles = filteredResults.length > 0 ? filteredResults : allArticles;
    var now = new Date().toLocaleDateString('zh-CN');

    // 生成 Markdown
    var md = '# MA-MG-HUB 文献简报\n生成日期: ' + now + '\n\n当前筛选: ' + articles.length + ' 篇\n\n';
    for (var i = 0; i < Math.min(articles.length, 50); i++) {
      var a = articles[i];
      var authors = (a.authors || []).slice(0, 3).join(', ');
      var tags = [];
      if (a.evidence_level) tags.push('证据等级 ' + a.evidence_level);
      var impactFactor = formatImpactFactor(a.journal_if);
      if (impactFactor) tags.push('IF ' + impactFactor);
      if (a.journal_quartile) tags.push('CAS ' + a.journal_quartile);
      if (a.china_related) tags.push('中国相关');
      md += (i+1) + '. ' + a.title + '\n';
      md += '   作者: ' + (authors || '未知') + ' · 期刊: ' + (a.journal || '未知') + '\n';
      md += '   PMID: ' + (a.pmid || '-') + (tags.length ? ' · ' + tags.join(' · ') : '') + '\n';
      md += '   ' + a.url + '\n\n';
    }
    if (articles.length > 50) md += '… 以及 ' + (articles.length - 50) + ' 篇\n';

    // 双栏弹窗
    var d = document.createElement('div');
    d.className = 'modal-overlay open';
    var closeBtn = '<button class="modal-close" type="button" data-brief-close="1">\u2715</button>';
    var preId = 'brief_' + Date.now();
    d.innerHTML =
      '<div class="modal literature-brief-modal">' +
        closeBtn +
        '<h2>\uD83D\uDCCB 文献简报</h2>' +
        '<div class="literature-brief-layout">' +
          '<div class="literature-brief-preview">' +
            '<div class="literature-brief-label">预览</div>' +
            '<pre id="' + preId + '" class="literature-brief-pre">' + escapeHtml(md) + '</pre>' +
          '</div>' +
          '<div class="literature-brief-actions">' +
            '<div class="literature-brief-label">操作</div>' +
            '<button class="btn literature-brief-copy" id="copy_' + preId + '">\uD83D\uDCCB 复制</button>' +
            '<p>复制后可粘贴到微信/飞书/邮件</p>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(d);

    d.querySelector('[data-brief-close]').addEventListener('click', function() {
      d.classList.remove('open');
    });

    document.getElementById('copy_' + preId).addEventListener('click', function() {
      var text = document.getElementById(preId).textContent;
      navigator.clipboard.writeText(text).then(function() {
        this.textContent = '\u2705 已复制';
        var self = this;
        setTimeout(function() { self.textContent = '\uD83D\uDCCB 复制'; }, 1500);
      }.bind(this));
    });
  });

  init();
})();

function toggleEvidenceRef() {
  var content = document.getElementById('evidenceContent');
  var arrow = document.getElementById('evidenceArrow');
  if (content && arrow) {
    content.classList.toggle('open');
    arrow.textContent = content.classList.contains('open') ? '▾' : '▸';
  }
}
