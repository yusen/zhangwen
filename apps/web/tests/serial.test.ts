import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { MicroPythonDevice, type SerialPortLike } from '../src/serial';
import type { UploadManifest } from '../../../packages/contracts/src/mu';

const encoder = new TextEncoder();
const decode = (value: Uint8Array) => new TextDecoder().decode(value);
const digest = (value: Uint8Array) => createHash('sha256').update(value).digest('hex');
const bytesHex = (value: Uint8Array) => Buffer.from(value).toString('hex');
const unhex = (value: string) => new Uint8Array(Buffer.from(value, 'hex'));
const filename = (code: string) => /(?:open|os\.rename)\("([^"]+)"/.exec(code)?.[1] ?? '';

/** Protocol peer only; this does NOT run Python or assert a physical board result. */
class FakePort implements SerialPortLike {
  files = new Map<string, Uint8Array>([['main.py', encoder.encode('print("old")\n')], ['user.txt', encoder.encode('do not change')]]);
  readable: ReadableStream<Uint8Array>;
  writable: WritableStream<Uint8Array>;
  controller!: ReadableStreamDefaultController<Uint8Array>;
  raw = false;
  current = '';
  oldOffset = 0;
  readFile = '';
  readingPath = '';
  readingOffset = 0;
  corruptStage = false;
  corruptMain = false;
  noResponse = false;
  errorOnce = '';
  chunkHook?: () => void;
  commands: string[] = [];
  constructor() {
    this.readable = new ReadableStream({ start: controller => { this.controller = controller; } });
    this.writable = new WritableStream({ write: value => this.receive(decode(value)) });
  }
  async open() {}
  async close() {}
  emit(value: string) {
    // Split all responses (including markers and UTF-8) across small packets.
    const bytes = encoder.encode(value);
    for (let i = 0; i < bytes.length; i += 3) this.controller.enqueue(bytes.slice(i, i + 3));
  }
  receive(value: string) {
    if (this.noResponse) return;
    if (value.includes('\x01')) { this.raw = true; this.emit('raw REPL; CTRL-B to exit\r\n>'); return; }
    if (value === '\x02') { this.raw = false; this.emit('\r\nMicroPython\r\n>>> '); return; }
    if (value.includes('\x03') && !this.raw) { this.emit('\r\nKeyboardInterrupt\r\n>>> '); return; }
    if (!value.endsWith('\x04')) { this.emit(value + '\n模拟输出\n'); return; }
    const code = value.slice(0, -1);
    this.commands.push(code);
    if (this.errorOnce && code.includes(this.errorOnce)) { this.errorOnce = ''; this.emit('OK\x04Traceback: fake failure\x04>'); return; }
    let output = '';
    if (code.includes('sys.implementation.name')) output = JSON.stringify({ implementation: 'micropython', platform: 'esp32', machine: 'TEST ESP32-S3 board', uniqueId: 'fake-test-only' });
    else if (code.includes('_zw_names=os.listdir')) output = JSON.stringify([...this.files].map(([path, bytes]) => ({ path, size: bytes.length, directory: false })));
    else if (code.startsWith('_zw_s=os.stat')) output = String(this.files.get(/os.stat\("([^"]+)"/.exec(code)![1])!.length);
    else if (code.startsWith('_zw_read=open')) { this.readingPath = filename(code); this.readingOffset = 0; }
    else if (code.includes('_zw_read.read')) { const bytes = this.files.get(this.readingPath)!; output = bytesHex(bytes.slice(this.readingOffset, this.readingOffset + 128)); this.readingOffset += 128; }
    else if (code.includes('"exists"')) output = JSON.stringify({ exists: this.files.has('main.py'), size: this.files.get('main.py')?.length ?? 0 });
    else if (code.startsWith('_zw_old=open')) this.oldOffset = 0;
    else if (code.includes('_zw_old.read')) { const old = this.files.get('main.py')!; output = bytesHex(old.slice(this.oldOffset, this.oldOffset + 128)); this.oldOffset += 128; }
    else if (code.startsWith('_zw_f=open')) { this.current = filename(code); this.files.set(this.current, new Uint8Array()); }
    else if (code.startsWith('_zw_f.write')) {
      const addition = unhex(/unhexlify\("([a-f0-9]*)"/.exec(code)![1]);
      const old = this.files.get(this.current)!;
      const combined = new Uint8Array(old.length + addition.length); combined.set(old); combined.set(addition, old.length); this.files.set(this.current, combined);
      this.chunkHook?.();
    } else if (code.includes('_zw_h=hashlib.sha256')) {
      this.readFile = /_zw_r=open\("([^"]+)"/.exec(code)![1];
      output = digest(this.files.get(this.readFile)!);
      if (this.corruptStage && this.readFile.endsWith('.tmp')) output = '0'.repeat(64);
      if (this.corruptMain && this.readFile === 'main.py' && this.files.get('main.py')?.[0] !== 112) output = '0'.repeat(64);
    } else if (code.includes('hashlib.sha256(b""')) output = digest(new Uint8Array());
    if (code.includes('os.remove')) {
      const match = /os.remove\("([^"]+)"/.exec(code);
      if (match) this.files.delete(match[1]);
    }
    if (code.includes('os.rename')) {
      const match = /os.rename\("([^"]+)","([^"]+)"/.exec(code)!;
      const old = this.files.get(match[1]);
      if (!old) { this.emit('OK\x04OSError: missing file\x04>'); return; }
      this.files.set(match[2], old); this.files.delete(match[1]);
    }
    this.emit('OK' + output + (output ? '\r\n' : '') + '\x04\x04>');
  }
}
function manifest(code = '# 新版本\nprint("hello")\n'): UploadManifest {
  const bytes = encoder.encode(code);
  return { projectId: 'fake-project', revision: 2, boardId: 'fake-board', hardwareRevisions: {}, files: [{ path: 'main.py', content: code, size: bytes.length, sha256: digest(bytes) }] };
}
async function setup() {
  const port = new FakePort(); const logs: string[] = [];
  const device = new MicroPythonDevice(port, text => logs.push(text), () => {}, 80);
  await device.connect();
  return { port, logs, device };
}

describe('MicroPython classic raw REPL + safe file upload', () => {
  it('lists and reads root files with hash verification and keeps a read-only upload receipt', async () => {
    const { port, device } = await setup();
    const plan = manifest('# 中文文件\n' + 'print(1)\n'.repeat(40));
    await device.upload(plan, async () => {}, () => {});
    const receipt = device.receipt;
    const files = await device.listFiles();
    expect(files.find(file => file.path === 'main.py')?.size).toBe(plan.files[0].size);
    const count = port.commands.length;
    const read = await device.readFile('main.py');
    expect(decode(read.bytes)).toBe(plan.files[0].content);
    expect(read.sha256).toBe(plan.files[0].sha256);
    expect(device.receipt).toBe(receipt);
    expect(port.commands.slice(count).some(code => /os.remove|os.rename|"wb"/.test(code))).toBe(false);
    await expect(device.readFile('../boot.py')).rejects.toThrow('根目录');
    await device.disconnect();
  });
  it('rejects oversized and corrupt reads without writing, then returns to a usable REPL', async () => {
    const { port, device } = await setup();
    port.files.set('huge.py', new Uint8Array(65537));
    await expect(device.readFile('huge.py')).rejects.toThrow('64 KiB');
    expect(device.state).toBe('connected');
    port.corruptMain = true; port.files.set('main.py', encoder.encode('# corrupt hash'));
    await expect(device.readFile('main.py')).rejects.toThrow('摘要');
    expect(device.state).toBe('connected');
    await device.disconnect();
  });
  it('tracks natural program completion and traceback across split serial bytes', async () => {
    const { port, device, logs } = await setup();
    await device.upload(manifest(), async () => {}, () => {});
    await device.run(); expect(device.state).toBe('running');
    port.emit('ZW_CIRCLE_OK\r\n>>> ');
    await new Promise(resolve => setTimeout(resolve, 5));
    expect(device.state).toBe('connected');
    expect(logs.join('')).toContain('程序已返回 REPL');
    await device.run();
    port.emit('Traceback (most recent call last):\r\nRuntimeError: test\r\n>>> ');
    await new Promise(resolve => setTimeout(resolve, 5));
    expect(device.state).toBe('connected');
    expect(logs.join('')).toContain('程序报错并返回 REPL');
    await device.disconnect();
  });
  it('identifies split byte responses, backs up, uploads UTF-8, verifies and runs only on request', async () => {
    const { port, device, logs } = await setup();
    expect(device.identity?.implementation).toBe('micropython');
    const plan = manifest();
    let backedUp = false;
    const receipt = await device.upload(plan, async data => {
      expect(decode(data.bytes!)).toBe('print("old")\n');
      expect(port.commands.some(code => code.startsWith('_zw_f=open'))).toBe(false);
      backedUp = true;
    }, () => {});
    expect(backedUp).toBe(true);
    expect(decode(port.files.get('main.py')!)).toBe(plan.files[0].content);
    expect(decode(port.files.get('user.txt')!)).toBe('do not change');
    expect(port.files.has(receipt.backupPath!)).toBe(true);
    expect(device.state).toBe('connected');
    expect(logs.join('')).not.toContain('运行命令已提交');
    await device.run(); expect(device.state).toBe('running');
    await device.stop(); expect(device.state).toBe('connected');
    await device.repl('print(1)'); expect(device.receipt).toBe(null);
    await device.disconnect(); expect(device.state).toBe('disconnected');
  });
  it('rejects a changed manifest or forbidden target before any write', async () => {
    const { device, port } = await setup();
    const plan = manifest(); plan.files[0].content = 'changed';
    await expect(device.upload(plan, async () => {}, () => {})).rejects.toThrow('清单');
    expect(port.commands.some(code => code.startsWith('_zw_f=open'))).toBe(false);
    await device.disconnect();
  });
  it('fails closed if browser backup cannot persist', async () => {
    const { device, port } = await setup();
    await expect(device.upload(manifest(), async () => { throw new Error('backup unavailable'); }, () => {})).rejects.toThrow('backup unavailable');
    expect(decode(port.files.get('main.py')!)).toBe('print("old")\n');
    expect(port.commands.some(code => code.startsWith('_zw_f=open'))).toBe(false);
    expect(device.receipt).toBe(null); await device.disconnect();
  });
  it('stage corruption keeps original main.py, removes only its own staging file', async () => {
    const { device, port } = await setup(); port.corruptStage = true;
    await expect(device.upload(manifest(), async () => {}, () => {})).rejects.toThrow('暂存');
    expect(decode(port.files.get('main.py')!)).toBe('print("old")\n');
    expect([...port.files.keys()].some(path => path.endsWith('.tmp'))).toBe(false);
    expect(device.receipt).toBe(null); await device.disconnect();
  });
  it('final readback failure restores original and does not produce a receipt', async () => {
    const { device, port, logs } = await setup(); port.corruptMain = true;
    await expect(device.upload(manifest(), async () => {}, () => {})).rejects.toThrow('目标');
    expect(decode(port.files.get('main.py')!)).toBe('print("old")\n');
    expect(logs.join('')).toContain('原 main.py 已恢复');
    expect(device.receipt).toBe(null); await device.disconnect();
  });
  it('cancel between chunks keeps original and cleans staging', async () => {
    const { device, port } = await setup(); port.chunkHook = () => device.cancel();
    await expect(device.upload(manifest('x'.repeat(800)), async () => {}, () => {})).rejects.toThrow('取消');
    expect(decode(port.files.get('main.py')!)).toBe('print("old")\n');
    expect([...port.files.keys()].some(path => path.endsWith('.tmp'))).toBe(false);
    await device.disconnect();
  });
  it('disconnect during a write reports recovery need and never claims success', async () => {
    const { device, port, logs } = await setup();
    port.chunkHook = () => { port.controller.error(new Error('USB unplugged')); port.noResponse = true; };
    await expect(device.upload(manifest(), async () => {}, () => {})).rejects.toThrow(/USB unplugged|Controller/);
    expect(device.state).toBe('attention'); expect(device.receipt).toBe(null);
    expect(logs.join('')).toContain('需要恢复');
    expect(decode(port.files.get('main.py')!)).toBe('print("old")\n');
    await device.disconnect();
  });
  it('timeout invalidates protocol; does not send blind rollback commands', async () => {
    const { device, port } = await setup(); port.noResponse = true;
    await expect(device.upload(manifest(), async () => {}, () => {})).rejects.toThrow('超时');
    expect(device.state).toBe('attention'); expect(device.receipt).toBe(null);
    expect(port.commands.some(code => code.includes('os.rename'))).toBe(false);
    await device.disconnect();
  });
  it('refuses to run if a different tool changed main.py after verification', async () => {
    const { device, port } = await setup();
    await device.upload(manifest(), async () => {}, () => {});
    port.files.set('main.py', encoder.encode('print("another tool")'));
    await expect(device.run()).rejects.toThrow('已变更');
    expect(device.receipt).toBe(null); await device.disconnect();
  });
  it('serial lock prevents concurrent operations', async () => {
    const { device } = await setup();
    let release!: () => void;
    const barrier = new Promise<void>(resolve => { release = resolve; });
    const uploading = device.upload(manifest(), async () => barrier, () => {});
    await new Promise(resolve => setTimeout(resolve, 10));
    await expect(device.stop()).rejects.toThrow('另一操作');
    release(); await uploading; await device.disconnect();
  });
});
