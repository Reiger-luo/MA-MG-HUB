#!/usr/bin/env node
/* 前端运行时冒烟：用 jsdom 真实执行页面脚本，覆盖 pytest 契约测试无法覆盖的渲染函数。
   检查诊治格局的分组章节 / 两侧语料 / 差异卡片，以及情报中心领域重大事件时间线。
   输出 JSON；全部通过退出 0，任一失败退出 1。 */
'use strict';

const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.resolve(__dirname, '..');
const read = (rel) => fs.readFileSync(path.join(ROOT, rel), 'utf8');
const checks = [];

function check(name, ok, detail) {
  checks.push({
    name: name,
    ok: Boolean(ok),
    detail: String(detail === undefined || detail === null ? '' : detail).slice(0, 240)
  });
}

function textOf(nodes) {
  return Array.from(nodes).map((node) => node.textContent.trim());
}

function bootPage(htmlRel, scriptRels, prelude) {
  // 去掉带 src 的 script，避免 jsdom 发起网络请求；数据脚本按顺序手动注入。
  const html = read(htmlRel).replace(/<script\b[^>]*\bsrc="[^"]*"[^>]*><\/script>/g, '');
  const dom = new JSDOM(html, {
    url: 'https://example.test/' + htmlRel,
    runScripts: 'outside-only',
    pretendToBeVisual: true
  });
  const win = dom.window;
  win.eval('window.MG_RELEASE_MANIFEST = ' + JSON.stringify({ run_id: 'frontend-smoke' }) + ';');
  if (prelude) win.eval(prelude);
  for (const rel of scriptRels) win.eval(read(rel));
  return doc(win);
}

function doc(win) {
  return win.document;
}

// ── 诊治格局：分组章节、两侧语料、差异卡片 ──
try {
  const document = bootPage('pages/landscape.html', [
    'assets/common.js',
    'data/landscape-data.js',
    'data/treatmentChapters.js',
    'data/clinicalQuestions.js',
    'data/landscapeKnowledgeReview.js',
    'assets/landscape.js'
  ]);
  const nav = textOf(document.querySelectorAll('#chapterNav .chapter-nav-item'));
  check('诊疗现状章节导航 7 章', nav.length === 7, nav.join(' / '));

  const targeted = Array.from(document.querySelectorAll('#chapterNav .chapter-nav-item'))
    .find((node) => node.textContent.indexOf('靶向生物制剂') >= 0);
  check('存在靶向生物制剂章节', Boolean(targeted), targeted ? targeted.textContent.trim() : '未找到');
  if (targeted) targeted.click();

  const groups = textOf(document.querySelectorAll('.chapter-statement-group > h4'));
  check('三层分组小标题（总定位/分类/重点药物）',
    groups.length === 3 && groups[0].indexOf('一、') === 0 &&
    groups[1].indexOf('二、') === 0 && groups[2].indexOf('三、') === 0,
    groups.join(' / '));

  const statements = Array.from(document.querySelectorAll('#chapterContent .evidence-statement'));
  check('该章陈述不少于 18 条', statements.length >= 18, statements.length);
  check('每条陈述带参考文献角标',
    statements.length > 0 && statements.every((node) => node.querySelector('sup.cite-mark')),
    statements.filter((node) => node.querySelector('sup.cite-mark')).length + ' / ' + statements.length);

  const refs = document.querySelectorAll('#chapterContent .chapter-refs li');
  check('章节参考文献 17 条', refs.length === 17, refs.length);

  const corpus = textOf(document.querySelectorAll('.corpus-group > span'));
  check('中外语料只分中国 / 国际两组',
    corpus.length === 2 && corpus[0].indexOf('中国') === 0 && corpus[1].indexOf('国际') === 0,
    corpus.join(' / '));

  const cards = document.querySelectorAll('.guideline-divergence-card');
  check('中外指南共识差异 10 条', cards.length === 10, cards.length);

  const meta = document.querySelector('#guidelineDivergenceMetaRow');
  const metaText = meta ? meta.textContent : '';
  check('引文回验 49 / 49', metaText.indexOf('49 / 49') >= 0, metaText.slice(0, 140));
  check('更新方式为周更联动', metaText.indexOf('周更发现新指南后联动刷新') >= 0, metaText.slice(0, 140));
} catch (error) {
  check('诊治格局页面运行时异常', false, String(error));
}

