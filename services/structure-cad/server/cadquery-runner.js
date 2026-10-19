import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { meshReportToCheck, meshValidationStatus, validateMeshArtifacts } from './mesh-validator.js';
import { writeArtifactSnapshotFile } from './stl-exporter.js';
import { writeWorkflowArtifactFiles } from './workflow-artifacts.js';

const RUN_TIMEOUT_MS = 90000;

export async function buildCadQueryArtifact({ rootDir, python, environment, body = {} }) {
  const designId = normalizeDesignId(body.designId || body.design_id || body.currentDesignState?.id || body.design_state?.id);
  const artifact = body.artifact && typeof body.artifact === 'object' ? body.artifact : null;
  const cadqueryCode = typeof body.cadquery_code === 'string'
    ? body.cadquery_code
    : typeof artifact?.cadquery_code === 'string'
      ? artifact.cadquery_code
      : '';

  let preflight = null;
  if (cadqueryCode) {
    preflight = await preflightCadQueryCode({ python, code: cadqueryCode });
    if (preflight.status === 'fail') {
      return {
        status: 'fail',
        blocking_reason: 'cadquery_preflight_failed',
        message: 'CadQuery source failed preflight checks.',
        preflight,
        exports: [],
        source: 'deterministic',
      };
    }
  }

  if (!environment?.cadqueryAvailable) {
    return {
      status: 'pending',
      blocking_reason: 'pending_missing_cadquery',
      message: '当前 Python 环境未检测到 cadquery/OCP，无法执行真实 CadQuery 建模。',
      preflight,
      requiredPythonPackages: environment?.requiredPythonPackages || ['cadquery', 'OCP'],
      environment,
      source: 'deterministic',
    };
  }

  if (!designId && !cadqueryCode) {
    return {
      status: 'needs_input',
      blocking_reason: 'missing_cadquery_source',
      message: '缺少 designId 或 cadquery_code，无法执行 CadQuery。',
      source: 'deterministic',
    };
  }

  const buildId = designId || `adhoc_${Date.now()}`;
  const exportDir = path.join(rootDir, 'exports', buildId);
  await mkdir(exportDir, { recursive: true });

  const sourcePath = path.join(exportDir, 'cadquery.py');
  const runnerPath = path.join(exportDir, 'run-cadquery-export.py');
  const stepPath = path.join(exportDir, 'model.step');
  const baseStepPath = path.join(exportDir, 'base.step');
  const lidStepPath = path.join(exportDir, 'lid.step');
  const hardwareStepPath = path.join(exportDir, 'hardware.step');
  const stlPath = path.join(exportDir, 'model.stl');
  const baseStlPath = path.join(exportDir, 'base.stl');
  const lidStlPath = path.join(exportDir, 'lid.stl');
  const hardwareStlPath = path.join(exportDir, 'hardware.stl');
  const meshChecksPath = path.join(exportDir, 'mesh-checks.json');

  const sourceCode = cadqueryCode || await readFile(sourcePath, 'utf8');
  preflight = preflight || await preflightCadQueryCode({ python, code: sourceCode });
  if (preflight.status === 'fail') {
    return {
      status: 'fail',
      blocking_reason: 'cadquery_preflight_failed',
      message: 'CadQuery source failed preflight checks.',
      preflight,
      exports: [],
      source: 'deterministic',
    };
  }
  await writeFile(sourcePath, sourceCode, 'utf8');
  await writeFile(runnerPath, buildRunnerScript({
    sourcePath,
    stepPath,
    baseStepPath,
    lidStepPath,
    hardwareStepPath,
    stlPath,
    baseStlPath,
    lidStlPath,
    hardwareStlPath,
  }), 'utf8');

  const result = await runPython(python, [runnerPath], { cwd: exportDir, timeoutMs: RUN_TIMEOUT_MS });
  if (result.exitCode !== 0) {
    return {
      status: 'fail',
      blocking_reason: 'cadquery_execution_failed',
      message: 'CadQuery 执行失败。',
      stdout: result.stdout,
      stderr: result.stderr,
      exports: [],
      source: 'deterministic',
    };
  }

  const meshValidationReport = await validateMeshArtifacts({
    python,
    environment,
    stlPaths: {
      stlPath,
      baseStlPath,
      lidStlPath,
    },
    outputPath: meshChecksPath,
    parameters: body.currentDesignState?.parameters || body.design_state?.parameters || body.artifact?.design_state?.parameters || {},
  });

  const exports = [
    {
      id: 'cadquery_step',
      label: '真实 CadQuery STEP',
      format: 'step',
      url: `/exports/${buildId}/model.step`,
      path: stepPath,
      fidelity: 'cadquery',
    },
    {
      id: 'cadquery_base_step',
      label: '底壳 STEP',
      format: 'step',
      url: `/exports/${buildId}/base.step`,
      path: baseStepPath,
      fidelity: 'cadquery',
    },
    {
      id: 'cadquery_lid_step',
      label: '上盖 STEP',
      format: 'step',
      url: `/exports/${buildId}/lid.step`,
      path: lidStepPath,
      fidelity: 'cadquery',
    },
    {
      id: 'cadquery_hardware_step',
      label: '硬件参考 STEP',
      format: 'step',
      url: `/exports/${buildId}/hardware.step`,
      path: hardwareStepPath,
      fidelity: 'cadquery',
    },
    {
      id: 'cadquery_stl',
      label: '真实 CadQuery STL',
      format: 'stl',
      url: `/exports/${buildId}/model.stl`,
      path: stlPath,
      fidelity: 'cadquery',
    },
    {
      id: 'cadquery_base_stl',
      label: '底壳 STL',
      format: 'stl',
      url: `/exports/${buildId}/base.stl`,
      path: baseStlPath,
      fidelity: 'cadquery',
    },
    {
      id: 'cadquery_lid_stl',
      label: '上盖 STL',
      format: 'stl',
      url: `/exports/${buildId}/lid.stl`,
      path: lidStlPath,
      fidelity: 'cadquery',
    },
    {
      id: 'cadquery_hardware_stl',
      label: '硬件参考 STL',
      format: 'stl',
      url: `/exports/${buildId}/hardware.stl`,
      path: hardwareStlPath,
      fidelity: 'cadquery',
    },
    {
      id: 'mesh_checks_json',
      label: 'Mesh validation checks',
      format: 'json',
      url: `/exports/${buildId}/mesh-checks.json`,
      path: meshChecksPath,
      fidelity: 'mesh_validation',
      status: meshValidationReport.status,
    },
  ];

  let responseExports = exports;
  let persistedArtifact = null;
  let persistWarning = null;
  if (artifact) {
    try {
      const persisted = await persistCadQueryBuildResult({
        rootDir,
        buildId,
        artifact,
        cadqueryExports: exports,
        meshValidationReport,
      });
      responseExports = persisted.exports;
      persistedArtifact = persisted.artifact;
    } catch (error) {
      persistWarning = {
        id: 'cadquery_artifact_persist_failed',
        status: 'warn',
        message: 'CadQuery exports were generated but could not be written back to artifact snapshots.',
        details: serializeError(error),
      };
    }
  }

  return {
    status: 'artifact_exports',
    designId: buildId,
    message: 'CadQuery 已执行并导出 STEP/STL。',
    exports: responseExports,
    artifact: persistedArtifact,
    warning: persistWarning,
    mesh_validation_report: meshValidationReport,
    mesh_validation_status: meshValidationStatus(meshValidationReport),
    stdout: result.stdout,
    stderr: result.stderr,
    source: 'deterministic',
  };
}

