/* MA-MG-HUB 文献情报页面 JS - 按月拆分版本 */
(function() {
  'use strict';

  let allArticles = [];
  let filteredResults = [];
  let currentPage = 0;
  const PAGE_SIZE = 10;
  const DATA_PREFIX = '/MA-MG-HUB/data/literature-';

  // DOM refs
  const $ = id => document.getElementById(id);
  const el = {
    loading: $('loading'),
    results: $('results'),
    filterCount: $('filterCount'),
    statTotal: $('statTotal'),
    filterKeyword: $('filterKeyword'),
    filterTime: $('filterTime'),
    filterChina: $('filterChina'),
    filterIF: $('filterIF'),
    filterQuartile: $('filterQuartile'),
    btnExport: $('btnExport'),
  };

  function monthStr(y, m) {
    return `${y}-${String(m).padStart(2, '0')}`;
  }

  // 从当前月递推到指定月份，生成所有中间月份
  function monthsSince(untilYM) {
    const [untilY, untilM] = untilYM.split('-').map(Number);
    const now = new Date();
    const months = [];
    const y = now.getFullYear();
    const m = now.getMonth() + 1;
    let cy = y, cm = m;
    while (cy > untilY || (cy === untilY && cm >= untilM)) {
      months.push(monthStr(cy, cm));
      cm--;
      while (cm <= 0) { cy--; cm += 12; }
    }
    return months;
  }

  function getMonthsToLoad() {
    // 一次加载近 1 年（12 个月）
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth() + 1;
    let py = y, pm = m - 11;
    while (pm <= 0) { py--; pm += 12; }
    return monthsSince(monthStr(py, pm));
  }

  async function loadMonth(ym) {
    const url = `${DATA_PREFIX}${ym}.json?_t=${Date.now()}`;
    try {
      const resp = await fetch(url);
      if (!resp.ok) return null;
      return await resp.json();
    } catch {
      return null;
    }
  }

  function fillChinaRelated(articles) {
    for (const a of articles) {
      if (a.china_related === null) {
        a.china_related = (a.affiliations || []).some(aff =>
          /\b(China|Chinese|Hong Kong|Taiwan|Macau)\b/i.test(aff)
        );
      }
    }
  }

  function parseDate(dateStr) {
    if (!dateStr) return null;
    if (/^\d{4}\/\d{2}\/\d{2}/.test(dateStr)) {
      const m = dateStr.match(/(\d{4})\/(\d{2})\/(\d{2})/);
      if (m) return new Date(+m[1], +m[2]-1, +m[3]);
    }
    const d = new Date(dateStr);
    return isNaN(d) ? null : d;
  }

  function populateMonths(articles) {
    const sel = el.filterTime;
    const ymSet = new Set();
    for (const a of articles) {
      const ed = a.entry_date || '';
      const m = ed.match(/^(\d{4})\/(\d{2})/);
      if (m) ymSet.add(`${m[1]}-${m[2]}`);
    }
    const sorted = Array.from(ymSet).sort().reverse();
    let lastYear = '';
    for (const ym of sorted) {
      const [y, m] = ym.split('-');
      if (y !== lastYear) {
        const opt = document.createElement('option');
        opt.disabled = true;
        opt.textContent = `── ${y}年 ──`;
        sel.appendChild(opt);
        lastYear = y;
      }
      const opt = document.createElement('option');
      opt.value = ym;
      opt.textContent = `${y}/${parseInt(m)} 月`;
      sel.appendChild(opt);
    }
    sel.value = 'all';
    sel.addEventListener('change', onMonthFilterChange);
  }

  let loadedMonths = new Set();

  async function onMonthFilterChange() {
    const val = el.filterTime.value;
    if (val === 'all') {
      applyFilters();
      return;
    }
    if (!loadedMonths.has(val)) {
      el.loading.textContent = `📡 加载 ${val} 月数据…`;
      const data = await loadMonth(val);
      if (data) {
        fillChinaRelated(data);
        allArticles = allArticles.concat(data);
        loadedMonths.add(val);
        el.loading.textContent = `📡 ${allArticles.length} 篇`;
      }
    }
    applyFilters();
  }

  function applyFilters(resetPage) {
    if (resetPage === undefined) resetPage = true;
    const keyword = (el.filterKeyword.value || '').toLowerCase().trim();
    const timeVal = el.filterTime.value;
    const chinaVal = el.filterChina.value;
    const ifVal = el.filterIF.value;
    const quartileVal = el.filterQuartile.value;

    function matchesIF(a) {
      const v = a.journal_if;
      if (v === null || v === undefined) return ifVal === 'all';
      if (ifVal === 'all') return true;
      const [lo, hi] = ifVal.split('-').map(Number);
      if (ifVal === '10') return v >= 10;
      return v >= lo && v < hi;
    }
    function matchesQuartile(a) {
      const q = a.journal_quartile;
      if (q === null || q === undefined) return quartileVal === 'all';
      if (quartileVal === 'all') return true;
      return String(q) === quartileVal;
    }

    filteredResults = allArticles.filter(a => {
      if (keyword) {
        const inTitle = (a.title || '').toLowerCase().includes(keyword);
        const inAuthors = (a.authors || []).some(au => au.toLowerCase().includes(keyword));
        const inJournal = (a.journal || '').toLowerCase().includes(keyword);
        const inPmid = a.pmid === keyword;
        if (!inTitle && !inAuthors && !inJournal && !inPmid) return false;
      }
      if (timeVal !== 'all' && a.entry_date && !a.entry_date.startsWith(timeVal.replace('-', '/'))) return false;
      if (chinaVal === 'china' && !a.china_related) return false;
      if (chinaVal === 'non-china' && a.china_related) return false;
      if (!matchesIF(a)) return false;
      if (!matchesQuartile(a)) return false;
      return true;
    });

    el.filterCount.textContent = filteredResults.length;
    if (resetPage) currentPage = 0;
    renderResults();
  }

  function renderResults() {
    const articles = filteredResults;
    el.results.innerHTML = '';
    if (articles.length === 0) {
      el.results.innerHTML = '<div class="empty-state"><h3>暂无匹配文献</h3><p>试试调整筛选条件</p></div>';
      return;
    }
    const totalPages = Math.ceil(articles.length / PAGE_SIZE);
    const start = currentPage * PAGE_SIZE;
    const pageArticles = articles.slice(start, start + PAGE_SIZE);

    const fragment = document.createDocumentFragment();
    for (const a of pageArticles) {
      fragment.appendChild(renderArticle(a));
    }
    el.results.appendChild(fragment);

    const nav = document.createElement('div');
    nav.className = 'pagination';
    nav.style.cssText = 'display:flex;justify-content:center;align-items:center;gap:0.5rem;margin-top:1rem;padding:0.5rem 0';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'btn';
    prevBtn.textContent = '‹ 上一页';
    prevBtn.disabled = currentPage === 0;
    prevBtn.addEventListener('click', () => { if (currentPage > 0) { currentPage--; renderResults(); window.scrollTo(0,0); } });
    nav.appendChild(prevBtn);

    const pageInfo = document.createElement('span');
    pageInfo.style.cssText = 'font-size:0.85rem;color:var(--fg3)';
    pageInfo.textContent = `${currentPage + 1} / ${totalPages} 页 (${articles.length} 篇)`;
    nav.appendChild(pageInfo);

    const nextBtn = document.createElement('button');
    nextBtn.className = 'btn';
    nextBtn.textContent = '下一页 ›';
    nextBtn.disabled = currentPage >= totalPages - 1;
    nextBtn.addEventListener('click', () => { if (currentPage < totalPages - 1) { currentPage++; renderResults(); window.scrollTo(0,0); } });
    nav.appendChild(nextBtn);

    el.results.appendChild(nav);
  }

  function renderArticle(article) {
    const entryDate = parseDate(article.entry_date);
    const dateStr = entryDate ? entryDate.toLocaleDateString('zh-CN') : (article.pub_date || '');
    const china = article.china_related;
    const evLevel = article.evidence_level;
    const studyTypes = article.study_types || [];

    const div = document.createElement('div');
    div.className = 'article-card';

    const authors = (article.authors || []).slice(0, 5).join(', ');
    const authorStr = authors + ((article.authors || []).length > 5 ? ' et al.' : '');

    let tagsHTML = '';
    if (china) tagsHTML += '<span class="badge-china">🇨🇳 中国</span>';
    if (evLevel) tagsHTML += `<span class="badge-evidence">证据等级 ${evLevel}</span>`;
    else if (studyTypes.length > 0 && studyTypes[0] !== 'Unclassified')
      tagsHTML += `<span class="badge-pending">${studyTypes[0]}</span>`;

    div.innerHTML = `
      <a class="article-card-title" href="${article.url}" target="_blank">${article.title || '(无标题)'}</a>
      <div class="article-card-meta">${article.journal || 'Unknown'} · ${dateStr}</div>
      <div class="article-card-authors">${authorStr || '作者未知'}</div>
      ${article.abstract ? `
        <button class="abstract-toggle" data-pmid="${article.pmid}">显示摘要</button>
        <div class="article-card-abstract" id="abs-${article.pmid}">${escapeHtml(article.abstract.slice(0, 300))}${article.abstract.length > 300 ? '…' : ''}</div>
      ` : ''}
      <div class="article-card-links">
        <a href="${article.url}" target="_blank">PubMed</a>
        ${article.doi ? `<a href="https://doi.org/${article.doi}" target="_blank">DOI</a>` : ''}
        ${tagsHTML}
      </div>
    `;

    const toggle = div.querySelector('.abstract-toggle');
    if (toggle) {
      toggle.addEventListener('click', function() {
        const abs = document.getElementById('abs-' + article.pmid);
        if (abs) {
          // 第一次展开：填充全文，不再截断
          if (abs.getAttribute('data-fulltext') !== '1') {
            abs.innerHTML = escapeHtml(article.abstract);
            abs.setAttribute('data-fulltext', '1');
          }
          abs.classList.toggle('open');
          this.textContent = abs.classList.contains('open') ? '收起摘要' : '显示摘要';
        }
      });
    }

    return div;
  }

  function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  }

  async function init() {
    const monthsToLoad = getMonthsToLoad();
    el.loading.textContent = `📡 加载 ${monthsToLoad.length} 个月数据…`;

    try {
      const results = await Promise.all(monthsToLoad.map(ym => loadMonth(ym)));
      allArticles = [];
      loadedMonths = new Set();
      for (let i = 0; i < monthsToLoad.length; i++) {
        if (results[i]) {
          fillChinaRelated(results[i]);
          allArticles = allArticles.concat(results[i]);
          loadedMonths.add(monthsToLoad[i]);
        }
      }

      if (allArticles.length === 0) {
        el.loading.innerHTML = '<div class="empty-state"><h3>暂无数据</h3><p>数据加载失败，请稍后刷新</p></div>';
        return;
      }

      el.loading.textContent = `📡 ${allArticles.length} 篇`;

      populateMonths(allArticles);

      // 更新统计
      // 文献总量——从 literature-full.json 单独加载
      fetch('/MA-MG-HUB/data/literature-full.json?_t=' + Date.now())
        .then(r => r.json())
        .then(full => {
          document.getElementById('statTotal').textContent = full.length.toLocaleString();
        })
        .catch(() => { document.getElementById('statTotal').textContent = '—'; });

      el.statTotal.textContent = '…'; // 由上面 fetch 覆盖

      const yearCount = allArticles.length;
      document.getElementById('statYear').textContent = yearCount;

      const chinaYear = allArticles.filter(a => {
        if (a.china_related === true) return true;
        if (a.china_related === null) {
          return (a.affiliations || []).some(aff =>
            /\b(China|Chinese|Hong Kong|Taiwan|Macau)\b/i.test(aff)
          );
        }
        return false;
      }).length;
      document.getElementById('statChinaYear').textContent = chinaYear;

      // 近30天
      const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - 30);
      const recent30 = allArticles.filter(a => { const d = parseDate(a.entry_date); return d && d >= cutoff; });
      document.getElementById('stat30d').textContent = recent30.length;

      // 近30天中国相关
      const china30d = recent30.filter(a => {
        if (a.china_related === true) return true;
        if (a.china_related === null) {
          return (a.affiliations || []).some(aff =>
            /\b(China|Chinese|Hong Kong|Taiwan|Macau)\b/i.test(aff)
          );
        }
        return false;
      }).length;
      document.getElementById('statChina30d').textContent = china30d;

      // 证据等级分布（以已有等级的总数作分母）
      const evCounts = {};
      let evTotal = 0;
      for (const a of allArticles) {
        const ev = a.evidence_level;
        if (ev) { evCounts[ev] = (evCounts[ev] || 0) + 1; evTotal++; }
      }
      const evOrder = ['I','II','III','IV','V','VI'];
      const evParts = [];
      for (const k of evOrder) {
        if (evCounts[k]) {
          const pct = (evCounts[k] / evTotal * 100).toFixed(1);
          evParts.push(`${k}级 ${evCounts[k]}篇（${pct}%）`);
        }
      }
      document.getElementById('statEvDist').textContent = evParts.join(' · ');

      applyFilters();
      document.getElementById('updateBadge').textContent = `数据: ${monthsToLoad[0]} 起 · ${allArticles.length}篇`;

    } catch (err) {
      el.loading.innerHTML = `<div class="empty-state"><h3>⚠️ 数据加载失败</h3><p>${err.message}</p></div>`;
      console.error('Literature page init error:', err);
    }
  }

  el.filterKeyword.addEventListener('input', applyFilters);
  el.filterChina.addEventListener('change', applyFilters);
  el.btnExport.addEventListener('click', function() {
    const articles = filteredResults.length > 0 ? filteredResults : allArticles;
    const now = new Date().toLocaleDateString('zh-CN');
    const top5 = articles.slice(0, 5);
    let text = `# MA-MG-HUB 文献简报\n生成日期: ${now}\n\n当前筛选: ${articles.length} 篇\n\n`;
    top5.forEach((a, i) => {
      const authors = (a.authors || []).slice(0, 3).join(', ');
      text += `\n${i+1}. ${a.title}\n   作者: ${authors || '未知'}\n   期刊: ${a.journal || '未知'}\n   链接: ${a.url}\n`;
    });

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay open';
    overlay.innerHTML = `
      <div class="modal">
        <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">✕</button>
        <h2>📋 文献简报预览</h2>
        <pre>${escapeHtml(text)}</pre>
        <div class="modal-actions">
          <button class="btn" id="copyBrief">📋 复制到剪贴板</button>
          <button class="btn" id="closeBrief">关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#copyBrief').addEventListener('click', function() {
      navigator.clipboard.writeText(text).then(() => {
        this.textContent = '✅ 已复制';
        setTimeout(() => this.textContent = '📋 复制到剪贴板', 2000);
      });
    });
    overlay.querySelector('#closeBrief').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  });

  init();
})();

function toggleEvidenceRef() {
  const content = document.getElementById('evidenceContent');
  const arrow = document.getElementById('evidenceArrow');
  if (content && arrow) {
    content.classList.toggle('open');
    arrow.textContent = content.classList.contains('open') ? '▾' : '▸';
  }
}
