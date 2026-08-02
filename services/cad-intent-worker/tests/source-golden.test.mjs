import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  buildConversationRoute,
} from '../../../references/source-packages/ZW-CAD-intent/server/conversation-route.js';
import {
  detectDeterministicProduct,
  listDeterministicTemplateProjects,
} from '../../../references/source-packages/ZW-CAD-intent/server/deterministic-products.js';
import {
  detectStandaloneStructuralPartsRequest,
} from '../../../references/source-packages/ZW-CAD-intent/server/structural-parts.js';
import {
  isSurfaceEngravingPrompt,
} from '../../../references/source-packages/ZW-CAD-intent/server/surface-engraving.js';
import { listWorkflowTools } from '../../../references/source-packages/ZW-CAD-intent/server/workflow-tools.js';

const golden = JSON.parse(
  await readFile(new URL('./goldens/source-contract.golden.json', import.meta.url), 'utf8'),
);

test('conversation routes stay bound to the source behavior', () => {
  const actual = golden.routes.map((entry) => {
    const result = buildConversationRoute(entry.input);
    return {
      route_action: result.route_action,
      confidence: result.confidence,
      workflow_stage: result.workflow_stage,
    };
  });
  assert.deepEqual(actual, golden.routes.map((entry) => entry.output));
});

test('deterministic templates, structural route and engraving remain discoverable', () => {
  const watering = detectDeterministicProduct({ prompt: '做一个自动浇花系统' });
  const enclosure = detectDeterministicProduct({ prompt: '给掌控板 3.0 做一个外壳' });
  assert.equal(watering?.product?.id, golden.productIds[0]);
  assert.equal(enclosure?.product?.id, golden.productIds[1]);

  const structural = detectStandaloneStructuralPartsRequest({
    routeAction: 'standalone_structural_parts',
    designMode: 'structural_part_project',
  });
  assert.equal(structural.requested, true);
  assert.equal(isSurfaceEngravingPrompt('在上盖正中央刻字“掌问”'), true);
});

test('template and workflow tool catalogs match the reviewed golden', () => {
  assert.deepEqual(
    listDeterministicTemplateProjects().map((item) => item.id),
    golden.templateIds,
  );
  assert.deepEqual(
    listWorkflowTools().map((item) => item.id),
    golden.workflowToolIds,
  );
});
