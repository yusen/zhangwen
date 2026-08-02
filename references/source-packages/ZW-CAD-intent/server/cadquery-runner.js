import { mkdir, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { meshReportToCheck, meshValidationStatus, validateMeshArtifacts } from './mesh-validator.js';
import { writeArtifactSnapshotFile } from './stl-exporter.js';
import { writeWorkflowArtifactFiles } from './workflow-artifacts.js';
import { touchProjectActivity, withProjectMutationLock } from './project-store.js';
import {
  acquireResultDirectoryLease,
  cleanupResultDirectories,
  isExpiredResultProject,
  normalizeTaskId,
  releaseResultDirectoryLease,
} from './result-store.js';

const RUN_TIMEOUT_MS = 90000;
const activeAdhocBuilds = new Set();

export async function buildCadQueryArtifact(options = {}) {
  const body = options.body || {};
  const suppliedDesignId = body.designId || body.design_id || body.currentDesignState?.id || body.design_state?.id;
  const managedDesignId = normalizeTaskId(suppliedDesignId);
  if (options.requireManagedProject === true && !managedDesignId) {
    return {
      status: 'fail',
      blocking_reason: 'cadquery_project_required',
      message: 'CadQuery 构建只能写入当前受管项目；请先生成或重新打开当前模型项目。',
      exports: [],
      source: 'deterministic',
    };
  }
  const designId = options.requireManagedProject === true
    ? managedDesignId
    : normalizeDesignId(suppliedDesignId);
  const buildId = designId || `adhoc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const leaseToken = designId
    ? acquireResultDirectoryLease({ rootDir: options.rootDir, resultId: designId })
    : '';
  let managedProjectValidated = false;
  let managedActivityRefreshed = false;
  if (!designId) activeAdhocBuilds.add(path.join(options.rootDir, 'exports', buildId));
  try {
    if (options.requireManagedProject === true) {
      const expired = await isExpiredResultProject({ rootDir: options.rootDir, resultId: designId });
      const manifestPath = path.join(options.rootDir, 'exports', designId, 'project', 'project.json');
      let manifest = null;
      try {
        manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
      } catch {
        manifest = null;
      }
      if (expired) {
        return {
          status: 'fail',
          blocking_reason: 'project_expired',
          message: '当前项目已超过“最近三个”保留范围，不能由旧页面重新创建。',
          exports: [],
          source: 'deterministic',
        };
      }
      if (manifest?.project_id !== designId || manifest?.schema_version !== 'zwcad_project_v1') {
        return {
          status: 'fail',
          blocking_reason: 'cadquery_project_manifest_missing',
          message: '没有找到当前项目的有效项目清单，CadQuery 构建已停止，避免创建游离目录。',
          exports: [],
          source: 'deterministic',
        };
      }
      managedProjectValidated = true;
    }
    const task = async () => {
      if (managedProjectValidated) {
        await touchProjectActivity({ rootDir: options.rootDir, projectId: designId });
        managedActivityRefreshed = true;
      }
      return buildCadQueryArtifactUnlocked({ ...options, forcedBuildId: buildId });
    };
    return designId
      ? await withProjectMutationLock({ rootDir: options.rootDir, projectId: designId }, task)
      : await task();
  } finally {
    if (leaseToken) {
      releaseResultDirectoryLease({ rootDir: options.rootDir, resultId: designId, leaseToken });
    }
    if (managedActivityRefreshed) {
      await cleanupResultDirectories({ rootDir: options.rootDir, keepCount: 3 }).catch(() => undefined);
    }
    if (!designId) {
      activeAdhocBuilds.delete(path.join(options.rootDir, 'exports', buildId));
      await cleanupAdhocCadQueryDirectories(options.rootDir).catch(() => undefined);
    }
  }
}

async function buildCadQueryArtifactUnlocked({ rootDir, python, environment, body = {}, forcedBuildId = '' }) {
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

  const buildId = forcedBuildId || designId || `adhoc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
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
  const engravingReportPath = path.join(exportDir, 'surface-engraving.json');
  const structuralPartsDir = path.join(exportDir, 'structural-parts');
  const structuralManifestPath = path.join(exportDir, 'structural-parts-manifest.json');
  const templatePartsDir = path.join(exportDir, 'template-parts');
  const templateManifestPath = path.join(exportDir, 'template-parts-manifest.json');

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
    engravingReportPath,
    structuralPartsDir,
    structuralManifestPath,
    templatePartsDir,
    templateManifestPath,
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

  const structuralManifest = await readJsonFile(structuralManifestPath, null);
  const structuralMode = structuralManifest?.schema_version === 'structural_parts_v1'
    && Array.isArray(structuralManifest.parts);
  const templateManifest = await readJsonFile(templateManifestPath, null);
  const templateMode = templateManifest?.schema_version === 'template_parts_v1'
    && Array.isArray(templateManifest.parts);
  const structuralMeshParts = structuralMode
    ? [
        ...structuralManifest.parts.map((item) => ({
          id: item.id,
          label: item.name || item.id,
          path: item.stl_path,
        })),
        { id: 'structural_scene', label: 'structural_scene', path: stlPath },
      ]
    : [];
  const templateMeshParts = templateMode
    ? templateManifest.parts
        .filter((item) => item.printable !== false)
        .map((item) => ({
          id: item.id,
          label: item.name || item.id,
          path: item.stl_path,
        }))
    : [];
  const meshValidationReport = await validateMeshArtifacts({
    python,
    environment,
    stlPaths: {
      stlPath,
      baseStlPath,
      lidStlPath,
    },
    parts: templateMode ? templateMeshParts : structuralMeshParts,
    outputPath: meshChecksPath,
    parameters: body.currentDesignState?.parameters || body.design_state?.parameters || body.artifact?.design_state?.parameters || {},
  });
  const surfaceEngravingReport = await readJsonFile(engravingReportPath, []);

  const legacyExports = [
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
    {
      id: 'surface_engraving_json',
      label: '模型表面刻字报告',
      format: 'json',
      url: `/exports/${buildId}/surface-engraving.json`,
      path: engravingReportPath,
      fidelity: 'cadquery_surface_engraving',
      status: 'available',
    },
  ];
  const structuralExports = structuralMode
    ? buildStructuralCadQueryExports({
        buildId,
        manifest: structuralManifest,
        stepPath,
        stlPath,
        meshChecksPath,
      })
    : [];
  const templateExports = templateMode
    ? buildTemplateCadQueryExports({
        buildId,
        manifest: templateManifest,
        stepPath,
        stlPath,
        meshChecksPath,
      })
    : [];
  const exports = templateMode ? templateExports : structuralMode ? structuralExports : legacyExports;

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
        surfaceEngravingReport,
        structuralPartsManifest: structuralManifest,
        templatePartsManifest: templateManifest,
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
    surface_engraving_report: surfaceEngravingReport,
    structural_parts_manifest: structuralManifest,
    template_parts_manifest: templateManifest,
    stdout: result.stdout,
    stderr: result.stderr,
    source: 'deterministic',
  };
}

