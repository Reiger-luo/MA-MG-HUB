/* MA-MG-HUB 文献情报页面 JS */
(function() {
  'use strict';

  let allArticles = [];
  let filteredResults = [];
  let currentPage = 0;
  const PAGE_SIZE = 20;

  const CACHE_BUST = '?_t=' + Date.now();
  const DATA_URL = '/MA-MG-HUB/data/literature-2026.json' + CACHE_BUST;

  // DOM refs
  const $ = id => document.getElementById(id);
  const el = {
    loading: $('loading'),
    results: $('results'),
    filterCount: $('filterCount'),
    statTotal: $('statTotal'),
    stat30d: $('stat30d'),
    statChina: $('statJournal'),
    statJournal: $('statJournal'),
    filterKeyword: $('filterKeyword'),
    filterTime: $('filterTime'),
    filterChina: $('filterChina'),
    filterIF: $('filterIF'),
    filterQuartile: $('filterQuartile'),
    btnExport: $('btnExport'),
  };

  // ── 工具函数 ──

  function daysAgo(n) {
    const d = new Date(); d.setDate(d.getDate() - n);
    return d;
  }

  function parseDate(dateStr) {
    if (!dateStr) return null;
    // EDAT: "2026/06/07 02:52"
    if (/^\d{4}\/\d{2}\/\d{2}/.test(dateStr)) {
      const m = dateStr.match(/(\d{4})\/(\d{2})\/(\d{2})/);
      if (m) return new Date(+m[1], +m[2]-1, +m[3]);
    }
    // PubDate: "2026-Jun-06"
    if (/^\d{4}-/.test(dateStr)) {
      const d = new Date(dateStr);
      if (!isNaN(d)) return d;
    }
    // fallback
    const d = new Date(dateStr);
    return isNaN(d) ? null : d;
  }

  function isChinaRelated(article) {
    if (article.china_related === true) return true;
    if (article.china_related === false) return false;
    // null → 从 affiliations 判断
    return (article.affiliations || []).some(aff =>
      /\b(China|Chinese|Hong Kong|Taiwan|Macau)\b/i.test(aff)
    );
  }

  // ── 中国检测（首次加载时一次性回填） ──

  function fillChinaRelated(articles) {
    for (const a of articles) {
      if (a.china_related === null) {
        a.china_related = isChinaRelated(a);
      }
    }
  }

  // ── 获取期刊列表 ──

  function getJournalList(articles) {
    const journals = new Set();
    for (const a of articles) {
      if (a.journal) journals.add(a.journal);
    }
    return Array.from(journals).sort();
  }

  // ── 渲染 ──

  function renderArticle(article) {
    const entryDate = parseDate(article.entry_date);
    const dateStr = entryDate ? entryDate.toLocaleDateString('zh-CN') : (article.pub_date || '');
    const china = article.china_related;

    const div = document.createElement('div');
    div.className = 'article-card';

    const authors = (article.authors || []).slice(0, 5).join(', ');
    const authorStr = authors + ((article.authors || []).length > 5 ? ' et al.' : '');

    div.innerHTML = `
      <a class="article-card-title" href="${article.url}" target="_blank">${article.title || '(无标题)'}</a>
      <div class="article-card-meta">${article.journal || 'Unknown'} · ${dateStr}</div>
      <div class="article-card-authors">${authorStr || '作者未知'}</div>
      ${article.abstract ? `
        <button class="abstract-toggle" data-pmid="${article.pmid}">显示摘要</button>
        <div class="article-card-abstract" id="abs-${article.pmid}">${escapeHtml(truncateAbstract(article.abstract))}</div>
      ` : ''}
      <div class="article-card-links">
        <a href="${article.url}" target="_blank">PubMed</a>
        ${article.doi ? `<a href="https://doi.org/${article.doi}" target="_blank">DOI</a>` : ''}
        ${china ? '<span class="badge-china">🇨🇳 中国</span>' : ''}
        <span class="badge-pending">证据等级待判定</span>
      </div>
    `;

    // 摘要切换
    const toggle = div.querySelector('.abstract-toggle');
    if (toggle) {
      toggle.addEventListener('click', function() {
        const abs = document.getElementById('abs-' + article.pmid);
        if (abs) {
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

  function truncateAbstract(text) {
    // 默认显示前 300 字，展开全文在 future 做
    return text.length > 500 ? text.slice(0, 500) + '…' : text;
  }

  function applyFilters(resetPage) {
    if (resetPage === undefined) resetPage = true;
    const keyword = (el.filterKeyword.value || '').toLowerCase().trim();
    const timeVal = el.filterTime.value;
    const chinaVal = el.filterChina.value;
    const ifVal = el.filterIF.value;
    const quartileVal = el.filterQuartile.value;

    const timeCutoff = timeVal === 'all' ? null : daysAgo(parseInt(timeVal));

    function matchesIF(a) {
      const v = a.journal_if;
      if (v === null || v === undefined) return ifVal === 'all'; // 未标注的不过滤
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
      if (timeCutoff) {
        const ed = parseDate(a.entry_date);
        if (ed && ed < timeCutoff) return false;
      }
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

    // 分页
    const totalPages = Math.ceil(articles.length / PAGE_SIZE);
    const start = currentPage * PAGE_SIZE;
    const pageArticles = articles.slice(start, start + PAGE_SIZE);

    const fragment = document.createDocumentFragment();
    for (const a of pageArticles) {
      fragment.appendChild(renderArticle(a));
    }
    el.results.appendChild(fragment);

    // 分页导航
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

  // ── 统计 ──

  function updateStats(articles) {
    el.statTotal.textContent = articles.length;

    const cutoff = daysAgo(30);
    const recent30 = articles.filter(a => {
      const d = parseDate(a.entry_date);
      return d && d >= cutoff;
    });
    el.stat30d.textContent = recent30.length;

    const china = articles.filter(a => a.china_related);
    document.querySelectorAll('.stat')[2].innerHTML = `中国相关 <strong>${china.length}</strong>`;

    const journals = new Set(articles.filter(a => a.journal).map(a => a.journal));
    el.statJournal.textContent = journals.size;
  }

  // ── 期刊选择器填充 ──

  function populateJournalSelect(articles) {
    const journals = getJournalList(articles);
    const sel = el.filterJournal;
    // 保留 first option
    sel.innerHTML = '<option value="all">全部期刊</option>';
    for (const j of journals) {
      const opt = document.createElement('option');
      opt.value = j; opt.textContent = j;
      sel.appendChild(opt);
    }
  }

  // ── 简报生成 ──

  function generateBrief(articles) {
    const now = new Date().toLocaleDateString('zh-CN');
    const chinaCount = articles.filter(a => a.china_related).length;
    const top5 = articles.slice(0, 5);

    let text = `# MA-MG-HUB 文献简报\n生成日期: ${now}\n\n`;
    text += `## 概览\n- 本周/筛选范围内: ${articles.length} 篇\n- 中国相关: ${chinaCount} 篇\n\n`;
    text += `## 重点文献\n`;
    top5.forEach((a, i) => {
      const authors = (a.authors || []).slice(0, 3).join(', ');
      text += `\n${i+1}. ${a.title}\n`;
      text += `   作者: ${authors || '未知'}\n`;
      text += `   期刊: ${a.journal || '未知'}\n`;
      text += `   日期: ${a.entry_date || a.pub_date || '未知'}\n`;
      text += `   链接: ${a.url}\n`;
    });

    return text;
  }

  // ── 初始化 ──

  async function init() {
    try {
      el.loading.textContent = '📡 正在加载文献数据 (10577篇)...';
      const resp = await fetch(DATA_URL);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      allArticles = await resp.json();
      el.loading.textContent = '📡 正在处理...';

      // 回填中国标记
      fillChinaRelated(allArticles);

      // 填充期刊选择器
      populateJournalSelect(allArticles);

      // 更新统计
      updateStats(allArticles);

      // 默认显示最近30天
      el.filterTime.value = '30';
      applyFilters();

      // 更新 badge
      const date = new Date();
      document.getElementById('updateBadge').textContent = `数据: ${date.toLocaleDateString('zh-CN')} · ${allArticles.length}篇`;

    } catch (err) {
      el.loading.innerHTML = `<div class="empty-state"><h3>⚠️ 数据加载失败</h3><p>${err.message}</p></div>`;
      console.error('Literature page init error:', err);
    }
  }

  // ── 事件绑定 ──

  el.filterKeyword.addEventListener('input', applyFilters);
  el.filterTime.addEventListener('change', applyFilters);
  el.filterChina.addEventListener('change', applyFilters);
  el.filterJournal.addEventListener('change', function() {
    const val = this.value;
    // 重新跑 filters + journal 额外过滤
    const filtered = allArticles.filter(a => {
      // 先跑基础 filter
      const keyword = (el.filterKeyword.value || '').toLowerCase().trim();
      if (keyword) {
        const inTitle = (a.title || '').toLowerCase().includes(keyword);
        const inAuthors = (a.authors || []).some(au => au.toLowerCase().includes(keyword));
        const inJournal = (a.journal || '').toLowerCase().includes(keyword);
        if (!inTitle && !inAuthors && !inJournal && a.pmid !== keyword) return false;
      }
      // journal
      if (val !== 'all' && a.journal !== val) return false;
      // time
      const timeVal = el.filterTime.value;
      if (timeVal !== 'all') {
        const d = parseDate(a.entry_date);
        if (d && d < daysAgo(parseInt(timeVal))) return false;
      }
      // china
      const chinaVal = el.filterChina.value;
      if (chinaVal === 'china' && !a.china_related) return false;
      if (chinaVal === 'non-china' && a.china_related) return false;
      return true;
    });
    filteredResults = filtered;
    el.filterCount.textContent = filtered.length;
    renderResults(filtered);
  });

  el.btnExport.addEventListener('click', function() {
    const text = generateBrief(filteredResults);
    // 弹窗
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

  // ── 启动 ──
  init();

})();
