import { test, expect } from '@playwright/test';

test('AI test checks form values without saving, separates generation failure, cancels and clears stale results', async ({ page }) => {
  await page.goto('/');
  const before = await (await page.request.get('/api/settings/ai')).json();
  const projects = await (await page.request.get('/api/projects')).json();
  await page.getByRole('button', { name: 'API 设置', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'API 设置', exact: true });
  await dialog.getByLabel('API Key').fill('unsaved-diagnostic-key');
  await dialog.getByLabel('模型名称').selectOption('deepseek-v4-pro');
  await page.evaluate(() => {
    const original = window.fetch.bind(window);
    const state = window as unknown as { diagTest: { emit: (event: unknown) => void; aborted: boolean; input: unknown } };
    window.fetch = async (input, init) => {
      if (!String(input).endsWith('/api/settings/ai/test')) return original(input, init);
      return new Response(new ReadableStream({ start(controller) {
        state.diagTest = {
          aborted: false, input: JSON.parse(String(init?.body)),
          emit(event) { controller.enqueue(new TextEncoder().encode(JSON.stringify(event) + '\n')); },
        };
        init?.signal?.addEventListener('abort', () => { state.diagTest.aborted = true; controller.error(new DOMException('Cancelled', 'AbortError')); });
        state.diagTest.emit({ type: 'check', check: { id: 'network', label: '网络连接', status: 'passed', detail: 'HTTPS 可达' } });
        state.diagTest.emit({ type: 'check', check: { id: 'generation', label: '实际生成', status: 'running', detail: '请求已受理，等待正文' } });
      } }), { headers: { 'content-type': 'application/x-ndjson' } });
    };
  });
  await dialog.getByRole('button', { name: '测试连接', exact: true }).click();
  const results = dialog.getByRole('region', { name: 'AI 检测结果' });
  await expect(results).toContainText('等待正文');
  await expect(dialog.getByRole('button', { name: '保存设置', exact: true })).toBeDisabled();
  expect(await page.evaluate(() => (window as unknown as { diagTest: { input: unknown } }).diagTest.input)).toEqual({ apiKey: 'unsaved-diagnostic-key', model: 'deepseek-v4-pro' });
  await dialog.getByRole('button', { name: '取消检测', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('检测已取消');
  expect(await page.evaluate(() => (window as unknown as { diagTest: { aborted: boolean } }).diagTest.aborted)).toBe(true);
  await expect(results).not.toContainText('检测中');
  await dialog.getByRole('button', { name: '测试连接', exact: true }).click();
  await expect(results).toContainText('等待正文');
  await page.evaluate(() => {
    const checks = [
      { id: 'network', label: '网络连接', status: 'passed', detail: 'HTTPS 可达' },
      { id: 'key', label: 'Key 认证', status: 'passed', detail: '认证已通过' },
      { id: 'model', label: '所选模型', status: 'passed', detail: '模型可用' },
      { id: 'balance', label: '账户可用性', status: 'passed', detail: '账户可用' },
      { id: 'generation', label: '实际生成', status: 'failed', detail: '30秒内未返回正文', elapsedMs: 30000, keepAlives: 2 },
    ];
    (window as unknown as { diagTest: { emit: (event: unknown) => void } }).diagTest.emit({ type: 'done', report: { healthy: false, model: 'deepseek-v4-pro', checkedAt: new Date().toISOString(), checks, suggestion: '供应商生成未及时输出，请稍后重测。' } });
  });
  await expect(results).toContainText('检测未通过');
  await expect(results).toContainText('30秒内未返回正文');
  await expect(results.locator('.ai-check.passed')).toHaveCount(4);
  await expect(results).not.toContainText('实际生成检测通过');
  expect(await (await page.request.get('/api/settings/ai')).json()).toEqual(before);
  expect(await (await page.request.get('/api/projects')).json()).toEqual(projects);
  const storage = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }));
  expect(storage).not.toContain('unsaved-diagnostic-key');
  // Changing the model invalidates the previous result.
  await dialog.getByLabel('模型名称').selectOption('deepseek-flash');
  await expect(results).toHaveCount(0);
  await dialog.getByRole('button', { name: '测试连接', exact: true }).click();
  await expect(results).toContainText('等待正文');
  await page.evaluate(() => (window as unknown as { diagTest: { emit: (event: unknown) => void } }).diagTest.emit({ type: 'done', report: { healthy: true, model: 'deepseek-flash', checkedAt: new Date().toISOString(), checks: [{ id: 'generation', label: '实际生成', status: 'passed', detail: '完整返回', elapsedMs: 700, firstTokenMs: 400 }], suggestion: '当前可以生成回答。' } }));
  await expect(results).toContainText('实际生成检测通过');
  await expect(results).toContainText('首字 0.4 秒');
  await dialog.getByRole('button', { name: '测试连接', exact: true }).click();
  await expect(results).toContainText('等待正文');
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  expect(await page.evaluate(() => (window as unknown as { diagTest: { aborted: boolean } }).diagTest.aborted)).toBe(true);
  await page.getByRole('button', { name: 'API 设置', exact: true }).click();
  await expect(dialog.getByLabel('API Key')).toHaveValue('');
  await expect(dialog.getByLabel('模型名称')).toHaveValue(before.aiModel);
});