// ── 情报中心：领域重大事件时间线 ──
try {
  const document = bootPage('pages/literature.html', [
    'assets/common.js',
    'data/literature-recent.js',
    'data/signals-weekly.js',
    'data/communityTaxonomy.js',
    'data/clinical-trials-data.js',
    'assets/literature.js'
  ], read('data/source-signals.js'));

  const tab = Array.from(document.querySelectorAll('[data-tab]'))
    .find((node) => node.getAttribute('data-tab') === 'events');
  check('存在领域重大事件标签', Boolean(tab), tab ? tab.textContent.trim() : '未找到');
  if (tab) tab.click();

  const groups = document.querySelectorAll('#majorEventsList .major-event-group');
  const expected = ['获批/监管', '指南/共识', 'II/III期文献', 'III期', '试验信号'];
  const groupTitles = textOf(document.querySelectorAll('.major-event-group-title'));
  check('五类模块并列齐全', expected.every((type) => groupTitles.indexOf(type) >= 0), groupTitles.join(' / '));

  const listText = document.querySelector('#majorEventsList')
    ? document.querySelector('#majorEventsList').textContent : '';
  check('德国共识进入时间线', listText.indexOf('Practical Guidance') >= 0, listText.slice(0, 120));
  check('境外获批进入时间线', listText.indexOf('Livsayis') >= 0 && listText.indexOf('Klygefa') >= 0, '');

  const masonryCount = document.querySelectorAll('#majorEventsList .major-event-masonry').length;
  check('每个模块自带瀑布流容器', masonryCount === groups.length, masonryCount + ' / ' + groups.length);

  const perModule = Array.from(groups).map((group) => group.querySelectorAll('.major-event-item').length);
  check('每模块卡片不超过 8 条', perModule.every((n) => n > 0 && n <= 8), perModule.join(' / '));
  const pubGroup = Array.from(groups).find((g) =>
    g.querySelector('.major-event-group-title').textContent.trim() === 'II/III期文献');
  check('重点药物文献最多 4 席', pubGroup && pubGroup.querySelectorAll('.major-event-item').length <= 4,
    pubGroup ? pubGroup.querySelectorAll('.major-event-item').length : '无模块');

  const items = document.querySelectorAll('#majorEventsList .major-event-item');
  const twoLineCards = Array.from(items).every((item) =>
    item.children.length === 2 &&
    item.children[0].classList.contains('major-event-title') &&
    item.children[1].classList.contains('major-event-meta'));
  check('卡片仅标题+元信息两行', twoLineCards, items.length);
  const sourceLabeled = Array.from(items).every((item) => {
    const source = item.querySelector('.major-event-source');
    if (!source) return true;
    const label = source.querySelector('.major-event-source-label');
    return label && label.textContent.trim() === '来源' && source.textContent.trim().length > 2 &&
      !item.querySelector('.major-event-body') && !item.querySelector('.major-event-type');
  });
  check('来源带标签且不与标题混排', sourceLabeled, items.length);
  const moduleStripes = Array.from(groups).every((group) =>
    /major-event--(regulatory|guideline|publication|trial|signal)/.test(group.className));
  check('模块带语义色条类', moduleStripes, groups.length);
} catch (error) {
  check('情报中心页面运行时异常', false, String(error));
}

