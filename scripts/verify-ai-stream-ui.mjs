// Production bundle, read-only API access. Generation/project writes are mocked.
import { chromium } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

const browser = await chromium.launch({ channel: 'msedge' });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [], layouts = [];
let project, mockedWrites = 0;
page.on('pageerror', error => errors.push(error.message));
await page.route('**/api/**', async route => {
  const request = route.request(), path = new URL(request.url()).pathname;
  if (request.method() !== 'GET') {
    mockedWrites++;
    if (path === '/api/projects') {
      const input = request.postDataJSON();
      project = { ...input, id: 'ui-smoke-only', revision: 1, checksum: '', updatedAt: '', messages: [] };
      return route.fulfill({ status: 201, json: project });
    }
    return route.abort();
  }
  if (path === '/api/session') {
    const response = await route.fetch();
    return route.fulfill({ json: { ...await response.json(), aiConfigured: true } });
  }
  if (path === '/api/projects') return route.fulfill({ json: { projects: [] } });
  if (path === '/api/projects/ui-smoke-only') return route.fulfill({ json: project });
  return route.continue();
});
try {
  await page.clock.install();
  await page.goto('http://127.0.0.1:3080/');
  const editor = page.getByRole('textbox', { name: 'MicroPython 代码编辑器' });
  await editor.fill('print("preserved draft")\n');
  await page.evaluate(() => {
    const original = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      if (!String(input).endsWith('/chat')) return original(input, init);
      return new Response(new ReadableStream({ start(controller) {
        controller.enqueue(new TextEncoder().encode('{"type":"status","phase":"waiting"}\n'));
        init.signal.addEventListener('abort', () => controller.error(new DOMException('Cancelled', 'AbortError')));
      } }), { headers: { 'content-type': 'application/x-ndjson' } });
    };
  });
  await page.getByLabel('发送给掌问 AI').fill('只读界面验收');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await page.getByRole('button', { name: '取消生成', exact: true }).waitFor();
  await page.clock.fastForward(21_000);
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark') await page.getByRole('button', { name: '切换深色主题' }).click();
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 900 });
      if (width === 375) await page.getByRole('button', { name: '掌问 AI', exact: true }).click();
      const progress = page.locator('.ai-progress');
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      if (overflow || !await progress.getByRole('button', { name: '取消生成' }).isVisible()) throw new Error('AI progress layout failed');
      if (!(await progress.innerText()).includes('供应商暂未返回正文')) throw new Error('Slow-provider hint missing');
      await page.screenshot({ path: `docs/ai-waiting-${theme}-${width}.png`, fullPage: true });
      layouts.push({ theme, width, overflow, cancelVisible: true, slowProviderHint: true });
    }
  }
  await page.getByRole('button', { name: '取消生成', exact: true }).click();
  await page.locator('.chat-error').getByText(/已取消/).waitFor();
  if (errors.length) throw new Error(JSON.stringify(errors));
  await writeFile('docs/ai-stream-ui-smoke.json', JSON.stringify({ layouts, pageErrors: errors, productionWrites: 0, mockedWrites, realProvider: false }, null, 2));
  console.log(JSON.stringify({ layouts, pageErrors: errors, productionWrites: 0, mockedWrites }));
} finally { await browser.close(); }
