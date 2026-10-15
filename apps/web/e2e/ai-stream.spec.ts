import { test, expect } from '@playwright/test';

test('streamed AI shows waiting/text, cancels safely, and offers code only after completion', async ({ page }) => {
  await page.route('**/api/session', async route => {
    const response = await route.fetch();
    await route.fulfill({ json: { ...await response.json(), aiConfigured: true } });
  });
  await page.goto('/');
  const editor = page.getByRole('textbox', { name: 'MicroPython 代码编辑器' });
  await expect(editor).toBeEditable();
  await editor.fill('print("keep my draft")\n');
  // Feed real browser ReadableStream chunks, including a split UTF-8 character.
  await page.evaluate(() => {
    const original = window.fetch.bind(window);
    const state = window as unknown as { aiTest: { emit: (event: unknown) => void; aborted: boolean } };
    window.fetch = async (input, init) => {
      if (!String(input).endsWith('/chat')) return original(input, init);
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          state.aiTest = {
            aborted: false,
            emit(event) {
              const bytes = new TextEncoder().encode(JSON.stringify(event) + '\n');
              for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
            },
          };
          init?.signal?.addEventListener('abort', () => {
            state.aiTest.aborted = true;
            controller.error(new DOMException('Cancelled', 'AbortError'));
          });
          state.aiTest.emit({ type: 'status', phase: 'waiting' });
        },
      });
      return new Response(stream, { headers: { 'content-type': 'application/x-ndjson' } });
    };
  });
  const prompt = page.getByLabel('发送给掌问 AI');
  const progress = page.locator('.ai-progress').getByRole('status');
  await prompt.fill('请生成中文注释程序');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(progress).toContainText('正在等待 DeepSeek 回答');
  await expect(progress).toContainText('1 秒', { timeout: 5000 });
  await page.evaluate(() => (window as unknown as { aiTest: { emit: (e: unknown) => void } }).aiTest.emit({ type: 'delta', content: '中文回答\n```python\nprint(2)\n```' }));
  await expect(page.getByLabel('掌问对话记录')).toContainText('中文回答');
  await expect(page.getByRole('button', { name: '查看代码', exact: true })).toHaveCount(0);
  await editor.fill('print("newer edit")\n');
  await page.getByRole('button', { name: '取消生成', exact: true }).click();
  await expect(page.locator('.chat-error')).toContainText('已取消');
  expect(await page.evaluate(() => (window as unknown as { aiTest: { aborted: boolean } }).aiTest.aborted)).toBe(true);
  await expect(prompt).toHaveValue('请生成中文注释程序');
  await expect(editor).toContainText('newer edit');
  await expect(page.getByRole('button', { name: '查看代码', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(progress).toContainText('正在等待');
  await page.evaluate(() => {
    const emit = (window as unknown as { aiTest: { emit: (e: unknown) => void } }).aiTest.emit;
    emit({ type: 'delta', content: '```python\nprint(3)\n```' });
    emit({ type: 'done', messages: [{ id: 'complete', role: 'assistant', status: 'COMPLETED', content: '```python\nprint(3)\n```' }] });
  });
  await expect(prompt).toHaveValue('');
  await expect(page.getByRole('button', { name: '查看代码', exact: true })).toBeVisible();
  await expect(editor).toContainText('newer edit');
  await expect(page.getByRole('button', { name: '运行', exact: true })).toBeDisabled();
});
