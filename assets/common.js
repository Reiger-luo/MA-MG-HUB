/* MA-MG-HUB 共用前端工具 */
(function () {
  'use strict';

  function stripTrailingSlash(value) {
    return String(value || '').replace(/\/+$/, '');
  }

  function detectBasePath() {
    if (typeof window.MG_HUB_BASE_PATH === 'string') {
      return stripTrailingSlash(window.MG_HUB_BASE_PATH);
    }
    var scripts = document.getElementsByTagName('script');
    for (var i = 0; i < scripts.length; i++) {
      var src = scripts[i].getAttribute('src') || '';
      if (src.indexOf('/assets/common.js') === -1 && src !== 'assets/common.js' && src !== '../assets/common.js') continue;
      try {
        var url = new URL(src, window.location.href);
        var pathname = url.pathname.replace(/\/assets\/common\.js$/, '');
        return pathname === '/' ? '' : stripTrailingSlash(pathname);
      } catch (err) {
        return '';
      }
    }
    var marker = '/MA-MG-HUB/';
    var index = window.location.pathname.indexOf(marker);
    return index === -1 ? '' : window.location.pathname.slice(0, index + marker.length - 1);
  }

  var basePath = detectBasePath();

  function escapeText(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[char];
    });
  }

  function safeClassToken(value, fallback) {
    var token = String(value == null ? '' : value).trim().replace(/[^a-zA-Z0-9_-]+/g, '-');
    return token || String(fallback || 'unknown');
  }

  function safeIdToken(value, fallback) {
    var token = safeClassToken(value, fallback || 'item');
    if (!/^[a-zA-Z]/.test(token)) token = 'id-' + token;
    return token;
  }

  function safeNumber(value, fallback) {
    var number = Number(value);
    return Number.isFinite(number) ? number : Number(fallback || 0);
  }

  function safePercent(value, fallback) {
    var number = Math.max(0, Math.min(100, safeNumber(value, fallback)));
    return escapeText(number);
  }

  function toPath(path) {
    var raw = String(path || '').trim();
    if (!raw) return basePath || '/';
    if (/^(https?:|obsidian:)?\/\//i.test(raw) || /^obsidian:/i.test(raw)) return raw;
    if (basePath && raw.indexOf(basePath + '/') === 0) return raw;
    if (raw.indexOf('/MA-MG-HUB/') === 0 && basePath !== '/MA-MG-HUB') {
      return (basePath || '') + raw.slice('/MA-MG-HUB'.length);
    }
    if (raw.charAt(0) === '/') return raw;
    if (!basePath && /\/pages\/[^/]*$/.test(window.location.pathname) && /^(assets|data|pages)\//.test(raw)) {
      return '../' + raw;
    }
    return (basePath ? basePath + '/' : '') + raw.replace(/^\.?\//, '');
  }

  function assetUrl(path) {
    return toPath(path);
  }

  function pageUrl(path) {
    return toPath(path);
  }

  function safeUrl(value, fallback) {
    var raw = String(value || '').trim();
    var fallbackUrl = fallback || '#';
    if (!raw) return escapeText(fallbackUrl);
    if (raw.charAt(0) === '#') return escapeText(raw);
    raw = toPath(raw);
    try {
      var resolved = new URL(raw, window.location.href);
      if (resolved.protocol === 'http:' || resolved.protocol === 'https:') {
        return escapeText(raw.charAt(0) === '/' ? raw : resolved.href);
      }
      if (resolved.protocol === 'obsidian:') {
        return escapeText(resolved.href);
      }
    } catch (err) {
      return escapeText(fallbackUrl);
    }
    return escapeText(fallbackUrl);
  }

  function loadScript(src, callback) {
    var finalSrc = /^(https?:)?\/\//i.test(src) ? src : assetUrl(src);
    var selectorSrc = finalSrc.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    var existing = document.querySelector('script[src="' + selectorSrc + '"]');
    if (existing && existing.getAttribute('data-loaded') === '1') {
      if (callback) callback(true);
      return;
    }
    if (existing && existing.getAttribute('data-loading') === '1') {
      if (callback) {
        existing.addEventListener('load', function () { callback(true); }, { once: true });
        existing.addEventListener('error', function () { callback(false); }, { once: true });
      }
      return;
    }
    var script = existing || document.createElement('script');
    script.src = finalSrc;
    script.setAttribute('data-loading', '1');
    script.onload = function () {
      script.setAttribute('data-loaded', '1');
      script.removeAttribute('data-loading');
      if (callback) callback(true);
    };
    script.onerror = function () {
      script.removeAttribute('data-loading');
      if (callback) callback(false);
    };
    if (!existing) document.head.appendChild(script);
  }

  function initTabs(options) {
    options = options || {};
    var tabAttr = options.tabAttr;
    if (!tabAttr) return null;
    var tabs = Array.prototype.slice.call(document.querySelectorAll('[' + tabAttr + ']'));
    if (!tabs.length) return null;
    var panelFor = options.panelFor || function (key) { return document.getElementById((options.panelPrefix || '') + key + (options.panelSuffix || '')); };
    var activeKey = options.initialKey || '';

    function setActive(key, shouldFocus) {
      activeKey = key;
      tabs.forEach(function (tab, index) {
        var tabKey = tab.getAttribute(tabAttr);
        var panel = panelFor(tabKey);
        var active = tabKey === key;
        var tabId = tab.id || tabAttr.replace(/^data-/, '') + '-tab-' + safeIdToken(tabKey, index);
        var panelId = panel ? (panel.id || tabAttr.replace(/^data-/, '') + '-panel-' + safeIdToken(tabKey, index)) : '';
        tab.id = tabId;
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
        tab.setAttribute('tabindex', active ? '0' : '-1');
        if (panelId) tab.setAttribute('aria-controls', panelId);
        tab.classList.toggle('active', active);
        if (panel) {
          panel.id = panelId;
          panel.setAttribute('role', 'tabpanel');
          panel.setAttribute('aria-labelledby', tabId);
          panel.classList.toggle('active', active);
          panel.hidden = !active;
        }
        if (active && shouldFocus) tab.focus();
      });
      if (options.onChange) options.onChange(key);
    }

    tabs.forEach(function (tab, index) {
      var key = tab.getAttribute(tabAttr);
      var panel = panelFor(key);
      if (tab.classList.contains('active') || (panel && panel.classList.contains('active'))) activeKey = activeKey || key;
      tab.addEventListener('click', function () { setActive(key, false); });
      tab.addEventListener('keydown', function (event) {
        var nextIndex = -1;
        if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = tabs.length - 1;
        if (nextIndex === -1) return;
        event.preventDefault();
        setActive(tabs[nextIndex].getAttribute(tabAttr), true);
      });
    });
    setActive(activeKey || tabs[0].getAttribute(tabAttr), false);
    return { activate: setActive, activeKey: function () { return activeKey; } };
  }

  window.MgHub = {
    basePath: basePath,
    escapeText: escapeText,
    escapeAttr: escapeText,
    safeClassToken: safeClassToken,
    safeIdToken: safeIdToken,
    safeNumber: safeNumber,
    safePercent: safePercent,
    safeUrl: safeUrl,
    assetUrl: assetUrl,
    pageUrl: pageUrl,
    loadScript: loadScript,
    initTabs: initTabs
  };
})();
