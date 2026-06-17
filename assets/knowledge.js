/* MA-MG-HUB 知识库 */
(function() {
  'use strict';

  var articles = window.MG_LITERATURE_DATA || [];
  var experts = (window.MG_EXPERT_PROFILES && window.MG_EXPERT_PROFILES.experts) || [];
  var questions = (window.MG_LANDSCAPE_DATA && window.MG_LANDSCAPE_DATA.evidence_questions) || [];
  var input = document.getElementById('knowledgeSearch');
  var elArticles = document.getElementById('knowledgeArticles');
  var elExperts = document.getElementById('knowledgeExperts');
  var elQuestions = document.getElementById('knowledgeQuestions');
  var badge = document.getElementById('knowledgeBadge');

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function haystackArticle(article) {
    return [
      article.title,
      article.abstract,
      article.journal,
      (article.authors || []).join(' '),
      (article.study_types || []).join(' '),
      article.evidence_level,
      article.pmid
    ].join(' ').toLowerCase();
  }

  function haystackExpert(expert) {
    return [
      expert.name_en,
      expert.affiliation,
      (expert.public_tags || []).join(' '),
      (expert.interests || []).map(function(item) { return item.term; }).join(' ')
    ].join(' ').toLowerCase();
  }

  function render() {
    var keyword = (input.value || '').trim().toLowerCase();
    var articleList = articles.filter(function(item) {
      return !keyword || haystackArticle(item).indexOf(keyword) !== -1;
    }).slice(0, 12);
    var expertList = experts.filter(function(item) {
      return !keyword || haystackExpert(item).indexOf(keyword) !== -1;
    }).slice(0, 10);
    var questionList = questions.filter(function(item) {
      var text = [item.question, item.summary, JSON.stringify(item.references || [])].join(' ').toLowerCase();
      return !keyword || text.indexOf(keyword) !== -1;
    }).slice(0, 8);

    elArticles.innerHTML = articleList.length ? articleList.map(renderArticle).join('') : empty('暂无匹配文献');
    elExperts.innerHTML = expertList.length ? expertList.map(renderExpert).join('') : empty('暂无匹配专家');
    elQuestions.innerHTML = questionList.length ? questionList.map(renderQuestion).join('') : empty('暂无匹配问题');
  }

  function renderArticle(article) {
    var tags = [
      article.evidence_level ? '证据 ' + article.evidence_level : '未分类',
      article.china_related ? '中国相关' : ''
    ].filter(Boolean).map(function(tag) {
      return '<span class="mini-chip">' + escapeHtml(tag) + '</span>';
    }).join('');
    return '<article class="compact-article">' +
      '<a href="' + article.url + '" target="_blank">' + escapeHtml(article.title || '(无标题)') + '</a>' +
      '<div>' + escapeHtml(article.journal || 'Unknown') + ' · PMID ' + escapeHtml(article.pmid || '-') + '</div>' +
      '<div class="chip-row">' + tags + '</div>' +
    '</article>';
  }

  function renderExpert(expert) {
    var metrics = expert.metrics || {};
    return '<article class="expert-row compact">' +
      '<strong>' + escapeHtml(expert.name_en) + '</strong>' +
      '<div>' + escapeHtml(expert.affiliation || '机构待识别') + '</div>' +
      '<div class="metric-line">发文 ' + (metrics.total_publications || 0) + ' · 近3年 ' + (metrics.recent_3y_publications || 0) + '</div>' +
      '<div class="chip-row">' + (expert.public_tags || []).slice(0, 4).map(function(tag) { return '<span class="mini-chip">' + escapeHtml(tag) + '</span>'; }).join('') + '</div>' +
    '</article>';
  }

  function renderQuestion(item) {
    return '<article class="evidence-question-card">' +
      '<div class="question-head"><strong>' + escapeHtml(item.question) + '</strong><span>' + (item.verified ? '已核实' : '待核实') + '</span></div>' +
      '<p>' + escapeHtml(item.summary || '') + '</p>' +
      '<div class="chip-row">' + (item.references || []).slice(0, 4).map(function(ref) { return '<span class="mini-chip">PMID ' + escapeHtml(ref.pmid) + '</span>'; }).join('') + '</div>' +
    '</article>';
  }

  function empty(text) {
    return '<div class="empty-state small"><h3>' + escapeHtml(text) + '</h3></div>';
  }

  input.addEventListener('input', render);
  if (badge) badge.textContent = articles.length + ' 篇文献 · ' + experts.length + ' 位专家 · ' + questions.length + ' 个问题';
  render();
})();
