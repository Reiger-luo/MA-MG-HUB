/* MA-MG-HUB 文献情报页面 JS */
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
    chinaAll: $('chinaAll'),
    chinaOnly: $('chinaOnly'),
    filterIFList: $('filterIFList'),
    filterQuartileList: $('filterQuartileList'),
    filterEvidenceList: $('filterEvidenceList'),
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

  function init() {
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
      el.chinaAll.addEventListener('change', applyFilters);
      el.chinaOnly.addEventListener('change', applyFilters);
      wireCheckboxAll('filterIFList');
      wireCheckboxAll('filterQuartileList');
      wireCheckboxAll('filterEvidenceList');

      // 统计
      document.getElementById('statTotal').textContent = allArticles.length;
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
      md += (i+1) + '. ' + a.title + '\n';
      md += '   作者: ' + (authors || '未知') + ' · 期刊: ' + (a.journal || '未知') + '\n';
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
