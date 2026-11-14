// 用无头浏览器实际加载 viewer.html，走一遍用户 journey 并断言；任何断言失败或页面脚本异常都以非零状态退出。
// 运行：node check_viewer.js [截图路径]
// 预期值来自 make_sample_traces.py 的构造：4 条 run，2 条失败；run-messy-log 有 7 步；run-audit-cases 有 11 步。
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1300, height: 800 } });
  page.setDefaultTimeout(5000);
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  await page.goto('file://' + path.resolve(__dirname, 'viewer.html'));
  let n = 0; const failures = [];
  const eq = (name, got, want) => { n++; const ok = JSON.stringify(got) === JSON.stringify(want);
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}: ${JSON.stringify(got)}`);
    if (!ok) failures.push(`${name}: expected ${JSON.stringify(want)}, got ${JSON.stringify(got)}`); };
  // 一组操作出错（例如元素不存在）时记为失败并继续，这样一次运行能看到所有失败项
  const group = async (name, fn) => { try { await fn(); } catch (e) { n++; failures.push(`${name}: ${String(e).split('\n')[0]}`); console.log(`FAIL ${name}: threw`); } };
  const count = sel => page.locator(sel).count();
  const runCount = () => count('#runs [data-run]');
  const search = q => page.fill('#query', q);
  const ENTITY = /&(quot|lt|gt|amp);/;                               // 页面可见文本里出现字面的实体 = 高亮破坏了转义

  await group('journey 1-5', async () => {
    eq('runs_all', await runCount(), 4);
    await page.selectOption('#filter', 'failed');                    // 1 筛选失败运行
    eq('runs_failed', await runCount(), 2);
    await page.click('#runs [data-run="run-messy-log"]');            // 2 打开轨迹
    eq('steps_messy', await count('#timeline [data-step]'), 7);
    const badges = await page.locator('#timeline .badge.warn').allTextContents();
    for (const flag of ['truncated_output', 'duplicate_result', 'orphan_result', 'missing_result']) eq('flag badge ' + flag, badges.includes(flag), true);
    await page.click('#timeline [data-step="6"]');                   // 3 找异常工具调用
    eq('detail_has_missing', (await page.locator('#detail pre').textContent()).includes('missing_result'), true);
    eq('failed_checks', await count('#detail td.bad'), 2);           // 4 查看评分证据
    await search('policy_blocked');                                  // 搜索
    eq('runs_after_search', await runCount(), 1);
    eq('marks', await count('#timeline mark'), 1);
    await search('');
    await page.selectOption('#filter', 'all');
    await page.click('#runs [data-run="run-wrong-order"]');
    await page.selectOption('#compare', 'run-ok');                   // 5 对比另一条运行
    eq('diverge_rows', await count('#timeline .row.diverge'), 2);
    await page.screenshot({ path: process.argv[2] || 'viewer_check.png' });
  });

  await group('#20 compare right column', async () => {              // 仍在对比视图：左 run-wrong-order，右 run-ok
    const right = '#timeline .cols > div:nth-child(2)';
    eq('#20 right column has no data-step', await count(right + ' [data-step]'), 0);
    await page.locator(right + ' .row').first().click();
    eq('#20 click on right column selects nothing', await count('#detail pre'), 0);
    await page.click('#timeline .cols > div:nth-child(1) [data-step="2"]');
    eq('#20 click on left column selects own step', (await page.locator('#detail pre').textContent()).includes('"B1"'), true);
    await page.selectOption('#compare', '');
  });

  await group('#19 highlight inside entities', async () => {         // 审计的复现：搜索 t，时间线出现字面的 &quot;
    await page.click('#runs [data-run="run-ok"]');
    await page.click('#timeline [data-step="1"]');
    await search('t');
    eq('#19 "t": timeline text has no literal entity', ENTITY.test(await page.locator('#timeline').textContent()), false);
    eq('#19 "t": detail text has no literal entity', ENTITY.test(await page.locator('#detail').textContent()), false);
    eq('#19 "t": something is highlighted', (await count('#timeline mark')) > 0, true);
  });

  await group('#19 queries with special characters', async () => {   // 只有 run-audit-cases 的用户消息含 "Jerry" <b>…</b> & co
    for (const q of ['"Jerry"', '<b>', '&', '"Jerry" <b>']) {
      await search(q);
      eq(`#19 ${q}: runs`, await runCount(), 1);
      eq(`#19 ${q}: first <mark> text in timeline`, await page.locator('#timeline mark').first().textContent(), q);
      eq(`#19 ${q}: timeline text has no literal entity`, ENTITY.test(await page.locator('#timeline').textContent()), false);
    }
    eq('#19 user text is not parsed as HTML', await count('#timeline .row b:text-is("urgent")'), 0);
    await page.click('#timeline [data-step="0"]');                   // 详情栏显示 JSON：引号显示为 \"，高亮仍然成立
    eq('#19 detail <mark> for a query with quotes', await page.locator('#detail pre mark').first().textContent(), '\\"Jerry\\" <b>');
  });

  await group('audit run', async () => {
    await search('');
    await page.click('#runs [data-run="run-audit-cases"]');
    eq('steps_audit', await count('#timeline [data-step]'), 11);
    const badges = await page.locator('#timeline .badge.warn').allTextContents();
    for (const flag of ['result_before_call', 'duplicate_call_id', 'ambiguous_pairing', 'unknown_event_type', 'conflicting_duplicate_result'])
      eq('flag badge ' + flag, badges.includes(flag), true);
    await page.selectOption('#filter', 'anomaly');
    eq('runs_anomaly', await runCount(), 2);
    await page.selectOption('#filter', 'all');
    await page.click('#runs [data-run="run-audit-cases"]');
    await page.selectOption('#compare', 'run-ok');                   // #21：verify_identity 的参数只是键顺序不同，不算分歧
    eq('#21 divergence position vs run-ok', (await page.locator('#timeline h2').textContent()).match(/位置 (\S+?)）/)[1], '2');
    await page.selectOption('#compare', '');
  });

  await group('search scope', async () => {
    await search('flags'); eq('search: JSON key name "flags" matches nothing', await runCount(), 0);
    await search('email'); eq('search: args key name "email" matches nothing', await runCount(), 0);
    await search('collateral');                                      // 检查项名称
    eq('search: check name', await runCount(), 3);
    eq('search: check name highlighted in detail', await count('#detail table mark'), 1);
    await search('claims_done'); eq('search: check evidence', await runCount(), 1);
    await search('');
  });

  eq('page_errors', errors, []);
  await browser.close();
  if (failures.length) { console.error(`CHECK FAILED: ${failures.length} of ${n} assertions\n  ` + failures.join('\n  ')); process.exit(1); }
  console.log(`CHECK PASSED: ${n} assertions`);
})().catch(e => { console.error('CHECK ERROR: ' + e); process.exit(1); });
