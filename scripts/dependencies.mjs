import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { equivalentRegistryUrl } from './download-sources.mjs';

function matchesPlatform(allowed, current) {
  if (!allowed) return true;
  if (allowed.includes(`!${current}`)) return false;
  const positive = allowed.filter(value => !value.startsWith('!'));
  return !positive.length || positive.includes(current) || positive.includes('any');
}

export function inspectNodeDependencies(root, platform = process.platform, arch = process.arch) {
  const lock = JSON.parse(readFileSync(resolve(root, 'package-lock.json'), 'utf8'));
  const manifest = JSON.parse(readFileSync(resolve(root, 'package.json'), 'utf8'));
  const problems = [];
  // A stale/missing receipt never substitutes for checking installed packages.
  let receipt;
  try { receipt = JSON.parse(readFileSync(resolve(root, 'node_modules/.package-lock.json'), 'utf8')); } catch { /* npm may not have written one */ }
  for (const name of Object.keys({ ...manifest.dependencies, ...manifest.devDependencies })) {
    if (!lock.packages[`node_modules/${name}`]) throw new Error(`package-lock.json 缺少 ${name}，请先同步锁文件。`);
  }
  for (const [path, expected] of Object.entries(lock.packages)) {
    if (!path || !matchesPlatform(expected.os, platform) || !matchesPlatform(expected.cpu, arch)) continue;
    let installed;
    try { installed = JSON.parse(readFileSync(resolve(root, path, 'package.json'), 'utf8')); } catch { /* missing or broken */ }
    if (!installed || installed.version !== expected.version) {
      problems.push({ package: path, expected: expected.version, installed: installed?.version ?? null });
      continue;
    }
    const recorded = receipt?.packages?.[path];
    if (recorded && ((recorded.integrity && expected.integrity && recorded.integrity !== expected.integrity)
      || (recorded.resolved && expected.resolved && !equivalentRegistryUrl(recorded.resolved, expected.resolved)))) {
      problems.push({ package: path, reason: 'installed package differs from lock' });
    }
    if (typeof installed.bin === 'string' && !existsSync(resolve(root, path, installed.bin))) {
      problems.push({ package: path, reason: 'missing executable' });
    } else if (installed.bin && typeof installed.bin === 'object') {
      if (Object.values(installed.bin).some(bin => !existsSync(resolve(root, path, bin)))) problems.push({ package: path, reason: 'missing executable' });
    }
  }
  return { ready: !problems.length, problems };
}
