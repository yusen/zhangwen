import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { inspectNodeDependencies } from '../dependencies.mjs';

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'zhangwen-dependency-test-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const write = (path, value) => {
    const target = join(root, path);
    mkdirSync(join(target, '..'), { recursive: true });
    writeFileSync(target, typeof value === 'string' ? value : JSON.stringify(value));
  };
  write('package.json', { dependencies: { example: '1.2.3' } });
  write('package-lock.json', { packages: {
    '': { dependencies: { example: '1.2.3' } },
    'node_modules/example': { version: '1.2.3' },
    'node_modules/platform-binary': { version: '2.0.0', optional: true, os: ['linux'], cpu: ['x64'] },
  } });
  write('node_modules/example/package.json', { name: 'example', version: '1.2.3', bin: { example: 'cli.js' } });
  write('node_modules/example/cli.js', 'console.log("ok");');
  return { root, write, inspect: () => inspectNodeDependencies(root, 'win32', 'x64') };
}

test('complete packages are reused even without a setup or npm receipt; foreign platform binaries are skipped', t => {
  const f = fixture(t);
  assert.deepEqual(f.inspect(), { ready: true, problems: [] });
});

test('a receipt cannot hide a removed package', t => {
  const f = fixture(t);
  f.write('node_modules/.package-lock.json', { packages: { 'node_modules/example': { version: '1.2.3' } } });
  rmSync(join(f.root, 'node_modules/example/package.json'));
  assert.equal(f.inspect().ready, false);
  assert.equal(f.inspect().problems[0].installed, null);
});

test('an installed version differing from the lock requires repair', t => {
  const f = fixture(t);
  f.write('node_modules/example/package.json', { version: '1.2.2' });
  assert.equal(f.inspect().ready, false);
  assert.equal(f.inspect().problems[0].expected, '1.2.3');
});

test('an applicable missing native package requires repair even if marked optional', t => {
  const f = fixture(t);
  assert.equal(inspectNodeDependencies(f.root, 'linux', 'x64').ready, false);
});

test('missing package executables are detected despite correct metadata', t => {
  const f = fixture(t);
  rmSync(join(f.root, 'node_modules/example/cli.js'));
  assert.equal(f.inspect().ready, false);
  assert.equal(f.inspect().problems[0].reason, 'missing executable');
});
