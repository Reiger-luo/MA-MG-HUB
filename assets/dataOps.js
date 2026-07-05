/* MA-MG-HUB 数据状态页 */
(function(){
    const hub = window.MgHub || {};
    const dashboard = window.MG_DASHBOARD_DATA || {};
    const stats = dashboard.stats || {};
    const status = window.MG_PIPELINE_STATUS || {};
    const communityAudit = window.MG_COMMUNITY_AUDIT || {};
    const graphHealth = window.MG_GRAPH_HEALTH || {};
    const topicCoverage = window.MG_WIKI_TOPIC_COVERAGE || {};
    const backendOptions = window.MG_BACKEND_OPTIONS || {};
    const communityTaxonomy = window.MG_COMMUNITY_TAXONOMY || {};
    const sourceList = document.getElementById('sourceList');
    const artifactGrid = document.getElementById('artifactGrid');
    const communityAuditGrid = document.getElementById('communityAuditGrid');
    const communityAuditNote = document.getElementById('communityAuditNote');
    const graphHealthGrid = document.getElementById('graphHealthGrid');
    const graphHealthNote = document.getElementById('graphHealthNote');
    const topicCoverageGrid = document.getElementById('topicCoverageGrid');
    const topicCoverageNote = document.getElementById('topicCoverageNote');
    const backendDecision = document.getElementById('backendDecision');
    const backendTriggerGrid = document.getElementById('backendTriggerGrid');
    const backendOptionGrid = document.getElementById('backendOptionGrid');
    const backendOptionNote = document.getElementById('backendOptionNote');
    const opsLog = document.getElementById('opsLog');
    const pipelineNote = document.getElementById('pipelineNote');
    const colorMap = { ok: 'green', generated: 'green', planned: 'yellow', manual: 'yellow', defer: 'yellow', missing: 'red' };
    const communityTitleById = {};
    (communityTaxonomy.communities || []).forEach(function(item) {
      communityTitleById[item.id] = item.title || item.id;
    });

    function escapeHtml(value) {
      if (hub.escapeText) return hub.escapeText(value);
      return String(value ?? '').replace(/[&<>"']/g, function(char) {
        return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
      });
    }

    function escapeClassToken(value, fallback) {
      if (!String(value || '').trim()) return fallback || '';
      if (hub.safeClassToken) return hub.safeClassToken(value, fallback);
      return String(value || fallback || 'unknown').replace(/[^a-zA-Z0-9_-]+/g, '-');
    }

    function escapeHref(value, fallback) {
      if (hub.safeUrl) return hub.safeUrl(value, fallback || '#');
      return escapeHtml(value || fallback || '#');
    }

    function pagePath(path) {
      return hub.pageUrl ? hub.pageUrl(path) : path;
    }

    function compactNumber(value) {
      const number = Number(value || 0);
      if (number >= 10000) return (number / 10000).toFixed(1).replace(/\.0$/, '') + '万';
      return String(number);
    }

    function formatRate(value, total) {
      const number = Number(value || 0);
      const denominator = Number(total || 0);
      if (!denominator) return '0%';
      return (number / denominator * 100).toFixed(1).replace(/\.0$/, '') + '%';
    }

    function communityTitle(communityId) {
      return communityTitleById[communityId] || communityId;
    }

    function communityHref(communityId) {
      if (communityId) return escapeHref(pagePath('pages/knowledge.html?community=' + encodeURIComponent(communityId)));
      return escapeHref(pagePath('pages/knowledge.html?tab=communities'));
    }

    function renderSources() {
      const fallback = [
        {
          name: 'PubMed 近一年公开库',
          meta: (stats.recent_articles || 0) + ' 篇近1年文献 · ' + (stats.china_articles || 0) + ' 篇中国相关 · ' + (stats.signals || 0) + ' 条候选信号',
          status: 'ok',
          status_label: '正常'
        }
      ];
      const sources = status.sources || fallback;
      sourceList.innerHTML = sources.map(function(source) {
        const color = escapeClassToken(colorMap[source.status] || 'gray', 'gray');
        return '<div class="source-card">' +
          '<div class="source-info">' +
            '<div class="source-name">' + escapeHtml(source.name) + '</div>' +
            '<div class="source-meta">' + escapeHtml(source.meta) + '</div>' +
          '</div>' +
          '<div class="source-status"><span class="dot ' + color + '"></span>' + escapeHtml(source.status_label || source.status || '-') + '</div>' +
        '</div>';
      }).join('');
    }

    function renderPipelineNote() {
      const pipeline = status.pipeline || {};
      const command = pipeline.local_command || 'bash scripts/run-local-weekly-sync.sh';
      const workflow = pipeline.workflow || 'weekly-pipeline';
      const schedule = pipeline.schedule || '每周';
      const policy = pipeline.policy || '周更只处理新增公开文献。';
      const upstream = (pipeline.upstream_sync || []).map(function(item) {
        return '<br>• <strong>' + escapeHtml(item.label || item.id) + '</strong>：' + escapeHtml(item.handoff || item.note || '');
      }).join('');
      pipelineNote.innerHTML = '本地更新命令：<code>' + escapeHtml(command) + '</code>。GitHub Actions：' +
        escapeHtml(workflow) + '（' + escapeHtml(schedule) + '）。<br>' + escapeHtml(policy) + upstream;
    }

    function renderArtifacts() {
      const artifacts = status.artifacts || [];
      if (!artifacts.length) {
        artifactGrid.innerHTML = '<div class="artifact-item"><div class="artifact-name">暂无产物状态</div><div class="artifact-meta">等待 pipeline-status.js 生成</div></div>';
        return;
      }
      artifactGrid.innerHTML = artifacts.map(function(item) {
        const count = item.count === null || item.count === undefined ? '' : ' · ' + item.count + ' 条';
        const size = item.size_kb === null || item.size_kb === undefined ? '' : ' · ' + item.size_kb + ' KB';
        return '<div class="artifact-item">' +
          '<div class="artifact-name">' + escapeHtml(item.label) + '</div>' +
          '<div class="artifact-meta">' + escapeHtml(item.id) + count + size + '<br>更新时间 ' + escapeHtml(item.updated_at || '-') + '</div>' +
        '</div>';
      }).join('');
    }

    function renderLogs() {
      const logs = status.logs || ['pipeline-status.js 尚未生成；页面正在使用 Dashboard 兜底数据。'];
      opsLog.innerHTML = logs.map(function(line) {
        return '<div class="log-line">' + escapeHtml(line) + '</div>';
      }).join('');
    }

    function renderCommunityAudit() {
      const summary = communityAudit.summary || {};
      const health = communityAudit.health || {};
      const total = Number(summary.total_articles || 0);
      if (!Object.keys(summary).length) {
        communityAuditGrid.innerHTML = '<div class="community-audit-card warning"><span>社区层</span><strong>未生成</strong><em>等待 communityAudit.js</em></div>';
        communityAuditNote.textContent = '社区语义层尚未生成；运行周更管线后会自动重建。';
        return;
      }

      const statusLabel = { ok: '正常', needsReview: '待 Review', warning: '关注', missing: '缺失' }[health.status] || (health.status || '未知');
      const items = [
        { label: '总文献', value: compactNumber(total), note: 'PubMed full abstract 基线' },
        { label: '已归类', value: compactNumber(summary.assigned_articles), note: formatRate(summary.assigned_articles, total) },
        { label: '未归类', value: compactNumber(summary.unassigned_articles), note: formatRate(summary.unassigned_articles, total) },
        { label: '低置信度', value: compactNumber(summary.low_confidence_articles), note: formatRate(summary.low_confidence_articles, total), level: 'warning' },
        { label: '冲突归类', value: compactNumber(summary.conflict_articles), note: formatRate(summary.conflict_articles, total), level: 'warning' },
        { label: '近14天未归类', value: compactNumber(summary.recent_unassigned_articles), note: '新文献覆盖检查', level: summary.recent_unassigned_articles ? 'danger' : '' },
        { label: '审计状态', value: statusLabel, note: '规则基线需持续校准', level: health.status === 'needsReview' ? 'warning' : '' }
      ];

      communityAuditGrid.innerHTML = items.map(function(item) {
        return '<a class="community-audit-card ' + escapeClassToken(item.level || '', '') + '" href="' + communityHref('') + '">' +
          '<span>' + escapeHtml(item.label) + '</span>' +
          '<strong>' + escapeHtml(item.value) + '</strong>' +
          '<em>' + escapeHtml(item.note) + '</em>' +
        '</a>';
      }).join('');

      const oversized = (communityAudit.oversized_communities || []).slice(0, 3).map(function(item) {
        return '<a class="ops-inline-link" href="' + communityHref(item.community_id) + '">' +
          escapeHtml(communityTitle(item.community_id)) + ' ' + escapeHtml(item.article_count) + ' 篇</a>';
      }).join('；');
      const notes = (health.notes || []).join('；');
      communityAuditNote.innerHTML = escapeHtml(notes || '社区层 audit 已生成。') +
        (oversized ? '<br>需优先 review 的过大社区：' + oversized : '');
    }

    function renderGraphHealth() {
      const summary = graphHealth.summary || {};
      const health = graphHealth.health || {};
      if (!Object.keys(summary).length) {
        graphHealthGrid.innerHTML = '<div class="community-audit-card warning"><span>图谱健康</span><strong>未生成</strong><em>等待 graphHealth.js</em></div>';
        graphHealthNote.textContent = '图谱健康层尚未生成；运行 build-knowledge-data.py 后会自动重建。';
        return;
      }
      const graphHref = escapeHref('knowledge.html');
      const statusLabel = { ok: '正常', needsReview: '待 Review', warning: '关注', missing: '缺失' }[health.status] || (health.status || '未知');
      const items = [
        { label: '社区映射节点', value: compactNumber(summary.community_mapped_nodes) + '/' + compactNumber(summary.total_nodes), note: 'dominant community' },
        { label: '社区映射关系', value: compactNumber(summary.community_mapped_edges) + '/' + compactNumber(summary.total_edges), note: '证据矩阵可过滤' },
        { label: '过大节点', value: compactNumber(summary.oversized_nodes), note: '概念或边界需 review', level: summary.oversized_nodes ? 'warning' : '' },
        { label: '弱关系', value: compactNumber(summary.weak_edges), note: '低覆盖或低置信度', level: summary.weak_edges ? 'warning' : '' },
        { label: '陈旧节点', value: compactNumber(summary.stale_nodes), note: '365 天未更新', level: summary.stale_nodes ? 'warning' : '' },
        { label: '图谱状态', value: statusLabel, note: 'abstract-level graph', level: health.status === 'needsReview' ? 'warning' : '' }
      ];
      graphHealthGrid.innerHTML = items.map(function(item) {
        return '<a class="community-audit-card ' + escapeClassToken(item.level || '', '') + '" href="' + graphHref + '">' +
          '<span>' + escapeHtml(item.label) + '</span>' +
          '<strong>' + escapeHtml(item.value) + '</strong>' +
          '<em>' + escapeHtml(item.note) + '</em>' +
        '</a>';
      }).join('');

      const oversizedNodes = (graphHealth.oversized_nodes || []).slice(0, 4).map(function(item) {
        const suffix = item.dominant_community_title ? ' · ' + item.dominant_community_title : '';
        return escapeHtml(item.title + ' ' + item.article_count + ' 篇' + suffix);
      }).join('；');
      const notes = (health.notes || []).join('；');
      graphHealthNote.innerHTML = escapeHtml(notes || '图谱健康层已生成。') +
        (oversizedNodes ? '<br>过大节点样本：' + oversizedNodes : '');
    }

    function renderTopicCoverage() {
      const summary = topicCoverage.stats || {};
      if (!Object.keys(summary).length) {
        topicCoverageGrid.innerHTML = '<div class="community-audit-card warning"><span>专题覆盖</span><strong>未生成</strong><em>等待 wikiTopicCoverage.js</em></div>';
        topicCoverageNote.textContent = '专题社区覆盖尚未生成；运行 buildWikiTopicCoverage.py 后会自动重建。';
        return;
      }
      const totalCommunities = Number(summary.community_count || 0);
      const coveredCommunities = Number(summary.covered_community_count || 0);
      const uncoveredCommunities = Number(summary.uncovered_community_count || 0);
      const items = [
        { label: 'wiki 专题', value: compactNumber(summary.topic_count), note: 'curated-topics.js' },
        { label: '覆盖社区', value: compactNumber(coveredCommunities) + '/' + compactNumber(totalCommunities), note: formatRate(coveredCommunities, totalCommunities) },
        { label: '未覆盖社区', value: compactNumber(uncoveredCommunities), note: '策展补齐点', level: uncoveredCommunities ? 'warning' : '' },
        { label: '未映射专题', value: compactNumber(summary.uncovered_topic_count), note: '缺锚点或 PMID', level: summary.uncovered_topic_count ? 'warning' : '' },
        { label: '本周更新专题', value: compactNumber(summary.updated_topic_count), note: 'updatedEvidence' },
        { label: '归类来源', value: summary.assignment_source || '-', note: '后台连接层' }
      ];
      topicCoverageGrid.innerHTML = items.map(function(item) {
        return '<a class="community-audit-card ' + escapeClassToken(item.level || '', '') + '" href="' + escapeHref(pagePath('pages/landscape.html?tab=answers')) + '">' +
          '<span>' + escapeHtml(item.label) + '</span>' +
          '<strong>' + escapeHtml(item.value) + '</strong>' +
          '<em>' + escapeHtml(item.note) + '</em>' +
        '</a>';
      }).join('');

      const gaps = ((topicCoverage.gaps || {}).low_coverage_communities || []).slice(0, 4).map(function(item) {
        return '<a class="ops-inline-link" href="' + communityHref(item.community_id) + '">' +
          escapeHtml(item.title || communityTitle(item.community_id)) + ' ' + escapeHtml(item.topic_count || 0) + ' 个专题</a>';
      }).join('；');
      topicCoverageNote.innerHTML = '专题覆盖依据 wiki anchor nodes、PMID assignment 和 taxonomy 关键词生成。' +
        (gaps ? '<br>待补齐社区：' + gaps : '');
    }

    function renderBackendOptions() {
      const summary = backendOptions.summary || {};
      if (!Object.keys(summary).length) {
        backendDecision.innerHTML = '<div class="backend-decision-card"><strong>后端选项未生成</strong><p>等待 backendOptions.js；运行周更管线后会自动重建。</p></div>';
        backendTriggerGrid.innerHTML = '';
        backendOptionGrid.innerHTML = '';
        backendOptionNote.textContent = '';
        return;
      }

      backendDecision.innerHTML = '<div class="backend-decision-card">' +
        '<strong>' + escapeHtml(summary.status_label || '后端评估') + '：' + escapeHtml(summary.decision || '') + '</strong>' +
        '<p>' + escapeHtml(summary.reason || '') + '</p>' +
        '<p>触发条件：' + escapeHtml(summary.triggered_count || 0) + '/' + escapeHtml(summary.total_triggers || 0) +
        ' · 首个候选：' + escapeHtml(summary.first_backend_candidate || '-') +
        ' · 本地主控：' + escapeHtml(summary.operator_backend || '-') + '</p>' +
      '</div>';

      backendTriggerGrid.innerHTML = (backendOptions.triggers || []).map(function(item) {
        return '<div class="community-audit-card ' + (item.triggered ? 'warning' : '') + '">' +
          '<span>' + escapeHtml(item.label) + '</span>' +
          '<strong>' + escapeHtml(item.triggered ? '已触发' : '未触发') + '</strong>' +
          '<em>' + escapeHtml(item.evidence || '') + '</em>' +
        '</div>';
      }).join('');

      backendOptionGrid.innerHTML = (backendOptions.options || []).map(function(item) {
        return '<div class="backend-option-card">' +
          '<span>' + escapeHtml(item.fit || 'option') + '</span>' +
          '<strong>' + escapeHtml(item.name || item.id || '') + '</strong>' +
          '<em>' + escapeHtml(item.recommendation || '') + '</em>' +
        '</div>';
      }).join('');

      const rules = (backendOptions.decision_rules || []).slice(0, 3).join('；');
      backendOptionNote.textContent = rules || 'Phase 6 后端评估已生成。';
    }

    renderSources();
    renderPipelineNote();
    renderArtifacts();
    renderCommunityAudit();
    renderGraphHealth();
    renderTopicCoverage();
    renderBackendOptions();
    renderLogs();
  })();
