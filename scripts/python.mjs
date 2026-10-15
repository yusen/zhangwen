import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
export const root = resolve(import.meta.dirname, '..');
const local = resolve(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
export const python = existsSync(local) ? local : (process.platform === 'win32' ? 'python' : 'python3');
export const env = { ...process.env, PYTHONPATH: resolve(root, 'services/local-api'), PYTHONUTF8: '1' };
