/* MA-MG-HUB 视图路由：模块是同一条判断簇的切面，不是独立目录。
 * - 主导航只声明 4 个视图：evidence / experts / answers 三个工作视图 + toolbox 工具箱
 * - 页面仍按原文件维护，view 映射把视图名解析成「文件 + 页内标签」
 * - 侧边切换用 pushState 更新 ?view=，支持直接分享链接
 */
(function() {
  var VIEWS = [
    { key: 'evidence', label: '证据与格局', file: 'landscape', tabs: ['overview', 'matrix', 'guide'] },
    { key: 'experts', label: '专家与合作', file: 'knowledge', tabs: ['graph', 'china-network'] },
    { key: 'answers', label: '应答与准备', file: 'msl', tabs: ['experts', 'visit'], extra: [{ file: 'literature', tab: 'literature' }] },
    { key: 'toolbox', label: '工具箱', file: 'literature', tabs: ['trials', 'china', 'conference'], note: '审阅与管线' }
  ];

  function findView(key) {
    for (var i = 0; i < VIEWS.length; i++) if (VIEWS[i].key === key) return VIEWS[i];
    return null;
  }

  function currentPage() {
    var path = window.location.pathname || '';
    var m = path.match(/([a-z0-9-]+)\.html$/);
    return m ? m[1] : 'index';
  }

  function route(viewKey, tabKey) {
    var view = findView(viewKey) || VIEWS[0];
    var tab = tabKey || view.tabs[0];
    var file = view.file;
    // extra 里声明了标签所在的其它文件
    (view.extra || []).forEach(function(item) {
      if (item.tab === tab) file = item.file;
    });
    var base = file === 'index' ? './' : (currentPage() === 'index' ? 'pages/' : '') + file + '.html';
    return { href: base + '?view=' + encodeURIComponent(view.key) + '&tab=' + encodeURIComponent(tab), view: view };
  }

  function activeKey() {
    var params = new URLSearchParams(window.location.search || '');
    var explicit = params.get('view');
    if (explicit && findView(explicit)) return explicit;
    var page = currentPage();
    for (var i = 0; i < VIEWS.length; i++) {
      var v = VIEWS[i];
      if (v.file === page) return v.key;
      if ((v.extra || []).some(function(item) { return item.file === page; })) return v.key;
    }
    return 'evidence';
  }

  function renderBar() {
    var host = document.getElementById('viewBar');
    if (!host) return;
    var active = activeKey();
    host.innerHTML = VIEWS.map(function(view) {
      var r = route(view.key);
      var cls = 'view-chip' + (view.key === active ? ' active' : '');
      var hint = view.note ? '<em>' + view.note + '</em>' : '';
      return '<a class="' + cls + '" href="' + r.href + '" data-view="' + view.key + '">' +
        view.label + hint + '</a>';
    }).join('');
  }

  function init() {
    renderBar();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  window.MG_VIEWS = { views: VIEWS, find: findView, route: route, activeKey: activeKey, activePage: currentPage };
})();
