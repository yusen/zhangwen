import { mkdtemp, readFile, rm, unlink, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildCadQueryArtifact } from './cadquery-runner.js';
import {
  buildProjectMemoryUpdate,
  hashCadQuerySource,
  requestModelEditPlan,
  validateModelEditPlanWithAst,
} from './model-edit-agent.js';
import { buildModelNeedsInput, getIntentModelConfig } from './model-sources.js';
import {
  commitProjectSourceRevision,
  readProjectWorkspace,
  restorePreviousProjectRevision,
  withProjectMutationLock,
} from './project-store.js';
import {
  buildSurfaceEngravingPatch,
  injectSurfaceEngravingCode,
  invalidateSurfaceEngravingOverridesForSource,
  normalizeSurfaceEngravings,
  stripSurfaceEngravingCode,
} from './surface-engraving.js';

const PENDING_MODEL_EDIT_SCHEMA_VERSION = 'pending_model_edit_v1';
const PENDING_MODEL_EDIT_FILENAME = 'pending-model-edit.json';
export async function handleModelEditRequest(body = {}, context = {}) {
  const projectId = text(body.taskId || body.task_id || body.currentDesignState?.id || body.design_state?.id) || '__missing_project__';
  return withProjectMutationLock(
    { rootDir: context.rootDir, projectId },
    () => handleModelEditRequestUnlocked(body, context),
  );
}