async function persistCadQueryBuildResult({
  rootDir,
  buildId,
  artifact,
  cadqueryExports,
  meshValidationReport,
}) {
  const mergedCadqueryExports = mergeExports(artifact.exports || [], cadqueryExports || []);
  const validationContext = {
    ...(artifact.design_state?.validation_context || artifact.validation_context || {}),
    mesh_validation: meshValidationStatus(meshValidationReport),
  };
  let nextArtifact = {
    ...artifact,
    exports: mergedCadqueryExports,
    mesh_validation_report: meshValidationReport,
    validation_context: validationContext,
    checks: replaceMeshValidationCheck(artifact.checks || [], meshValidationReport),
    design_state: {
      ...(artifact.design_state || {}),
      id: buildId,
      exports: mergedCadqueryExports,
      mesh_validation_report: meshValidationReport,
      validation_context: validationContext,
    },
  };

  const workflowExports = await writeWorkflowArtifactFiles({
    rootDir,
    designId: buildId,
    artifact: nextArtifact,
  });
  const fullExports = mergeExports(nextArtifact.exports, workflowExports);
  nextArtifact = {
    ...nextArtifact,
    exports: fullExports,
    design_state: {
      ...nextArtifact.design_state,
      exports: fullExports,
    },
  };
  await writeArtifactSnapshotFile({
    rootDir,
    designId: buildId,
    artifact: nextArtifact,
  });

  return {
    artifact: nextArtifact,
    exports: fullExports,
  };
}

