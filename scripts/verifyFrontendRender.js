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
  check('章节参考文献 16 条', refs.length === 16, refs.length);

  const corpus = textOf(document.querySelectorAll('.corpus-group > span'));
  check('中外语料只分中国 / 国际两组',
    corpus.length === 2 && corpus[0].indexOf('中国') === 0 && corpus[1].indexOf('国际') === 0,
    corpus.join(' / '));

  const cards = document.querySelectorAll('.guideline-divergence-card');
  check('中外指南共识差异 10 条', cards.length === 10, cards.length);

  const meta = document.querySelector('#guidelineDivergenceMetaRow');
  const metaText = meta ? meta.textContent : '';
  check('引文回验 43 / 43', metaText.indexOf('43 / 43') >= 0, metaText.slice(0, 140));
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

  const items = document.querySelectorAll('#majorEventsList .major-event-item');
  check('时间线 12 条', items.length === 12, items.length);

  const types = Array.from(new Set(textOf(document.querySelectorAll('#majorEventsList .major-event-type'))));
  const expected = ['获批/监管', '指南/共识', 'II/III期文献', 'III期', '试验信号'];
  check('五类事件齐全', expected.every((type) => types.indexOf(type) >= 0), types.join(' / '));

  const listText = document.querySelector('#majorEventsList')
    ? document.querySelector('#majorEventsList').textContent : '';
  check('德国共识进入时间线', listText.indexOf('Practical Guidance') >= 0, listText.slice(0, 120));

  const pubCount = textOf(document.querySelectorAll('#majorEventsList .major-event-type'))
    .filter((type) => type === 'II/III期文献').length;
  check('重点药物文献最多 4 席', pubCount <= 4, pubCount);
} catch (error) {
  check('情报中心页面运行时异常', false, String(error));
}

const ok = checks.every((item) => item.ok);
process.stdout.write(JSON.stringify({ ok: ok, checks: checks }, null, 2) + '\n');
process.exit(ok ? 0 : 1);
