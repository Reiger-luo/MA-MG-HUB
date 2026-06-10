/* MA-MG-HUB 文献情报页面 JS - 从 .js 全局变量加载 */
(function() {
  'use strict';

  let allArticles = [];
  let filteredResults = [];
  let currentPage = 0;
  const PAGE_SIZE = 10;

  const $ = id => document.getElementById(id);
  const el = {
    loading: $('loading'),
    results: $('results'),
    filterCount: $('filterCount'),
    statTotal: $('statTotal'),
    filterKeyword: $('filterKeyword'),
    filterTimeList: $('filterTimeList'),
    chinaCheck: $('chinaCheck'),
    nonChinaCheck: $('nonChinaCheck'),
    filterIF: $('filterIF'),
    filterQuartile: $('filterQuartile'),
    filterEvidence: $('filterEvidence'),
    btnExport: $('btnExport'),
  };

  function parseDate(dateStr) {
    if (!dateStr) return null;
    var m = dateStr.match(/(\d{4})\/(\d{2})\/(\d{2})/);
    if (m) return new Date(+m[1], +m[2]-1, +m[3]);
    var d = new Date(dateStr);
    return isNaN(d) ? null : d;
  }

  function getSelectedMonths() {
    var cbs = el.filterTimeList.querySelectorAll('input[type="checkbox"]');
    var checked = [];
    for (var i = 0; i < cbs.length; i++) {
      if (cbs[i].checked) checked.push(cbs[i].value);
    }
    return checked;
  }

  function getChinaFilter() {
    var china = el.chinaCheck.checked;
    var nonChina = el.nonChinaCheck.checked;
    if (china && !nonChina) return 'china';
    if (!china && nonChina) return 'non-china';
    return 'all';
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
        var allItems = el.filterTimeList.querySelectorAll('input[type="checkbox"]');
        if (checkedItems.length === allItems.length - 1) {
          allCheckbox.checked = true;
        } else {
          allCheckbox.checked = false;
        }
      }
      applyFilters();
    });
  }

  function applyFilters(resetPage) {
    if (resetPage === undefined) resetPage = true;
    var keyword = (el.filterKeyword.value || '').toLowerCase().trim();
    var selectedMonths = getSelectedMonths();
    var chinaVal = getChinaFilter();
    var ifVal = el.filterIF.value;
    var quartileVal = el.filterQuartile.value;
    var evidenceVal = el.filterEvidence.value;

    var allSelected = false;
    for (var s = 0; s < selectedMonths.length; s++) {
      if (selectedMonths[s] === 'all') { allSelected = true; break; }
    }

    function matchesIF(a) {
      var v = a.journal_if;
      if (v === null || v === undefined) return ifVal === 'all';
      if (ifVal === 'all') return true;
      var parts = ifVal.split('-').map(Number);
      if (ifVal === '10') return v >= 10;
      return v >= parts[0] && v < parts[1];
    }
    function matchesQuartile(a) {
      var q = a.journal_quartile;
      if (q === null || q === undefined) return quartileVal === 'all';
      if (quartileVal === 'all') return true;
      return String(q).charAt(0) === quartileVal;
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
      if (chinaVal === 'non-china' && a.china_related) continue;
      if (!matchesIF(a)) continue;
      if (!matchesQuartile(a)) continue;
      if (evidenceVal !== 'all' && a.evidence_level !== evidenceVal) continue;
      filteredResults.push(a);
    }

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
    nav.style.cssText = 'display:flex;justify-content:center;align-items:center;gap:0.5rem;margin-top:1rem;padding:0.5rem 0';

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

    div.innerHTML =
      '<a class="article-card-title" href="' + article.url + '" target="_blank">' + (article.title || '(无标题)') + '</a>' +
      '<div class="article-card-meta">' + (article.journal || 'Unknown') + ' · ' + dateStr + '</div>' +
      '<div class="article-card-authors">' + (authorStr || '作者未知') + '</div>' +
      (article.abstract
        ? '<button class="abstract-toggle" data-pmid="' + article.pmid + '">显示摘要</button>' +
          '<div class="article-card-abstract" id="abs-' + article.pmid + '">' + escapeHtml(article.abstract.slice(0, 300)) + (article.abstract.length > 300 ? '…' : '') + '</div>'
        : '') +
      '<div class="article-card-links">' +
        '<a href="' + article.url + '" target="_blank">PubMed</a>' +
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

  function init() {
    el.loading.textContent = '📡 加载文献数据…';

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

      // 统计
      document.getElementById('statTotal').textContent = '10,577';
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

      // 证据等级
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

      // 事件监听
      el.filterKeyword.addEventListener('input', applyFilters);
      el.chinaCheck.addEventListener('change', applyFilters);
      el.nonChinaCheck.addEventListener('change', applyFilters);
      el.filterIF.addEventListener('change', applyFilters);
      el.filterQuartile.addEventListener('change', applyFilters);
      el.filterEvidence.addEventListener('change', applyFilters);

      applyFilters();
      document.getElementById('updateBadge').textContent = '数据: ' + allArticles.length + ' 篇';

    } catch (err) {
      el.loading.innerHTML = '<div class="empty-state"><h3>⚠️ 数据加载失败</h3><p>' + err.message + '</p></div>';
      console.error('Literature page init error:', err);
    }
  }

  el.btnExport.addEventListener('click', function() {
    var articles = filteredResults.length > 0 ? filteredResults : allArticles;
    var now = new Date().toLocaleDateString('zh-CN');
    var top5 = articles.slice(0, 5);
    var text = '# MA-MG-HUB 文献简报\n生成日期: ' + now + '\n\n当前筛选: ' + articles.length + ' 篇\n\n';
    for (var i = 0; i < top5.length; i++) {
      var a = top5[i];
      var authors = (a.authors || []).slice(0, 3).join(', ');
      text += '\n' + (i+1) + '. ' + a.title + '\n   作者: ' + (authors || '未知') + '\n   期刊: ' + (a.journal || '未知') + '\n   链接: ' + a.url + '\n';
    }

    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML =
      '<div class="modal">' +
        '<button class="modal-close" onclick="this.closest(\'.modal-overlay\').remove()">✕</button>' +
        '<h2>📋 文献简报预览</h2>' +
        '<pre>' + escapeHtml(text) + '</pre>' +
        '<div class="modal-actions">' +
          '<button class="btn" id="copyBrief">📋 复制到剪贴板</button>' +
          '<button class="btn" id="closeBrief">关闭</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    overlay.querySelector('#copyBrief').addEventListener('click', function() {
      navigator.clipboard.writeText(text).then(function() {
        this.textContent = '✅ 已复制';
        var self = this;
        setTimeout(function() { self.textContent = '📋 复制到剪贴板'; }, 2000);
      }.bind(this));
    });
    overlay.querySelector('#closeBrief').addEventListener('click', function() { overlay.remove(); });
    overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
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