function buildStructuralCadQueryExports({ buildId, manifest, stepPath, stlPath, meshChecksPath }) {
  const parts = Array.isArray(manifest?.parts) ? manifest.parts : [];
  return [
    {
      id: 'cadquery_structural_scene_step',
      label: '结构件整体预览 STEP',
      format: 'step',
      url: `/exports/${buildId}/model.step`,
      path: stepPath,
      fidelity: 'cadquery',
      printable: false,
      scene_only: true,
    },
    {
      id: 'cadquery_structural_scene_stl',
      label: '结构件整体预览 STL',
      format: 'stl',
      url: `/exports/${buildId}/model.stl`,
      path: stlPath,
      fidelity: 'cadquery',
      printable: false,
      scene_only: true,
    },
    ...parts.flatMap((part) => [
      {
        id: `cadquery_structural_${part.id}_step`,
        label: `${part.name || part.id} STEP`,
        format: 'step',
        url: `/exports/${buildId}/structural-parts/${part.step_filename}`,
        path: part.step_path,
        fidelity: 'cadquery',
        printable_part_id: part.id,
      },
      {
        id: `cadquery_structural_${part.id}_stl`,
        label: `${part.name || part.id} STL`,
        format: 'stl',
        url: `/exports/${buildId}/structural-parts/${part.stl_filename}`,
        path: part.stl_path,
        fidelity: 'cadquery',
        printable_part_id: part.id,
      },
    ]),
    {
      id: 'structural_parts_manifest_json',
      label: '结构件导出清单',
      format: 'json',
      url: `/exports/${buildId}/structural-parts-manifest.json`,
      path: path.join(path.dirname(stepPath), 'structural-parts-manifest.json'),
      fidelity: 'cadquery_structural_parts_manifest',
      status: 'available',
    },
    {
      id: 'mesh_checks_json',
      label: 'Mesh validation checks',
      format: 'json',
      url: `/exports/${buildId}/mesh-checks.json`,
      path: meshChecksPath,
      fidelity: 'mesh_validation',
      status: 'available',
    },
  ];
}

