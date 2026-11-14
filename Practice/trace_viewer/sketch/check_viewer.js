// 用无头浏览器实际加载 viewer.html，走一遍用户 journey 并断言。运行：node check_viewer.js
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
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