async function handleModelEditRequestUnlocked(body = {}, context = {}) {
  const routeAction = body.conversationRoute?.route_action
    || body.conversation_route?.route_action
    || body.routeAction
    || body.route_action
    || 'model_edit';
  const projectId = text(body.taskId || body.task_id || body.currentDesignState?.id || body.design_state?.id);
  if (!projectId) return modelEditNeedsInput('当前没有可修改的模型项目。', 'model_edit_requires_project', ['请先生成模型，再描述修改要求。']);

  let workspace;
  try {
    workspace = await readProjectWorkspace({ rootDir: context.rootDir, projectId });
  } catch (error) {
    return modelEditNeedsInput(
      error instanceof Error ? error.message : String(error),
      error?.code || 'model_edit_project_read_failed',
      ['请重新打开当前项目或先生成模型。'],
    );
  }
  if (workspace.status !== 'ready') {
    return modelEditNeedsInput('当前项目目录存在，但还没有可修改的项目源码副本。', 'model_edit_project_source_missing', ['请先重新生成当前模型。']);
  }

  const artifact = await loadProjectArtifact(context.rootDir, projectId, body);
  let workingArtifact = artifact;
  if (routeAction === 'cancel_model_edit') {
    await clearPendingModelEdit(workspace);
    return artifactResponse(artifact, workspace, {
      title: '已取消模型修改',
      message: '上一轮待确认修改已取消，当前项目源码和模型保持不变。',
      modelEditPlan: null,
      routeAction,
    });
  }
  if (routeAction === 'undo_model_edit') {
    await clearPendingModelEdit(workspace);
    try {
      const restored = await restorePreviousProjectRevision({
        rootDir: context.rootDir,
        projectId,
        expectedSourceHash: workspace.source_hash,
        transformSource: (source) => synchronizeSurfaceEngravingSource({
          source,
          artifact: workingArtifact,
        }).source,
      });
      return await buildCommittedArtifact({
        artifact: workingArtifact,
        workspace: restored,
        routeAction,
        plan: {
          schema_version: 'model_edit_plan_v1',
          plan_id: `undo-${restored.revision_id}`,
          project_id: projectId,
          intent_summary: `撤销最近一次修改，恢复到上一版项目源码。`,
          source_hash: workspace.source_hash,
          operations: [{ id: 'restore-previous-revision', type: 'restore_revision', summary: '恢复上一版项目源码' }],
          risk_level: 'low',
          requires_confirmation: false,
        },
        previousWorkspace: workspace,
        context,
      });
    } catch (error) {
      return modelEditNeedsInput(
        error instanceof Error ? error.message : String(error),
        error?.code || 'model_edit_undo_failed',
        ['请确认当前项目已有至少一次可撤销的修改。'],
      );
    }
  }

  const confirmed = routeAction === 'confirm_model_edit';
  let plan = null;
  if (confirmed) {
    const suppliedPlan = body.modelEditPlan
      || body.model_edit_plan
      || body.lastNeedsInput?.model_edit_plan
      || body.last_needs_input?.model_edit_plan;
    let pending;
    try {
      pending = await readPendingModelEdit(workspace);
    } catch (error) {
      await clearPendingModelEdit(workspace);
      return modelEditNeedsInput(
        error instanceof Error ? error.message : String(error),
        error?.code || 'model_edit_confirmation_invalid',
        ['请重新提交模型修改要求，系统会重新生成待确认方案。'],
      );
    }
    if (!pending) {
      return modelEditNeedsInput(
        '没有找到可确认的待执行模型修改，原模型保持不变。',
        'model_edit_confirmation_missing',
        ['请重新描述需要执行的模型修改。'],
      );
    }
    const suppliedPlanId = text(suppliedPlan?.plan_id || suppliedPlan?.planId);
    if (suppliedPlanId && suppliedPlanId !== pending.plan_id) {
      return modelEditNeedsInput(
        '待确认方案与当前项目保存的方案不一致，已拒绝执行。',
        'model_edit_confirmation_mismatch',
        ['请刷新当前项目后重新确认，或重新描述修改要求。'],
      );
    }
    plan = pending.plan;
  } else {
    // A new edit request supersedes any older high-impact confirmation.
    await clearPendingModelEdit(workspace);
  }
  if (!plan) {
    const config = getIntentModelConfig();
    try {
      const requestPlan = context.requestModelEditPlan || requestModelEditPlan;
      plan = await requestPlan({
        prompt: text(body.latestUserMessage || body.latest_user_message || body.prompt),
        projectId,
        source: workspace.source,
        sourceHash: workspace.source_hash,
        sourceFilename: workspace.source_filename,
        projectMemory: workspace.project_memory,
        modelIndex: workspace.model_index,
        editHistory: workspace.project_memory?.model_edit_history || [],
        recentConversation: body.projectConversation || body.project_conversation || [],
        config,
      });
    } catch (error) {
      return buildModelNeedsInput(error, {
        config,
        code: error?.code || 'llm_model_edit_failed',
        requestKind: 'model_edit',
      });
    }
  }

  if (['needs_input', 'noop', 'blocked'].includes(plan?.status)) {
    const blocked = plan.status === 'blocked';
    if (confirmed) await clearPendingModelEdit(workspace);
    return {
      ...modelEditNeedsInput(
        plan.intent_summary || (plan.status === 'noop'
          ? '没有识别到可执行的模型修改。'
          : blocked
            ? '模型修改计划已被阻断，原模型保持不变。'
            : '还需要补充模型修改信息。'),
        plan.status === 'noop' ? 'model_edit_noop' : blocked ? 'model_edit_blocked' : 'model_edit_needs_input',
        plan.questions?.length ? plan.questions : ['请说明要修改的对象、期望结果，以及用于区分目标的位置描述。'],
      ),
      model_edit_plan: plan,
      project_source_hash: workspace.source_hash,
    };
  }

  const validatePlan = context.validateModelEditPlanWithAst || context.validateModelEditPlan || validateModelEditPlanWithAst;
  const validation = await validatePlan(plan, {
    source: workspace.source,
    sourceHash: workspace.source_hash,
    projectId,
    sourceFilename: workspace.source_filename,
    python: context.python,
    requireCadQueryImport: true,
  });
  if (!validation.valid || !['ok', 'needs_confirmation'].includes(validation.status)) {
    if (confirmed) await clearPendingModelEdit(workspace);
    return {
      ...modelEditNeedsInput(
        validation.message || '模型修改没有通过安全检查，原模型保持不变。',
        'model_edit_validation_failed',
        ['请重新描述修改要求；系统只接受当前项目源码中的精确、安全修改。'],
      ),
      model_edit_plan: validation.plan,
      model_edit_validation: summarizeValidation(validation),
      project_source_hash: workspace.source_hash,
    };
  }

  // A model edit changes the source that a previous forced engraving was
  // confirmed against. Invalidate that override before staging, so the
  // preview/build path cannot accidentally reuse a stale bypass marker.
  const synchronizedSource = synchronizeSurfaceEngravingSource({
    source: validation.source,
    artifact,
  });
  workingArtifact = synchronizedSource.artifact;
  if (synchronizedSource.invalidated) {
    validation.source = synchronizedSource.source;
    validation.source_hash_after = hashCadQuerySource(synchronizedSource.source);
  }

  const requestText = text(body.latestUserMessage || body.latest_user_message || body.prompt);
  if (!confirmed && requiresHighImpactModelEditConfirmation(requestText, validation.plan)) {
    validation.plan = {
      ...validation.plan,
      risk_level: 'high',
      requires_confirmation: true,
      risk_reasons: [
        ...(Array.isArray(validation.plan.risk_reasons) ? validation.plan.risk_reasons : []),
        '这项要求会改变主体边线、孔槽或其他实体结构，必须由用户确认。',
      ],
    };
  }

  const staged = await stageAndBuildModelEdit({
    workspace,
    source: validation.source,
    plan: validation.plan,
    currentDesignState: {
      ...(body.currentDesignState || body.design_state || {}),
      ...(workingArtifact?.design_state || {}),
    },
    context,
  });
  if (staged.status !== 'pass') {
    await removeStagedFile(staged.staged_path);
    return {
      ...modelEditNeedsInput(
        staged.message || '修改后的模型没有通过 CadQuery 构建验证，原模型保持不变。',
        staged.blocking_reason || 'model_edit_build_failed',
        ['请调整修改要求，或缩小本次改动范围后重试。'],
      ),
      model_edit_plan: validation.plan,
      model_edit_validation: summarizeValidation(validation),
      model_edit_preflight: staged,
      project_source_hash: workspace.source_hash,
    };
  }

  if (validation.plan.requires_confirmation && !confirmed) {
    try {
      await writePendingModelEdit(workspace, validation, staged);
    } catch (error) {
      await removeStagedFile(staged.staged_path);
      return modelEditNeedsInput(
        error instanceof Error ? error.message : String(error),
        error?.code || 'model_edit_confirmation_save_failed',
        ['请重新提交模型修改要求。'],
      );
    }
    return {
      status: 'needs_input',
      title: '模型修改需要确认',
      message: `这项修改会影响主体结构、开孔或硬件关系：${withoutTerminalPunctuation(validation.plan.intent_summary || '高影响模型修改')}。确认后才会写入当前项目副本。`,
      questions: ['请回复“确认修改”执行，或回复“取消修改”保持当前模型。'],
      blocking_reason: 'model_edit_confirmation',
      requires_confirmation: true,
      model_edit_plan: validation.plan,
      model_edit_validation: summarizeValidation(validation),
      model_edit_preflight: staged,
      project_source_hash: workspace.source_hash,
      project_revision: workspace.project_revision,
    };
  }

  const memory = buildProjectMemoryUpdate({
    projectId,
    previousMemory: workspace.project_memory,
    plan: validation.plan,
    sourceHashBefore: validation.source_hash_before,
    sourceHashAfter: validation.source_hash_after,
    revisionId: `revision-${workspace.project_revision + 1}`,
  });
  let committed;
  try {
    committed = await commitProjectSourceRevision({
      rootDir: context.rootDir,
      projectId,
      source: validation.source,
      expectedSourceHash: validation.source_hash_before,
      summary: validation.plan.intent_summary || '按自然语言要求更新当前项目模型。',
      changeType: confirmed ? 'confirm_model_edit' : 'model_edit',
      operations: validation.plan.operations,
      riskLevel: validation.plan.risk_level,
      projectMemoryUpdate: memory,
    });
  } catch (error) {
    return modelEditNeedsInput(
      error instanceof Error ? error.message : String(error),
      error?.code || 'model_edit_commit_failed',
      ['请刷新当前项目后重新提交修改要求。'],
    );
  } finally {
    await removeStagedFile(staged.staged_path);
    await clearPendingModelEdit(workspace);
  }
  return buildCommittedArtifact({
    artifact: workingArtifact,
    workspace: committed,
    previousWorkspace: workspace,
    routeAction,
    plan: validation.plan,
    context,
  });
}