function buildTemplateCadQueryExports({ buildId, manifest, stepPath, stlPath, meshChecksPath }) {
  const parts = Array.isArray(manifest?.parts) ? manifest.parts : [];
  const references = Array.isArray(manifest?.references) ? manifest.references : [];
  const exports = [
    {
      id: 'cadquery_template_scene_step',
      label: '模板整体场景 STEP',
      format: 'step',
      url: `/exports/${buildId}/model.step`,
      path: stepPath,
      fidelity: 'cadquery',
      printable: false,
      scene_only: true,
    },
    {
      id: 'cadquery_template_scene_stl',
      label: '模板整体场景 STL',
      format: 'stl',
      url: `/exports/${buildId}/model.stl`,
      path: stlPath,
      fidelity: 'cadquery',
      printable: false,
      scene_only: true,
    },
    ...parts.flatMap((part) => {
      const safeId = part.safe_id || sanitizeExportId(part.id);
      const printable = part.printable !== false;
      return [
        {
          id: `cadquery_template_${safeId}_step`,
          label: `${part.name || part.id} STEP`,
          format: 'step',
          url: `/exports/${buildId}/template-parts/${part.step_filename}`,
          path: part.step_path,
          fidelity: 'cadquery',
          printable,
          template_part_id: part.id,
        },
        {
          id: `cadquery_template_${safeId}_stl`,
          label: `${part.name || part.id} STL`,
          format: 'stl',
          url: `/exports/${buildId}/template-parts/${part.stl_filename}`,
          path: part.stl_path,
          fidelity: 'cadquery',
          printable,
          ...(printable ? { printable_part_id: part.id } : {}),
          template_part_id: part.id,
        },
      ];
    }),
  ];
  if (references.length && manifest.references_step_path && manifest.references_stl_path) {
    exports.push(
      {
        id: 'cadquery_template_references_step',
        label: '模板参考件 STEP',
        format: 'step',
        url: `/exports/${buildId}/template-parts/references.step`,
        path: manifest.references_step_path,
        fidelity: 'cadquery',
        printable: false,
        reference_only: true,
      },
      {
        id: 'cadquery_template_references_stl',
        label: '模板参考件 STL',
        format: 'stl',
        url: `/exports/${buildId}/template-parts/references.stl`,
        path: manifest.references_stl_path,
        fidelity: 'cadquery',
        printable: false,
        reference_only: true,
      },
    );
  }
  exports.push(
    {
      id: 'template_parts_manifest_json',
      label: '模板件导出清单',
      format: 'json',
      url: `/exports/${buildId}/template-parts-manifest.json`,
      path: path.join(path.dirname(stepPath), 'template-parts-manifest.json'),
      fidelity: 'cadquery_template_parts_manifest',
      status: 'available',
    },
    {
      id: 'mesh_checks_json',
      label: 'Mesh validation checks',
      format: 'json',
      url: `/exports/${buildId}/mesh-checks.json`,
      path: meshChecksPath,
      fidelity: 'mesh_validation',
      status: 'available',
    },
  );
  return exports;
}

