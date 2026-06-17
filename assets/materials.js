/* MA-MG-HUB 内容工坊 */
(function() {
  'use strict';

  var payload = window.MG_CONTENT_MODULES || { modules: [], templates: [], compliance_rules: [] };
  var modules = payload.modules || [];
  var templates = payload.templates || [];
  var selectedTemplateId = templates[0] ? templates[0].id : '';

  var el = {
    badge: document.getElementById('moduleBadge'),
    template: document.getElementById('templateSelect'),
    moduleList: document.getElementById('moduleList'),
    compliance: document.getElementById('complianceBox'),
    draft: document.getElementById('draftOutput')
  };

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function init() {
    el.template.innerHTML = templates.map(function(t) {
      return '<option value="' + t.id + '">' + escapeHtml(t.name) + '</option>';
    }).join('');
    el.template.value = selectedTemplateId;
    el.template.addEventListener('change', function() {
      selectedTemplateId = this.value;
      renderModules();
    });
    document.getElementById('btnCompose').addEventListener('click', composeDraft);
    if (el.badge) el.badge.textContent = modules.length + ' 个模块 · ' + templates.length + ' 个模板';
    renderModules();
  }

  function currentTemplate() {
    return templates.find(function(t) { return t.id === selectedTemplateId; }) || templates[0] || { modules: [] };
  }

  function renderModules() {
    var template = currentTemplate();
    var selected = new Set(template.modules || []);
    el.moduleList.innerHTML = modules.map(function(module) {
      var checked = selected.has(module.id) ? 'checked' : '';
      var status = module.verified ? '已核实' : (module.placeholder ? '占位' : '待核实');
      var claims = (module.claims || []).slice(0, 3).map(function(claim) {
        return '<li>' + escapeHtml(claim.text) + '<span>PMID ' + escapeHtml(claim.pmid || '-') + ' · ' + escapeHtml(claim.evidence_level || '未分类') + '</span></li>';
      }).join('');
      return '<article class="module-card">' +
        '<label class="module-check"><input type="checkbox" value="' + module.id + '" ' + checked + '> <strong>' + escapeHtml(module.title) + '</strong></label>' +
        '<div class="module-meta">' + escapeHtml(module.type) + ' · ' + escapeHtml(status) + ' · 更新 ' + escapeHtml(module.updated_at) + '</div>' +
        '<p>' + escapeHtml(module.summary || '') + '</p>' +
        '<ul>' + claims + '</ul>' +
      '</article>';
    }).join('');
    renderCompliance();
  }

  function selectedModules() {
    var ids = Array.from(el.moduleList.querySelectorAll('input[type="checkbox"]:checked')).map(function(input) {
      return input.value;
    });
    return modules.filter(function(module) { return ids.indexOf(module.id) !== -1; });
  }

  function renderCompliance() {
    var selected = selectedModules();
    var missingPmid = selected.some(function(module) {
      return (module.claims || []).some(function(claim) { return !claim.pmid; });
    });
    var unverified = selected.filter(function(module) { return !module.verified; }).length;
    var placeholders = selected.filter(function(module) { return module.placeholder; }).length;
    var rows = [
      { ok: !missingPmid, text: '所有声明绑定 PMID' },
      { ok: unverified === 0, text: unverified === 0 ? '模块已复核' : unverified + ' 个模块待医学/合规复核' },
      { ok: placeholders === 0, text: placeholders === 0 ? '无 placeholder 模块' : placeholders + ' 个 placeholder 模块' },
      { ok: false, text: '超说明书暗示需人工终审' }
    ];
    el.compliance.innerHTML = rows.map(function(row) {
      return '<div class="compliance-row ' + (row.ok ? 'ok' : 'warn') + '">' +
        '<span>' + (row.ok ? '通过' : '需处理') + '</span><strong>' + escapeHtml(row.text) + '</strong>' +
      '</div>';
    }).join('');
  }

  function composeDraft() {
    renderCompliance();
    var template = currentTemplate();
    var selected = selectedModules();
    var lines = [];
    lines.push('# ' + template.name);
    lines.push('');
    lines.push('生成时间：' + new Date().toLocaleString('zh-CN'));
    lines.push('状态：草稿，需医学/合规终审');
    lines.push('');
    selected.forEach(function(module, index) {
      lines.push('## ' + (index + 1) + '. ' + module.title);
      lines.push(module.summary || '');
      lines.push('');
      (module.claims || []).forEach(function(claim) {
        lines.push('- ' + claim.text + '（PMID: ' + (claim.pmid || '缺失') + '，证据等级: ' + (claim.evidence_level || '未分类') + '）');
      });
      lines.push('');
    });
    lines.push('## 合规提示');
    lines.push('- 所有内容仅为自动组装草稿。');
    lines.push('- verified=false 的模块不得直接对外使用。');
    lines.push('- 涉及适应症、疗效比较、安全性结论时需人工核查原文。');
    el.draft.value = lines.join('\n');
  }

  init();
})();
