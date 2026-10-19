// No network listener. FastAPI supplies a bounded command over stdin.
// Only this trusted pipeline generates Python; no caller-supplied code is run.
import { configurePlatformModel } from './server/model-sources.js';
import { listHardwareLibrary } from './server/hardware-library.js';
import { prepareDesign, buildDesignFromDraft, regenerateDesign, validateCurrentDesign } from './server/pipeline.js';
import { verifyBomFunctionCoverage } from './server/function-verifier.js';
import { buildCadQueryArtifact } from './server/cadquery-runner.js';
import { prepare } from './prepare.js';

let input = '';
for await (const chunk of process.stdin) { input += chunk; if (input.length > 16000000) throw new Error('Input too large'); }
const job = JSON.parse(input);
configurePlatformModel(job.settings);
const environment = job.environment;
// Offline mode is explicitly limited to an enclosure for the selected parts.
// It never claims to have verified product functions with AI.
const functionVerifier = job.offline ? async ({bom}) => {
  const missing = bom.filter(x => !job.body.selectedHardwareIds.includes(x.hardware_id));
  return {status: missing.length ? 'needs_input' : 'ok', verification_status: missing.length ? 'fail' : 'pass',
    reason: missing.length ? '请选定主控及全部需要装入外壳的硬件。' : '',
    covered_functions: ['仅为用户选定硬件设计外壳；未评估其他产品功能'], source: 'selected_parts_only',
    library_violations: missing.map(x => x.hardware_id)};
} : verifyBomFunctionCoverage;
const context = {rootDir: job.rootDir, environment, functionVerifier, hardwareLibrarySummary: listHardwareLibrary().profiles};
let result;
if (job.action === 'catalog') result = listHardwareLibrary();
else if (job.action === 'selected') result = await prepareDesign({...job.body, prompt: '为当前选定硬件设计一个带盖矩形外壳，保留USB开口'}, context);
else if (job.action === 'build') result = await buildDesignFromDraft(job.body, context);
else if (job.action === 'parameters') result = await regenerateDesign(job.body, context);
else if (job.action === 'validate') result = {...job.previousResult, ...validateCurrentDesign({...job.body, cadquery_code: job.previousResult?.cadquery_code || ''}, context)};
else result = await prepare(job.body, context);
if (result.status === 'artifact' && job.action !== 'validate') {
  // The artifact was just generated here from checked structured data.
  const build = await buildCadQueryArtifact({rootDir: job.rootDir, python: job.python, environment,
    body: {designId: result.design_state.id, artifact: result}});
  if (build.status === 'artifact_exports') {
    result = build.artifact || {...result, exports: [...result.exports, ...build.exports]};
  }
  result.build = {status: build.status, message: build.message, blocking_reason: build.blocking_reason};
}
process.stdout.write(JSON.stringify(result));