function sanitizeExportId(value = '') {
  const text = String(value || '');
  const safe = text
    .replace(/[^a-zA-Z0-9_-]+/g, '_')
    .replace(/^[-_]+|[-_]+$/g, '');
  return safe || 'template_part';
}

export async function cleanupAdhocCadQueryDirectories(rootDir, keepCount = 3) {
  const exportsDir = path.join(rootDir, 'exports');
  await mkdir(exportsDir, { recursive: true });
  const candidates = [];
  for (const entry of await readdir(exportsDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || !/^adhoc_\d+(?:_[a-z0-9]+)?$/i.test(entry.name)) continue;
    const fullPath = path.join(exportsDir, entry.name);
    if (activeAdhocBuilds.has(fullPath)) continue;
    candidates.push({ path: fullPath, name: entry.name, mtimeMs: (await stat(fullPath)).mtimeMs });
  }
  candidates.sort((left, right) => right.mtimeMs - left.mtimeMs || right.name.localeCompare(left.name));
  for (const item of candidates.slice(Math.max(0, keepCount))) {
    const resolvedExports = path.resolve(exportsDir);
    const resolvedTarget = path.resolve(item.path);
    if (path.basename(resolvedTarget) !== item.name || !resolvedTarget.startsWith(`${resolvedExports}${path.sep}`)) continue;
    await rm(resolvedTarget, { recursive: true, force: true });
  }
}

