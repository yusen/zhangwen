import type { DeviceFile, DeviceFileContent, DeviceIdentity, DeviceState, UploadManifest, UploadReceipt } from '../../../packages/contracts/src/platform';

export interface SerialPortLike {
  readable: ReadableStream<Uint8Array> | null;
  writable: WritableStream<Uint8Array> | null;
  open(options: { baudRate: number }): Promise<void>;
  close(): Promise<void>;
}
export interface SerialApi { requestPort(): Promise<SerialPortLike> }
export function serialApi(): SerialApi | undefined {
  return (navigator as Navigator & { serial?: SerialApi }).serial;
}
const encoder = new TextEncoder();
export async function sha256(bytes: Uint8Array): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', new Uint8Array(bytes).buffer);
  return Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, '0')).join('');
}
const quote = (value: string) => JSON.stringify(value);
const hex = (bytes: Uint8Array) => Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
const JSON_IMPORT = 'try:\n import json\nexcept ImportError:\n import ujson as json';
const HASH_IMPORT = 'try:\n import hashlib\nexcept ImportError:\n import uhashlib as hashlib';

class DeviceResponseTimeout extends Error {}

/** One reader, one writer, a bounded buffer and one operation per browser port. */
export class MicroPythonDevice {
  state: DeviceState = 'disconnected';
  identity: DeviceIdentity | null = null;
  receipt: UploadReceipt | null = null;
  private reader?: ReadableStreamDefaultReader<Uint8Array>;
  private writer?: WritableStreamDefaultWriter<Uint8Array>;
  private reading?: Promise<void>;
  private buffer = '';
  private waiter?: () => void;
  private fault?: Error;
  private closing = false;
  private capture = false;
  private busy = false;
  private cancelled = false;
  private mode: 'friendly' | 'raw' = 'friendly';
  private outputTail = '';
  private runTraceback = false;
  constructor(private port: SerialPortLike, private log: (text: string) => void, private changed: () => void = () => {}, private timeout = 8000) {}
  private setState(state: DeviceState) { this.state = state; this.changed(); }

  async connect(): Promise<DeviceIdentity> {
    this.setState('connecting');
    try {
      await this.port.open({ baudRate: 115200 });
      if (!this.port.readable || !this.port.writable) throw new Error('串口未提供可读写通道。');
      this.reader = this.port.readable.getReader();
      this.writer = this.port.writable.getWriter();
      this.reading = this.pump();
      return await this.operation(async () => {
        this.log('\n[固件检测] 正在验证 MicroPython，请稍候…\n');
        let parsed: unknown;
        try {
          await this.enterRaw();
          // Check the runtime before importing MicroPython-only board modules.
          const result = await this.execute('import sys\n' + JSON_IMPORT + '\nif sys.implementation.name != "micropython":\n print(json.dumps({"implementation":sys.implementation.name}))\nelse:\n import os, machine, binascii\n print(json.dumps({"implementation":sys.implementation.name,"platform":sys.platform,"machine":os.uname().machine,"uniqueId":binascii.hexlify(machine.unique_id()).decode()}))');
          parsed = JSON.parse(result.trim());
        } catch (error) {
          if (error instanceof DeviceResponseTimeout) throw new Error('未检测到有效的 MicroPython 响应，可能是固件版本不对，请重刷固件。若已刷入 MicroPython，请确认串口、数据线及主控已退出 BOOT 下载模式后重试连接。');
          if (error instanceof SyntaxError || (error instanceof Error && error.message.startsWith('MicroPython:'))) throw new Error('MicroPython 固件检测未通过，请重刷当前主控对应的固件后重新连接。');
          throw error;
        }
        if (!parsed || typeof parsed !== 'object') throw new Error('固件身份响应无效，无法确认 MicroPython，请重刷当前主控对应的固件。');
        const value = parsed as Record<string, unknown>;
        if (value.implementation !== 'micropython') throw new Error('固件版本不对：当前设备不是 MicroPython 固件，请重刷当前主控对应的固件后重新连接。');
        if (['machine', 'platform', 'uniqueId'].some(key => typeof value[key] !== 'string' || !value[key])) throw new Error('MicroPython 固件身份信息不完整，请重刷当前主控对应的固件后重新连接。');
        this.identity = value as unknown as DeviceIdentity;
        await this.friendly();
        this.log(`\n[固件检测通过 · 已识别 MicroPython] ${this.identity.machine}\n`);
        return this.identity;
      });
    } catch (error) {
      await this.disconnect();
      throw error;
    }
  }

