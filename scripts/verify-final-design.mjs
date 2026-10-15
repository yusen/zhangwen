// Actual production UI, disposable local browser drafts, no project/device/model writes.
import { chromium } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/projects', route => {
    if (route.request().method() !== 'GET') throw new Error('Production write forbidden in smoke test');
    return route.fulfill({ json: { projects: [] } });
  });
  await page.goto('http://127.0.0.1:3080/');
  await page.getByRole('button', { name: '主控板', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: /行空板 K10/ }).click();
  await page.getByRole('button', { name: '添加模块', exact: true }).click();
  if (await page.getByRole('checkbox').count() !== 68) throw new Error('Catalog incomplete');
  await page.getByRole('checkbox', { name: /选择DFRobot DFR0033/ }).check();
  await page.getByRole('checkbox', { name: /选择DFRobot SER0006/ }).check();
  await page.getByRole('button', { name: '加入所选模块' }).click();
  await page.getByRole('textbox', { name: 'MicroPython 代码编辑器' }).fill('from machine import Pin\nimport time\n\nled = Pin(2, Pin.OUT)\n\ndef blink(times, gap):\n    for i in range(times):\n        led.value(1)\n        time.sleep(gap)\n        led.value(0)\n        time.sleep(gap)\n\n# 请按实际主控板与接线修改引脚\nblink(3, 0.3)\n');
  const layouts = [];
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark') await page.getByRole('button', { name: '切换深色主题' }).click();
    for (const width of [1440, 1024, 720, 375]) {
      await page.setViewportSize({ width, height: 900 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      if (width === 375) await page.getByRole('button', { name: '代码', exact: true }).click();
      const layout = await page.evaluate(() => ({ width: innerWidth, theme: document.documentElement.dataset.theme,
        overflow: document.documentElement.scrollWidth > innerWidth,
        toolbar: getComputedStyle(document.querySelector('.tool-icon')).borderRadius,
        iconSize: getComputedStyle(document.querySelector('.tool-icon')).width,
        editorVisible: document.querySelector('.code-panel').getBoundingClientRect().width > 0 }));
      if (layout.overflow || !layout.editorVisible || layout.toolbar !== '9px' || layout.iconSize !== '40px') throw new Error(JSON.stringify(layout));
      layouts.push(layout);
      if (width === 1440 || width === 375) await page.screenshot({ path: `docs/final-workbench-${theme}-${width}.png`, fullPage: true });
      if (width === 375) await page.getByRole('button', { name: '硬件库', exact: true }).click();
      await page.getByRole('button', { name: '添加模块', exact: true }).click();
      const picker = await page.evaluate(() => {
        const list = document.querySelector('.sensor-picker-list');
        const footer = document.querySelector('.sensor-picker-actions').getBoundingClientRect();
        return { width: innerWidth, overflow: document.documentElement.scrollWidth > innerWidth,
          scrolls: list.scrollHeight > list.clientHeight,
          cardHeight: list.querySelector('.module-card').getBoundingClientRect().height,
          footerVisible: footer.top >= 0 && footer.bottom <= innerHeight };
      });
      if (picker.overflow || !picker.scrolls || picker.cardHeight < 230 || !picker.footerVisible) throw new Error(JSON.stringify(picker));
      if (width === 1440 || width === 375) await page.screenshot({ path: `docs/final-picker-${theme}-${width}.png` });
      await page.keyboard.press('Escape');
      await page.getByRole('button', { name: '帮助', exact: true }).focus();
      await page.keyboard.press('Enter');
      await page.getByRole('dialog').waitFor();
      await page.keyboard.press('Escape');
      if (width === 375) await page.getByRole('button', { name: '代码', exact: true }).click();
    }
    await page.setViewportSize({ width: 1440, height: 900 });
  }
  await page.reload();
  await page.locator('.selected-sensor-list .module-card').first().waitFor({ state: 'attached' });
  if (await page.locator('html').getAttribute('data-theme') !== 'dark') throw new Error('Theme lost');
  if (await page.locator('.selected-sensor-list .module-card').count() !== 2) throw new Error('Draft modules lost');
  if (errors.length) throw new Error(errors.join('\n'));
  const report = { layouts, catalogModules: 68, themes: true, keyboardDialogs: true, pickerScroll: true,
    draftRestored: true, productionWrites: false, pageErrors: errors };
  await writeFile('docs/final-design-ui-smoke.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally { await browser.close(); }
