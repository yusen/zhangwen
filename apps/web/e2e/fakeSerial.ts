/** In-browser protocol peer for isolated E2E only. Never used by the product. */
export function installFakeSerial() {
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  const files = new Map<string, Uint8Array>([['main.py', encoder.encode('print("old")\n')], ['user.txt', encoder.encode('preserved')]]);
  let stream: ReadableStreamDefaultController<Uint8Array>;
  let raw = false;
  let current = '';
  let offset = 0;
  const hex = (bytes: Uint8Array) => Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  const digest = async (bytes: Uint8Array) => hex(new Uint8Array(await crypto.subtle.digest('SHA-256', new Uint8Array(bytes).buffer)));
  const emit = (value: string) => stream.enqueue(encoder.encode(value));
  const port = {
    open: async () => {}, close: async () => {},
    readable: new ReadableStream<Uint8Array>({ start(controller) { stream = controller; } }),
    writable: new WritableStream<Uint8Array>({ async write(bytes) {
      const value = decoder.decode(bytes);
      if (value.includes('\x01')) { raw = true; emit('raw REPL; CTRL-B to exit\r\n>'); return; }
      if (value === '\x02') { raw = false; emit('\r\n>>> '); return; }
      if (!raw) { emit(value.includes('\x03') ? '\r\n>>> ' : value + '\r\nFAKE_PROGRAM_DONE\r\n>>> '); return; }
      const code = value.slice(0, -1);
      let out = '';
      if (code.includes('sys.implementation.name')) out = JSON.stringify({ implementation: 'micropython', platform: 'esp32', machine: 'FAKE mPython ESP32', uniqueId: 'fake-ui-only' });
      else if (code.includes('_zw_names=os.listdir')) out = JSON.stringify([...files].map(([path, data]) => ({ path, size: data.length, directory: false })));
      else if (code.includes('"exists"')) out = JSON.stringify({ exists: files.has('main.py'), size: files.get('main.py')?.length ?? 0 });
      else if (code.startsWith('_zw_s=os.stat')) out = String(files.get(/os.stat\("([^"]+)"/.exec(code)![1])!.length);
      else if (code.startsWith('_zw_old=open')) { current = 'main.py'; offset = 0; }
      else if (code.startsWith('_zw_read=open')) { current = /open\("([^"]+)"/.exec(code)![1]; offset = 0; }
      else if (/_zw_(?:old|read)\.read/.test(code)) { out = hex(files.get(current)!.slice(offset, offset + 128)); offset += 128; }
      else if (code.startsWith('_zw_f=open')) { current = /open\("([^"]+)"/.exec(code)![1]; files.set(current, new Uint8Array()); }
      else if (code.startsWith('_zw_f.write')) {
        const data = /unhexlify\("([a-f0-9]*)"/.exec(code)![1];
        const added = new Uint8Array(data.length / 2);
        for (let i = 0; i < added.length; i++) added[i] = parseInt(data.slice(i * 2, i * 2 + 2), 16);
        const prior = files.get(current)!; const joined = new Uint8Array(prior.length + added.length);
        joined.set(prior); joined.set(added, prior.length); files.set(current, joined);
      } else if (code.includes('_zw_h=hashlib.sha256')) out = await digest(files.get(/_zw_r=open\("([^"]+)"/.exec(code)![1])!);
      else if (code.includes('hashlib.sha256(b""')) out = await digest(new Uint8Array());
      if (code.includes('os.rename')) { const match = /os.rename\("([^"]+)","([^"]+)"/.exec(code)!; files.set(match[2], files.get(match[1])!); files.delete(match[1]); }
      emit('OK' + out + (out ? '\r\n' : '') + '\x04\x04>');
    } }),
  };
  Object.defineProperty(navigator, 'serial', { value: { requestPort: async () => port }, configurable: true });
}
