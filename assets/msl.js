/* MA-MG-HUB MSL 工作台 */
(function() {
  'use strict';

  var profiles = (window.MG_EXPERT_PROFILES && window.MG_EXPERT_PROFILES.experts) || [];
  var signals = (window.MG_SIGNALS_DATA && window.MG_SIGNALS_DATA.signals) || [];
  var selectedExpertId = profiles[0] ? profiles[0].id : '';
  var selectedTopic = 'all';

  var el = {
    update: document.getElementById('mslUpdate'),
    search: document.getElementById('expertSearch'),
    topicFilters: document.getElementById('topicFilters'),
    expertCount: document.getElementById('expertCount'),
    expertList: document.getElementById('expertList'),
    expertDetail: document.getElementById('expertDetail'),
    visitExpert: document.getElementById('visitExpert'),
    visitType: document.getElementById('visitType'),
    visitBrief: document.getElementById('visitBrief'),
    visitTopic: document.getElementById('visitTopic'),
    expertView: document.getElementById('expertView'),
    materialRequest: document.getElementById('materialRequest'),
    followDeadline: document.getElementById('followDeadline'),
    followupList: document.getElementById('followupList'),
    saveNote: document.getElementById('visitSaveNote')
  };

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  function bindTabs() {
    var tabs = document.querySelectorAll('[data-msl-tab]');
    var panels = document.querySelectorAll('.intel-tab-panel');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener('click', function() {
        var key = this.getAttribute('data-msl-tab');
        for (var t = 0; t < tabs.length; t++) tabs[t].classList.remove('active');
        for (var p = 0; p < panels.length; p++) panels[p].classList.remove('active');
        this.classList.add('active');
        document.getElementById('msl-' + key).classList.add('active');
      });
    }
  }

  function topTopics() {
    var counts = {};
    for (var i = 0; i < profiles.length; i++) {
      var tags = profiles[i].public_tags || [];
      for (var j = 0; j < tags.length; j++) counts[tags[j]] = (counts[tags[j]] || 0) + 1;
    }
    return Object.keys(counts).sort(function(a, b) { return counts[b] - counts[a]; }).slice(0, 10);
  }

  function renderTopicFilters() {
    var topics = topTopics();
    var html = '<label class="filter-checkbox-item"><input type="radio" name="topic" value="all" checked> 全部</label>';
    for (var i = 0; i < topics.length; i++) {
      html += '<label class="filter-checkbox-item"><input type="radio" name="topic" value="' + escapeHtml(topics[i]) + '"> ' + escapeHtml(topics[i]) + '</label>';
    }
    el.topicFilters.innerHTML = html;
    el.topicFilters.addEventListener('change', function(e) {
      if (e.target && e.target.name === 'topic') {
        selectedTopic = e.target.value;
        renderExperts();
      }
    });
  }

  function filteredExperts() {
    var keyword = (el.search.value || '').trim().toLowerCase();
    return profiles.filter(function(expert) {
      var text = [
        expert.name_en,
        expert.name_zh,
        expert.affiliation,
        (expert.public_tags || []).join(' '),
        (expert.interests || []).map(function(x) { return x.term; }).join(' ')
      ].join(' ').toLowerCase();
      var topicOk = selectedTopic === 'all' || text.indexOf(selectedTopic.toLowerCase()) !== -1;
      return topicOk && (!keyword || text.indexOf(keyword) !== -1);
    });
  }

  function renderExperts() {
    var list = filteredExperts();
    el.expertCount.textContent = list.length;
    if (!list.length) {
      el.expertList.innerHTML = '<div class="empty-state"><h3>暂无匹配专家</h3></div>';
      return;
    }
    if (!list.some(function(item) { return item.id === selectedExpertId; })) selectedExpertId = list[0].id;
    el.expertList.innerHTML = list.slice(0, 60).map(renderExpertRow).join('');
    var cards = el.expertList.querySelectorAll('.expert-row');
    for (var i = 0; i < cards.length; i++) {
      cards[i].addEventListener('click', function() {
        selectedExpertId = this.getAttribute('data-expert-id');
        renderExperts();
        renderExpertDetail();
      });
    }
    renderExpertDetail();
  }

  function renderExpertRow(expert) {
    var metrics = expert.metrics || {};
    var tags = (expert.public_tags || []).slice(0, 3).map(function(tag) {
      return '<span class="mini-chip">' + escapeHtml(tag) + '</span>';
    }).join('');
    return '<article class="expert-row ' + (expert.id === selectedExpertId ? 'active' : '') + '" data-expert-id="' + expert.id + '">' +
      '<strong>' + escapeHtml(expert.name_en) + '</strong>' +
      '<div>' + escapeHtml(expert.affiliation || '机构待识别') + '</div>' +
      '<div class="metric-line">发文 ' + (metrics.total_publications || 0) + ' · 近3年 ' + (metrics.recent_3y_publications || 0) + ' · 最高IF ' + (metrics.highest_if || 0) + '</div>' +
      '<div class="chip-row">' + tags + '</div>' +
    '</article>';
  }

  function getSelectedExpert() {
    return profiles.find(function(item) { return item.id === selectedExpertId; }) || profiles[0];
  }

  function renderExpertDetail() {
    var expert = getSelectedExpert();
    if (!expert) {
      el.expertDetail.innerHTML = '<div class="empty-state"><h3>暂无专家数据</h3></div>';
      return;
    }
    var metrics = expert.metrics || {};
    var interests = (expert.interests || []).slice(0, 8).map(function(item) {
      var width = Math.min(100, Math.max(12, item.count * 8));
      return '<div class="interest-bar"><span>' + escapeHtml(item.term) + '</span><div><i style="width:' + width + '%"></i></div><strong>' + item.count + '</strong></div>';
    }).join('');
    var timeline = (expert.timeline || []).slice(0, 6).map(function(item) {
      return '<li><a href="' + item.url + '" target="_blank">' + escapeHtml(item.title) + '</a><span>' + escapeHtml(item.pub_date || item.entry_date || '') + ' · PMID ' + escapeHtml(item.pmid) + '</span></li>';
    }).join('');
    var collaborators = (expert.collaborators || []).slice(0, 6).map(function(item) {
      return '<span class="mini-chip">' + escapeHtml(item.name) + ' ' + item.count + '</span>';
    }).join('');
    el.expertDetail.innerHTML =
      '<div class="detail-title">' +
        '<h2>' + escapeHtml(expert.name_en) + '</h2>' +
        '<p>' + escapeHtml(expert.affiliation || '机构待识别') + '</p>' +
      '</div>' +
      '<div class="metric-grid">' +
        '<div><span>总发文</span><strong>' + (metrics.total_publications || 0) + '</strong></div>' +
        '<div><span>近3年</span><strong>' + (metrics.recent_3y_publications || 0) + '</strong></div>' +
        '<div><span>最高IF</span><strong>' + (metrics.highest_if || 0) + '</strong></div>' +
        '<div><span>中国相关</span><strong>' + (metrics.china_related || 0) + '</strong></div>' +
      '</div>' +
      '<h3>研究兴趣向量</h3>' + (interests || '<div class="muted">暂无主题</div>') +
      '<h3>主要合作者</h3><div class="chip-row">' + (collaborators || '<span class="muted">暂无数据</span>') + '</div>' +
      '<h3>近期文献时间线</h3><ol class="timeline-list">' + timeline + '</ol>';
  }

  function renderVisitOptions() {
    el.visitExpert.innerHTML = profiles.slice(0, 160).map(function(expert) {
      return '<option value="' + expert.id + '">' + escapeHtml(expert.name_en) + '</option>';
    }).join('');
    el.visitExpert.value = selectedExpertId;
    el.visitExpert.addEventListener('change', function() {
      selectedExpertId = this.value;
    });
  }

  function generateBrief() {
    var expert = profiles.find(function(item) { return item.id === el.visitExpert.value; }) || getSelectedExpert();
    if (!expert) return;
    var topicText = (expert.public_tags || []).join('、') || 'MG 研究';
    var relatedSignals = signals.filter(function(signal) {
      var joined = ((signal.keywords || []).join(' ') + ' ' + signal.summary).toLowerCase();
      return (expert.public_tags || []).some(function(tag) { return joined.indexOf(tag.toLowerCase()) !== -1; });
    }).slice(0, 3);
    if (!relatedSignals.length) relatedSignals = signals.slice(0, 3);
    el.visitBrief.innerHTML =
      '<h3>' + escapeHtml(el.visitType.value) + '简报 · ' + escapeHtml(expert.name_en) + '</h3>' +
      '<p><strong>专家概览：</strong>累计发文 ' + expert.metrics.total_publications + ' 篇，近 3 年 ' + expert.metrics.recent_3y_publications + ' 篇，研究关注 ' + escapeHtml(topicText) + '。</p>' +
      '<p><strong>建议开场：</strong>围绕近期 ' + escapeHtml(topicText) + ' 文献变化，确认专家当前关注的证据缺口与材料需求。</p>' +
      '<h4>可关联的近期信号</h4>' +
      '<ul>' + relatedSignals.map(function(s) {
        return '<li>' + escapeHtml(s.strength + '信号 · ' + s.summary) + '</li>';
      }).join('') + '</ul>' +
      '<h4>可追问问题</h4>' +
      '<ul><li>您目前最关注哪类 MG 患者的治疗证据？</li><li>现有材料中哪一类数据最影响临床接受度？</li><li>是否需要我们后续补充具体文献或安全性数据？</li></ul>';
  }

  function storageKey() {
    return 'MA_MG_HUB_VISITS';
  }

  function loadVisits() {
    try {
      return JSON.parse(localStorage.getItem(storageKey()) || '[]');
    } catch (e) {
      return [];
    }
  }

  function saveVisits(visits) {
    localStorage.setItem(storageKey(), JSON.stringify(visits));
  }

  function saveVisit() {
    var expert = profiles.find(function(item) { return item.id === el.visitExpert.value; }) || getSelectedExpert();
    if (!expert) return;
    var visits = loadVisits();
    var material = (el.materialRequest.value || '').trim();
    var record = {
      id: 'v_' + Date.now(),
      expert_id: expert.id,
      expert_name: expert.name_en,
      type: el.visitType.value,
      date: new Date().toISOString().slice(0, 10),
      topic: (el.visitTopic.value || '').trim(),
      expert_view: (el.expertView.value || '').trim(),
      material_request: material,
      deadline: el.followDeadline.value,
      status: material ? '待准备' : '已关闭'
    };
    visits.unshift(record);
    saveVisits(visits);
    el.saveNote.textContent = '已保存到本地工作台。';
    el.visitTopic.value = '';
    el.expertView.value = '';
    el.materialRequest.value = '';
    el.followDeadline.value = '';
    renderFollowups();
  }

  function renderFollowups() {
    var visits = loadVisits();
    var items = visits.filter(function(v) { return v.material_request; });
    if (!items.length) {
      el.followupList.innerHTML = '<div class="empty-state"><h3>暂无 Follow-up</h3><p>在拜访助手中录入材料需求后会出现在这里</p></div>';
      return;
    }
    items.sort(function(a, b) { return String(a.deadline || '9999').localeCompare(String(b.deadline || '9999')); });
    el.followupList.innerHTML = items.map(function(item) {
      var overdue = item.deadline && new Date(item.deadline) < new Date() && item.status !== '已关闭';
      return '<article class="followup-card ' + (overdue ? 'overdue' : '') + '">' +
        '<div><strong>' + escapeHtml(item.material_request) + '</strong><span>' + escapeHtml(item.expert_name) + ' · ' + escapeHtml(item.topic || '未填写主题') + '</span></div>' +
        '<div class="followup-meta"><span>' + escapeHtml(item.status) + '</span><span>截止 ' + escapeHtml(item.deadline || '未设置') + '</span></div>' +
        '<button class="btn" data-close-followup="' + item.id + '">标记关闭</button>' +
      '</article>';
    }).join('');
    var buttons = el.followupList.querySelectorAll('[data-close-followup]');
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener('click', function() {
        var id = this.getAttribute('data-close-followup');
        var visits = loadVisits();
        for (var j = 0; j < visits.length; j++) {
          if (visits[j].id === id) visits[j].status = '已关闭';
        }
        saveVisits(visits);
        renderFollowups();
      });
    }
  }

  function init() {
    bindTabs();
    renderTopicFilters();
    renderExperts();
    renderVisitOptions();
    renderFollowups();
    el.search.addEventListener('input', renderExperts);
    document.getElementById('btnGenerateBrief').addEventListener('click', generateBrief);
    document.getElementById('btnSaveVisit').addEventListener('click', saveVisit);
    document.getElementById('btnClearClosed').addEventListener('click', function() {
      saveVisits(loadVisits().filter(function(item) { return item.status !== '已关闭'; }));
      renderFollowups();
    });
    if (el.update) {
      el.update.textContent = '专家画像 ' + profiles.length + ' 位 · 本地闭环 MVP';
    }
  }

  init();
})();
