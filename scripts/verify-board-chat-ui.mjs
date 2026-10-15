import { chromium } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
const browser = await chromium.launch({ channel: 'msedge' });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const errors = [];
let writes = 0;
page.on('pageerror', error => errors.push(error.message));
await page.route('**/api/**', async route => {
  if (route.request().method() !== 'GET') { writes++; await route.abort(); return; }
  if (new URL(route.request().url()).pathname === '/api/projects') { await route.fulfill({ json: { projects: [] } }); return; }
  await route.continue();
});
const layouts = [];
try {
  await page.goto('http://127.0.0.1:3080/');
  const editor = page.getByRole('textbox', { name: 'MicroPython 代码编辑器' });
  await editor.fill('print("local draft")\n');
  await page.getByLabel('发送给掌问 AI').fill('请帮我检查代码');
  const sendEnabledBeforeSave = await page.getByRole('button', { name: '发送', exact: true }).isEnabled();
  if (!sendEnabledBeforeSave) throw new Error('Unnamed project still prevents sending');
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark') await page.getByRole('button', { name: '切换深色主题' }).click();
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 900 });
      if (width === 375) await page.getByRole('button', { name: '硬件库', exact: true }).click();
      await page.getByRole('button', { name: '主控', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: '选择主控板', exact: true });
      await dialog.waitFor();
      const cards = await dialog.locator('.board-product-card').count();
      const image = dialog.locator('.board-product-image img');
      await image.evaluateAll(elements => Promise.all(elements.map(element => element.decode())));
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      const focus = await page.getByLabel('搜索主控板').evaluate(element => element === document.activeElement);
      if (cards !== 5 || overflow || !focus) throw new Error('Board picker layout failed');
      await page.screenshot({ path: `docs/board-picker-${theme}-${width}.png`, fullPage: true });
      await page.getByLabel('搜索主控板').fill('K10');
      if (await dialog.locator('.board-product-card').count() !== 1) throw new Error('Board search failed');
      await page.keyboard.press('Escape');
      await page.getByRole('button', { name: '文件', exact: true }).click();
      await page.getByRole('dialog', { name: '项目与设备文件' }).waitFor();
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error('Files overflow');
      if (await page.getByRole('button', { name: '刷新设备文件', exact: true }).isEnabled()) throw new Error('Disconnected device files enabled');
      await page.screenshot({ path: `docs/device-files-${theme}-${width}.png`, fullPage: true });
      await page.keyboard.press('Escape');
      layouts.push({ width, theme, cards, imageLoaded: true, overflow, searchFocused: focus, filesDialogVerified: true });
    }
  }
  await page.getByRole('button', { name: '主控', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: /行空板 K10/ }).click();
  await page.getByRole('button', { name: '添加模块', exact: true }).click();
  if (!await page.locator('.sensor-picker-context').textContent().then(text => text.includes('DFRobot'))) throw new Error('Board module family failed');
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '代码', exact: true }).click();
  if (!await editor.textContent().then(text => text.includes('local draft'))) throw new Error('Board choice overwrote code');
  if (errors.length || writes) throw new Error('Unexpected errors or production writes');
  const report = { sendEnabledBeforeSave, layouts, codePreserved: true, moduleFamily: 'DFRobot', pageErrors: errors, productionWrites: writes };
  await writeFile('docs/board-chat-ui-smoke.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally { await browser.close(); }
