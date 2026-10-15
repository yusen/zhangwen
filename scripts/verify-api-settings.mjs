import { chromium } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
const browser = await chromium.launch({ channel: 'msedge' });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const faults = [];
page.on('pageerror', error => faults.push(error.message));
let writes = 0;
await page.route('**/api/**', async route => {
  if (route.request().method() !== 'GET') {
    writes++; await route.abort(); return;
  }
  if (new URL(route.request().url()).pathname === '/api/projects') {
    await route.fulfill({ json: { projects: [] } }); return;
  }
  await route.continue();
});
const layouts = [];
try {
  await page.goto('http://127.0.0.1:3080/');
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value; }, theme);
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 900 });
      await page.getByRole('button', { name: 'API 设置', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: 'API 设置', exact: true });
      await dialog.waitFor();
      const key = dialog.getByLabel('API Key');
      const models = await dialog.getByLabel('模型名称').locator('option').evaluateAll(options => options.map(option => option.value));
      if (!models.includes('deepseek-flash') || !models.includes('deepseek-v4-pro') || models.includes('deepseek-chat') || models.includes('deepseek-reasoner')) throw new Error('API model identifiers are outdated');
      const metrics = await key.evaluate(element => ({ password: element.type === 'password', empty: element.value === '', focused: document.activeElement === element }));
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      if (overflow || !metrics.password || !metrics.empty || !metrics.focused) throw new Error('API settings layout or key field failed');
      await page.screenshot({ path: `docs/api-settings-${theme}-${width}.png`, fullPage: true });
      await page.keyboard.press('Escape');
      if (await dialog.count()) throw new Error('Escape did not dismiss dialog');
      layouts.push({ theme, width, overflow, ...metrics, models });
    }
  }
  if (faults.length || writes) throw new Error('Unexpected errors or writes');
  const report = { layouts, pageErrors: faults, productionWrites: writes };
  await writeFile('docs/api-settings-ui-smoke.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally { await browser.close(); }
