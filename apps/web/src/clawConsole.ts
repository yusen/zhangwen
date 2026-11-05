import type { SerialPortLike } from './serial';

/** ESP console only: no raw REPL, shell, reset, arbitrary command or auto-retry. */
export class ClawConsole {
  private reader?: ReadableStreamDefaultReader<Uint8Array>;
  private writer?: WritableStreamDefaultWriter<Uint8Array>;
  private reading?: Promise<void>;
  private buffer = '';
  private fault = '';
  private notify?: () => void;
  private busy = false;
  private closed = false;
  constructor(private port: SerialPortLike, private log: (text: string) => void) {}

  async connect() {
    try {
      await this.port.open({ baudRate: 115200 });
      if (!this.port.readable || !this.port.writable) throw new Error('USB控制台没有可读写通道。');
      this.reader = this.port.readable.getReader(); this.writer = this.port.writable.getWriter();
      this.reading = this.pump();
      await this.command('', 5000);
      const help = await this.command('help lua', 5000);
      if (!help.includes('--run') || !help.includes('--timeout-ms')) throw new Error('未识别到兼容的Claw Lua控制台。请检查USB端口及固件；无需刷入MicroPython。');
    } catch (e) { await this.disconnect(); throw e; }
  }
  private async pump() {
    const decoder = new TextDecoder();
    try {
      while (this.reader) {
        const part = await this.reader.read();
        if (part.done) break;
        const text = decoder.decode(part.value, { stream: true });
        this.log(text);
        if (this.busy) {
          this.buffer += text;
          if (this.buffer.length > 16000) { this.fault = '控制台输出超过16000字符，运行结果待核对，未自动重试。'; break; }
          this.notify?.();
        }
      }
      if (!this.closed && !this.fault) this.fault = 'USB控制台已断开；设备任务可能仍在运行，未自动重连或重发。';
    } catch { if (!this.closed) this.fault = 'USB读取失败，运行结果未知。'; }
    finally { this.notify?.(); }
  }
  private async command(command: string, timeout: number) {
    if (this.busy || this.closed || this.fault || !this.writer) throw new Error(this.fault || '控制台未就绪或正在运行。');
    this.busy = true; this.buffer = '';
    const until = Date.now() + timeout;
    try {
      await this.writer.write(new TextEncoder().encode(command + '\r\n'));
      while (true) {
        if (this.fault) throw new Error(this.fault);
        const clean = this.buffer.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '');
        // A delayed idle prompt may arrive after the next write. Require this
        // command's echo before accepting a prompt; never treat it as a run receipt.
        if ((!command || clean.includes(command)) && /(?:^|[\r\n])[\w(). -]{1,48}> ?$/.test(clean)) return clean;
        if (Date.now() >= until) {
          this.fault = '未在期限内收到控制台返回，结果未知；请核对日志后断开重连，不会自动重发。';
          throw new Error(this.fault);
        }
        await new Promise<void>(resolve => {
          const timer = setTimeout(() => { this.notify = undefined; resolve(); }, Math.min(250, until - Date.now()));
          this.notify = () => { clearTimeout(timer); this.notify = undefined; resolve(); };
        });
      }
    } finally { this.busy = false; }
  }
  async run(path: string, timeoutMs: number) {
    if (!/^temp\/zw_[a-f0-9]{16}\.lua$/.test(path) || !Number.isInteger(timeoutMs) || timeoutMs < 1000 || timeoutMs > 60000) throw new Error('Lua运行清单不正确。');
    // Every run is bounded; a prompt means console returned, never physical success.
    return this.command(`lua --run --path ${path} --timeout-ms ${timeoutMs}`, timeoutMs + 5000);
  }
  async disconnect() {
    this.closed = true;
    try { await this.reader?.cancel(); } catch { /* already unplugged */ }
    await this.reading;
    this.reader?.releaseLock(); this.writer?.releaseLock(); this.reader = undefined; this.writer = undefined;
    try { await this.port.close(); } catch { /* unopened/unplugged */ }
  }
}
