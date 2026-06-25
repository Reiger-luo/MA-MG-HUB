/* MA-MG-HUB 诊治格局 */
(function() {
  'use strict';

  var data = window.MG_LANDSCAPE_DATA || {};

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function compactNumber(value) {
    var num = Number(value || 0);
    return num >= 1000 ? (num / 1000).toFixed(1).replace(/\.0$/, '') + 'k' : String(num);
  }

  function bindTabs() {
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

  function renderBadge() {
    var badge = $('landscapeBadge');
    var overview = data.overview || {};
    if (badge) {
      badge.textContent = (overview.month_change_count || 0) + ' 条格局变化 · ' +
        (overview.living_answer_count || 0) + ' 个 Living Answer';
    }
    var positioning = $('landscapePositioning');
    if (positioning && overview.positioning) positioning.textContent = overview.positioning;
  }

  function renderStats() {
    var overview = data.overview || {};
    var stats = [
      ['格局变化', overview.month_change_count || (data.monthly_changes || []).length, '本月影响提示'],
      ['已获批对象', overview.competitive_count || (data.approved_competitive_matrix || data.competitive_matrix || []).length, '中国监管 + 证据厚度'],
      ['临床管线', overview.clinical_pipeline_count || (data.clinical_pipeline_matrix || []).length, 'ClinicalTrials Phase II+'],
      ['问题答案', overview.living_answer_count || (data.living_answers || []).length, 'abstract-based']
    ];
    var box = $('landscapeStats');
    if (!box) return;
    box.innerHTML = stats.map(function(item) {
      return '<article class="landscape-stat-card"><span>' + escapeHtml(item[0]) + '</span><strong>' +
        escapeHtml(compactNumber(item[1])) + '</strong><em>' + escapeHtml(item[2]) + '</em></article>';
    }).join('');
  }

  function renderRefLinks(refs, limit) {
    refs = refs || [];
    if (!refs.length) return '<span class="muted-text">暂无 PMID</span>';
    return refs.slice(0, limit || 3).map(function(ref) {
      var pmid = ref.pmid || '';
      return '<a class="pmid-chip" href="' + escapeHtml(ref.url || ('https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/')) +
        '" target="_blank" rel="noopener">PMID ' + escapeHtml(pmid) + '</a>';
    }).join('');
  }

  function renderSourceLinks(regulatory) {
    regulatory = regulatory || {};
    var links = [];
    if (regulatory.source_url) {
      links.push('<a class="regulatory-source-link" href="' + escapeHtml(regulatory.source_url) + '" target="_blank" rel="noopener">来源 1</a>');
    }
    if (regulatory.secondary_url) {
      links.push('<a class="regulatory-source-link" href="' + escapeHtml(regulatory.secondary_url) + '" target="_blank" rel="noopener">来源 2</a>');
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
    var changes = data.monthly_changes || [];
    var box = $('monthlyChangeList');
    if (!box) return;
    if (!changes.length) {
      box.innerHTML = '<div class="kg-empty-hint">暂无格局变化数据。</div>';
      return;
    }
    box.innerHTML = changes.map(function(change) {
      return '<article class="landscape-change-card">' +
        '<div class="change-card-head"><span>' + escapeHtml(change.type || '变化') + '</span><strong>' + escapeHtml(change.title) + '</strong></div>' +
        '<p>' + escapeHtml(change.why_it_matters || '') + '</p>' +
        '<div class="change-meta-grid">' +
          '<div><span>影响位置</span><strong>' + escapeHtml(change.treatment_position || '-') + '</strong></div>' +
          '<div><span>竞争叙事</span><strong>' + escapeHtml(change.competitive_narrative || '-') + '</strong></div>' +
          '<div><span>MSL 准备</span><strong>' + escapeHtml(change.msl_action || '-') + '</strong></div>' +
        '</div>' +
        '<div class="pmid-row">' + renderRefLinks(change.references, 3) + '</div>' +
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

  function renderTrialLinks(trials, limit) {
    trials = trials || [];
    if (!trials.length) return '<span class="muted-text">暂无 NCT</span>';
    return trials.slice(0, limit || 3).map(function(trial) {
      return '<a class="pmid-chip" href="' + escapeHtml(trial.url || ('https://clinicaltrials.gov/study/' + trial.nct_id)) +
        '" target="_blank" rel="noopener">' + escapeHtml(trial.nct_id || 'NCT') + '</a>';
    }).join('');
  }

  function renderPhaseSteps(stageNumber) {
    stageNumber = Number(stageNumber || 0);
    return '<div class="phase-stepper" aria-label="开发阶段">' + [1, 2, 3, 4].map(function(step) {
      var cls = step < stageNumber ? 'done' : step === stageNumber ? 'active' : '';
      return '<span class="' + cls + '">' + step + '</span>';
    }).join('') + '</div>';
  }

  function renderTargetGroupCell(items) {
    var first = items[0] || {};
    var targets = {};
    items.forEach(function(item) {
      if (item.target) targets[item.target] = true;
    });
    var tags = Object.keys(targets).slice(0, 5).map(function(target) {
      return '<em>' + escapeHtml(target) + '</em>';
    }).join('');
    return '<td class="target-group-cell" rowspan="' + escapeHtml(items.length) + '">' +
      '<strong>' + escapeHtml(first.target_type || '待补充') + '</strong>' +
      '<span>' + escapeHtml(items.length) + ' 个药物</span>' +
      '<div>' + tags + '</div>' +
    '</td>';
  }

  function renderClinicalPipelineRows(rows) {
    var groups = [];
    rows.forEach(function(item) {
      var last = groups[groups.length - 1];
      if (!last || last.key !== item.target_type) {
        groups.push({ key: item.target_type, items: [item] });
      } else {
        last.items.push(item);
      }
    });
    return groups.map(function(group) {
      return group.items.map(function(item, index) {
        var keyTrial = item.key_trial || (item.trials || [])[0] || {};
        var targetCell = index === 0 ? renderTargetGroupCell(group.items) : '';
        return '<tr>' +
          targetCell +
          '<td><strong>' + escapeHtml(item.name) + '</strong><br><span>' + escapeHtml((item.sponsors || []).join(' / ') || item.sponsor_hint || '-') + '</span></td>' +
          '<td>' + escapeHtml(item.indication || 'Myasthenia Gravis') + '<br><span>' + escapeHtml(item.population || '未标注') + '</span></td>' +
          '<td><div class="trial-title">' + escapeHtml(keyTrial.title || '-') + '</div><div class="pmid-row">' + renderTrialLinks(item.trials, 2) + '</div></td>' +
          '<td>' + renderPhaseSteps(item.stage_number) + '<strong class="phase-label">' + escapeHtml(item.highest_phase_label || '-') + '</strong><br><span>' + escapeHtml(item.status_summary || '-') + ' · ' + escapeHtml(item.study_count || 0) + ' 项</span></td>' +
          '<td>' + escapeHtml(keyTrial.start || '-') + '</td>' +
          '<td>' + escapeHtml(keyTrial.primary_completion || '-') + '</td>' +
          '<td>' + escapeHtml(keyTrial.completion || '-') + '<br><span>更新 ' + escapeHtml(item.latest_update || '-') + '</span></td>' +
        '</tr>';
      }).join('');
    }).join('');
  }

  function renderClinicalPipelineMatrix() {
    var rows = data.clinical_pipeline_matrix || [];
    var meta = data.clinical_pipeline_meta || {};
    var box = $('clinicalPipelineMatrix');
    if (!box) return;
    var metaBox = $('clinicalPipelineMeta');
    if (metaBox) {
      metaBox.textContent = (meta.source || 'ClinicalTrials.gov') + ' · ' +
        (meta.generated_at || '-') + ' · ' + (meta.item_count || rows.length || 0) + ' 个对象';
    }
    if (!rows.length) {
      box.innerHTML = '<div class="kg-empty-hint">暂无符合条件的 Phase II+ 临床开发管线。</div>';
      return;
    }
    box.innerHTML = '<table><tr><th>靶点类型</th><th>药物</th><th>适应症/人群</th><th>关键试验</th><th>最高阶段</th><th>开始</th><th>Readout</th><th>结束</th></tr>' +
      renderClinicalPipelineRows(rows) + '</table>';
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
        (answer.anchor_nodes || []).join(' ')
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
        return '<a class="mini-chip chip-button" href="/MA-MG-HUB/pages/knowledge.html?node=' + escapeHtml(node) + '">' + escapeHtml(node) + '</a>';
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
        '<p class="answer-limitation">' + escapeHtml(answer.abstract_limitation || '') + '</p>' +
      '</article>';
    }).join('');
  }

  function bindAnswerFilters() {
    ['answerSearch', 'answerCategory', 'answerStance'].forEach(function(id) {
      var el = $(id);
      if (el) el.addEventListener(id === 'answerSearch' ? 'input' : 'change', renderAnswers);
    });
  }

  function init() {
    bindTabs();
    renderBadge();
    renderStats();
    renderMonthlyChanges();
    renderCompetitiveMatrix();
    renderClinicalPipelineMatrix();
    renderChinaLandscape();
    populateAnswerFilters();
    bindAnswerFilters();
    renderAnswers();
  }

  init();
})();