// ── 中国情报：柱形点击交叉筛选（mock ECharts 捕获 setOption 与 click handler） ──
try {
  const chinaJson = read('data/china-intelligence.js')
    .replace(/^window\.MG_CHINA_DATA\s*=\s*/, '')
    .replace(/;\s*$/, '');
  const chinaPrelude =
    'window.MG_CHINA_DATA = ' + chinaJson + ';\n' +
    'window.echarts = { init: function(el) {' +
      'var inst = { setOption: function(o){ this.option = o; },' +
      ' on: function(k,h){ this.handlers = this.handlers || {}; this.handlers[k] = h; },' +
      ' resize: function(){} };' +
      'if (!window.__chinaCharts) window.__chinaCharts = {};' +
      'window.__chinaCharts[el.id] = inst; return inst; } };\n';
  const chinaDoc = bootPage('pages/literature.html', [
    'assets/common.js',
    'data/literature-recent.js',
    'data/signals-weekly.js',
    'data/communityTaxonomy.js',
    'data/clinical-trials-data.js',
    'assets/literature.js'
  ], chinaPrelude);
  const chinaWin = chinaDoc.defaultView;
  const chinaTab = Array.from(chinaDoc.querySelectorAll('[data-tab]'))
    .find((node) => node.getAttribute('data-tab') === 'china');
  if (chinaTab) chinaTab.click();

  const filterBar = chinaDoc.querySelector('#chinaFilterBar');
  const chipTexts = () => textOf(chinaDoc.querySelectorAll('#chinaFilterBar .china-filter-chip'));
  const hitCount = () => Number((chinaDoc.querySelector('#chinaFilterCount').textContent.match(/\d+/) || [0])[0]);
  const topCount = (blockIndex) => {
    const blocks = chinaDoc.querySelectorAll('#chinaSourceList .source-block');
    return Number(blocks[blockIndex].querySelector('.rank-count-link').textContent);
  };
  const monthly = chinaWin.__chinaCharts && chinaWin.__chinaCharts.chinaMonthlyChart;
  const evidence = chinaWin.__chinaCharts && chinaWin.__chinaCharts.chinaEvidenceChart;
  const quartile = chinaWin.__chinaCharts && chinaWin.__chinaCharts.chinaQuartileChart;

  check('中国情报榜单初始 22 项', chinaDoc.querySelectorAll('#chinaSourceList .rank-list-item').length === 22,
    chinaDoc.querySelectorAll('#chinaSourceList .rank-list-item').length);
  check('图表实例全部初始化', Boolean(monthly && evidence && quartile));
  check('初始筛选状态条隐藏', filterBar && filterBar.hidden === true);
  const journal0 = topCount(0);
  const institution0 = topCount(1);

  if (monthly && monthly.handlers && monthly.handlers.click) {
    const labels = monthly.option.xAxis.data;
    const monthIndex = labels.findIndex((label) => String(label).replace('\n', '-') === '2026-03');
    monthly.handlers.click({ seriesType: 'bar', dataIndex: monthIndex });
    check('点击月份后显示筛选 chip', chipTexts().some((text) => text.indexOf('2026-03') >= 0), chipTexts().join(' / '));
    check('月份命中 18 篇', hitCount() === 18, chinaDoc.querySelector('#chinaFilterCount').textContent);
    check('期刊榜按月份重算', topCount(0) < journal0, journal0 + ' -> ' + topCount(0));
    check('机构榜按月份重算', topCount(1) < institution0, institution0 + ' -> ' + topCount(1));
  }

  if (evidence && evidence.handlers && evidence.handlers.click) {
    evidence.handlers.click({ seriesType: 'bar', dataIndex: 3 });
    const afterEvidence = hitCount();
    check('点击证据等级新增 chip', chipTexts().some((text) => text.indexOf('IV') >= 0), chipTexts().join(' / '));
    check('证据等级进一步收窄命中', afterEvidence > 0 && afterEvidence < 18, afterEvidence);
  }

  if (quartile && quartile.handlers && quartile.handlers.click) {
    const beforeQuartile = topCount(0);
    quartile.handlers.click({ seriesType: 'bar', dataIndex: 2 });
    check('点击分区新增 chip', chipTexts().some((text) => text.indexOf('3区') >= 0), chipTexts().join(' / '));
    check('分区联动期刊榜', topCount(0) <= beforeQuartile, beforeQuartile + ' -> ' + topCount(0));
    quartile.handlers.click({ seriesType: 'bar', dataIndex: 2 });
    check('再次点击同一分区取消筛选', !chipTexts().some((text) => text.indexOf('3区') >= 0), chipTexts().join(' / '));
  }

  chinaDoc.querySelector('#chinaFilterClear').click();
  check('清除全部后状态条隐藏', filterBar.hidden === true);
  check('清除全部后榜单恢复', topCount(0) === journal0 && topCount(1) === institution0,
    topCount(0) + ' / ' + topCount(1));

  if (evidence && evidence.handlers && evidence.handlers.click) {
    evidence.handlers.click({ seriesType: 'bar', dataIndex: 3 });
    check('独立点击证据等级即筛选期刊', topCount(0) < journal0, journal0 + ' -> ' + topCount(0));
    check('独立点击证据等级即筛选机构', topCount(1) < institution0, institution0 + ' -> ' + topCount(1));
    evidence.handlers.click({ seriesType: 'bar', dataIndex: 3 });
  }

  // 同维度多选：并集而非替换，跨维度仍为交集。
  if (monthly && monthly.handlers && monthly.handlers.click) {
    const labels = monthly.option.xAxis.data;
    const idxOf = (value) => labels.findIndex((label) => String(label).replace('\n', '-') === value);
    monthly.handlers.click({ seriesType: 'bar', dataIndex: idxOf('2026-03') });
    const singleHit = hitCount();
    const singleTop = topCount(0);
    monthly.handlers.click({ seriesType: 'bar', dataIndex: idxOf('2026-04') });
    check('月份多选保留两个 chip', chipTexts().length === 2, chipTexts().join(' / '));
    check('月份多选命中为并集 33 篇', hitCount() === 33, singleHit + ' + 15 -> ' + hitCount());
    check('月份多选期刊榜按并集重算', topCount(0) > singleTop, singleTop + ' -> ' + topCount(0));
    const marchChip = Array.from(chinaDoc.querySelectorAll('#chinaFilterBar .china-filter-chip'))
      .find((node) => node.textContent.indexOf('2026-03') >= 0);
    if (marchChip) marchChip.click();
    check('单独移除一个 chip 仅保留另一个', chipTexts().length === 1 && chipTexts()[0].indexOf('2026-04') >= 0,
      chipTexts().join(' / '));
    check('移除后命中回到单月 15 篇', hitCount() === 15, hitCount());
    monthly.handlers.click({ seriesType: 'bar', dataIndex: idxOf('2026-04') });
    check('取消最后一个月恢复无筛选', filterBar.hidden === true, chipTexts().join(' / '));
  }

  if (evidence && evidence.handlers && evidence.handlers.click) {
    evidence.handlers.click({ seriesType: 'bar', dataIndex: 3 });
    const ivHit = hitCount();
    evidence.handlers.click({ seriesType: 'bar', dataIndex: 2 });
    check('证据等级多选保留两个 chip', chipTexts().length === 2, chipTexts().join(' / '));
    check('证据等级多选命中为并集 129 篇', hitCount() === 129, ivHit + ' -> ' + hitCount());
    chinaDoc.querySelector('#chinaFilterClear').click();
  }

  if (quartile && quartile.handlers && quartile.handlers.click) {
    quartile.handlers.click({ seriesType: 'bar', dataIndex: 1 });
    quartile.handlers.click({ seriesType: 'bar', dataIndex: 2 });
    check('分区多选保留两个 chip', chipTexts().length === 2, chipTexts().join(' / '));
    check('分区多选命中为并集 164 篇', hitCount() === 164, hitCount());
    chinaDoc.querySelector('#chinaFilterClear').click();
  }
} catch (error) {
  check('中国情报联动运行时异常', false, String(error));
}

const ok = checks.every((item) => item.ok);
process.stdout.write(JSON.stringify({ ok: ok, checks: checks }, null, 2) + '\n');
process.exit(ok ? 0 : 1);
