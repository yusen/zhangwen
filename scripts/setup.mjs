// Source installation, with cached successful steps. Never touches user data.
import { spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, openSync, writeFileSync, readFileSync, readdirSync, closeSync, unlinkSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { root } from './python.mjs';
import { inspectNodeDependencies } from './dependencies.mjs';

const runtime = resolve(root, '.runtime');
mkdirSync(runtime, { recursive: true });
const lockPath = join(runtime, 'setup.lock');
const statePath = join(runtime, 'setup-state.json');
const localPython = resolve(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const npmCli = process.env.ZHANGWEN_NPM_CLI || resolve(process.execPath, '..', process.platform === 'win32' ? 'node_modules/npm/bin/npm-cli.js' : '../lib/node_modules/npm/bin/npm-cli.js');
const args = process.argv.slice(2);
const prepareOnly = args.includes('--prepare-only');
const serverArgs = args.filter(arg => arg !== '--prepare-only');
let state = {};
try { state = JSON.parse(readFileSync(statePath, 'utf8')); } catch { /* first run */ }
function digest(paths) {
  const hash = createHash('sha256');
  function visit(relative) {
    const path = resolve(root, relative);
    if (!existsSync(path)) return;
    const entries = readdirSafe(path);
    if (entries) for (const item of entries.sort()) visit(`${relative}/${item}`);
    else hash.update(relative).update(readFileSync(path));
  }
  for (const path of paths) visit(path);
  return hash.digest('hex');
}
function readdirSafe(path) {
  try { return readdirSync(path); } catch (error) { if (error.code === 'ENOTDIR') return null; throw error; }
}
function run(command, argv, extraEnv = {}) {
  return new Promise((accept, reject) => {
    const child = spawn(command, argv, { cwd: root, env: { ...process.env, ...extraEnv }, stdio: 'inherit', windowsHide: true });
    const stop = signal => child.kill(signal);
    const interrupt = () => stop('SIGINT');
    const terminate = () => stop('SIGTERM');
    process.on('SIGINT', interrupt); process.on('SIGTERM', terminate);
    child.on('error', reject);
    child.on('exit', code => {
      process.off('SIGINT', interrupt); process.off('SIGTERM', terminate);
      code === 0 ? accept() : reject(new Error(`${command} 退出码 ${code ?? 'signal'}`));
    });
  });
}
async function npm(argv) {
  if (existsSync(npmCli)) return run(process.execPath, [npmCli, ...argv]);
  // Common Unix installations can keep npm outside the node prefix.
  if (process.platform !== 'win32') return run('npm', argv);
  throw new Error('找不到 npm，请使用 start-web.bat 准备完整 Node 环境。');
}
let lock;
try {
  if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('请使用 Node.js 22 或更新版本；Windows 可直接双击 start-web.bat。');
  if (existsSync(lockPath)) {
    const pid = Number(readFileSync(lockPath, 'utf8'));
    if (!Number.isSafeInteger(pid) || pid <= 0) throw new Error('安装锁无效，请关闭安装窗口后删除 .runtime/setup.lock 再试。');
    try { process.kill(pid, 0); throw new Error('本目录正在安装，请等待另一个启动窗口完成。'); }
    catch (error) { if (error.code !== 'ESRCH') throw error; }
    unlinkSync(lockPath);
  }
  lock = openSync(lockPath, 'wx');
  writeFileSync(lock, String(process.pid));
  if (!existsSync(localPython)) {
    console.log('准备项目内 Python 虚拟环境（需要 Python 3.11+）…');
    await run(process.env.ZHANGWEN_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'), ['-m', 'venv', resolve(root, '.venv')]);
  }
  await run(localPython, ['-c', 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"']);
  function inspectPython() {
    const probe = spawnSync(localPython, ['scripts/check-python-deps.py'], { cwd: root, env: { ...process.env, PYTHONUTF8: '1' }, encoding: 'utf8', timeout: 30_000, windowsHide: true });
    try { return JSON.parse(probe.stdout); }
    catch { throw new Error('Python 依赖检测失败，请检查 .venv 是否可运行。'); }
  }
  console.log('检测实际安装的 Python 依赖…');
  const pythonDeps = inspectPython();
  if (!pythonDeps.ready) {
    console.log(`Python 依赖缺失或不匹配（${pythonDeps.problems.length} 项），补齐锁定依赖…`);
    if (!pythonDeps.pipAvailable) await run(localPython, ['-m', 'ensurepip', '--upgrade']);
    await run(localPython, ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', 'services/local-api/requirements-web-lock.txt'], { PYTHONUTF8: '1' });
    if (!inspectPython().ready) {
      console.log('Python 安装记录存在但模块不可用，修复项目内锁定依赖…');
      await run(localPython, ['-m', 'pip', 'install', '--disable-pip-version-check', '--force-reinstall', '--no-deps', '-r', 'services/local-api/requirements-web-lock.txt'], { PYTHONUTF8: '1' });
    }
    if (!inspectPython().ready) throw new Error('Python 依赖安装后仍未通过检查，请查看上方错误。');
  } else console.log('Python 依赖完整，复用现有安装。');
  console.log('检测实际安装的前端依赖…');
  const nodeDeps = inspectNodeDependencies(root);
  if (!nodeDeps.ready) {
    console.log(`前端依赖缺失或不匹配（${nodeDeps.problems.length} 项），恢复锁定依赖并优先复用下载缓存…`);
    await npm(['ci', '--prefer-offline', '--no-audit', '--no-fund']);
    if (!inspectNodeDependencies(root).ready) throw new Error('前端依赖安装后仍未通过检查，请查看上方错误。');
  } else console.log('前端依赖完整，复用现有安装。');
  const buildKey = digest(['apps/web/src', 'apps/web/index.html', 'packages', 'tsconfig.json', 'vite.config.ts', 'package.json', 'package-lock.json']);
  if (state.build !== buildKey || !existsSync(resolve(root, 'dist/index.html'))) {
    console.log('构建工作台页面…');
    await npm(['run', 'build']);
    state.build = buildKey;
    writeFileSync(statePath, JSON.stringify(state, null, 2));
  }
} catch (error) {
  console.error(`准备失败：${error.message}\n修复网络或环境后重新启动即可；项目数据未被重置。`);
  process.exitCode = 1;
} finally {
  if (lock !== undefined) { closeSync(lock); unlinkSync(lockPath); }
}
if (!process.exitCode) {
  if (prepareOnly) console.log('安装和构建完成。');
  else {
    if (process.platform === 'darwin') {
      // Older in-app updaters run their own old installer: the selected new
      // version repairs the missing app before its first normal launch.
      const repair = spawnSync(localPython, ['scripts/create-macos-app.py', '--repair-managed',
        ...(process.env.ZHANGWEN_APPLICATIONS_DIR ? ['--applications-dir', process.env.ZHANGWEN_APPLICATIONS_DIR] : [])],
      { cwd: root, stdio: 'inherit', timeout: 15_000 });
      if (repair.error || repair.status !== 0) console.warn('应用入口未能修复；平台仍可启动。请重跑最新安装命令，查看 Application 路径和错误。');
    }
    try { await run(process.execPath, ['scripts/start.mjs', ...serverArgs]); }
    catch (error) { console.error(error.message); process.exitCode = 1; }
  }
}