  private async pump(): Promise<void> {
    const decoder = new TextDecoder();
    try {
      while (this.reader) {
        const { value, done } = await this.reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        if (this.capture) {
          if (this.buffer.length + text.length > 300_000) throw new Error('设备响应超出缓冲上限。');
          this.buffer += text;
        } else {
          this.log(text);
          if (this.state === 'running') {
            this.outputTail = (this.outputTail + text).slice(-512);
            if (this.outputTail.includes('Traceback (most recent call last):')) this.runTraceback = true;
            if (this.outputTail.endsWith('>>> ')) {
              this.setState('connected');
              this.log(this.runTraceback ? '\n[程序报错并返回 REPL] 请查看上方错误，未标记实物成功。\n' : '\n[程序已返回 REPL] 请结合串口输出和实物观察核对结果。\n');
            }
          }
        }
        this.waiter?.();
      }
      if (!this.closing) throw new Error('设备已断开。重新连接后核对设备文件。');
    } catch (error) {
      if (!this.closing) {
        this.fault = error instanceof Error ? error : new Error(String(error));
        this.receipt = null;
        this.setState('attention');
        this.log(`\n[连接中断] ${this.fault.message}\n`);
        this.waiter?.();
      }
    }
  }

  private async send(value: string | Uint8Array): Promise<void> {
    if (this.fault) throw this.fault;
    if (!this.writer) throw new Error('设备未连接。');
    try { await this.writer.write(typeof value === 'string' ? encoder.encode(value) : value); }
    catch (error) {
      this.fault ??= error instanceof Error ? error : new Error(String(error));
      throw this.fault;
    }
  }
  private async until(marker: string): Promise<string> {
    const deadline = Date.now() + this.timeout;
    for (;;) {
      if (this.fault) throw this.fault;
      const index = this.buffer.indexOf(marker);
      if (index >= 0) {
        const result = this.buffer.slice(0, index);
        this.buffer = this.buffer.slice(index + marker.length);
        return result;
      }
      const remaining = deadline - Date.now();
      if (remaining <= 0) {
        this.fault = new DeviceResponseTimeout('设备响应超时。请重新连接并核对备份文件，当前协议状态不再可信。');
        throw this.fault;
      }
      await new Promise<void>(resolve => {
        const timer = setTimeout(() => { this.waiter = undefined; resolve(); }, remaining);
        this.waiter = () => { clearTimeout(timer); this.waiter = undefined; resolve(); };
      });
    }
  }
  private async enterRaw(): Promise<void> {
    this.capture = true;
    this.buffer = '';
    await this.send('\r\x03\x03\x01');
    await this.until('raw REPL; CTRL-B to exit\r\n>');
    this.mode = 'raw';
  }
  private async execute(code: string): Promise<string> {
    if (this.mode !== 'raw') throw new Error('需要 raw REPL。');
    // Commands are small (one 128-byte file chunk), avoiding a large raw REPL burst.
    await this.send(code + '\x04');
    await this.until('OK');
    const output = await this.until('\x04');
    const error = await this.until('\x04');
    await this.until('>');
    if (error.trim()) throw new Error(`MicroPython: ${error.trim()}`);
    return output;
  }
  private async friendly(): Promise<void> {
    await this.send('\x02');
    await this.until('>>> ');
    this.mode = 'friendly';
  }
  private async operation<T>(action: () => Promise<T>, final: DeviceState = 'connected'): Promise<T> {
    if (this.busy) throw new Error('设备正在执行另一操作。');
    if (this.fault) throw this.fault;
    this.busy = true;
    this.capture = true;
    this.setState('busy');
    try {
      const result = await action();
      if (!(final === 'running' && this.state === 'connected')) this.setState(final);
      return result;
    } catch (error) {
      // A device Python error with a known raw prompt can return safely to REPL.
      if (!this.fault && this.mode === 'raw') {
        try { await this.friendly(); this.setState('connected'); }
        catch { this.setState('attention'); }
      } else this.setState('attention');
      throw error;
    } finally {
      this.busy = false;
      this.capture = false;
      if (this.buffer) this.log(this.buffer);
      this.buffer = '';
    }
  }