async function stageAndBuildModelEdit({ workspace, source, plan, currentDesignState, context }) {
  const stagedPath = path.join(workspace.project_dir, 'staged', `${plan.plan_id}.cq.py`);
  await writeFile(stagedPath, source, 'utf8');
  if (!context.environment?.cadqueryAvailable) {
    return {
      status: 'fail',
      blocking_reason: 'model_edit_cadquery_unavailable',
      message: '当前 CadQuery 环境不可用，模型修改未写入项目。',
      staged_path: stagedPath,
    };
  }
  const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'zwcad-model-edit-'));
  try {
    const buildArtifact = context.buildCadQueryArtifact || context.buildArtifact || buildCadQueryArtifact;
    let build;
    try {
      build = await buildArtifact({
        rootDir: tempRoot,
        python: context.python,
        environment: context.environment,
        body: {
          designId: 'model_edit_stage',
          cadquery_code: source,
          currentDesignState,
        },
      });
    } catch {
      return {
        status: 'fail',
        blocking_reason: 'model_edit_cadquery_build_exception',
        message: '暂存模型构建发生异常，原模型保持不变。',
        staged_path: stagedPath,
      };
    }
    if (build.status !== 'artifact_exports') {
      return {
        status: 'fail',
        blocking_reason: build.blocking_reason || 'model_edit_cadquery_build_failed',
        message: build.message || '暂存模型构建失败。',
        staged_path: stagedPath,
        build_status: build.status,
      };
    }
    if (build.mesh_validation_status === 'fail') {
      return {
        status: 'fail',
        blocking_reason: 'model_edit_mesh_validation_failed',
        message: '修改后的模型网格校验未通过，原模型保持不变。',
        staged_path: stagedPath,
        mesh_validation_status: build.mesh_validation_status,
      };
    }
    return {
      status: 'pass',
      staged_path: stagedPath,
      source_hash: workspace.source_hash,
      build_status: build.status,
      mesh_validation_status: build.mesh_validation_status,
      exports: (build.exports || []).map((item) => item.id),
    };
  } finally {
    await rm(tempRoot, { recursive: true, force: true });
  }
}