function replaceMeshValidationCheck(checks = [], meshValidationReport) {
  const meshCheck = meshReportToCheck(meshValidationReport);
  const result = [];
  let replaced = false;
  for (const check of Array.isArray(checks) ? checks : []) {
    if (check?.id === 'mesh_validation') {
      if (!replaced) result.push(meshCheck);
      replaced = true;
    } else {
      result.push(check);
    }
  }
  if (!replaced) result.push(meshCheck);
  return result;
}

function mergeExports(existing = [], incoming = []) {
  const byKey = new Map();
  for (const item of [...existing, ...incoming]) {
    const key = item.id || item.url || item.path || JSON.stringify(item);
    byKey.set(key, item);
  }
  return [...byKey.values()];
}

function serializeError(error) {
  if (!error || typeof error !== 'object') return { message: String(error || 'unknown error') };
  return {
    name: error.name || 'Error',
    code: typeof error.code === 'string' ? error.code : '',
    path: typeof error.path === 'string' ? error.path : '',
    message: error instanceof Error ? error.message : String(error),
  };
}

export async function preflightCadQueryCode({ python, code }) {
  const text = typeof code === 'string' ? code : '';
  const staticCheck = staticCheckCadQueryCode(text);
  if (staticCheck.status === 'fail') return staticCheck;
  const astResult = await runPythonAstParse({ python, code: text });
  if (astResult.exitCode !== 0) {
    return {
      status: 'fail',
      id: 'python_ast_parse',
      message: 'Python AST parse failed.',
      details: {
        stdout: astResult.stdout,
        stderr: astResult.stderr,
      },
    };
  }
  return {
    status: 'pass',
    id: 'cadquery_preflight',
    message: 'CadQuery source passed static and Python syntax preflight checks.',
    details: {
      static: staticCheck.details,
    },
  };
}