  cancel() { this.cancelled = true; }

  async upload(manifest: UploadManifest, persistBackup: (data: { path: string; bytes: Uint8Array | null; identity: DeviceIdentity }) => Promise<void>, progress: (done: number, total: number) => void): Promise<UploadReceipt> {
    if (!this.identity) throw new Error('先连接并识别 MicroPython 设备。');
    if (manifest.files.length !== 1 || manifest.files[0].path !== 'main.py') throw new Error('首版只允许清单中的 main.py。');
    const file = manifest.files[0];
    const bytes = encoder.encode(file.content);
    if (bytes.length > 65536 || bytes.length !== file.size || await sha256(bytes) !== file.sha256) throw new Error('上传清单内容、大小或摘要不一致。');
    this.receipt = null;
    this.cancelled = false;
    return this.operation(async () => {
      const id = crypto.randomUUID().replaceAll('-', '');
      const staging = `.zw-${id}.tmp`;
      const backup = `.zw-${id}.bak`;
      let hadOriginal = false;
      let staged = false;
      let moved = false;
      let installed = false;
      try {
        await this.enterRaw();
        // Probe SHA support before any file write. Missing capabilities fail closed.
        await this.execute('import os, binascii\n' + HASH_IMPORT + '\nprint(binascii.hexlify(hashlib.sha256(b"").digest()).decode())');
        const existing = JSON.parse((await this.execute(JSON_IMPORT + '\nprint(json.dumps({"exists":"main.py" in os.listdir(),"size":os.stat("main.py")[6] if "main.py" in os.listdir() else 0}))')).trim()) as { exists: boolean; size: number };
        if (existing.size > 65536) throw new Error('设备 main.py 超过备份上限，未开始写入。请先自行备份。');
        hadOriginal = existing.exists;
        let original: Uint8Array | null = null;
        if (hadOriginal) {
          await this.execute('_zw_old=open("main.py","rb")');
          const chunks: number[] = [];
          for (let offset = 0; offset < existing.size; offset += 128) {
            const data = (await this.execute('print(binascii.hexlify(_zw_old.read(128)).decode())')).trim();
            if (!/^(?:[a-f0-9]{2})*$/.test(data)) throw new Error('旧文件备份响应无效。');
            for (let i = 0; i < data.length; i += 2) chunks.push(parseInt(data.slice(i, i + 2), 16));
          }
          await this.execute('_zw_old.close()');
          original = new Uint8Array(chunks);
          if (original.length !== existing.size) throw new Error('旧文件备份不完整，未开始写入。');
          const originalHash = await this.fileHash('main.py');
          if (await sha256(original) !== originalHash) throw new Error('旧文件备份摘要不一致，未开始写入。');
        }
        // Persist backup before the first write, so a tab/device loss is recoverable.
        await persistBackup({ path: backup, bytes: original, identity: this.identity! });
        if (this.cancelled) throw new Error('上传已取消，原文件保留。');
        await this.execute(`_zw_f=open(${quote(staging)},"wb")`);
        staged = true;
        for (let offset = 0; offset < bytes.length; offset += 128) {
          if (this.cancelled) throw new Error('上传已取消。');
          await this.execute(`_zw_f.write(binascii.unhexlify("${hex(bytes.slice(offset, offset + 128))}"))`);
          progress(Math.min(offset + 128, bytes.length), bytes.length);
        }
        await this.execute('_zw_f.close()');
        if (await this.fileHash(staging) !== file.sha256) throw new Error('暂存文件回读校验失败。');
        if (this.cancelled) throw new Error('上传已取消。');
        if (hadOriginal) { await this.execute(`os.rename("main.py",${quote(backup)})`); moved = true; }
        await this.execute(`os.rename(${quote(staging)},"main.py")`);
        staged = false;
        installed = true;
        if (await this.fileHash('main.py') !== file.sha256) throw new Error('目标文件回读校验失败。');
        if (this.cancelled) throw new Error('上传已取消。');
        await this.friendly();
        const receipt: UploadReceipt = { projectId: manifest.projectId, revision: manifest.revision, sha256: file.sha256,
          identity: this.identity!, backupPath: hadOriginal ? backup : null, verifiedAt: new Date().toISOString() };
        this.receipt = receipt;
        this.log(`\n[上传回读一致] main.py · ${bytes.length} bytes\n${hadOriginal ? `设备备份保留：${backup}\n` : ''}尚未运行；点击「运行」启动程序。\n`);
        return receipt;
      } catch (error) {
        this.receipt = null;
        try {
          if (this.mode === 'raw' && !this.fault) {
            if (staged) await this.execute(`try:\n _zw_f.close()\nexcept:\n pass\nif ${quote(staging)} in os.listdir():\n os.remove(${quote(staging)})`);
            if (moved) {
              await this.execute(`if "main.py" in os.listdir():\n os.remove("main.py")\nos.rename(${quote(backup)},"main.py")`);
              this.log('\n[恢复] 原 main.py 已恢复。\n');
            } else if (installed && !hadOriginal) await this.execute('os.remove("main.py")');
            await this.friendly();
            this.log('\n[上传未完成] 未将结果标为成功。\n');
          } else throw new Error('串口不再可用。');
        } catch {
          this.log(`\n[需要恢复] 请重新连接并核对 main.py、${staging} 和 ${backup}；浏览器备份已保留。\n`);
        }
        throw error;
      }
    });
  }