async function buildCommittedArtifact({ artifact, workspace, previousWorkspace, routeAction, plan, context }) {
  const synchronized = synchronizeSurfaceEngravingSource({
    source: workspace.source,
    artifact,
  });
  const nextArtifact = artifactResponse(synchronized.artifact, workspace, {
    title: routeAction === 'undo_model_edit' ? '已撤销最近一次模型修改' : '模型修改已完成',
    message: routeAction === 'undo_model_edit'
      ? '当前项目已恢复到上一版模型源码，并生成了新的撤销修订。'
      : `${withoutTerminalPunctuation(plan.intent_summary || '模型修改')}。修改只写入当前项目副本。`,
    modelEditPlan: plan,
    routeAction,
  });
  const buildArtifact = context.buildCadQueryArtifact || context.buildArtifact || buildCadQueryArtifact;
  let build;
  try {
    build = await buildArtifact({
      rootDir: context.rootDir,
      python: context.python,
      environment: context.environment,
      body: {
        designId: workspace.project_id,
        cadquery_code: workspace.source,
        currentDesignState: nextArtifact.design_state,
        artifact: nextArtifact,
      },
    });
  } catch {
    build = {
      status: 'fail',
      blocking_reason: 'model_edit_final_build_exception',
      message: '正式模型刷新发生异常。',
    };
  }
  const buildFailure = committedBuildFailure(build);
  if (buildFailure) {
    const recovery = previousWorkspace
      ? await recoverCommittedSource({
          artifact,
          committedWorkspace: workspace,
          previousWorkspace,
          plan,
          routeAction,
          context,
        })
      : { status: 'not_attempted', workspace };
    const responseWorkspace = recovery.workspace || workspace;
    const preservedArtifact = artifactResponse(recovery.artifact || artifact, responseWorkspace, {
      title: '模型修改未完成',
      message: recovery.status === 'restored'
        ? '正式模型刷新失败，项目源码已自动恢复到修改前版本。'
        : '正式模型刷新失败，系统未能自动恢复项目源码。',
      modelEditPlan: plan,
      routeAction,
    });
    return {
      ...preservedArtifact,
      ...modelEditNeedsInput(
        recovery.status === 'restored'
          ? `${buildFailure.message} 项目源码已恢复，原模型保持不变。`
          : `${buildFailure.message} 自动恢复失败，请停止继续修改并检查当前项目。`,
        buildFailure.blocking_reason,
        recovery.status === 'restored'
          ? ['请调整修改要求后重试。']
          : ['请重新打开当前项目，确认源码与模型版本后再继续。'],
      ),
      model_edit_plan: plan,
      model_edit_recovery: summarizeRecovery(recovery),
      project_revision: responseWorkspace.project_revision,
      project_source_hash: responseWorkspace.source_hash,
    };
  }
  return artifactResponse(build.artifact || nextArtifact, workspace, {
    title: nextArtifact.title,
    message: nextArtifact.message,
    modelEditPlan: plan,
    routeAction,
  });
}

