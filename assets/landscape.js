/* MA-MG-HUB 诊治格局 */
(function() {
  'use strict';

  var hub = window.MgHub || {};
  var data = window.MG_LANDSCAPE_DATA || {};
  var chinaLandscape = data.china_landscape || {};
  var themeDivergence = chinaLandscape.theme_divergence || {};
  var guidelineDivergence = chinaLandscape.guideline_divergence || {};
  var sourceSignals = window.MG_SOURCE_SIGNALS || { channels: [] };
  var curatedTopicPayload = window.MG_CURATED_TOPICS || { topics: [] };
  var curatedTopics = curatedTopicPayload.topics || [];
  var topicCoveragePayload = window.MG_WIKI_TOPIC_COVERAGE || { stats: {}, topic_coverage: [], community_coverage: [] };
  var topicById = {};
  var topicCoverageById = {};
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
    return pageUrl('pages/knowledge.html?topic=' + encodeURIComponent(topicId || '') + communityQuery);
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

  // ── 诊疗现状 / 临床问题：角标引用与章节渲染 ──
  var treatmentChapters = (window.MG_TREATMENT_CHAPTERS || {}).chapters || [];
  var clinicalQuestionGroups = (window.MG_CLINICAL_QUESTIONS || {}).groups || [];
  var knowledgeReview = window.MG_KNOWLEDGE_REVIEW || { candidates: [] };
  var activeChapterId = treatmentChapters.length ? treatmentChapters[0].id : '';

  // 周更候选新证据：只展示 I/II 级命中项，标记"待确认"，不混入正文
  function renderPendingCandidates(targetType, targetId) {
    var items = (knowledgeReview.candidates || []).filter(function (cand) {
      return cand.target_type === targetType && cand.target_id === targetId;
    });
    if (!items.length) return '';
    return '<div class="pending-candidates"><h5>本周候选新证据（I/II 级 · 待确认）</h5>' +
      items.map(function (cand) {
        return '<p><a href="' + escapeHref(cand.url) + '" target="_blank" rel="noopener">PMID ' + escapeHtml(cand.pmid) + '</a> ' +
          escapeHtml(cand.title) + '<span class="pending-note"> ' + escapeHtml(cand.journal || '') + ' · 证据 ' + escapeHtml(cand.evidence_level || '-') + ' · 待确认</span></p>';
      }).join('') + '</div>';
  }

  function citationMarks(refItems, refMap) {
    return (refItems || []).map(function (ref) {
      var key = ref.pmid || ref.key;
      var n = refMap[key];
      return n ? '<sup class="cite-mark">[' + n + ']</sup>' : '';
    }).join('');
  }

  function renderStatement(item, refMap) {
    return '<p class="evidence-statement">' + escapeHtml(item.text) + citationMarks(item.refs, refMap) + '</p>';
  }

  function renderEvidenceRefs(refs) {
    if (!refs || !refs.length) return '';
    return '<ol class="chapter-refs">' + refs.map(function (ref) {
      var text = escapeHtml(ref.text);
      var label = ref.kind === 'article' && ref.lang === 'en' && ref.url
        ? '<a href="' + escapeHref(ref.url) + '" target="_blank" rel="noopener">' + text + '</a>'
        : text;
      return '<li value="' + ref.n + '">' + label + '</li>';
    }).join('') + '</ol>';
  }

  function renderChapterNav() {
    var nav = $('chapterNav');
    if (!nav) return;
    nav.innerHTML = treatmentChapters.map(function (chapter) {
      return '<button type="button" class="chapter-nav-item' + (chapter.id === activeChapterId ? ' active' : '') +
        '" data-chapter-id="' + escapeHtml(chapter.id) + '">' + escapeHtml(chapter.title) + '</button>';
    }).join('');
    Array.prototype.forEach.call(nav.querySelectorAll('[data-chapter-id]'), function (button) {
      button.addEventListener('click', function () {
        activeChapterId = button.getAttribute('data-chapter-id');
        renderChapterNav();
        renderChapterContent();
      });
    });
  }

  function renderChapterContent() {
    var box = $('chapterContent');
    if (!box) return;
    var chapter = null;
    treatmentChapters.forEach(function (item) { if (item.id === activeChapterId) chapter = item; });
    if (!chapter) {
      box.innerHTML = '<div class="kg-empty-hint">请选择左侧章节查看诊疗现状。</div>';
      return;
    }
    var branchHtml = (chapter.branches || []).map(function (branch) {
      return '<div class="chapter-branch"><h4>分歧 · ' + escapeHtml(branch.topic) + '</h4>' +
        branch.sides.map(function (side) {
          return '<div class="branch-side"><strong>' + escapeHtml(side.label) + '</strong>' +
            renderStatement(side, chapter.ref_map) + '</div>';
        }).join('') + '</div>';
    }).join('');
    box.innerHTML =
      '<h3>' + escapeHtml(chapter.title) + '</h3>' +
      '<p class="chapter-summary">' + escapeHtml(chapter.summary || '') + '</p>' +
      (chapter.statements || []).map(function (item) { return renderStatement(item, chapter.ref_map); }).join('') +
      branchHtml +
      renderPendingCandidates('chapter', chapter.id) +
      '<h4 class="refs-title">参考文献</h4>' + renderEvidenceRefs(chapter.refs);
  }

  function renderChapters() {
    var meta = $('chaptersMeta');
    if (meta) meta.textContent = treatmentChapters.length ? treatmentChapters.length + ' 个章节 · 版本 ' + ((window.MG_TREATMENT_CHAPTERS || {}).version || '') : '待生成';
    renderChapterNav();
    renderChapterContent();
  }

  function renderQuestions() {
    var box = $('questionGroups');
    if (!box) return;
    var total = 0;
    clinicalQuestionGroups.forEach(function (group) { total += group.questions.length; });
    var meta = $('questionsMeta');
    if (meta) meta.textContent = total ? total + ' 个问题 · ' + clinicalQuestionGroups.length + ' 个方向' : '待生成';
    if (!clinicalQuestionGroups.length) {
      box.innerHTML = '<div class="kg-empty-hint">临床问题库待生成。</div>';
      return;
    }
    box.innerHTML = clinicalQuestionGroups.map(function (group) {
      return '<section class="question-group"><h3>' + escapeHtml(group.title) + '</h3>' +
        group.questions.map(function (q) {
          var stanceClass = q.stance === '证据不足' ? 'insufficient' : 'cautious';
          return '<article class="question-card">' +
            '<div class="question-card-head"><h4>' + escapeHtml(q.question) + '</h4>' +
              '<span class="stance-badge stance-' + stanceClass + '">' + escapeHtml(q.stance || '待评估') + '</span></div>' +
            (q.whyOpen ? '<p class="question-open">未解决点：' + escapeHtml(q.whyOpen) + '</p>' : '') +
            (q.answer || []).map(function (item) { return renderStatement(item, q.ref_map); }).join('') +
            renderPendingCandidates('question', q.id) +
            '<h5 class="refs-title">参考文献</h5>' + renderEvidenceRefs(q.refs) +
          '</article>';
        }).join('') + '</section>';
    }).join('');
  }

  function applyInitialKnowledgeRoute() {
    var topicId = getQueryParam('topic');
    var communityId = getQueryParam('community');
    if (topicId) {
      window.location.href = pageUrl('pages/knowledge.html?topic=' + encodeURIComponent(topicId) +
        (communityId ? '&community=' + encodeURIComponent(communityId) : ''));
      return;
    }
    var tab = getQueryParam('tab');
    if (tab === 'chapters' || tab === 'questions') activateLandscapeTab(tab);
  }

  function init() {
    bindTabs();
    renderBadge();
    renderStats();
    renderCompetitiveMatrix();
    renderMajorEvents();
    renderChapters();
    renderQuestions();
    renderThemeDivergence();
    renderGuidelineDivergence();
    bindPmidModal();
    applyInitialKnowledgeRoute();
  }

  init();
})();
