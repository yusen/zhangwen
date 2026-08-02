import assert from 'node:assert/strict';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { sanitizeBuildResult } from '../src/build-result.mjs';

test('build result publishes only files that exist below host staging', async () => {
  const rootDir = await mkdtemp(path.join(os.tmpdir(), 'zw-cad-result-'));
  const exportDir = path.join(rootDir, 'exports', 'job');
  const previewPath = path.join(exportDir, 'preview.glb');
  const missingPath = path.join(exportDir, 'optional-lid.stl');
  const outsidePath = path.join(os.tmpdir(), 'zw-cad-outside.step');
  try {
    await mkdir(exportDir, { recursive: true });
    await writeFile(previewPath, Buffer.from('glTF-preview'));
    await writeFile(outsidePath, Buffer.from('ISO-10303-21'));

    const result = await sanitizeBuildResult(
      {
        status: 'artifact_exports',
        exports: [
          { id: 'preview', format: 'glb', path: previewPath },
          { id: 'optional-lid', format: 'stl', path: missingPath, status: 'available' },
          { id: 'outside', format: 'step', path: outsidePath, status: 'available' },
        ],
      },
      rootDir,
      'a'.repeat(64),
    );

    const preview = result.exports.find((item) => item.id === 'preview');
    const missing = result.exports.find((item) => item.id === 'optional-lid');
    const outside = result.exports.find((item) => item.id === 'outside');
    assert.equal(preview.status, 'available');
    assert.equal(preview.storageKey, 'exports/job/preview.glb');
    assert.equal(missing.status, 'unavailable');
    assert.equal(missing.storageKey, '');
    assert.equal(outside.status, 'unavailable');
    assert.equal(outside.storageKey, '');
  } finally {
    await rm(rootDir, { recursive: true, force: true });
    await rm(outsidePath, { force: true });
  }
});
