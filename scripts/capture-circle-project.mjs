import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
const report = JSON.parse(readFileSync('docs/device-acceptance/real-com522.json', 'utf8'));
const browser = await chromium.launch({ channel: 'msedge' });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.route('**/api/**', async route => {
  if (route.request().method() !== 'GET') throw new Error('Capture must be read-only');
  await route.continue();
});
try {
  await page.goto('http://127.0.0.1:3080/');
  await page.getByRole('button', { name: '加载', exact: true }).click();
  await page.locator('.load-project-row').filter({ hasText: '掌控板2.0空心圆验收' }).click();
  await page.getByRole('textbox', { name: 'MicroPython 代码编辑器' }).filter({ hasText: 'oled.circle(64, 32, 24, 1)' }).waitFor();
  if (await page.evaluate(() => localStorage.getItem('mu-active-project')) !== report.projectId) throw new Error('Wrong project');
  await page.getByText('已保存 · v1', { exact: true }).waitFor();
  await page.screenshot({ path: 'docs/device-acceptance/circle-project.png', fullPage: true });
  console.log('Saved circle project renders correctly; read-only capture.');
} finally { await browser.close(); }