  private async fileHash(path: string): Promise<string> {
    const result = (await this.execute(`_zw_h=hashlib.sha256()\n_zw_r=open(${quote(path)},"rb")\nwhile True:\n _zw_b=_zw_r.read(256)\n if not _zw_b: break\n _zw_h.update(_zw_b)\n_zw_r.close()\nprint(binascii.hexlify(_zw_h.digest()).decode())`)).trim();
    if (!/^[a-f0-9]{64}$/.test(result)) throw new Error('设备未返回有效 SHA-256。');
    return result;
  }

  async listFiles(): Promise<DeviceFile[]> {
    if (this.state !== 'connected') throw new Error('先连接设备并停止正在运行的程序。');
    return this.operation(async () => {
      await this.enterRaw();
      const response = await this.execute('import os\n' + JSON_IMPORT + '\n_zw_names=os.listdir()\nif len(_zw_names)>256: raise ValueError("Too many root files")\nprint(json.dumps([{"path":n,"size":os.stat(n)[6],"directory":bool(os.stat(n)[0]&0x4000)} for n in _zw_names]))');
      const files: unknown = JSON.parse(response.trim());
      if (!Array.isArray(files) || files.length > 256 || files.some(item => !item || typeof item.path !== 'string' || !Number.isSafeInteger(item.size) || item.size < 0 || typeof item.directory !== 'boolean')) throw new Error('设备文件列表响应无效。');
      await this.friendly();
      return (files as DeviceFile[]).sort((a, b) => a.path.localeCompare(b.path));
    });
  }