function staticCheckCadQueryCode(code) {
  const codeWithoutStrings = stripPythonStringLiterals(code);
  const required = [
    'import cadquery as cq',
    'base_part = build_hollow_base()',
    'base_part = apply_screw_bosses(base_part)',
    'lid_part = build_lid()',
    'lid_part = apply_lid_screw_holes(lid_part)',
    'def apply_mounts',
    'base_part, lid_part = apply_mounts(base_part, lid_part)',
    'hardware_reference_parts = build_hardware_references()',
  ];
  const forbiddenPatterns = [
    /\bopen\s*\(/,
    /\bexec\s*\(/,
    /\beval\s*\(/,
    /\bsubprocess\b/,
    /\bos\.system\b/,
    /\brequests\b/,
    /\bsocket\b/,
  ];
  const missing = required.filter((needle) => !code.includes(needle));
  const forbidden = forbiddenPatterns
    .filter((pattern) => pattern.test(codeWithoutStrings))
    .map((pattern) => pattern.source);
  if (!code.trim()) {
    return {
      status: 'fail',
      id: 'empty_cadquery_code',
      message: 'CadQuery code is empty.',
      details: { missing, forbidden },
    };
  }
  if (missing.length || forbidden.length) {
    return {
      status: 'fail',
      id: 'cadquery_static_safety',
      message: 'CadQuery source failed required entry point or blocked API checks.',
      details: { missing, forbidden },
    };
  }
  return {
    status: 'pass',
    id: 'cadquery_static_safety',
    message: 'CadQuery source passed static safety checks.',
    details: { missing: [], forbidden: [] },
  };
}

function stripPythonStringLiterals(code = '') {
  let result = '';
  let index = 0;
  while (index < code.length) {
    const quote = code[index];
    const nextTwo = code.slice(index, index + 3);
    if (nextTwo === '"""' || nextTwo === "'''") {
      const end = code.indexOf(nextTwo, index + 3);
      result += '""';
      index = end === -1 ? code.length : end + 3;
      continue;
    }
    if (quote === '"' || quote === "'") {
      result += '""';
      index += 1;
      while (index < code.length) {
        if (code[index] === '\\') {
          index += 2;
          continue;
        }
        if (code[index] === quote) {
          index += 1;
          break;
        }
        index += 1;
      }
      continue;
    }
    result += quote;
    index += 1;
  }
  return result;
}

function runPythonAstParse({ python, code }) {
  const script = [
    'import ast, sys',
    'source = sys.stdin.read()',
    'ast.parse(source)',
    'print("ok")',
  ].join('\n');
  return runPython(python, ['-c', script], {
    cwd: process.cwd(),
    timeoutMs: 15000,
    input: code,
  });
}

function buildRunnerScript({
  sourcePath,
  stepPath,
  baseStepPath,
  lidStepPath,
  hardwareStepPath,
  stlPath,
  baseStlPath,
  lidStlPath,
  hardwareStlPath,
}) {
  return `import os
import runpy
import sys

source_path = ${JSON.stringify(sourcePath)}
source_dir = os.path.dirname(os.path.abspath(source_path))
original_sys_path = list(sys.path)
sys.path = [
    item for item in sys.path
    if item and os.path.abspath(item) != source_dir
]
import cadquery as cq
from cadquery import exporters
sys.path = original_sys_path

ns = runpy.run_path(source_path)

base = ns.get("base_part")
lid = ns.get("lid_part")
hardware = ns.get("hardware_reference_parts", [])

if base is None or lid is None:
    raise RuntimeError("cadquery.py must define base_part and lid_part")

assembly = cq.Assembly(name="zwcad_intent_assembly")
assembly.add(base, name="base_part")
assembly.add(lid, name="lid_part")
hardware_assembly = cq.Assembly(name="zwcad_intent_hardware")
for index, part in enumerate(hardware):
    assembly.add(part, name=f"hardware_reference_{index}")
    hardware_assembly.add(part, name=f"hardware_reference_{index}")

exporters.export(base, ${JSON.stringify(baseStepPath)})
exporters.export(lid, ${JSON.stringify(lidStepPath)})
assembly.save(${JSON.stringify(stepPath)})
exporters.export(base, ${JSON.stringify(baseStlPath)})
exporters.export(lid, ${JSON.stringify(lidStlPath)})
if hasattr(assembly, "toCompound"):
    exporters.export(assembly.toCompound(), ${JSON.stringify(stlPath)})
else:
    exporters.export(base, ${JSON.stringify(stlPath)})
if hardware:
    hardware_assembly.save(${JSON.stringify(hardwareStepPath)})
    if hasattr(hardware_assembly, "toCompound"):
        exporters.export(hardware_assembly.toCompound(), ${JSON.stringify(hardwareStlPath)})
    else:
        exporters.export(hardware[0], ${JSON.stringify(hardwareStlPath)})
else:
    empty_hardware = cq.Workplane("XY").box(0.01, 0.01, 0.01)
    exporters.export(empty_hardware, ${JSON.stringify(hardwareStepPath)})
    exporters.export(empty_hardware, ${JSON.stringify(hardwareStlPath)})
print("exported")
`;
}

function runPython(python, args, { cwd, timeoutMs, input = '' }) {
  return new Promise((resolve) => {
    const child = spawn(python, args, {
      cwd,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      child.kill();
    }, timeoutMs);
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('close', (exitCode) => {
      clearTimeout(timer);
      resolve({ exitCode, stdout, stderr });
    });
    child.on('error', (error) => {
      clearTimeout(timer);
      resolve({ exitCode: 1, stdout, stderr: error.message });
    });
    if (input) child.stdin?.write(input);
    child.stdin?.end();
  });
}

function normalizeDesignId(value) {
  const text = typeof value === 'string' ? value.trim() : '';
  return /^[a-zA-Z0-9_-]{6,64}$/.test(text) ? text : '';
}
