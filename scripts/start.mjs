import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { python, env, root } from './python.mjs';
if (!existsSync(resolve(root, 'dist/index.html'))) {
  console.error('前端尚未构建。请先执行 npm install 和 npm run build。');
  process.exit(1);
}
const child = spawn(python, ['-m', 'zhangwen.web', ...process.argv.slice(2)], { cwd: root, env, stdio: 'inherit', windowsHide: true });
child.on('error', () => { console.error('无法启动 Python。请先按 README 准备 Python 环境。'); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
