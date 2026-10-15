/** Real browser Web Serial acceptance. No mock port, Flash or backend serial. */
import { chromium } from 'playwright';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

mkdirSync('docs/device-acceptance', { recursive: true });
const context = await chromium.launchPersistentContext('.browser-data/device-acceptance', { channel: 'msedge', headless: false, viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const cdp = await context.newCDPSession(page);
const report = { date: '2026-10-15', transport: 'real browser Web Serial', port: 'COM522', prompts: [], errors: [], phase: 'connect' };
page.on('pageerror', e => report.errors.push(e.message));
try {
  await cdp.send('DeviceAccess.enable');
  cdp.on('DeviceAccess.deviceRequestPrompted', async event => {
    report.prompts.push(event.devices.map(item => ({ name: item.name, id: item.id })));
    const device = event.devices.find(item => item.name.includes('COM522'));
    if (device) await cdp.send('DeviceAccess.selectPrompt', { id: event.id, deviceId: device.id });
  });
  await page.goto('http://127.0.0.1:3080/');
  await page.getByRole('button', { name: '主控', exact: true }).click();
  await page.getByRole('button', { name: '掌控板 2.0（ESP32）', exact: true }).click();
  await page.getByRole('button', { name: '连接设备', exact: true }).click();
  console.log('请选择原生串口窗口中的 COM522 并连接。等待实际 MicroPython 身份响应。');
  await page.getByRole('button', { name: '已连接 · 断开', exact: true }).waitFor({ timeout: 300000 });
  report.log = await page.getByLabel('串口输出').innerText();
  await page.screenshot({ path: 'docs/device-acceptance/connected.png', fullPage: true });
  report.phase = 'identified';
  const repl = page.getByLabel('REPL 命令');
  await repl.fill('import mpython; print("ZW_OLED_CAPS", mpython.oled.width, mpython.oled.height, hasattr(mpython.oled, "circle"))');
  await page.getByRole('button', { name: '发送 REPL 命令', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.serial-log')?.textContent?.includes('ZW_OLED_CAPS 128 64 True'), { timeout: 15000 });
  report.phase = 'mpython-128x64-confirmed';
  const code = readFileSync('examples/mpython-v2-circle/main.py', 'utf8');
  await page.getByRole('textbox', { name: 'MicroPython 代码编辑器' }).fill(code);
  await page.getByRole('button', { name: '保存', exact: true }).click();
  const naming = page.getByRole('dialog', { name: '保存项目', exact: true });
  if (await naming.count()) {
    await page.getByLabel('项目名称').fill('掌控板2.0空心圆验收');
    await page.getByRole('button', { name: '保存项目', exact: true }).click();
  }
  await page.getByText(/已保存 · v\d+/).waitFor();
  await page.getByRole('button', { name: '检查', exact: true }).click();
  await page.getByLabel('检查结果').filter({ hasText: '静态检查完成' }).waitFor();
  report.phase = 'saved-and-checked';
  report.projectId = await page.evaluate(() => localStorage.getItem('mu-active-project'));
  await page.getByRole('button', { name: '上传', exact: true }).click();
  await page.getByRole('dialog', { name: '确认上传 main.py' }).waitFor();
  report.manifest = await page.locator('.upload-details').innerText();
  await page.getByRole('checkbox', { name: /我已核对实际板型/ }).check();
  await page.getByRole('button', { name: '开始上传', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.serial-log')?.textContent?.includes('[上传回读一致]'), { timeout: 60000 });
  report.phase = 'uploaded-readback-verified';
  // Export the pre-write browser backup so it is also recoverable outside this context.
  const backupDownload = page.waitForEvent('download', { timeout: 10000 });
  await page.getByRole('button', { name: '备份', exact: true }).click();
  const downloaded = await backupDownload.catch(() => null);
  if (downloaded) { await downloaded.saveAs('docs/device-acceptance/main-before-upload.py'); report.backupExported = true; }
  await page.getByRole('button', { name: '运行', exact: true }).click();
  await page.waitForFunction(() => {
    const output = document.querySelector('.serial-log')?.textContent ?? '';
    return output.includes('\nZW_CIRCLE_OK: center=(64,32), radius=24, outline') && output.includes('[程序已返回 REPL]');
  }, { timeout: 20000 });
  report.phase = 'executed-and-returned';
  await page.getByRole('button', { name: '文件', exact: true }).click();
  await page.getByRole('button', { name: '刷新设备文件', exact: true }).click();
  const main = page.locator('.device-file-row').filter({ has: page.getByText('main.py', { exact: true }) });
  await main.getByRole('button', { name: '读取', exact: true }).click();
  await page.locator('.device-file-preview').getByText('main.py · 回读校验一致', { exact: true }).waitFor();
  report.files = await page.locator('.device-file-list').innerText();
  report.readbackMatches = (await page.locator('.device-file-preview pre').innerText()).trimEnd() === code.trimEnd();
  await page.screenshot({ path: 'docs/device-acceptance/files-readback.png', fullPage: true });
  await page.keyboard.press('Escape');
  // Reads the framebuffer only; does not claim to observe the physical screen.
  await repl.fill('print("ZW_CIRCLE_PIXELS", oled.pixel(64,32), oled.pixel(64,8), oled.pixel(88,32), oled.pixel(64,56), oled.pixel(40,32))');
  await page.getByRole('button', { name: '发送 REPL 命令', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.serial-log')?.textContent?.includes('ZW_CIRCLE_PIXELS 0 1 1 1 1'), { timeout: 15000 });
  report.framebuffer = 'center=0; four radius24 boundary points=1';
  report.log = await page.getByLabel('串口输出').innerText();
  report.physicalScreenObserved = false;
  await page.screenshot({ path: 'docs/device-acceptance/circle-executed.png', fullPage: true });
  console.log(JSON.stringify(report));
} catch (error) {
  report.errors.push(String(error));
  report.log = await page.getByLabel('串口输出').innerText().catch(() => '');
  report.feedback = await page.locator('.feedback').innerText().catch(() => '');
  await page.screenshot({ path: 'docs/device-acceptance/connect-error.png', fullPage: true }).catch(() => {});
  console.log(JSON.stringify(report));
  process.exitCode = 1;
} finally {
  writeFileSync('docs/device-acceptance/real-board.json', JSON.stringify(report, null, 2));
  const disconnect = page.getByRole('button', { name: /断开/, exact: false });
  if (await disconnect.count()) await disconnect.click().catch(() => {});
  await context.close();
}