  async readFile(path: string): Promise<DeviceFileContent> {
    if (this.state !== 'connected') throw new Error('先连接设备并停止正在运行的程序。');
    if (!path || path.length > 128 || path === '.' || path === '..' || /[/\\\x00-\x1f\x7f]/.test(path)) throw new Error('仅允许读取设备根目录中的单个文件。');
    return this.operation(async () => {
      await this.enterRaw();
      await this.execute('import os, binascii\n' + HASH_IMPORT);
      const size = Number((await this.execute(`_zw_s=os.stat(${quote(path)})\nif _zw_s[0]&0x4000: raise ValueError("Not a file")\nprint(_zw_s[6])`)).trim());
      if (!Number.isSafeInteger(size) || size < 0 || size > 65536) throw new Error('设备文件超过64 KiB读取上限或大小无效。');
      const bytes = new Uint8Array(size);
      await this.execute(`_zw_read=open(${quote(path)},"rb")`);
      try {
        for (let offset = 0; offset < size; offset += 128) {
          const data = (await this.execute('print(binascii.hexlify(_zw_read.read(128)).decode())')).trim();
          const expected = Math.min(128, size - offset);
          if (!/^(?:[a-f0-9]{2})*$/.test(data) || data.length !== expected * 2) throw new Error('设备文件读取不完整。');
          for (let i = 0; i < expected; i++) bytes[offset + i] = parseInt(data.slice(i * 2, i * 2 + 2), 16);
        }
      } finally {
        if (!this.fault) await this.execute('_zw_read.close()');
      }
      const digest = await sha256(bytes);
      if (await this.fileHash(path) !== digest) throw new Error('设备文件读取摘要不一致。');
      await this.friendly();
      this.log(`\n[文件读取校验一致] ${path} · ${size} bytes\n`);
      return { path, bytes, sha256: digest };
    });
  }

  async run(): Promise<void> {
    if (!this.receipt || this.state !== 'connected') throw new Error('先完成上传回读校验。');
    await this.operation(async () => {
      await this.enterRaw();
      // Refuse a stale receipt if main.py was changed by another tool.
      await this.execute('import binascii\n' + HASH_IMPORT);
      if (await this.fileHash('main.py') !== this.receipt!.sha256) { this.receipt = null; throw new Error('设备 main.py 已变更，请重新上传。'); }
      await this.friendly();
      this.outputTail = ''; this.runTraceback = false;
      this.setState('running');
      this.capture = false;
      await this.send('exec(compile(open("main.py").read(),"main.py","exec"))\r');
      this.log('\n[运行命令已提交] 请根据串口输出和实物观察判断结果。\n');
    }, 'running');
  }
  async stop(): Promise<void> {
    await this.operation(async () => {
      this.buffer = '';
      await this.send('\x03\x03');
      const output = await this.until('>>> ');
      if (output) this.log(output);
      this.mode = 'friendly';
      this.log('\n[已中断] 设备返回 REPL 提示符。\n');
    });
  }
  async repl(command: string): Promise<void> {
    if (this.busy || this.state !== 'connected' || this.mode !== 'friendly') throw new Error('先停止程序并等待设备空闲。');
    if (!command.trim() || command.length > 4000 || /[\r\n\x00-\x1f\x7f]/.test(command)) throw new Error('REPL请输入一条不含控制字符的命令，最多4000字符。');
    this.receipt = null; // arbitrary REPL can modify files; never reuse an old receipt.
    this.outputTail = ''; this.runTraceback = false;
    this.setState('running');
    try { await this.send(command + '\r'); }
    catch (err) { this.setState('attention'); throw err; }
  }
  async disconnect(): Promise<void> {
    this.closing = true;
    this.cancelled = true;
    this.receipt = null;
    try { await this.reader?.cancel(); await this.reading; } catch { /* disconnected */ }
    this.reader?.releaseLock(); this.reader = undefined;
    try { this.writer?.releaseLock(); this.writer = undefined; await this.port.close(); } catch { /* already closed */ }
    this.identity = null;
    this.setState('disconnected');
  }
}
