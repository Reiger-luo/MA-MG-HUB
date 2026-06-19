/* MA-MG-HUB 文献情报页面 JS */
(function() {
  'use strict';

  let allArticles = [];
  let filteredResults = [];
  let signalItems = [];
  let signalFilter = 'all';
  let chinaMonthlyChart = null;
  let chinaEvidenceChart = null;
  let currentPage = 0;
  const PAGE_SIZE = 10;
  const SIGNAL_WINDOW_DAYS = 14;

  const $ = id => document.getElementById(id);
  const el = {
    loading: $('loading'),
    results: $('results'),
    filterCount: $('filterCount'),
    statTotal: $('statTotal'),
    filterKeyword: $('filterKeyword'),
    sortMode: $('sortMode'),
    filterTimeList: $('filterTimeList'),
    chinaAll: $('chinaAll'),
    chinaOnly: $('chinaOnly'),
    filterIFList: $('filterIFList'),
    filterQuartileList: $('filterQuartileList'),
    filterEvidenceList: $('filterEvidenceList'),
    btnExport: $('btnExport'),
    signalSummary: $('signalSummary'),
    signalList: $('signalList'),
    signalKeywords: $('signalKeywords'),
    chinaBadge: $('chinaBadge'),
    chinaRecentList: $('chinaRecentList'),
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
    return { I: 6, II: 5, III: 4, IV: 3, V: 2, VI: 1 }[level || ''] || 0;
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

    var authors = (article.authors || []).slice(0, 5).join(', ');
    var authorStr = authors + ((article.authors || []).length > 5 ? ' et al.' : '');

    var tagsHTML = '';
    if (china) tagsHTML += '<span class="badge-china">🇨🇳 中国</span>';
    if (evLevel) tagsHTML += '<span class="badge-evidence">证据等级 ' + evLevel + '</span>';
    else if (studyTypes.length > 0 && studyTypes[0] !== 'Unclassified')
      tagsHTML += '<span class="badge-pending">' + studyTypes[0] + '</span>';
    var impactFactor = formatImpactFactor(article.journal_if);
    if (impactFactor) tagsHTML += '<span class="badge-metric">IF ' + impactFactor + '</span>';
    if (article.journal_quartile) tagsHTML += '<span class="badge-metric">CAS ' + escapeHtml(String(article.journal_quartile)) + '</span>';

    div.innerHTML =
      '<a class="article-card-title" href="' + article.url + '" target="_blank">' + (article.title || '(无标题)') + '</a>' +
      '<div class="article-card-meta">' + (article.journal || 'Unknown') + ' · ' + dateStr + '</div>' +
      '<div class="article-card-authors">' + (authorStr || '作者未知') + '</div>' +
      (article.abstract
        ? '<button class="abstract-toggle" data-pmid="' + article.pmid + '">显示摘要</button>' +
          '<div class="article-card-abstract" id="abs-' + article.pmid + '">' + escapeHtml(article.abstract.slice(0, 300)) + (article.abstract.length > 300 ? '…' : '') + '</div>'
        : '') +
      '<div class="article-card-links">' +
        (article.doi ? '<a href="https://doi.org/' + article.doi + '" target="_blank">DOI</a>' : '') +
        tagsHTML +
      '</div>';

    var toggle = div.querySelector('.abstract-toggle');
    if (toggle) {
      (function(pmid, abstract) {
        toggle.addEventListener('click', function() {
          var abs = document.getElementById('abs-' + pmid);
          if (abs) {
            if (abs.getAttribute('data-fulltext') !== '1') {
              abs.innerHTML = escapeHtml(abstract);
              abs.setAttribute('data-fulltext', '1');
            }
            abs.classList.toggle('open');
            this.textContent = abs.classList.contains('open') ? '收起摘要' : '显示摘要';
          }
        });
      })(article.pmid, article.abstract);
    }
    return div;
  }

  function escapeHtml(text) {
    var d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  }

  function bindTabs() {
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
        if (key === 'china') resizeChinaCharts();
      });
    }
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
    if (ev === 'I' || ev === 'II' || ifVal >= 10) strength = '强';
    else if (ifVal >= 5 || ev === 'III' || ev === 'IV' || article.china_related) strength = '中';

    var score = ifVal + (ev === 'I' ? 7 : ev === 'II' ? 5 : ev ? 2 : 0) + (article.china_related ? 1.5 : 0) + (SIGNAL_WINDOW_DAYS - age) / 3;
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
          age: 0
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
      if (signalFilter === 'all' || signalItems[j].strength === signalFilter) filtered.push(signalItems[j]);
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
      keywordHtml += '<span class="keyword-pill">' + escapeHtml(topics[x]) + '<strong>' + topicCounts[topics[x]] + '</strong></span>';
    }
    el.signalKeywords.innerHTML = keywordHtml || '<span class="muted">暂无主题</span>';
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
    return '' +
      '<article class="signal-card signal-' + item.strength + '">' +
        '<div class="signal-card-head">' +
          '<span class="signal-strength">' + item.strength + '信号</span>' +
          '<span class="signal-type">' + item.type + '</span>' +
        '</div>' +
        '<a class="signal-title" href="' + a.url + '" target="_blank">' + escapeHtml(a.title || '(无标题)') + '</a>' +
        '<div class="signal-meta">' + escapeHtml(a.journal || 'Unknown') + ' · ' + dateStr + ' · PMID ' + escapeHtml(a.pmid || '-') + '</div>' +
        '<div class="signal-topic-row">' + tagHtml + '</div>' +
      '</article>';
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
    if (!el.chinaRecentList || !el.chinaSourceList) return;
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

    var recentHtml = '';
    for (var r = 0; r < Math.min(chinaArticles.length, 10); r++) {
      var a = chinaArticles[r];
      recentHtml += renderCompactArticle(a);
    }
    el.chinaRecentList.innerHTML = recentHtml || '<div class="empty-state"><h3>暂无中国相关文献</h3></div>';

    var sourceHtml = '';
    if (chinaPayload && chinaPayload.top_journals && chinaPayload.top_journals.length) {
      sourceHtml += '<div class="source-block"><h4>主要期刊</h4>' + renderRankItems(chinaPayload.top_journals, 10, 'journal') + '</div>';
      sourceHtml += '<div class="source-block"><h4>机构线索</h4>' + renderRankItems(chinaPayload.top_institutions || [], 8, 'institution') + '</div>';
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
      sourceHtml += '<div class="source-block"><h4>机构线索</h4>' + renderRankList(institutionCounts, 8) + '</div>';
    }
    el.chinaSourceList.innerHTML =
      sourceHtml;
    bindRankLinks();

    renderChinaCharts(chinaArticles, chinaPayload);
  }

  function renderCompactArticle(article) {
    var d = parseDate(article.entry_date);
    var dateStr = d ? d.toLocaleDateString('zh-CN') : (article.pub_date || '');
    var meta = [escapeHtml(article.journal || 'Unknown'), dateStr, 'PMID ' + escapeHtml(article.pmid || '-')];
    if (article.evidence_level) meta.push('证据等级 ' + escapeHtml(article.evidence_level));
    var impactFactor = formatImpactFactor(article.journal_if);
    if (impactFactor) meta.push('IF ' + impactFactor);
    if (article.journal_quartile) meta.push('CAS ' + escapeHtml(String(article.journal_quartile)));
    return '' +
      '<article class="compact-article">' +
        '<a href="' + article.url + '" target="_blank">' + escapeHtml(article.title || '(无标题)') + '</a>' +
        '<div>' + meta.join(' · ') + '</div>' +
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
    if (typeof echarts === 'undefined') {
      var monthlyEl = document.getElementById('chinaMonthlyChart');
      var evidenceEl = document.getElementById('chinaEvidenceChart');
      if (monthlyEl) monthlyEl.innerHTML = '<div class="chart-fallback">图表库未加载</div>';
      if (evidenceEl) evidenceEl.innerHTML = '<div class="chart-fallback">图表库未加载</div>';
      return;
    }

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
      monthLabels.push(monthKeys[i].replace('-', '/'));
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
        grid: { left: 36, right: 16, top: 42, bottom: 28 },
        xAxis: { type: 'category', data: monthLabels, axisLabel: { color: '#6b7280' } },
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
        var ev = chinaArticles[j].evidence_level || '未分类';
        evidenceCounts[ev] = (evidenceCounts[ev] || 0) + 1;
      }
    }
    var evOrder = ['I', 'II', 'III', 'IV', 'V', 'VI', '未分类'];
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
  }

  function resizeChinaCharts() {
    setTimeout(function() {
      if (chinaMonthlyChart) chinaMonthlyChart.resize();
      if (chinaEvidenceChart) chinaEvidenceChart.resize();
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

      // 事件监听
      el.filterKeyword.addEventListener('input', applyFilters);
      if (el.sortMode) el.sortMode.addEventListener('change', applyFilters);
      el.chinaAll.addEventListener('change', applyFilters);
      el.chinaOnly.addEventListener('change', applyFilters);
      wireCheckboxAll('filterIFList');
      wireCheckboxAll('filterQuartileList');
      wireCheckboxAll('filterEvidenceList');

      // 统计
      document.getElementById('statTotal').textContent = window.MG_TOTAL_COUNT || allArticles.length;
      document.getElementById('statYear').textContent = allArticles.length;

      var chinaYear = 0;
      for (var i = 0; i < allArticles.length; i++) {
        if (allArticles[i].china_related) chinaYear++;
      }
      document.getElementById('statChinaYear').textContent = chinaYear;

      var cutoff = new Date(); cutoff.setDate(cutoff.getDate() - 30);
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
      var evOrder = ['I','II','III','IV','V','VI'];
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
      renderChinaInsights();
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
    var closeBtn = '<button class="modal-close" onclick="this.parentElement.parentElement.classList.remove(\'open\')">\u2715</button>';
    var preId = 'brief_' + Date.now();
    d.innerHTML =
      '<div class="modal" style="max-width:900px">' +
        closeBtn +
        '<h2>\uD83D\uDCCB 文献简报</h2>' +
        '<div style="display:flex;gap:1rem;min-height:350px">' +
          '<div style="flex:1;display:flex;flex-direction:column">' +
            '<div style="font-size:0.78rem;color:var(--fg3);margin-bottom:0.3rem">预览</div>' +
            '<pre id="' + preId + '" style="flex:1;font-size:0.8rem;line-height:1.5;white-space:pre-wrap;word-break:break-word;color:var(--fg2);background:var(--bg);padding:0.8rem;border-radius:6px;border:1px solid var(--bg3);overflow-y:auto">' + escapeHtml(md) + '</pre>' +
          '</div>' +
          '<div style="width:160px;flex-shrink:0">' +
            '<div style="font-size:0.78rem;color:var(--fg3);margin-bottom:0.5rem">操作</div>' +
            '<button class="btn" id="copy_' + preId + '" style="display:block;width:100%;margin-bottom:0.4rem;text-align:center">\uD83D\uDCCB 复制</button>' +
            '<p style="font-size:0.72rem;color:var(--fg3)">复制后可粘贴到微信/飞书/邮件</p>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(d);

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
