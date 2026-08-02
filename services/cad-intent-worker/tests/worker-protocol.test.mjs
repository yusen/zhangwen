import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const workerPath = fileURLToPath(new URL('../src/worker.mjs', import.meta.url));

test('worker exposes reviewed source tools without an HTTP or host-path surface', async () => {
  const response = await request('describe', {});
  assert.equal(response.ok, true);
  assert.equal(response.result.source, 'ZW-CAD-intent');
  assert.ok(response.result.workflowTools.some((item) => item.id === 'model_edit'));
  assert.deepEqual(response.result.boundaries.slice(0, 2), ['no_http', 'no_project_store']);
});

test('worker drafts the deterministic watering template and returns bound source', async () => {
  const response = await request('draft', {
    projectId: 'prj_worker_test',
    baseProjectVersion: 0,
    prompt: 'automatic plant watering system',
    routeContext: {},
    capabilitySnapshot: [],
    hardwareProfileSnapshot: { selectedHardwareIds: [] },
  });
  assert.equal(response.ok, true);
  assert.equal(response.result.status, 'ready');
  assert.match(response.result.source, /import cadquery as cq/);
  assert.match(response.result.sourceSha256, /^[a-f0-9]{64}$/);
  assert.ok(response.result.objectIndex.some((item) => item.id === 'base_part'));
});

test('generic structure request uses the controlled project context', async () => {
  const response = await request('draft', {
    projectId: 'prj_context_test',
    baseProjectVersion: 2,
    prompt: '给这个项目生成一个外壳',
    projectStructureContext: {
      schemaVersion: 1,
      projectId: 'prj_context_test',
      projectVersion: 2,
      projectionHash: 'a'.repeat(64),
      contextSha256: 'b'.repeat(64),
      projectName: '电子相册',
      initialIdea: '做一个行空板电子相册',
      currentRecommendation: '使用行空板 K10 和板载摄像头',
      confirmedFacts: [
        { key: 'photo_source', label: '照片来源', displayValue: '板载摄像头' },
      ],
      selectedHardware: [
        { id: 'hw_seed_unihiker_k10', name: '行空板 K10' },
      ],
      mechanicalProfiles: [],
      upstreamArtifacts: [],
      currentCadRevision: null,
    },
    capabilitySnapshot: [],
  });

  assert.equal(response.ok, true);
  assert.equal(response.result.status, 'ready');
  assert.equal(response.result.deterministicProduct.id, 'unihiker_photo_album');
});

test('explicit current request wins over an older project product context', async () => {
  const response = await request('draft', {
    projectId: 'prj_context_priority',
    baseProjectVersion: 3,
    prompt: '改为生成行空板电子相册外壳',
    projectStructureContext: {
      schemaVersion: 1,
      projectId: 'prj_context_priority',
      projectVersion: 3,
      projectionHash: 'c'.repeat(64),
      contextSha256: 'd'.repeat(64),
      projectName: '旧浇花项目',
      initialIdea: '自动浇花装置',
      currentRecommendation: '土壤湿度传感器和水泵',
      confirmedFacts: [],
      selectedHardware: [],
      mechanicalProfiles: [],
      upstreamArtifacts: [],
      currentCadRevision: null,
    },
    capabilitySnapshot: [],
  });

  assert.equal(response.ok, true);
  assert.equal(response.result.status, 'ready');
  assert.equal(response.result.deterministicProduct.id, 'unihiker_photo_album');
});

test('model edit creates one exact hash-bound parameter patch', async () => {
  const source = 'parameters = {"wall_thickness": 2.4}\n';
  const hash = await sha256(source);
  const response = await request('plan_edit', {
    projectId: 'prj_worker_test',
    baseProjectVersion: 1,
    prompt: 'wall thickness increase by 1mm',
    source,
    sourceSha256: hash,
    objectIndex: [],
  });
  assert.equal(response.ok, true);
  assert.equal(response.result.status, 'ready');
  assert.equal(response.result.patch.search, 'wall_thickness": 2.4');
  assert.equal(response.result.patch.replace, 'wall_thickness": 3.4');
  assert.match(response.result.resultSourceSha256, /^[a-f0-9]{64}$/);
});

test('worker rejects host paths and stale source hashes', async () => {
  const forbidden = await request('route', { prompt: 'box', rootDir: 'C:/unsafe' });
  assert.equal(forbidden.ok, false);
  assert.equal(forbidden.error.code, 'FORBIDDEN_FIELD');

  const stale = await request('plan_edit', {
    prompt: 'wall thickness increase by 1mm',
    source: 'wall_thickness = 2',
    sourceSha256: '0'.repeat(64),
  });
  assert.equal(stale.ok, false);
  assert.equal(stale.error.code, 'SOURCE_HASH_MISMATCH');
});

test('real export action accepts only a hash-bound source and host-owned staging', async () => {
  const source = 'import cadquery as cq\nresult = cq.Workplane("XY").box(1, 1, 1)\n';
  const response = await request('build', {
    source,
    sourceSha256: await sha256(source),
  });
  assert.equal(response.ok, false);
  assert.equal(response.error.code, 'CAD_STAGING_UNAVAILABLE');
});

async function request(action, payload) {
  const child = spawn(process.execPath, [workerPath], { stdio: ['pipe', 'pipe', 'pipe'] });
  let stdout = '';
  let stderr = '';
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', (chunk) => { stdout += chunk; });
  child.stderr.on('data', (chunk) => { stderr += chunk; });
  child.stdin.end(`${JSON.stringify({ protocol: 'zhangwen.cad.intent.worker', version: 1, id: `req-${action}`, action, payload })}\n`);
  const exitCode = await new Promise((resolve) => child.once('close', resolve));
  assert.equal(exitCode, 0, stderr);
  return JSON.parse(stdout.trim());
}

async function sha256(value) {
  const { createHash } = await import('node:crypto');
  return createHash('sha256').update(value).digest('hex');
}
