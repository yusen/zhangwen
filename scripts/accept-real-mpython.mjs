/** Explicit development acceptance; real COM522, same product MicroPythonDevice.
 * This verifies the shared protocol on hardware, not browser chooser permission.
 */
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import ts from 'typescript';
import { python, env } from './python.mjs';
const source = ts.transpileModule(readFileSync('apps/web/src/serial.ts', 'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { MicroPythonDevice } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
mkdirSync('docs/device-acceptance', { recursive: true });
const report = { date: '2026-10-15', port: 'COM522', transport: 'standalone real COM acceptance of shared serial.ts; browser chooser not verified', phase: 'connecting', log: '', deviceWrites: false, physicalScreenObserved: false };
const child = spawn(python, ['-u', 'scripts/acceptance-serial-peer.py'], { env, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
let nextId = 0;
const pending = new Map();
let stream;
child.stderr.on('data', data => { report.transportError = (report.transportError ?? '') + data.toString(); });
child.on('exit', code => { if (code && stream) stream.error(new Error('Acceptance transport exited: ' + code)); });
createInterface({ input: child.stdout }).on('line', line => {
  const value = JSON.parse(line);
  if (value.data) stream.enqueue(new Uint8Array(Buffer.from(value.data, 'base64')));
  if (value.fault) stream.error(new Error(value.fault));
  if (value.id) { const request = pending.get(value.id); pending.delete(value.id); clearTimeout(request?.timer); if (value.error) request?.reject(new Error(value.error)); else request?.resolve(); }
});
function call(op, data) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('Acceptance transport timed out')); }, 10000);
    pending.set(id, { resolve, reject, timer });
    child.stdin.write(JSON.stringify({ id, op, data }) + '\n');
  });
}
const port = {
  readable: new ReadableStream({ start(controller) { stream = controller; } }),
  writable: new WritableStream({ write(bytes) { return call('write', Buffer.from(bytes).toString('base64')); } }),
  open: () => call('open'), close: () => call('close'),
};
const device = new MicroPythonDevice(port, text => { report.log = (report.log + text).slice(-60000); }, () => {}, 12000);
async function waitLog(marker, timeout = 15000) {
  const start = Date.now();
  while (!report.log.includes(marker)) {
    if (Date.now() - start > timeout || device.state === 'attention') throw new Error('No confirmed device output: ' + marker);
    await new Promise(resolve => setTimeout(resolve, 50));
  }
}
async function api(path, method = 'GET', body) {
  const response = await fetch('http://127.0.0.1:3080/api' + path, { method, headers: { 'content-type': 'application/json', origin: 'http://127.0.0.1:3080', 'x-mu-session': token }, body: body ? JSON.stringify(body) : undefined });
  const value = await response.json(); if (!response.ok) throw new Error(value.detail ?? response.status); return value;
}
let token = '';
try {
  report.identity = await device.connect();
  report.phase = 'identified';
  console.log('Identified:', report.identity.machine);
  await device.repl('import mpython; print("ZW_OLED_CAPS", mpython.oled.width, mpython.oled.height, hasattr(mpython.oled, "circle"))');
  await waitLog('ZW_OLED_CAPS 128 64 True');
  report.phase = 'mpython-oled-confirmed';
  const before = await device.listFiles(); report.filesBefore = before;
  token = (await (await fetch('http://127.0.0.1:3080/api/session')).json()).token;
  const code = readFileSync('examples/mpython-v2-circle/main.py', 'utf8');
  const project = await api('/projects', 'POST', { name: '掌控板2.0空心圆验收', boardId: 'hw_labplus_mpython_v2', code, componentIds: [] });
  report.projectId = project.id;
  report.check = await api('/check', 'POST', { code, boardId: project.boardId, componentIds: [] });
  if (!report.check.valid) throw new Error('Static check failed');
  const manifest = await api('/projects/' + project.id + '/upload-manifest', 'POST', { expectedRevision: project.revision });
  report.manifest = manifest;
  report.phase = 'saved-checked-manifest';
  report.receipt = await device.upload(manifest, async backup => {
    report.previousFileExisted = backup.bytes !== null;
    report.originalSize = backup.bytes?.length ?? 0;
    report.backupPath = backup.path;
    // Durable local backup before the shared protocol writes its staging file.
    mkdirSync('.device-backups', { recursive: true });
    if (backup.bytes) {
      report.localBackup = '.device-backups/' + backup.path + '.py';
      writeFileSync(report.localBackup, backup.bytes, { flag: 'wx' });
    }
    writeFileSync('docs/device-acceptance/backup-metadata.json', JSON.stringify({ path: backup.path, identity: backup.identity, size: report.originalSize, existed: report.previousFileExisted }, null, 2));
  }, () => { report.deviceWrites = true; });
  report.phase = 'uploaded-verified';
  console.log('Uploaded and SHA-256 verified:', report.receipt.sha256);
  await device.run();
  await waitLog('\nZW_CIRCLE_OK: center=(64,32), radius=24, outline');
  await waitLog('[程序已返回 REPL]');
  report.phase = 'executed-and-returned';
  const readback = await device.readFile('main.py');
  report.readbackMatches = new TextDecoder().decode(readback.bytes) === code;
  if (!report.readbackMatches) throw new Error('Explicit file readback differs');
  report.filesAfter = await device.listFiles();
  await device.repl('print("ZW_CIRCLE_PIXELS", oled.pixel(64,32), oled.pixel(64,8), oled.pixel(88,32), oled.pixel(64,56), oled.pixel(40,32))');
  await waitLog('ZW_CIRCLE_PIXELS 0 1 1 1 1');
  report.framebuffer = 'center=0; four radius24 boundary points=1';
  report.phase = 'execution-framebuffer-verified';
  console.log(JSON.stringify({ phase: report.phase, readbackMatches: report.readbackMatches, framebuffer: report.framebuffer, projectId: report.projectId, backupPath: report.backupPath }));
} catch (error) {
  report.error = String(error); console.log(JSON.stringify(report)); process.exitCode = 1;
} finally {
  await device.disconnect().catch(() => {});
  child.stdin.end();
  writeFileSync('docs/device-acceptance/real-com522.json', JSON.stringify(report, null, 2));
}
