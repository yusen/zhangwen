// Read-only production smoke test: project lists are masked and selections stay
// in this disposable browser context. No project, model or device write occurs.
import { chromium } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const faults = [];
  page.on('pageerror', error => faults.push(error.message));
  await page.route('**/api/projects', route => {
    if (route.request().method() !== 'GET') throw new Error('Unexpected production write');
    return route.fulfill({ json: { projects: [] } });
  });
  await page.goto('http://127.0.0.1:3080/');
  await page.getByRole('button', { name: '主控板', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: /行空板 K10/ }).click();
  await page.getByRole('button', { name: '添加模块', exact: true }).click();
  const checkboxes = page.getByRole('checkbox');
  const count = await checkboxes.count();
  if (count !== 68) throw new Error(`Expected 68 modules, got ${count}`);
  if (!await checkboxes.first().isEnabled()) throw new Error('Scratch checkbox disabled');
  const filters = page.getByRole('group', { name: '模块类型' });
  await filters.getByRole('button', { name: /输入模块/ }).click();
  const inputs = await checkboxes.count();
  if (inputs !== 54) throw new Error('Expected 54 input modules');
  await page.getByRole('checkbox', { name: /选择DFRobot DFR0033/ }).check();
  await page.getByRole('checkbox', { name: /选择DFRobot SEN0248/ }).check();
  await filters.getByRole('button', { name: /输出模块/ }).click();
  const outputs = await checkboxes.count();
  if (outputs !== 14) throw new Error('Expected 14 output modules');
  await page.getByRole('checkbox', { name: /选择DFR0486/ }).check();
  await page.getByRole('checkbox', { name: /选择DFRobot SER0006/ }).check();
  await filters.getByRole('button', { name: /全部模块/ }).click();
  const layouts = [];
  for (const width of [1440, 375]) {
    await page.setViewportSize({ width, height: 900 });
    await page.locator('.sensor-picker-list').evaluate(node => { node.scrollTop = node.scrollHeight; });
    const layout = await page.evaluate(() => {
      const list = document.querySelector('.sensor-picker-list');
      const search = document.querySelector('.picker-search').getBoundingClientRect();
      const action = document.querySelector('.sensor-picker-actions').getBoundingClientRect();
      return { width: innerWidth, overflow: document.documentElement.scrollWidth > innerWidth,
        listScrolls: list.scrollHeight > list.clientHeight,
        cardHeight: document.querySelector('.sensor-picker-list .module-card').getBoundingClientRect().height,
        searchVisible: search.top >= 0 && search.bottom <= innerHeight,
        actionVisible: action.top >= 0 && action.bottom <= innerHeight };
    });
    await page.locator('.sensor-picker-list').evaluate(node => { node.scrollTop = 0; });
    await page.screenshot({ path: `docs/mu-module-picker-${width}.png` });
    if (layout.overflow || !layout.listScrolls || layout.cardHeight < 230 || !layout.searchVisible || !layout.actionVisible) throw new Error(JSON.stringify(layout));
    layouts.push(layout);
  }
  await page.getByRole('button', { name: '加入所选模块' }).click();
  await page.setViewportSize({ width: 1440, height: 900 });
  if (await page.locator('.selected-sensor-list .hardware-card').count() !== 4) throw new Error('Selection not added');
  await page.reload();
  await page.locator('.selected-sensor-list .hardware-card').first().waitFor();
  if (await page.locator('.selected-sensor-list .hardware-card').count() !== 4) throw new Error('Scratch not restored');
  await page.screenshot({ path: 'docs/mu-module-project-1440.png' });
  await page.setViewportSize({ width: 375, height: 900 });
  await page.getByRole('button', { name: '硬件库', exact: true }).click();
  await page.screenshot({ path: 'docs/mu-module-project-375.png', fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('button', { name: '添加模块', exact: true }).click();
  await page.getByRole('textbox', { name: '搜索硬件' }).fill('SEN0193');
  if (await page.getByRole('checkbox').count() !== 1) throw new Error('Search incorrect');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '主控板', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: /Seeed Studio XIAO ESP32S3 Sense/ }).click();
  await page.getByRole('button', { name: '添加模块', exact: true }).click();
  if (await page.getByRole('checkbox').count() !== 0) throw new Error('DFRobot leaked into Grove');
  if (faults.length) throw new Error(faults.join('\n'));
  const report = { moduleCount: count, inputCount: inputs, outputCount: outputs, scratchSelection: true, scratchReload: true,
    search: true, groveIsolation: true, pageErrors: faults, layouts };
  await writeFile('docs/module-ui-smoke.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally {
  await browser.close();
}
