import { spawn } from 'node:child_process';
import { python, env, root } from './python.mjs';
const child = spawn(python, ['-m', 'pytest', 'services/local-api/tests', '-q', ...process.argv.slice(2)], { cwd: root, env, stdio: 'inherit', windowsHide: true });
child.on('error', error => { console.error(error.message); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
