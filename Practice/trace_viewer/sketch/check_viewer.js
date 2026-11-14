// 用无头浏览器实际加载 viewer.html，走一遍用户 journey 并断言；任何断言失败或页面脚本异常都以非零状态退出。
// 运行：node check_viewer.js [截图路径]
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1300, height: 800 } });
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  await page.goto('file://' + path.resolve(__dirname, 'viewer.html'));
  const out = {};
  out.runs_all = await page.locator('#runs [data-run]').count();
  await page.selectOption('#filter', 'failed');                      // 1 筛选失败运行
  out.runs_failed = await page.locator('#runs [data-run]').count();
  await page.click('#runs [data-run="run-messy-log"]');              // 2 打开轨迹
  out.steps_messy = await page.locator('#timeline [data-step]').count();
  out.flag_badges = await page.locator('#timeline .badge.warn').allTextContents();
  await page.click('#timeline [data-step="6"]');                     // 3 找异常工具调用
  out.detail_has_missing = (await page.locator('#detail pre').textContent()).includes('missing_result');
  out.failed_checks = await page.locator('#detail td.bad').count();  // 4 查看评分证据
  await page.fill('#query', 'policy_blocked');                       // 搜索
  out.runs_after_search = await page.locator('#runs [data-run]').allTextContents().then(a => a.length);
  out.marks = await page.locator('#timeline mark').count();
  await page.fill('#query', '');
  await page.selectOption('#filter', 'all');
  await page.click('#runs [data-run="run-wrong-order"]');
  await page.selectOption('#compare', 'run-ok');                     // 5 对比另一条运行
  out.diverge_rows = await page.locator('#timeline .row.diverge').count();
  await page.screenshot({ path: process.argv[2] || 'viewer_check.png' });
  out.page_errors = errors;
  await browser.close();
  // 预期值来自 raw_traces.json 的构造：3 条 run，2 条失败；run-messy-log 有 7 步与 4 种步骤级异常标记
  const expected = {
    runs_all: 3, runs_failed: 2, steps_messy: 7, detail_has_missing: true, failed_checks: 2,
    runs_after_search: 1, marks: 1, diverge_rows: 2, page_errors: [],
  };
  const failures = [];
  for (const [k, want] of Object.entries(expected)) {
    if (JSON.stringify(out[k]) !== JSON.stringify(want)) failures.push(`${k}: expected ${JSON.stringify(want)}, got ${JSON.stringify(out[k])}`);
  }
  for (const flag of ['truncated_output', 'duplicate_result', 'orphan_result', 'missing_result']) {
    if (!out.flag_badges.includes(flag)) failures.push(`flag badge missing: ${flag}`);
  }
  console.log(JSON.stringify(out, null, 1));
  if (failures.length) { console.error('CHECK FAILED:\n  ' + failures.join('\n  ')); process.exit(1); }
  console.log('CHECK PASSED: ' + (Object.keys(expected).length + 4) + ' assertions');
})().catch(e => { console.error('CHECK ERROR: ' + e); process.exit(1); });