async function persistCadQueryBuildResult({
  rootDir,
  buildId,
  artifact,
  cadqueryExports,
  meshValidationReport,
  surfaceEngravingReport = [],
  structuralPartsManifest = null,
  templatePartsManifest = null,
}) {
  const mergedCadqueryExports = mergeExports(artifact.exports || [], cadqueryExports || []);
  const validationContext = {
    ...(artifact.design_state?.validation_context || artifact.validation_context || {}),
    mesh_validation: meshValidationStatus(meshValidationReport),
  };
  let nextArtifact = {
    ...artifact,
    exports: mergedCadqueryExports,
    printable_parts: artifact.printable_parts,
    project_files: artifact.project_files,
    mesh_validation_report: meshValidationReport,
    surface_engraving_report: surfaceEngravingReport,
    ...(structuralPartsManifest ? { structural_parts_manifest: structuralPartsManifest } : {}),
    ...(templatePartsManifest ? { template_parts_manifest: templatePartsManifest } : {}),
    validation_context: validationContext,
    checks: replaceMeshValidationCheck(artifact.checks || [], meshValidationReport),
    design_state: {
      ...(artifact.design_state || {}),
      id: buildId,
      exports: mergedCadqueryExports,
      printable_parts: artifact.design_state?.printable_parts || artifact.printable_parts,
      project_files: artifact.design_state?.project_files || artifact.project_files,
      mesh_validation_report: meshValidationReport,
      surface_engraving_report: surfaceEngravingReport,
      ...(structuralPartsManifest ? { structural_parts_manifest: structuralPartsManifest } : {}),
      ...(templatePartsManifest ? { template_parts_manifest: templatePartsManifest } : {}),
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
  const legacyRequiredPatterns = [
    ['import cadquery as cq', /^\s*import\s+cadquery\s+as\s+cq\s*$/m],
    ['base_part assignment', /^\s*base_part\s*=/m],
    ['lid_part assignment', /^\s*lid_part\s*=/m],
    ['hardware_reference_parts assignment', /^\s*hardware_reference_parts\s*=/m],
  ];
  const structuralRequiredPatterns = [
    ['import cadquery as cq', /^\s*import\s+cadquery\s+as\s+cq\s*$/m],
    ['STRUCTURAL_PARTS_SCHEMA_VERSION assignment', /^\s*STRUCTURAL_PARTS_SCHEMA_VERSION\s*=/m],
    ['structural_parts assignment', /^\s*structural_parts\s*=/m],
  ];
  const templateRequiredPatterns = [
    ['import cadquery as cq', /^\s*import\s+cadquery\s+as\s+cq\s*$/m],
    ['TEMPLATE_PARTS_SCHEMA_VERSION assignment', /^\s*TEMPLATE_PARTS_SCHEMA_VERSION\s*=/m],
    ['template_parts assignment', /^\s*template_parts\s*=/m],
    ['template_scene or result assignment', /^\s*(?:template_scene|result)\s*=/m],
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
  const looksStructural = /^\s*STRUCTURAL_PARTS_SCHEMA_VERSION\s*=/m.test(codeWithoutStrings)
    || /^\s*structural_parts\s*=/m.test(codeWithoutStrings);
  const looksTemplate = /^\s*TEMPLATE_PARTS_SCHEMA_VERSION\s*=/m.test(codeWithoutStrings)
    || /^\s*template_parts\s*=/m.test(codeWithoutStrings);
  const contract = looksTemplate ? 'template_parts_v1' : looksStructural ? 'structural_parts_v1' : 'enclosure_v1';
  const requiredPatterns = looksTemplate
    ? templateRequiredPatterns
    : looksStructural
      ? structuralRequiredPatterns
      : legacyRequiredPatterns;
  const missing = requiredPatterns.filter(([, pattern]) => !pattern.test(codeWithoutStrings)).map(([label]) => label);
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
    details: { missing: [], forbidden: [], contract },
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
  engravingReportPath,
  structuralPartsDir,
  structuralManifestPath,
  templatePartsDir,
  templateManifestPath,
}) {
  return `import json
import os
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

def show_object(*args, **kwargs):
    return None

ns = runpy.run_path(source_path, init_globals={"show_object": show_object})

base = ns.get("base_part")
lid = ns.get("lid_part")
hardware = ns.get("hardware_reference_parts", [])
structural_schema = ns.get("STRUCTURAL_PARTS_SCHEMA_VERSION", "")
structural_parts = ns.get("structural_parts", [])
template_schema = ns.get("TEMPLATE_PARTS_SCHEMA_VERSION", "")
template_parts = ns.get("template_parts", [])
template_reference_parts = ns.get("template_reference_parts", [])
template_scene = ns.get("template_scene", ns.get("result"))
surface_engraving_report = ns.get("SURFACE_ENGRAVING_REPORT", [])

def safe_part_id(raw_id, fallback):
    safe_id = "".join(character if character.isalnum() or character in "-_" else "_" for character in str(raw_id)).strip("-_")
    return safe_id or fallback

def placement_translation(entry):
    placement = entry.get("placement_mm") or {}
    if isinstance(placement, (list, tuple)):
        values = list(placement) + [0, 0, 0]
        return (float(values[0]), float(values[1]), float(values[2]))
    if not isinstance(placement, dict):
        raise RuntimeError("placement_mm must be an object or a three-value list")
    return (
        float(placement.get("x", 0)),
        float(placement.get("y", 0)),
        float(placement.get("z", 0)),
    )

def placed_object(entry):
    part_object = entry["object"]
    translation = placement_translation(entry)
    return (
        part_object.translate(translation) if hasattr(part_object, "translate") and any(translation)
        else part_object,
        translation,
    )

def save_scene(scene, step_path, stl_path, fallback_object=None):
    if scene is None:
        if fallback_object is None:
            raise RuntimeError("template scene is empty")
        scene = fallback_object
    if hasattr(scene, "save"):
        scene.save(step_path)
    else:
        exporters.export(scene, step_path)
    if hasattr(scene, "toCompound"):
        exporters.export(scene.toCompound(), stl_path)
    else:
        exporters.export(scene, stl_path)

if template_schema == "template_parts_v1":
    if not isinstance(template_parts, list) or not template_parts:
        raise RuntimeError("template_parts_v1 source must define a non-empty template_parts list")
    if not isinstance(template_reference_parts, list):
        raise RuntimeError("template_reference_parts must be a list")
    os.makedirs(${JSON.stringify(templatePartsDir)}, exist_ok=True)
    generated_scene = cq.Assembly(name="zwcad_intent_template_scene")
    reference_assembly = cq.Assembly(name="zwcad_intent_template_references")
    manifest_parts = []
    manifest_references = []
    used_ids = set()
    for index, entry in enumerate(template_parts):
        if not isinstance(entry, dict) or entry.get("object") is None:
            raise RuntimeError(f"template_parts[{index}] must contain an object")
        raw_id = str(entry.get("id") or f"template_part_{index + 1}")
        safe_id = safe_part_id(raw_id, f"template_part_{index + 1}")
        if safe_id in used_ids:
            raise RuntimeError(f"template_parts contains duplicate export id: {safe_id}")
        used_ids.add(safe_id)
        part_object = entry["object"]
        scene_object, translation = placed_object(entry)
        generated_scene.add(scene_object, name=safe_id)
        step_filename = f"{safe_id}.step"
        stl_filename = f"{safe_id}.stl"
        part_step_path = os.path.join(${JSON.stringify(templatePartsDir)}, step_filename)
        part_stl_path = os.path.join(${JSON.stringify(templatePartsDir)}, stl_filename)
        exporters.export(part_object, part_step_path)
        exporters.export(part_object, part_stl_path)
        manifest_parts.append({
            "id": raw_id,
            "safe_id": safe_id,
            "name": str(entry.get("name") or raw_id),
            "step_filename": step_filename,
            "stl_filename": stl_filename,
            "step_path": part_step_path,
            "stl_path": part_stl_path,
            "placement_mm": {"x": translation[0], "y": translation[1], "z": translation[2]},
            "printable": bool(entry.get("printable", True)),
        })
    if not any(part.get("printable", True) for part in manifest_parts):
        raise RuntimeError("template_parts_v1 source must declare at least one printable template part")
    for index, entry in enumerate(template_reference_parts):
        normalized_entry = entry if isinstance(entry, dict) else {"object": entry}
        if normalized_entry.get("object") is None:
            raise RuntimeError(f"template_reference_parts[{index}] must contain an object")
        raw_id = str(normalized_entry.get("id") or f"template_reference_{index + 1}")
        safe_id = safe_part_id(raw_id, f"template_reference_{index + 1}")
        reference_object, translation = placed_object(normalized_entry)
        generated_scene.add(reference_object, name=f"reference_{safe_id}_{index + 1}")
        reference_assembly.add(reference_object, name=f"reference_{safe_id}_{index + 1}")
        manifest_references.append({
            "id": raw_id,
            "safe_id": safe_id,
            "name": str(normalized_entry.get("name") or raw_id),
            "placement_mm": {"x": translation[0], "y": translation[1], "z": translation[2]},
            "printable": False,
        })
    scene_to_export = template_scene if template_scene is not None else generated_scene
    save_scene(scene_to_export, ${JSON.stringify(stepPath)}, ${JSON.stringify(stlPath)}, template_parts[0]["object"])
    references_step_path = None
    references_stl_path = None
    if manifest_references:
        references_step_path = os.path.join(${JSON.stringify(templatePartsDir)}, "references.step")
        references_stl_path = os.path.join(${JSON.stringify(templatePartsDir)}, "references.stl")
        save_scene(reference_assembly, references_step_path, references_stl_path, template_reference_parts[0])
    with open(${JSON.stringify(templateManifestPath)}, "w", encoding="utf-8") as template_manifest_file:
        json.dump({
            "schema_version": "template_parts_v1",
            "scene_step_path": ${JSON.stringify(stepPath)},
            "scene_stl_path": ${JSON.stringify(stlPath)},
            "scene_only": True,
            "parts": manifest_parts,
            "references": manifest_references,
            "references_step_path": references_step_path,
            "references_stl_path": references_stl_path,
        }, template_manifest_file, ensure_ascii=False, indent=2)
elif structural_schema == "structural_parts_v1":
    if not isinstance(structural_parts, list) or not structural_parts:
        raise RuntimeError("structural_parts_v1 source must define a non-empty structural_parts list")
    os.makedirs(${JSON.stringify(structuralPartsDir)}, exist_ok=True)
    scene_assembly = cq.Assembly(name="zwcad_intent_structural_scene")
    manifest_parts = []
    used_ids = set()
    for index, entry in enumerate(structural_parts):
        if not isinstance(entry, dict) or entry.get("object") is None:
            raise RuntimeError(f"structural_parts[{index}] must contain an object")
        raw_id = str(entry.get("id") or f"structural_part_{index + 1}")
        safe_id = "".join(character if character.isalnum() or character in "-_" else "_" for character in raw_id).strip("-_")
        safe_id = safe_id or f"structural_part_{index + 1}"
        if safe_id in used_ids:
            safe_id = f"{safe_id}_{index + 1}"
        used_ids.add(safe_id)
        part_object = entry["object"]
        placement = entry.get("placement_mm") or {}
        translation = (
            float(placement.get("x", 0)),
            float(placement.get("y", 0)),
            float(placement.get("z", 0)),
        )
        placed_object = part_object.translate(translation) if hasattr(part_object, "translate") else part_object
        scene_assembly.add(placed_object, name=safe_id)
        step_filename = f"{safe_id}.step"
        stl_filename = f"{safe_id}.stl"
        part_step_path = os.path.join(${JSON.stringify(structuralPartsDir)}, step_filename)
        part_stl_path = os.path.join(${JSON.stringify(structuralPartsDir)}, stl_filename)
        exporters.export(part_object, part_step_path)
        exporters.export(part_object, part_stl_path)
        manifest_parts.append({
            "id": raw_id,
            "name": str(entry.get("name") or raw_id),
            "step_filename": step_filename,
            "stl_filename": stl_filename,
            "step_path": part_step_path,
            "stl_path": part_stl_path,
            "placement_mm": {"x": translation[0], "y": translation[1], "z": translation[2]},
            "printable": True,
        })
    scene_assembly.save(${JSON.stringify(stepPath)})
    if hasattr(scene_assembly, "toCompound"):
        exporters.export(scene_assembly.toCompound(), ${JSON.stringify(stlPath)})
    else:
        exporters.export(structural_parts[0]["object"], ${JSON.stringify(stlPath)})
    with open(${JSON.stringify(structuralManifestPath)}, "w", encoding="utf-8") as structural_manifest_file:
        json.dump({
            "schema_version": "structural_parts_v1",
            "scene_step_path": ${JSON.stringify(stepPath)},
            "scene_stl_path": ${JSON.stringify(stlPath)},
            "scene_only": True,
            "parts": manifest_parts,
        }, structural_manifest_file, ensure_ascii=False, indent=2)
else:
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
with open(${JSON.stringify(engravingReportPath)}, "w", encoding="utf-8") as engraving_report_file:
    json.dump(surface_engraving_report, engraving_report_file, ensure_ascii=False, indent=2)
print("exported")
`;
}

async function readJsonFile(filePath, fallback) {
  try {
    return JSON.parse(await readFile(filePath, 'utf8'));
  } catch {
    return fallback;
  }
}

function runPython(python, args, { cwd, timeoutMs, input = '' }) {
  return new Promise((resolve) => {
    const child = spawn(python, args, {
      cwd,
      env: {
        ...process.env,
        PYTHONUTF8: '1',
        PYTHONIOENCODING: 'utf-8',
      },
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      child.kill();
    }, timeoutMs);
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString('utf8');
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
    });
    child.on('close', (exitCode) => {
      clearTimeout(timer);
      resolve({ exitCode, stdout, stderr });
    });
    child.on('error', (error) => {
      clearTimeout(timer);
      resolve({ exitCode: 1, stdout, stderr: error.message });
    });
    if (input) child.stdin?.write(input, 'utf8');
    child.stdin?.end();
  });
}

function normalizeDesignId(value) {
  const text = typeof value === 'string' ? value.trim() : '';
  return /^[a-zA-Z0-9_-]{6,64}$/.test(text) ? text : '';
}