function synchronizeSurfaceEngravingSource({ source = '', artifact = {} } = {}) {
  const original = artifact && typeof artifact === 'object' ? artifact : {};
  const originalDesignState = original.design_state && typeof original.design_state === 'object'
    ? original.design_state
    : {};
  const rawEngravings = Array.isArray(original.surface_engravings)
    ? original.surface_engravings
    : Array.isArray(originalDesignState.surface_engravings)
      ? originalDesignState.surface_engravings
      : [];
  if (!rawEngravings.length) {
    if (sourceContainsForcedEngravingOverride(source)) {
      const cleanSource = stripSurfaceEngravingCode(source);
      const {
        original_feature_intersection_override: _override,
        ...withoutTopLevelOverride
      } = original;
      const nextDesignState = {
        ...originalDesignState,
        surface_engravings: [],
        surface_engraving_patch: '',
        surface_engraving_preflight: null,
        surface_engraving_report: [],
        warnings: (Array.isArray(originalDesignState.warnings)
          ? originalDesignState.warnings
          : []).filter((warning) => !isSurfaceEngravingOverrideWarning(warning)),
      };
      return {
        source: cleanSource,
        artifact: {
          ...withoutTopLevelOverride,
          cadquery_code: cleanSource,
          surface_engravings: [],
          surface_engraving_patch: '',
          surface_engraving_preflight: null,
          surface_engraving_report: [],
          warnings: (Array.isArray(original.warnings) ? original.warnings : [])
            .filter((warning) => !isSurfaceEngravingOverrideWarning(warning)),
          design_state: nextDesignState,
        },
        invalidated: true,
        invalidated_ids: [],
      };
    }
    return { source: String(source || ''), artifact: original, invalidated: false, invalidated_ids: [] };
  }

  const normalized = normalizeSurfaceEngravings(rawEngravings);
  const nextEngravings = invalidateSurfaceEngravingOverridesForSource(normalized, source);
  const nextById = new Map(nextEngravings.map((item) => [item.id, item]));
  const invalidatedIds = normalized
    .filter((item) => item.allow_original_feature_intersection === true
      && nextById.get(item.id)?.allow_original_feature_intersection !== true)
    .map((item) => item.id)
    .filter(Boolean);
  const staleOverrideInSource = sourceContainsForcedEngravingOverride(source)
    && !nextEngravings.some((item) => item.allow_original_feature_intersection === true);
  if (!invalidatedIds.length && !staleOverrideInSource) {
    return { source: String(source || ''), artifact: original, invalidated: false, invalidated_ids: [] };
  }

  const cleanSource = stripSurfaceEngravingCode(source);
  const patch = buildSurfaceEngravingPatch(nextEngravings);
  const nextSource = nextEngravings.length
    ? injectSurfaceEngravingCode(cleanSource, nextEngravings, patch)
    : cleanSource;
  const nextWarnings = (Array.isArray(originalDesignState.warnings)
    ? originalDesignState.warnings
    : []).filter((warning) => !isSurfaceEngravingOverrideWarning(warning));
  const nextDesignState = {
    ...originalDesignState,
    surface_engravings: nextEngravings,
    surface_engraving_patch: patch,
    surface_engraving_preflight: null,
    surface_engraving_report: [],
    warnings: nextWarnings,
  };
  const {
    original_feature_intersection_override: _override,
    ...withoutTopLevelOverride
  } = original;
  const nextArtifact = {
    ...withoutTopLevelOverride,
    cadquery_code: nextSource,
    surface_engravings: nextEngravings,
    surface_engraving_patch: patch,
    surface_engraving_preflight: null,
    surface_engraving_report: [],
    warnings: (Array.isArray(original.warnings) ? original.warnings : [])
      .filter((warning) => !isSurfaceEngravingOverrideWarning(warning)),
    design_state: nextDesignState,
  };
  return {
    source: nextSource,
    artifact: nextArtifact,
    invalidated: true,
    invalidated_ids: invalidatedIds,
  };
}

function sourceContainsForcedEngravingOverride(source = '') {
  const value = String(source || '');
  return /["']allow_original_feature_intersection["']\s*:\s*(?:True|true)/.test(value)
    || /["']original_feature_intersection_source_hash["']\s*:\s*["'][a-f0-9]{64}["']/i.test(value);
}

function isSurfaceEngravingOverrideWarning(value = {}) {
  if (!value || typeof value !== 'object') return false;
  const id = String(value.id || '').toLowerCase();
  const message = String(value.message || '');
  return id === 'surface_engraving_original_feature_intersection_override'
    || id.startsWith('surface_engraving_override_')
    || (message.includes('强制刻字') && message.includes('文字可能被边界裁断'));
}

function artifactResponse(artifact, workspace, { title, message, modelEditPlan, routeAction }) {
  const original = artifact && typeof artifact === 'object' ? artifact : {};
  const base = synchronizeArtifactParameters(original, modelEditPlan);
  const revisionIntent = {
    status: 'ok',
    route_action: routeAction,
    prompt: modelEditPlan?.intent_summary || '',
    operations: modelEditPlan?.operations || [],
    risk_level: modelEditPlan?.risk_level || 'low',
    summary: modelEditPlan?.intent_summary || message,
    source: 'llm_model_edit',
  };
  const projectState = {
    project_id: workspace.project_id,
    project_manifest: workspace.project_manifest,
    project_revision: workspace.project_revision,
    project_source_hash: workspace.source_hash,
    model_index: workspace.model_index,
    project_memory_summary: workspace.project_memory?.summary || '',
    model_edit_history: workspace.project_memory?.model_edit_history || [],
  };
  const projectFiles = updateProjectFileState(base.project_files || base.design_state?.project_files, workspace);
  return {
    ...base,
    ...projectState,
    status: 'artifact',
    title,
    message,
    cadquery_code: workspace.source,
    project_files: projectFiles,
    model_edit_plan: modelEditPlan,
    revision_intent: revisionIntent,
    source: 'llm_model_edit',
    design_state: {
      ...(base.design_state || {}),
      ...projectState,
      id: workspace.project_id,
      project_files: projectFiles,
      model_edit_plan: modelEditPlan,
      revision_intent: revisionIntent,
    },
  };
}

function synchronizeArtifactParameters(artifact = {}, plan = {}) {
  const assignments = numericAssignmentsFromPatches(plan?.patches || plan?.code_patches || []);
  if (!assignments.size) return artifact;
  const designState = artifact.design_state && typeof artifact.design_state === 'object'
    ? artifact.design_state
    : {};
  const cadParameters = designState.cad_parameters && typeof designState.cad_parameters === 'object'
    ? designState.cad_parameters
    : {};
  return {
    ...artifact,
    parameters: updateMatchingParameterValues(artifact.parameters, assignments),
    design_state: {
      ...designState,
      parameters: updateMatchingParameterValues(designState.parameters, assignments),
      cad_parameters: {
        ...cadParameters,
        geometry: updateMatchingParameterValues(cadParameters.geometry, assignments),
      },
      enclosure_parameters: updateMatchingParameterValues(designState.enclosure_parameters, assignments),
    },
  };
}

function numericAssignmentsFromPatches(patches = []) {
  const assignments = new Map();
  for (const patch of Array.isArray(patches) ? patches : []) {
    for (const line of String(patch?.new_text || '').split(/\r?\n/)) {
      const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*$/);
      if (!match) continue;
      const value = Number(match[2]);
      if (Number.isFinite(value)) assignments.set(match[1], value);
    }
  }
  return assignments;
}

function updateMatchingParameterValues(value, assignments, depth = 0) {
  if (!value || typeof value !== 'object' || depth > 8) return value;
  if (Array.isArray(value)) return value.map((item) => updateMatchingParameterValues(item, assignments, depth + 1));
  const result = {};
  for (const [key, item] of Object.entries(value)) {
    if (assignments.has(key) && (typeof item === 'number' || Number.isFinite(Number(item)))) {
      result[key] = assignments.get(key);
    } else {
      result[key] = updateMatchingParameterValues(item, assignments, depth + 1);
    }
  }
  return result;
}

function updateProjectFileState(value, workspace) {
  const files = value && typeof value === 'object' ? { ...value } : {};
  files.model_source = {
    ...(files.model_source || {}),
    id: 'project_model_source',
    label: '项目模型源文件',
    format: 'py',
    url: `/exports/${workspace.project_id}/project/${workspace.source_filename}`,
    path: workspace.source_path,
    fidelity: 'project_source',
    editable: true,
    source_hash: workspace.source_hash,
    project_revision: workspace.project_revision,
    revision_id: workspace.revision_id,
  };
  return files;
}

async function loadProjectArtifact(rootDir, projectId, body) {
  const supplied = body.currentArtifact || body.current_artifact || body.artifact;
  if (supplied && typeof supplied === 'object') return supplied;
  try {
    return JSON.parse(await readFile(path.join(rootDir, 'exports', projectId, 'artifact.json'), 'utf8'));
  } catch {
    const designState = body.currentDesignState || body.design_state || {};
    return { status: 'artifact', design_state: designState, cadquery_code: body.currentCadQueryCode || body.current_cadquery_code || '' };
  }
}

async function writePendingModelEdit(workspace, validation, staged) {
  const plan = validation?.plan;
  if (!plan?.plan_id || plan.requires_confirmation !== true) {
    const error = new Error('待确认模型修改缺少稳定计划 ID 或高风险确认标记。');
    error.code = 'model_edit_confirmation_invalid';
    throw error;
  }
  const payload = {
    schema_version: PENDING_MODEL_EDIT_SCHEMA_VERSION,
    project_id: workspace.project_id,
    plan_id: plan.plan_id,
    source_hash_before: validation.source_hash_before,
    source_hash_after: validation.source_hash_after,
    staged_filename: path.basename(staged.staged_path || ''),
    created_at: new Date().toISOString(),
    plan,
  };
  await writeFile(pendingModelEditPath(workspace), `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
}

async function readPendingModelEdit(workspace) {
  let raw;
  try {
    raw = await readFile(pendingModelEditPath(workspace), 'utf8');
  } catch (error) {
    if (error?.code === 'ENOENT') return null;
    throw error;
  }
  let pending;
  try {
    pending = JSON.parse(raw);
  } catch {
    const error = new Error('当前项目保存的待确认模型修改已损坏，已拒绝执行。');
    error.code = 'model_edit_confirmation_invalid';
    throw error;
  }
  if (pending?.schema_version !== PENDING_MODEL_EDIT_SCHEMA_VERSION
    || pending.project_id !== workspace.project_id
    || !pending.plan_id
    || pending.plan?.plan_id !== pending.plan_id
    || pending.plan?.requires_confirmation !== true) {
    const error = new Error('当前项目保存的待确认模型修改格式不正确，已拒绝执行。');
    error.code = 'model_edit_confirmation_invalid';
    throw error;
  }
  if (pending.source_hash_before !== workspace.source_hash) {
    const error = new Error('项目源码已在待确认期间发生变化，旧修改方案不能继续执行。');
    error.code = 'model_edit_confirmation_stale';
    throw error;
  }
  return pending;
}

async function clearPendingModelEdit(workspace) {
  const pendingPath = pendingModelEditPath(workspace);
  let stagedFilename = '';
  try {
    const pending = JSON.parse(await readFile(pendingPath, 'utf8'));
    const candidate = path.basename(text(pending?.staged_filename));
    if (candidate === text(pending?.staged_filename) && /^[A-Za-z0-9_-]+\.cq\.py$/i.test(candidate)) {
      stagedFilename = candidate;
    }
  } catch {
    // The fixed pending file is removed below even when its JSON is invalid.
  }
  if (stagedFilename) {
    await removeStagedFile(path.join(workspace.project_dir, 'staged', stagedFilename));
  }
  await removeStagedFile(pendingPath);
}

function pendingModelEditPath(workspace) {
  return path.join(workspace.project_dir, 'staged', PENDING_MODEL_EDIT_FILENAME);
}

async function recoverCommittedSource({
  artifact,
  committedWorkspace,
  previousWorkspace,
  plan,
  routeAction,
  context,
}) {
  let restored;
  const synchronizedPrevious = synchronizeSurfaceEngravingSource({
    source: previousWorkspace.source,
    artifact,
  });
  try {
    restored = await commitProjectSourceRevision({
      rootDir: context.rootDir,
      projectId: committedWorkspace.project_id,
      source: synchronizedPrevious.source,
      expectedSourceHash: committedWorkspace.source_hash,
      summary: `自动恢复失败的模型修改：${plan.intent_summary || plan.plan_id || '未命名修改'}。`,
      changeType: 'model_edit_build_rollback',
      operations: [{ id: 'restore-after-build-failure', type: 'restore_revision', summary: '正式构建失败后恢复修改前源码' }],
      riskLevel: 'low',
      projectMemoryUpdate: previousWorkspace.project_memory,
    });
  } catch (error) {
    return {
      status: 'failed',
      workspace: committedWorkspace,
      error: error instanceof Error ? error.message : String(error),
      error_code: error?.code || 'model_edit_rollback_failed',
    };
  }

  const recoveryPlan = {
    schema_version: 'model_edit_plan_v1',
    plan_id: `rollback-${plan.plan_id || restored.revision_id}`,
    project_id: restored.project_id,
    intent_summary: '正式构建失败，自动恢复修改前源码。',
    source_hash: committedWorkspace.source_hash,
    operations: [{ id: 'restore-after-build-failure', type: 'restore_revision', summary: '恢复修改前源码' }],
    risk_level: 'low',
    requires_confirmation: false,
  };
  const recoveryArtifact = artifactResponse(synchronizedPrevious.artifact, restored, {
    title: '原模型已恢复',
    message: '正式构建失败，项目源码已自动恢复到修改前版本。',
    modelEditPlan: recoveryPlan,
    routeAction: `${routeAction}_rollback`,
  });
  const buildArtifact = context.buildCadQueryArtifact || context.buildArtifact || buildCadQueryArtifact;
  try {
    const rebuilt = await buildArtifact({
      rootDir: context.rootDir,
      python: context.python,
      environment: context.environment,
      body: {
        designId: restored.project_id,
        cadquery_code: restored.source,
        currentDesignState: recoveryArtifact.design_state,
        artifact: recoveryArtifact,
      },
    });
    const rebuildFailure = committedBuildFailure(rebuilt);
    return {
      status: 'restored',
      workspace: restored,
      artifact: rebuildFailure ? recoveryArtifact : rebuilt.artifact,
      rebuild_status: rebuildFailure ? 'fail' : rebuilt.status,
      rebuild_blocking_reason: rebuildFailure?.blocking_reason || '',
    };
  } catch (error) {
    return {
      status: 'restored',
      workspace: restored,
      artifact: recoveryArtifact,
      rebuild_status: 'exception',
      rebuild_error: error instanceof Error ? error.message : String(error),
    };
  }
}

function committedBuildFailure(build = {}) {
  if (build.status !== 'artifact_exports') {
    return {
      blocking_reason: build.blocking_reason || 'model_edit_final_build_failed',
      message: build.message || '真实模型刷新失败。',
    };
  }
  if (build.mesh_validation_status === 'fail') {
    return {
      blocking_reason: 'model_edit_mesh_validation_failed',
      message: '正式模型的网格校验未通过。',
    };
  }
  if (!build.artifact || build.warning?.id === 'cadquery_artifact_persist_failed') {
    return {
      blocking_reason: 'model_edit_artifact_persist_failed',
      message: '真实模型已生成，但 Artifact 元数据没有可靠保存。',
    };
  }
  return null;
}

function summarizeRecovery(value = {}) {
  return {
    status: value.status || 'not_attempted',
    project_revision: value.workspace?.project_revision,
    project_source_hash: value.workspace?.source_hash,
    rebuild_status: value.rebuild_status,
    rebuild_blocking_reason: value.rebuild_blocking_reason,
    error_code: value.error_code,
    error: value.error,
  };
}

function summarizeValidation(value = {}) {
  return {
    status: value.status,
    valid: value.valid,
    source_hash_before: value.source_hash_before,
    source_hash_after: value.source_hash_after,
    risk: value.risk,
    errors: value.errors,
    safety: value.safety ? { status: value.safety.status, id: value.safety.id, message: value.safety.message } : null,
  };
}

function modelEditNeedsInput(message, blockingReason, questions = []) {
  return {
    status: 'needs_input',
    title: '需要确认模型修改',
    message,
    questions,
    blocking_reason: blockingReason,
    source: 'llm_model_edit',
  };
}

async function removeStagedFile(filePath) {
  if (!filePath) return;
  try {
    await unlink(filePath);
  } catch {
    // The staged file is non-authoritative; a missing cleanup target is harmless.
  }
}

function text(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function requiresHighImpactModelEditConfirmation(prompt = '', plan = {}) {
  const planText = [
    plan?.intent_summary,
    ...(Array.isArray(plan?.operations) ? plan.operations.map((item) => (
      `${item?.type || ''} ${item?.id || ''} ${item?.target_id || ''} ${item?.summary || ''} ${JSON.stringify(item?.parameters || {})}`
    )) : []),
    ...(Array.isArray(plan?.patches) ? plan.patches.map((item) => `${item?.old_text || ''}\n${item?.new_text || ''}`) : []),
  ].join('\n');
  const combined = `${prompt}\n${planText}`;
  const edgeChange = /圆角|倒圆|圆弧角|倒角|切角|磨圆|修圆|去锐边|削平|\b(?:fillet|chamfer|roundover)\b|(?:fillet|chamfer|roundover)[a-z0-9_]*(?:radius|size)|(?:edge|corner)[a-z0-9_]*(?:radius|fillet|chamfer)/i;
  if (edgeChange.test(combined)) return true;
  const openingChange = /(?:开|打|钻|做|增加|添加|新增|扩大|扩孔|加大|放大|变大|缩小|缩径|变小|调整|修改|改成|改为|封上?|封闭|封堵|堵上?|删除|删掉|移除|去掉).{0,20}(?:散热孔|通风孔|开孔|开口|按钮孔|螺丝孔|安装孔|孔径|孔位|圆孔|方孔|孔|槽口|槽|窗口)|(?:散热孔|通风孔|开孔|开口|按钮孔|螺丝孔|安装孔|孔径|孔位|圆孔|方孔|孔|槽口|槽|窗口).{0,20}(?:移动|移到|扩大|扩孔|加大|放大|变大|缩小|缩径|变小|调整|修改|改成|改为|封上?|封闭|封堵|堵上?|删除|删掉|移除|去掉)|\b(?:add|create|drill|cut|resize|enlarge|shrink|move|remove|delete|close|seal|modify|update)[a-z_ -]{0,16}(?:hole|opening|slot|cutout)\b|\b(?:hole|opening|slot|cutout)[a-z_ -]{0,16}(?:diameter|radius|width|height|length|size|offset|move|resize|remove|delete|close|seal)\b|\.(?:cut|hole|cboreHole|cskHole|slot2D)\s*\(/i;
  return openingChange.test(combined);
}

function withoutTerminalPunctuation(value) {
  return text(value).replace(/[。.!！；;，,\s]+$/u, '');
}
