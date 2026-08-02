import {
  renderGenerationTraceContent,
  renderHealthContent,
  renderNeedsInputContent,
  renderNeedsInputDetails,
  renderSelfCheckContent,
} from './renderers.js';
import {
  isRealCadQuerySource,
  selectViewerSourceFromExports,
  viewerStatusActionForModelEvent,
} from './model-source.js';
import {
  readFirstStartQuery,
  shouldOpenModelSourceOnFirstStart,
} from './startup-query.js';

const state = {
  hardware: [],
  hardwareSystems: {},
  templateProjects: [],
  activeHardwareSystemTab: 'xiao',
  activeHardwareModelType: 'electronic_component',
  activeCustomHardwareType: 'electronic',
  customHardwareWorkbenchOpen: false,
  selectedHardwareIds: new Set(),
  customHardwareProfiles: [],
  customHardwarePreview: null,
  customHardwarePreviewFailure: null,
  customHardwareConversation: [],
  customHardwareThumbnailDataUrl: '',
  customHardwareFormRevision: 0,
  draft: null,
  requirementAnalysis: null,
  workflowStage: 'idle',
  artifact: null,
  partialBom: null,
  cadqueryBuild: null,
  cadqueryAutoBuildPromise: null,
  cadqueryPreviewBuildKeys: new Set(),
  health: null,
  selfCheck: null,
  validationResult: null,
  parameterRegenerateTimer: null,
  isBusy: false,
  isCadqueryBuilding: false,
  modelViewer: null,
  modelViewerError: null,
  viewerNotice: null,
  viewerSourceKey: '',
  previewRevision: 0,
  activeView: 'preview',
  previewMode: 'assembly',
  previewZoom: 1,
  hardwareDrawerOpen: false,
  rightTab: 'bom',
  exportFormat: '',
  exportResult: null,
  exportDirectoryHandle: null,
  exportDirectoryName: '',
  parameterOverrides: {},
  hardwareFaceOverrides: {},
  hardwareRotationOverrides: {},
  conversationRoute: null,
  revisionIntent: null,
  userAnswers: [],
  surfaceEngravingDraft: null,
  surfaceEngravingTurns: [],
  lastPrompt: '',
  lastNeedsInput: null,
  currentTaskId: '',
  taskActive: false,
  modelSources: [],
  activeModelSourceId: '',
  llmConnection: null,
  llmWorkflowFailure: null,
  modelSourceDraftId: '',
};

const PARAMETER_REGENERATE_DELAY_MS = 700;
const POSITIVE_DEFAULT_PARAMETER_KEYS = new Set(['inner_length_x', 'inner_width_y', 'inner_height_z']);
const TEMPLATE_PROJECT_SYSTEM_ID = 'template_projects';

const els = {
  promptForm: document.querySelector('#promptForm'),
  promptInput: document.querySelector('#promptInput'),
  newTaskButton: document.querySelector('#newTaskButton'),
  newTaskDialog: document.querySelector('#newTaskDialog'),
  sampleButton: document.querySelector('#sampleButton'),
  messages: document.querySelector('#messages'),
  modelViewer: document.querySelector('#modelViewer'),
  viewerStatus: document.querySelector('#viewerStatus'),
  viewerStatusTitle: document.querySelector('#viewerStatusTitle'),
  viewerStatusBody: document.querySelector('#viewerStatusBody'),
  sceneSvg: document.querySelector('#sceneSvg'),
  codeView: document.querySelector('#codeView'),
  checksView: document.querySelector('#checksView'),
  previewView: document.querySelector('#previewView'),
  confirmationView: document.querySelector('#confirmationView'),
  exportLinks: document.querySelector('#exportLinks'),
  exportStlButton: document.querySelector('#exportStlButton'),
  exportStlDialog: document.querySelector('#exportStlDialog'),
  exportStlParts: document.querySelector('#exportStlParts'),
  exportStlPath: document.querySelector('#exportStlPath'),
  exportStlStatus: document.querySelector('#exportStlStatus'),
  parameterGroups: document.querySelector('#parameterGroups'),
  rightBomPanel: document.querySelector('#rightBomPanel'),
  regenerateButton: document.querySelector('#regenerateButton'),
  bomTabButton: document.querySelector('#bomTabButton'),
  guiTabButton: document.querySelector('#guiTabButton'),
  hardwareList: document.querySelector('#hardwareList'),
  hardwareSystemTabs: document.querySelector('#hardwareSystemTabs'),
  hardwareSearch: document.querySelector('#hardwareSearch'),
  categoryFilter: document.querySelector('#categoryFilter'),
  openCustomHardwareButton: document.querySelector('#openCustomHardwareButton'),
  hardwareCount: document.querySelector('#hardwareCount'),
  bomSummary: document.querySelector('#bomSummary'),
  customHardwarePanel: document.querySelector('#customHardwarePanel'),
  customHardwareInput: document.querySelector('#customHardwareInput'),
  customHardwareName: document.querySelector('#customHardwareName'),
  customHardwareThumbnail: document.querySelector('#customHardwareThumbnail'),
  customHardwareHints: document.querySelector('#customHardwareHints'),
  customHardwareBackButton: document.querySelector('#customHardwareBackButton'),
  previewCustomHardwareButton: document.querySelector('#previewCustomHardwareButton'),
  confirmCustomHardwareButton: document.querySelector('#confirmCustomHardwareButton'),
  customHardwareStatus: document.querySelector('#customHardwareStatus'),
  appShell: document.querySelector('.app-shell'),
  hardwareDrawer: document.querySelector('#hardwareDrawer'),
  drawerToggle: document.querySelector('#drawerToggle'),
  selectedHardwareCount: document.querySelector('#selectedHardwareCount'),
  zoomOutButton: document.querySelector('#zoomOutButton'),
  zoomInButton: document.querySelector('#zoomInButton'),
  zoomResetButton: document.querySelector('#zoomResetButton'),
  zoomLabel: document.querySelector('#zoomLabel'),
  modeButtons: document.querySelector('.mode-buttons'),
  sourceStatus: document.querySelector('#sourceStatus'),
  cadqueryStatus: document.querySelector('#cadqueryStatus'),
  llmStatusButton: document.querySelector('#llmStatusButton'),
  modelSourceDialog: document.querySelector('#modelSourceDialog'),
  modelSourceList: document.querySelector('#modelSourceList'),
  modelSourceForm: document.querySelector('#modelSourceForm'),
  modelSourceName: document.querySelector('#modelSourceName'),
  modelSourceBaseUrl: document.querySelector('#modelSourceBaseUrl'),
  modelSourceModel: document.querySelector('#modelSourceModel'),
  modelSourceApiKey: document.querySelector('#modelSourceApiKey'),
  modelSourceEnabled: document.querySelector('#modelSourceEnabled'),
  modelSourceStatus: document.querySelector('#modelSourceStatus'),
};

init();

async function init() {
  const startupQuery = readFirstStartQuery(window.location);
  bindEvents();
  initializeModelViewer();
  addMessage('agent', '先说需求', '告诉我你想做什么产品，我会先分析硬件、BOM 和可行性，再进入建模。');
  await loadHealth();
  await loadModelSources();
  applyFirstStartQuery(startupQuery);
  await loadHardwareLibrary();
  renderAll();
}

function applyFirstStartQuery(startupQuery = {}) {
  if (!startupQuery.present) return;
  window.history.replaceState(window.history.state, '', startupQuery.cleanUrl);
  if (shouldOpenModelSourceOnFirstStart({
    requested: startupQuery.requested,
    llmStatus: state.llmConnection?.status || '',
  })) {
    openModelSourceDialog();
  }
}

async function initializeModelViewer() {
  setViewerStatus('3D 查看器加载中', '正在载入本地 Three.js 模型查看器。', { thinking: true });
  try {
    const { createModelViewer } = await import('./model-viewer.js');
    state.modelViewer = createModelViewer(els.modelViewer, {
      onStatus: handleModelViewerStatus,
    });
    state.modelViewerError = null;
    renderPreview();
  } catch (error) {
    state.modelViewer = null;
    state.modelViewerError = error instanceof Error ? error.message : String(error);
    setViewerStatus(
      '3D 查看器未就绪',
      'Three.js 依赖未加载成功。请先在 ZW-CAD-intent 目录安装依赖：npm install。',
    );
  }
}

function bindEvents() {
  els.promptForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    await handlePromptSubmit();
  });

  els.newTaskButton?.addEventListener('click', () => {
    if (state.isBusy) return;
    openNewTaskDialog();
  });

  els.newTaskDialog?.addEventListener('click', (event) => {
    if (event.target === els.newTaskDialog || event.target.closest('[data-action="cancel-new-task"]')) {
      closeNewTaskDialog();
      return;
    }
    if (event.target.closest('[data-action="confirm-new-task"]')) {
      closeNewTaskDialog();
      resetCurrentTask();
    }
  });

  els.sampleButton.addEventListener('click', () => {
    els.promptInput.value = '做一个带 OLED 屏、两个按钮和蜂鸣器的桌面计时器外壳，要有 USB-C 开口和四角螺丝柱。';
    els.promptInput.focus();
  });

  document.querySelectorAll('.segmented button').forEach((button) => {
    button.addEventListener('click', () => {
      state.activeView = button.dataset.view;
      renderActiveView();
    });
  });

  els.bomTabButton?.addEventListener('click', () => {
    state.rightTab = 'bom';
    renderRightPane();
  });
  els.guiTabButton?.addEventListener('click', () => {
    state.rightTab = 'gui';
    renderRightPane();
  });

  els.modeButtons?.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-mode]');
    if (!button) return;
    state.previewMode = button.dataset.mode || 'assembly';
    renderPreview();
    els.modeButtons.querySelectorAll('button[data-mode]')
      .forEach((item) => item.classList.toggle('active', item === button));
  });

  els.regenerateButton.addEventListener('click', () => {
    clearPendingParameterRegenerate();
    if (state.requirementAnalysis && !state.draft && !state.artifact) {
      prepare(state.lastPrompt || state.requirementAnalysis.partial_intent?.product_name || '', {
        keepUserAnswers: true,
        taskId: currentTaskId(),
      });
      return;
    }
    if (state.draft?.design_state && !state.artifact) {
      collectParameterOverridesFromInputs();
      prepare(state.lastPrompt || state.draft.design_state.intent?.product_name || '', {
        keepUserAnswers: true,
        currentDesignState: state.draft.design_state,
        taskId: currentTaskId(),
      });
      return;
    }
    regenerate();
  });
  els.drawerToggle.addEventListener('click', toggleHardwareDrawer);
  els.zoomOutButton.addEventListener('click', () => setPreviewZoom(state.previewZoom - 0.15));
  els.zoomInButton.addEventListener('click', () => setPreviewZoom(state.previewZoom + 0.15));
  els.zoomResetButton.addEventListener('click', () => {
    setPreviewZoom(1);
    state.modelViewer?.resetView();
  });
  els.hardwareSearch.addEventListener('input', renderHardwareList);
  els.categoryFilter.addEventListener('change', renderHardwareList);
  els.openCustomHardwareButton?.addEventListener('click', openCustomHardwareLibrary);
  els.hardwareSystemTabs?.addEventListener('click', (event) => {
    const tab = event.target.closest('[data-hardware-system-tab]');
    if (!tab) return;
    state.activeHardwareSystemTab = tab.dataset.hardwareSystemTab || 'xiao';
    if (state.activeHardwareSystemTab === 'common') state.activeHardwareModelType = 'electronic_component';
    state.customHardwareWorkbenchOpen = false;
    els.categoryFilter.value = '';
    renderHardwareSystemTabs();
    renderCategoryFilter();
    renderHardwareList();
  });
  els.customHardwarePanel?.addEventListener('click', handleCustomHardwarePanelClick);
  els.customHardwareThumbnail?.addEventListener('change', handleCustomHardwareThumbnailChange);
  els.customHardwareName?.addEventListener('input', invalidateCustomHardwarePreview);
  els.customHardwareInput?.addEventListener('input', invalidateCustomHardwarePreview);
  els.messages.addEventListener('click', handleResolutionOptionClick);
  els.confirmationView?.addEventListener('click', async (event) => {
    const buildButton = event.target.closest('[data-action="build-confirmed"]');
    if (buildButton) {
      buildButton.disabled = true;
      buildButton.textContent = '开始建模...';
      await buildConfirmedDesign();
      return;
    }
    const editButton = event.target.closest('[data-action="edit-description"]');
    if (editButton) {
      els.promptInput.focus();
      return;
    }
    const requirementButton = event.target.closest('[data-action="confirm-requirement-analysis"]');
    if (requirementButton) {
      requirementButton.disabled = true;
      requirementButton.textContent = '进入预审...';
      await confirmRequirementAnalysis();
      return;
    }
    await handleResolutionOptionClick(event);
  });
  els.checksView.addEventListener('click', async (event) => {
    const selfCheckButton = event.target.closest('[data-action="run-self-check"]');
    if (selfCheckButton) {
      await runSelfCheck();
      return;
    }
    const validateButton = event.target.closest('[data-action="validate-design"]');
    if (validateButton) {
      await runDesignValidation();
      return;
    }
    await handleResolutionOptionClick(event);
  });
  els.exportLinks?.addEventListener('click', async (event) => {
    const filterButton = event.target.closest('[data-export-format]');
    if (filterButton) {
      await setExportFormat(filterButton.dataset.exportFormat || '');
      return;
    }
    const button = event.target.closest('[data-action="run-cadquery"]');
    if (!button) return;
    await runCadQueryBuild();
  });
  els.exportStlButton?.addEventListener('click', openExportStlDialog);
  els.exportStlDialog?.addEventListener('click', async (event) => {
    if (event.target === els.exportStlDialog || event.target.closest('[data-action="cancel-export-stl"]')) {
      closeExportStlDialog();
      return;
    }
    if (event.target.closest('[data-action="preview-export-path"]')) {
      await chooseExportDirectory();
      return;
    }
    if (event.target.closest('[data-action="confirm-export-stl"]')) {
      await confirmExportStl();
    }
  });
  els.llmStatusButton?.addEventListener('click', openModelSourceDialog);
  els.modelSourceDialog?.addEventListener('click', async (event) => {
    if (event.target === els.modelSourceDialog || event.target.closest('[data-action="close-model-source"]')) {
      closeModelSourceDialog();
      return;
    }
    const item = event.target.closest('[data-model-source-id]');
    if (item) {
      selectModelSourceDraft(item.dataset.modelSourceId || '');
      return;
    }
    if (event.target.closest('[data-action="new-model-source"]')) {
      selectModelSourceDraft('');
      return;
    }
    if (event.target.closest('[data-action="activate-model-source"]')) {
      await activateSelectedModelSource();
      return;
    }
    if (event.target.closest('[data-action="probe-model-source"]')) {
      await probeSelectedModelSource();
    }
  });
  els.modelSourceForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    await saveModelSourceFromForm();
  });
}

async function handlePromptSubmit() {
  const prompt = els.promptInput.value.trim();
  if (!prompt) return;
  els.promptInput.value = '';
  state.taskActive = true;

  if (state.draft?.design_state && !state.artifact && isBuildConfirmationPrompt(prompt)) {
    addMessage('user', '用户确认', prompt);
    await buildConfirmedDesign();
    return;
  }

  const hasExistingContext = Boolean(state.requirementAnalysis || state.draft || state.artifact || (state.taskActive && state.lastPrompt));
  const selectedHardwareEnclosureRequested = state.selectedHardwareIds.size > 0
    && (isSelectedHardwareEnclosurePrompt(prompt) || isGenericEnclosureBuildPrompt(prompt));
  const currentCadQueryCode = state.artifact?.cadquery_code || '';
  const startsNewRequirement = hasExistingContext
    && isNewRequirementPrompt(prompt)
    && !selectedHardwareEnclosureRequested;
  const title = state.artifact?.design_state
    ? '修改意见'
    : startsNewRequirement
      ? '用户需求'
      : state.requirementAnalysis
      ? isRequirementConfirmationPrompt(prompt) ? '确认分析' : '修改需求'
      : hasExistingContext
        ? '补充信息'
        : '用户需求';
  addMessage('user', title, prompt);
  if (startsNewRequirement) {
    state.selectedHardwareIds = new Set();
    state.userAnswers = [];
    state.currentTaskId = '';
    clearSurfaceEngravingContext();
  } else if (selectedHardwareEnclosureRequested) {
    clearSurfaceEngravingContext();
  } else if (hasExistingContext && !isRequirementConfirmationPrompt(prompt) && !selectedHardwareEnclosureRequested) {
    state.userAnswers.push(`${title}：${prompt}`);
  }
  const preparePrompt = startsNewRequirement || selectedHardwareEnclosureRequested
    ? prompt
    : hasExistingContext && state.lastPrompt ? state.lastPrompt : prompt;
  await prepare(preparePrompt, {
    keepUserAnswers: hasExistingContext && !startsNewRequirement,
    currentDesignState: startsNewRequirement ? null : state.artifact?.design_state || state.draft?.design_state,
    currentCadQueryCode: startsNewRequirement ? '' : currentCadQueryCode,
    taskId: startsNewRequirement ? '' : currentTaskId(),
    latestUserMessage: prompt,
    routeAction: selectedHardwareEnclosureRequested ? 'selected_hardware_enclosure' : startsNewRequirement ? 'new_requirement' : '',
    selectedHardwareIds: startsNewRequirement ? [] : undefined,
  });
}

function isConfirmationPrompt(prompt = '') {
  const text = String(prompt).trim().replace(/[。.!！\s]/g, '');
  return [
    '确认',
    '确认方案',
    '确认这个方案',
    '继续',
    '继续建模',
    '继续生成',
    '开始建模',
    '开始生成',
    '生成模型',
    '生成3D',
    '生成3d',
    '确认继续',
    '按这个方案',
    '按这个方案建模',
    '就按这个做',
    '就这样',
    '没问题继续',
    '可以',
  ].includes(text);
}

function isBuildConfirmationPrompt(prompt = '') {
  return isConfirmationPrompt(prompt);
}

function isRequirementConfirmationPrompt(prompt = '') {
  const text = String(prompt).trim().replace(/[。.!！\s]/g, '');
  return [
    '确认',
    '确认分析',
    '认可',
    '认可分析',
    '继续',
    '继续预审',
    '按这个分析',
    '分析正确',
    '没问题',
    '可以',
  ].includes(text);
}

function isSelectedHardwareEnclosurePrompt(prompt = '') {
  const text = String(prompt).trim();
  return /(选定|已选|当前|这些|所选).{0,8}(硬件|模块).{0,16}(盒子|外壳|壳|保护盒)|给.{0,6}(选定|已选|当前|这些|所选).{0,8}(硬件|模块).{0,16}(盒子|外壳|壳|保护盒)|不用管需求|不管需求|不要分析需求|不需要需求|只用.{0,8}(硬件|模块)|selected\s+hardware.*(box|enclosure|case)/i.test(text);
}

function isGenericEnclosureBuildPrompt(prompt = '') {
  const text = String(prompt).trim().replace(/\s+/g, '');
  if (!text || text.length > 24) return false;
  return /^(?:请|帮我)?(?:直接|开始|现在)?(?:做|生成|制作|设计|建模)(?:一个|个|下)?(?:带盖)?(?:盒子|外壳|壳|保护盒)$|^(?:盒子|外壳|壳|保护盒)(?:生成|建模|制作|设计)$|^(?:生成|制作|设计|建模)(?:盒子|外壳|壳|保护盒)$|^(?:make|build|generate|design)(?:a|an)?(?:box|case|enclosure)$/i.test(text);
}

function isNewRequirementPrompt(prompt = '') {
  const text = String(prompt).trim();
  if (!text) return false;
  if (isSelectedHardwareEnclosurePrompt(text)) return false;
  return /(?:新项目|新任务|另一个项目|另外做一个|重新开始一个项目|我要做的(?:是|事)|我想做的(?:是|事)|需求改成|这不是当前模型|不要修改当前模型)/i.test(text);
}

function currentTaskId() {
  return state.currentTaskId || state.artifact?.design_state?.id || '';
}

function activeResolutionOptions() {
  return [
    state.lastNeedsInput?.resolution_options,
    state.requirementAnalysis?.resolution_options,
    state.validationResult?.resolution_options,
    state.draft?.resolution_options,
  ].find((options) => Array.isArray(options) && options.length) || [];
}

function buildConversationContext(source = 'prompt_submit') {
  return {
    workflowStage: state.workflowStage,
    currentStage: state.workflowStage,
    taskId: currentTaskId(),
    hasRequirementAnalysis: Boolean(state.requirementAnalysis),
    hasDraft: Boolean(state.draft?.design_state),
    hasArtifact: Boolean(state.artifact?.design_state),
    hasCurrentDesignState: Boolean(state.artifact?.design_state || state.draft?.design_state),
    latestUserActionSource: source,
  };
}

function isSurfaceEngravingResponse(result = {}) {
  const routeAction = result.conversation_route?.route_action
    || result.conversationRoute?.route_action
    || '';
  return routeAction === 'surface_engraving'
    || result.source === 'llm_surface_engraving'
    || String(result.blocking_reason || '').startsWith('surface_engraving_')
    || Boolean(result.surface_engraving_draft || result.surfaceEngravingDraft);
}

function normalizeSurfaceEngravingTurns(value = []) {
  if (!Array.isArray(value)) return [];
  const turns = [];
  for (const item of value) {
    const content = typeof item === 'string'
      ? item.trim()
      : String(item?.content || item?.message || item?.text || item?.user_message || '').trim();
    if (content && !turns.includes(content)) turns.push(content);
  }
  return turns.slice(-12);
}

function updateSurfaceEngravingContext(result = {}, latestUserMessage = '') {
  const responseDraft = result.surface_engraving_draft || result.surfaceEngravingDraft || null;
  if (responseDraft) state.surfaceEngravingDraft = responseDraft;
  const responseTurns = normalizeSurfaceEngravingTurns(
    result.surface_engraving_turns
      || result.surfaceEngravingTurns
      || responseDraft?.user_turns,
  );
  const accumulatedTurns = responseTurns.length ? responseTurns : state.surfaceEngravingTurns;
  state.surfaceEngravingTurns = normalizeSurfaceEngravingTurns([
    ...accumulatedTurns,
    latestUserMessage,
  ]);
}

function clearSurfaceEngravingContext() {
  state.surfaceEngravingDraft = null;
  state.surfaceEngravingTurns = [];
}

function openNewTaskDialog() {
  els.newTaskDialog?.classList.remove('hidden');
}

function closeNewTaskDialog() {
  els.newTaskDialog?.classList.add('hidden');
}

function resetCurrentTask() {
  clearPendingParameterRegenerate();
  clearModelPreview();
  state.selectedHardwareIds = new Set();
  state.draft = null;
  state.requirementAnalysis = null;
  state.workflowStage = 'idle';
  state.artifact = null;
  state.partialBom = null;
  state.cadqueryBuild = null;
  state.cadqueryAutoBuildPromise = null;
  state.cadqueryPreviewBuildKeys = new Set();
  state.selfCheck = null;
  state.validationResult = null;
  state.isBusy = false;
  state.isCadqueryBuilding = false;
  state.viewerNotice = null;
  state.viewerSourceKey = '';
  state.previewRevision = 0;
  state.activeView = 'preview';
  state.previewMode = 'assembly';
  state.activeHardwareModelType = 'electronic_component';
  state.rightTab = 'bom';
  state.exportFormat = '';
  state.exportResult = null;
  state.exportDirectoryHandle = null;
  state.exportDirectoryName = '';
  state.parameterOverrides = {};
  state.hardwareFaceOverrides = {};
  state.hardwareRotationOverrides = {};
  state.conversationRoute = null;
  state.revisionIntent = null;
  state.userAnswers = [];
  clearSurfaceEngravingContext();
  state.lastPrompt = '';
  state.lastNeedsInput = null;
  state.currentTaskId = '';
  state.taskActive = false;
  state.customHardwarePreview = null;
  state.customHardwarePreviewFailure = null;
  state.customHardwareWorkbenchOpen = false;
  els.promptInput.value = '';
  if (els.customHardwareInput) els.customHardwareInput.value = '';
  if (els.customHardwareName) els.customHardwareName.value = '';
  if (els.customHardwareThumbnail) els.customHardwareThumbnail.value = '';
  setCustomHardwareStatus('');
  els.messages.innerHTML = '';
  document.querySelectorAll('.mode-buttons button').forEach((button) => {
    button.classList.toggle('active', button.dataset.mode === state.previewMode);
  });
  addMessage('agent', '新项目', '请描述新的电子产品或结构需求。');
  renderAll();
}

function clearModelPreview() {
  state.viewerNotice = null;
  state.viewerSourceKey = '';
  state.modelViewerError = null;
  state.modelViewer?.clear?.();
  setModelViewerVisible(false);
  if (els.sceneSvg) {
    els.sceneSvg.style.display = 'none';
    els.sceneSvg.innerHTML = '';
  }
  hideViewerStatus();
}

async function loadHealth() {
  const health = await api('/api/health');
  state.health = health;
  const service = health.service_identity?.project || health.project || 'ZW-CAD-intent';
  const port = health.service_identity?.port || health.port || 5187;
  state.llmConnection = health.llmConnection || state.llmConnection;
  els.sourceStatus.textContent = `${service} : ${port}`;
  renderLlmStatus();
  els.cadqueryStatus.textContent = health.environment?.cadqueryAvailable
    ? 'CadQuery: 可用'
    : 'CadQuery: pending';
}

async function loadModelSources(options = {}) {
  try {
    const result = await api('/api/model-sources');
    applyModelSourcesPayload(result);
    if (options.probe) await probeModelSource('', { automatic: true });
  } catch (error) {
    state.llmConnection = {
      status: 'failed',
      message: error.message,
    };
    renderLlmStatus();
  }
}

async function refreshModelSourcesQuietly() {
  try {
    await loadModelSources();
  } catch {
    // loadModelSources already normalizes connection errors for the status badge.
  }
}

function applyModelSourcesPayload(result = {}) {
  state.modelSources = Array.isArray(result.sources) ? result.sources : [];
  state.activeModelSourceId = result.activeSourceId || result.active_source_id || state.activeModelSourceId;
  if (result.connection) {
    state.llmConnection = result.connection;
    if (result.connection.status === 'connected') {
      state.llmWorkflowFailure = null;
    }
  }
  if (!state.modelSourceDraftId) {
    state.modelSourceDraftId = state.activeModelSourceId || state.modelSources[0]?.id || '';
  }
  renderLlmStatus();
  renderModelSourceDialog();
}

async function probeModelSource(id = '', options = {}) {
  if (!options.automatic) {
    setLlmStatus({
      status: 'checking',
    message: '正在检测 LLM 连接。',
      source_id: id || state.activeModelSourceId,
    });
  }
  const result = await api('/api/model-sources/probe', {
    method: 'POST',
    body: { id },
  });
  applyModelSourcesPayload(result);
  if (result.connection?.status === 'connected') {
    setLlmStatus(result.connection, { workflowFailure: false });
  }
  return result.connection || state.llmConnection;
}

function setLlmStatus(connection = {}, options = {}) {
  state.llmConnection = connection;
  if (options.workflowFailure) {
    state.llmWorkflowFailure = connection;
  } else if (options.workflowFailure === false) {
    state.llmWorkflowFailure = null;
  }
  renderLlmStatus();
}

function renderLlmStatus() {
  if (!els.llmStatusButton) return;
  const connection = state.llmConnection || {};
  const status = connection.status || 'unknown';
  const labels = {
    connected: 'LLM: 已连接',
    failed: 'LLM: 连接失败',
    llm_intent_failed: 'LLM: 调用失败',
    not_configured: 'LLM: 未配置',
    checking: 'LLM: 检测中',
    unknown: 'LLM: 未检测',
  };
  els.llmStatusButton.textContent = labels[status] || labels.unknown;
  els.llmStatusButton.dataset.state = status;
  els.llmStatusButton.title = [
    status === 'connected' ? 'LLM 已连接，只表示模型源探测通过；本轮调用仍可能失败。' : '',
    '点击切换 LLM 模型源',
    connection.model ? `模型：${connection.model}` : '',
    connection.base_url ? `地址：${connection.base_url}` : '',
    connection.message || '',
  ].filter(Boolean).join('\n');
}

function openModelSourceDialog() {
  els.modelSourceDialog?.classList.remove('hidden');
  if (!state.modelSources.length) {
    loadModelSources().catch((error) => setModelSourceStatus(error.message, 'fail'));
  } else {
    renderModelSourceDialog();
  }
}

function closeModelSourceDialog() {
  els.modelSourceDialog?.classList.add('hidden');
}

function renderModelSourceDialog() {
  if (!els.modelSourceList || !els.modelSourceForm) return;
  els.modelSourceList.innerHTML = state.modelSources.map((source) => {
    const active = source.id === state.activeModelSourceId;
    const selected = source.id === state.modelSourceDraftId;
    const status = source.lastProbe?.status || '';
    return `
      <button class="model-source-item ${active ? 'active' : ''}" data-model-source-id="${escapeHtml(source.id)}" type="button" aria-pressed="${selected ? 'true' : 'false'}">
        <strong>${escapeHtml(source.name || source.id)}</strong>
        <span>${escapeHtml(source.model || '')}</span>
        <span>${escapeHtml(status ? `状态：${status}` : '状态：未检测')}</span>
        <span>${source.hasApiKey ? escapeHtml(source.maskedApiKey || '已保存 key') : '未保存 key'}</span>
      </button>
    `;
  }).join('');
  fillModelSourceForm(selectedModelSource());
}

function selectedModelSource() {
  return state.modelSources.find((item) => item.id === state.modelSourceDraftId)
    || state.modelSources.find((item) => item.id === state.activeModelSourceId)
    || state.modelSources[0]
    || null;
}

function selectModelSourceDraft(id) {
  state.modelSourceDraftId = id;
  fillModelSourceForm(selectedModelSource());
  setModelSourceStatus(id ? '' : '正在新增模型源。', '');
  renderModelSourceDialog();
}

function fillModelSourceForm(source) {
  if (!els.modelSourceForm) return;
  els.modelSourceName.value = source?.name || '';
  els.modelSourceBaseUrl.value = source?.baseUrl || 'https://api.openai.com/v1';
  els.modelSourceModel.value = source?.model || 'gpt-5.5';
  els.modelSourceApiKey.value = '';
  els.modelSourceApiKey.placeholder = source?.hasApiKey
    ? `已保存：${source.maskedApiKey || '****'}，留空则保持原密钥`
    : '请输入 API key';
  els.modelSourceEnabled.checked = source?.enabled !== false;
}

async function saveModelSourceFromForm() {
  const body = {
    id: state.modelSourceDraftId || undefined,
    name: els.modelSourceName.value.trim(),
    baseUrl: els.modelSourceBaseUrl.value.trim(),
    model: els.modelSourceModel.value.trim(),
    enabled: els.modelSourceEnabled.checked,
  };
  const apiKey = els.modelSourceApiKey.value.trim();
  if (apiKey) body.apiKey = apiKey;
  setModelSourceStatus('正在保存模型源...', '');
  const result = await api('/api/model-sources', {
    method: 'POST',
    body,
  });
  applyModelSourcesPayload(result);
  state.modelSourceDraftId = result.source?.id || state.modelSourceDraftId;
  setModelSourceStatus('模型源已保存。', 'pass');
  await probeModelSource(state.modelSourceDraftId);
}

async function activateSelectedModelSource() {
  const source = selectedModelSource();
  if (!source) {
    setModelSourceStatus('请先保存一个模型源。', 'fail');
    return;
  }
  setModelSourceStatus('正在切换模型源...', '');
  const result = await api('/api/model-sources/active', {
    method: 'POST',
    body: { id: source.id },
  });
  applyModelSourcesPayload(result);
  setModelSourceStatus('已切换当前模型源。', 'pass');
  await probeModelSource(source.id);
}

async function probeSelectedModelSource() {
  const source = selectedModelSource();
  if (!source) {
    setModelSourceStatus('请先保存一个模型源。', 'fail');
    return;
  }
  setModelSourceStatus('正在测试连接...', '');
  const connection = await probeModelSource(source.id);
  setModelSourceStatus(connection.message || '检测完成。', connection.status === 'connected' ? 'pass' : 'fail');
}

function setModelSourceStatus(message, status) {
  if (!els.modelSourceStatus) return;
  els.modelSourceStatus.textContent = message || '';
  els.modelSourceStatus.className = `model-source-status ${status || ''}`.trim();
}

async function loadHardwareLibrary() {
  const library = await api('/api/hardware/library');
  state.hardware = library.profiles || [];
  state.hardwareSystems = library.hardware_systems || {};
  state.templateProjects = Array.isArray(library.template_projects) ? library.template_projects : [];
  if (!hardwareSystemTabs().some((item) => item.id === state.activeHardwareSystemTab)) {
    state.activeHardwareSystemTab = 'xiao';
  }
  if (state.activeHardwareSystemTab === 'common'
    && !hardwareModelTypeTabs().some((item) => item.id === state.activeHardwareModelType)) {
    state.activeHardwareModelType = 'electronic_component';
  }
  els.hardwareCount.textContent = `${state.hardware.length} 个硬件`;
  renderHardwareSystemTabs();
  renderCategoryFilter();
}

async function prepare(prompt, options = {}) {
  clearPendingParameterRegenerate();
  if (!options.keepUserAnswers) {
    state.userAnswers = [];
    state.hardwareFaceOverrides = {};
    state.hardwareRotationOverrides = {};
  }
  const requestContext = buildConversationContext(options.actionSource || 'prompt_submit');
  const requestRequirementAnalysis = options.currentRequirementAnalysis || state.requirementAnalysis;
  const requestTaskId = options.taskId || currentTaskId();
  const requestStartedAt = state.requirementAnalysis?.task_started_at || state.artifact?.design_state?.result_started_at || '';
  const requestSelectedHardwareIds = Array.isArray(options.selectedHardwareIds)
    ? options.selectedHardwareIds
    : [...state.selectedHardwareIds];
  const requestActiveResolutionOptions = Array.isArray(options.activeResolutionOptions)
    ? options.activeResolutionOptions
    : activeResolutionOptions();
  const preservedArtifact = state.artifact;
  const requestCadQueryCode = options.currentCadQueryCode || preservedArtifact?.cadquery_code || '';
  state.lastPrompt = prompt;
  state.workflowStage = 'analyzing';
  state.artifact = null;
  state.draft = null;
  state.requirementAnalysis = null;
  state.viewerNotice = null;
  state.viewerSourceKey = '';
  state.isCadqueryBuilding = false;
  state.rightTab = 'bom';
  renderAll();
  renderPreview();
  setBusy(true);
  try {
    const result = await api('/api/agent/prepare', {
      method: 'POST',
      body: {
        prompt,
        selectedHardwareIds: requestSelectedHardwareIds,
        customHardwareProfiles: state.customHardwareProfiles,
        parameterOverrides: state.parameterOverrides,
        hardwareFaceOverrides: state.hardwareFaceOverrides,
        hardwareRotationOverrides: state.hardwareRotationOverrides,
        userAnswers: state.userAnswers,
        currentDesignState: options.currentDesignState,
        currentCadQueryCode: requestCadQueryCode,
        currentRequirementAnalysis: requestRequirementAnalysis,
        activeResolutionOptions: requestActiveResolutionOptions,
        lastNeedsInput: state.lastNeedsInput,
        surfaceEngravingDraft: state.surfaceEngravingDraft,
        surfaceEngravingTurns: state.surfaceEngravingTurns,
        projectManifest: preservedArtifact?.project_manifest || preservedArtifact?.design_state?.project_manifest || null,
        projectRevision: preservedArtifact?.project_revision || preservedArtifact?.design_state?.project_revision || null,
        projectSourceHash: preservedArtifact?.project_source_hash || preservedArtifact?.design_state?.project_source_hash || '',
        modelIndex: preservedArtifact?.model_index || preservedArtifact?.design_state?.model_index || null,
        projectMemorySummary: preservedArtifact?.project_memory_summary || preservedArtifact?.design_state?.project_memory_summary || '',
        modelEditHistory: preservedArtifact?.model_edit_history || preservedArtifact?.design_state?.model_edit_history || [],
        conversationContext: requestContext,
        routeAction: options.routeAction || '',
        resolutionOptionId: options.resolutionOptionId || '',
        revisionIntent: options.revisionIntent,
        taskId: requestTaskId,
        taskStartedAt: requestStartedAt,
        latestUserMessage: options.latestUserMessage || '',
        requirementAnalysisConfirmed: options.requirementAnalysisConfirmed === true,
      },
    });
    if (result.status === 'needs_input' && preservedArtifact) {
      state.artifact = preservedArtifact;
    }
    await receiveResult(result, false, {
      latestUserMessage: options.latestUserMessage || '',
    });
  } catch (error) {
    state.workflowStage = 'idle';
    state.isCadqueryBuilding = false;
    if (preservedArtifact) {
      state.artifact = preservedArtifact;
      state.workflowStage = 'review';
    }
    renderConfirmation();
    renderPreview();
    addMessage('agent', '分析失败', error.message);
  } finally {
    await refreshModelSourcesQuietly();
    setBusy(false);
  }
}

async function generate(prompt, options = {}) {
  await prepare(prompt, options);
}

async function confirmRequirementAnalysis() {
  if (!state.requirementAnalysis) return;
  state.workflowStage = 'analyzing';
  const prompt = state.lastPrompt || state.requirementAnalysis.partial_intent?.product_name || '';
  state.viewerNotice = null;
  renderAll();
  setBusy(true);
  try {
    const result = await api('/api/agent/prepare', {
      method: 'POST',
      body: {
        prompt,
        selectedHardwareIds: [...state.selectedHardwareIds],
        customHardwareProfiles: state.customHardwareProfiles,
        parameterOverrides: state.parameterOverrides,
        hardwareFaceOverrides: state.hardwareFaceOverrides,
        hardwareRotationOverrides: state.hardwareRotationOverrides,
        userAnswers: state.userAnswers,
        currentRequirementAnalysis: state.requirementAnalysis,
        conversationContext: buildConversationContext('confirm_requirement_analysis_button'),
        routeAction: 'confirm_requirement_analysis',
        taskId: currentTaskId(),
        taskStartedAt: state.requirementAnalysis?.task_started_at || '',
        latestUserMessage: '',
        requirementAnalysisConfirmed: true,
      },
    });
    await receiveResult(result);
  } catch (error) {
    state.workflowStage = 'requirement_analysis';
    renderAll();
    addMessage('agent', '分析确认失败', error.message);
  } finally {
    await refreshModelSourcesQuietly();
    setBusy(false);
  }
}

async function buildConfirmedDesign() {
  if (!state.draft?.design_state) return;
  collectParameterOverridesFromInputs();
  state.workflowStage = 'building';
  state.viewerNotice = null;
  state.viewerSourceKey = '';
  state.isCadqueryBuilding = true;
  renderAll();
  setBusy(true);
  try {
    const result = await api('/api/design/build', {
      method: 'POST',
      body: {
        prompt: state.lastPrompt || state.draft.intent?.product_name || '',
        draftDesignState: state.draft.design_state,
        customHardwareProfiles: state.customHardwareProfiles,
        parameterOverrides: state.parameterOverrides,
        hardwareFaceOverrides: state.hardwareFaceOverrides,
        hardwareRotationOverrides: state.hardwareRotationOverrides,
        intentAnalysis: state.draft.intent_analysis,
        resolutionOptionRoute: state.draft.resolution_option_route || state.draft.design_state?.resolution_option_route || null,
        ignoredMissingHardwareRequests: state.draft.ignored_missing_hardware_requests || state.draft.design_state?.ignored_missing_hardware_requests || [],
        droppedFunctions: state.draft.dropped_functions || state.draft.design_state?.dropped_functions || [],
        conversationRoute: {
          route_action: 'build_confirmed',
          confidence: 1,
          reason: '用户确认参数草案并开始建模。',
          source: 'frontend_build_button',
        },
        conversationContext: buildConversationContext('build_confirmed_button'),
        routeAction: 'build_confirmed',
        taskId: currentTaskId(),
      },
    });
    await receiveResult(result);
  } catch (error) {
    state.workflowStage = 'confirming';
    state.isCadqueryBuilding = false;
    renderAll();
    addMessage('agent', '建模失败', error.message);
  } finally {
    await refreshModelSourcesQuietly();
    setBusy(false);
  }
}

async function regenerate(options = {}) {
  if (!state.artifact?.design_state) return;
  if (state.isBusy || state.cadqueryAutoBuildPromise || (options.automatic && state.isCadqueryBuilding)) {
    if (options.automatic) scheduleParameterRegenerate();
    return;
  }
  collectParameterOverridesFromInputs();
  state.viewerNotice = null;
  state.viewerSourceKey = '';
  state.isCadqueryBuilding = true;
  renderPreview();
  setBusy(true);
  try {
    const result = await api('/api/design/regenerate', {
      method: 'POST',
      body: {
        currentDesignState: state.artifact.design_state,
        customHardwareProfiles: state.customHardwareProfiles,
        parameterOverrides: state.parameterOverrides,
        hardwareFaceOverrides: state.hardwareFaceOverrides,
        hardwareRotationOverrides: state.hardwareRotationOverrides,
        taskId: currentTaskId(),
      },
    });
    await receiveResult(result, true, { quiet: Boolean(options.automatic) });
  } catch (error) {
    state.isCadqueryBuilding = false;
    renderPreview();
    addMessage('agent', '重生成失败', error.message);
  } finally {
    await refreshModelSourcesQuietly();
    setBusy(false);
  }
}

async function receiveResult(result, regenerated = false, options = {}) {
  const contextTransition = result.context_transition
    || result.conversation_route?.context_transition
    || result.conversationRoute?.context_transition
    || null;
  if (contextTransition?.clear_surface_engraving_draft) {
    clearSurfaceEngravingContext();
    if (String(state.lastNeedsInput?.blocking_reason || '').startsWith('surface_engraving_')) {
      state.lastNeedsInput = null;
    }
  }
  if (result.status === 'deterministic_product') {
    clearSurfaceEngravingContext();
    state.workflowStage = 'deterministic_product';
    state.requirementAnalysis = null;
    state.draft = null;
    state.artifact = null;
    state.lastNeedsInput = result;
    state.isCadqueryBuilding = false;
    state.viewerNotice = null;
    state.partialBom = Array.isArray(result.partial_bom) ? result.partial_bom : [];
    state.conversationRoute = result.conversation_route || null;
    state.revisionIntent = result.revision_intent || null;
    state.currentTaskId = result.taskId || result.task_id || state.currentTaskId;
    state.taskActive = true;
    for (const item of result.partial_bom || []) state.selectedHardwareIds.add(item.hardware_id);
    addMessage(
      'agent',
      result.title || '内置确定性产品',
      result.message || '',
      deterministicProductBullets(result),
      renderDeterministicProductDetails(result),
    );
    renderAll();
    return;
  }
  if (result.status === 'requirement_analysis') {
    clearSurfaceEngravingContext();
    state.workflowStage = 'requirement_analysis';
    state.requirementAnalysis = result;
    state.currentTaskId = result.taskId || result.task_id || state.currentTaskId;
    state.taskActive = true;
    state.draft = null;
    state.artifact = null;
    state.lastNeedsInput = null;
    state.isCadqueryBuilding = false;
    state.viewerNotice = null;
    state.partialBom = Array.isArray(result.partial_bom) ? result.partial_bom : [];
    state.conversationRoute = result.conversation_route || null;
    state.revisionIntent = result.revision_intent || null;
    for (const item of result.partial_bom || []) state.selectedHardwareIds.add(item.hardware_id);
    const intentSource = result.intent_analysis?.source || 'model_intent';
    addMessage(
      'agent',
      result.title || '需求分析确认',
      result.message || '',
      requirementAnalysisBullets(result.requirement_analysis_report),
      renderRequirementAnalysisDetails(result.requirement_analysis_report),
    );
    renderAll();
    return;
  }
  if (result.status === 'needs_input') {
    if (isSurfaceEngravingResponse(result)) {
      updateSurfaceEngravingContext(result, options.latestUserMessage || '');
    } else {
      clearSurfaceEngravingContext();
    }
    state.workflowStage = 'blocked';
    state.requirementAnalysis = null;
    state.draft = null;
    state.isCadqueryBuilding = false;
    state.viewerNotice = null;
    state.lastNeedsInput = result;
    state.partialBom = Array.isArray(result.partial_bom) ? result.partial_bom : [];
    state.conversationRoute = result.conversation_route || null;
    state.revisionIntent = result.revision_intent || null;
    if (String(result.blocking_reason || '').startsWith('llm_')) {
      setLlmStatus({
        status: result.blocking_reason === 'llm_unavailable' ? 'not_configured' : 'llm_intent_failed',
        message: result.message || '',
        model: result.model_error?.model || '',
        base_url: result.model_error?.base_url || '',
        source_id: result.model_error?.source_id || '',
      }, { workflowFailure: true });
    }
    addMessage('agent', result.title || '需要补充信息', result.message || '', [], renderNeedsInputDetails(result));
    renderNeedsInput(result);
    renderBomSummary();
    renderRightPane();
    renderConfirmation();
    renderPreview();
    return;
  }
  if (result.status === 'confirmation') {
    clearSurfaceEngravingContext();
    state.workflowStage = 'confirming';
    state.requirementAnalysis = null;
    state.draft = result;
    state.artifact = null;
    state.lastNeedsInput = null;
    state.llmWorkflowFailure = null;
    state.partialBom = Array.isArray(result.bom) ? result.bom : [];
    state.conversationRoute = result.conversation_route || null;
    state.revisionIntent = result.revision_intent || null;
    state.currentTaskId = result.taskId || result.task_id || state.currentTaskId || result.design_state?.id || '';
    state.taskActive = true;
    state.validationResult = null;
    state.cadqueryBuild = null;
    state.cadqueryPreviewBuildKeys = new Set();
    state.exportResult = null;
    state.exportFormat = '';
    state.rightTab = 'bom';
    state.hardwareFaceOverrides = { ...(result.design_state?.hardware_face_overrides || state.hardwareFaceOverrides) };
    state.hardwareRotationOverrides = { ...(result.design_state?.hardware_rotation_overrides || state.hardwareRotationOverrides) };
    syncSelectedHardwareFromResult(result, { replaceWhenMissingIgnored: true });
    state.parameterOverrides = flattenParameters(result.parameters);
    const intentSource = result.intent_analysis?.source || 'model_intent';
    addMessage('agent', result.title || '参数确认', result.message || '', [
      `BOM：${(result.bom || []).map((item) => item.name).join('、')}`,
      summarizeFunctionVerification(result.function_verification_report),
      `预审：${summarizeChecks(result.checks)}`,
    ].filter(Boolean));
    renderAll();
    return;
  }
  if (result.status !== 'artifact') {
    state.isCadqueryBuilding = false;
    state.viewerNotice = null;
    addMessage('agent', '未知响应', JSON.stringify(result, null, 2));
    renderPreview();
    return;
  }
  state.workflowStage = 'review';
  clearSurfaceEngravingContext();
  state.requirementAnalysis = null;
  state.draft = null;
  state.artifact = result;
  bumpPreviewRevision();
  state.currentTaskId = result.taskId || result.task_id || state.currentTaskId;
  state.taskActive = true;
  state.activeView = 'preview';
  state.rightTab = isStandaloneStructuralArtifact(result) ? 'bom' : 'gui';
  state.lastNeedsInput = null;
  state.llmWorkflowFailure = null;
  state.partialBom = null;
  state.cadqueryBuild = null;
  state.cadqueryAutoBuildPromise = null;
  state.cadqueryPreviewBuildKeys = new Set();
  state.isCadqueryBuilding = true;
  state.viewerNotice = null;
  state.viewerSourceKey = '';
  state.validationResult = null;
  state.exportResult = null;
  state.exportFormat = '';
  state.conversationRoute = result.conversation_route || null;
  state.revisionIntent = result.revision_intent || null;
  state.hardwareFaceOverrides = { ...(result.design_state?.hardware_face_overrides || state.hardwareFaceOverrides) };
  state.hardwareRotationOverrides = { ...(result.design_state?.hardware_rotation_overrides || state.hardwareRotationOverrides) };
  syncSelectedHardwareFromResult(result, { replaceWhenMissingIgnored: true });
  state.parameterOverrides = flattenParameters(result.parameters);
  if (!options.quiet) {
    if (result.source === 'llm_model_edit' || result.model_edit_plan) {
      const modelEditRouteAction = result.revision_intent?.route_action
        || result.conversation_route?.route_action
        || '';
      addMessage('agent', result.title || '模型修改已完成', result.message || '', [
        result.project_revision ? `项目修订：${result.project_revision}` : '',
        result.model_edit_plan?.risk_level ? `影响级别：${modelEditRiskLabel(result.model_edit_plan.risk_level)}` : '',
        modelEditRouteAction === 'cancel_model_edit'
          ? '待确认修改已取消，当前项目源码未改变。'
          : modelEditRouteAction === 'undo_model_edit'
            ? '已生成撤销修订；公共模板和其他项目未改变。'
            : '修改已写入当前项目副本，公共模板和其他项目未改变。',
      ].filter(Boolean));
    } else if (isStandaloneStructuralArtifact(result)) {
      addMessage('agent', regenerated ? '结构件项目已更新' : result.title || '结构件模型已生成', result.message || '', [
        `结构件：${(result.bom || []).map((item) => item.name || item.hardware_id).join('、')}`,
        '当前只生成结构件，不包含主控或带盖盒体。',
        '多件模型按 15 mm 间距并排预览；需要个性化修改时可直接描述尺寸、孔槽或圆角。',
      ]);
    } else if (isDeterministicTemplateArtifact(result)) {
      const message = deterministicTemplateUserMessage(result, { regenerated });
        addMessage('agent', message.title, message.body, message.bullets);
      } else {
        const intentSource = result.intent_analysis?.source || 'model_intent';
        addMessage('agent', regenerated ? '已按参数重生成' : result.title, result.message, [
        `Intent：${intentSource}`,
        `BOM：${result.bom.map((item) => item.name).join('、')}`,
        summarizeFunctionVerification(result.function_verification_report),
        `校验：${summarizeChecks(result.checks)}`,
        '请拖动模型检查结构，满意后导出 STL；如果要优化，请直接输入修改建议。',
        ].filter(Boolean));
      }
      if (Array.isArray(result.surface_engravings) && result.surface_engravings.length) {
        addMessage('agent', '刻字已应用', surfaceEngravingUserMessage(result));
      } else if (result.conversation_route?.route_action === 'surface_engraving') {
        addMessage('agent', '刻字已更新', '当前模型的表面刻字已按本轮操作更新。');
      }
  }
  renderAll();
  if ((result.source === 'llm_model_edit' || result.model_edit_plan)
    && (result.exports || []).some((item) => item.id === 'cadquery_stl')) {
    state.isCadqueryBuilding = false;
    renderExportLinks();
    renderPreview();
    return;
  }
  await runCadQueryBuild({ automatic: true, quiet: true });
}

function modelEditRiskLabel(value = '') {
  return { low: '低', medium: '中', high: '高' }[String(value).toLowerCase()] || String(value);
}

async function handleResolutionOptionClick(event) {
  const button = event.target.closest('[data-resolution-option-id]');
  if (!button) return;
  const option = findResolutionOption(button.dataset.resolutionOptionId);
  if (!option) return;
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = '处理中...';
  const optionText = `${option.label || option.id || '处理选项'}：${option.description || ''}`.trim();
  addMessage('user', '选择处理方案', optionText);
  addMessage('agent', '已收到选择', '我会按这个处理方案更新当前任务，并从受影响步骤继续。');
  try {
    await applyResolutionOption(option);
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

function findResolutionOption(optionId) {
  const optionLists = [
    state.lastNeedsInput?.resolution_options,
    state.requirementAnalysis?.resolution_options,
    state.validationResult?.resolution_options,
    state.draft?.resolution_options,
  ];
  for (const options of optionLists) {
    if (!Array.isArray(options)) continue;
    const option = options.find((item) => item.id === optionId);
    if (option) return option;
  }
  return null;
}

function syncSelectedHardwareFromResult(result = {}, options = {}) {
  const bom = Array.isArray(result.bom) ? result.bom : [];
  const ignoredMissing = Array.isArray(result.ignored_missing_hardware_requests) && result.ignored_missing_hardware_requests.length
    || Array.isArray(result.design_state?.ignored_missing_hardware_requests) && result.design_state.ignored_missing_hardware_requests.length;
  if (options.replaceWhenMissingIgnored && ignoredMissing) {
    state.selectedHardwareIds = new Set(bom.map((item) => item.hardware_id).filter(Boolean));
    renderDrawerState();
    renderHardwareList();
    return;
  }
  for (const item of bom) {
    if (item.hardware_id) state.selectedHardwareIds.add(item.hardware_id);
  }
}

async function applyResolutionOption(option) {
  const action = option.action || '';
  const fromValidation = (state.validationResult?.resolution_options || [])
    .some((item) => item.id === option.id);
  if (action === 'provide_custom_hardware_profile' || action === 'complete_hardware_profile') {
    state.hardwareDrawerOpen = true;
    state.activeHardwareSystemTab = 'user_custom';
    state.customHardwareWorkbenchOpen = false;
    renderDrawerState();
    renderHardwareSystemTabs();
    renderCategoryFilter();
    renderHardwareList();
    addMessage(
      'agent',
      '等待自定义硬件',
      '请在底部硬件库抽屉中点击“自定义硬件”，用自然语言描述缺失硬件并预览确认。确认后会写入用户自定义硬件库。',
    );
    return;
  }

  if (action === 'confirm_requirement_analysis') {
    await confirmRequirementAnalysis();
    return;
  }

  if (fromValidation && (action === 'increase_box_size' || action === 'adjust_parameter') && state.artifact?.design_state) {
    Object.assign(state.parameterOverrides, normalizeResolutionParameterOverrides(option.parameter_overrides));
    await regenerate();
    return;
  }

  const prompt = state.lastPrompt || els.promptInput.value.trim();
  if (!prompt) {
    addMessage('agent', '缺少原始需求', '请重新输入产品需求后再选择处理方式。');
    return;
  }

  const answer = `用户选择 resolution option：${option.id || action}。${option.description || option.label || ''}`;
  state.userAnswers.push(answer);

  if (action === 'increase_box_size' || action === 'adjust_parameter') {
    Object.assign(state.parameterOverrides, normalizeResolutionParameterOverrides(option.parameter_overrides));
  }

  if (action === 'change_mounting_face') {
    addMessage('agent', '需要指定安装面', '请在输入框说明要把哪个硬件移到哪个面，例如“把蜂鸣器移到右侧”。');
    return;
  }

  if (action === 'remove_or_replace_hardware') {
    addMessage('agent', '需要选择硬件', '请在硬件库抽屉移除或替换具体硬件，或在输入框说明要删掉哪个硬件。');
    return;
  }

  if (action === 'remove_or_replace_feature' || action === 'ignore_missing_hardware_continue') {
    state.userAnswers.push('用户选择忽略缺失硬件或砍掉硬件库暂不支持的功能。');
  }

  await prepare(prompt, {
    keepUserAnswers: true,
    currentDesignState: state.draft?.design_state || state.artifact?.design_state,
    taskId: currentTaskId(),
    resolutionOptionId: option.id || '',
    activeResolutionOptions: activeResolutionOptions(),
    actionSource: 'resolution_option_button',
  });
}

function normalizeResolutionParameterOverrides(overrides = {}) {
  const result = {};
  if (!overrides || typeof overrides !== 'object') return result;
  for (const [key, value] of Object.entries(overrides)) {
    const number = Number(value);
    if (Number.isFinite(number)) result[key] = number;
  }
  return result;
}

function renderAll() {
  renderDrawerState();
  renderHardwareSystemTabs();
  renderCategoryFilter();
  renderPreviewModeButtons();
  renderBomSummary();
  renderRightPane();
  renderHardwareList();
  renderCustomHardwareList();
  renderParameters();
  renderConfirmation();
  renderPreview();
  renderCode();
  renderChecks();
  renderExportLinks();
  renderActiveView();
  els.regenerateButton.disabled = !state.artifact && !state.draft && !state.requirementAnalysis;
  els.regenerateButton.textContent = state.requirementAnalysis
    ? '重新分析'
    : state.draft && !state.artifact ? '重新预审' : '重生成';
}

function designModeOf(value = null) {
  return String(value?.design_mode || value?.designMode || value?.design_state?.design_mode || '').trim();
}

function isStandaloneStructuralArtifact(value = state.artifact) {
  return ['standalone_structural_parts', 'structural_part_project'].includes(designModeOf(value));
}

function isTemplateCaseArtifact(value = state.artifact) {
  return designModeOf(value) === 'template_case'
    || value?.template_case === true
    || value?.design_state?.template_case === true;
}

function selectedHardwareAreStandaloneStructuralParts() {
  if (!state.selectedHardwareIds.size) return false;
  return [...state.selectedHardwareIds].every((id) => {
    const profile = findHardwareProfile(id);
    return profile?.hardware_system === 'common' && hardwareModelTypeOf(profile) === 'structural_part';
  });
}

function structuralPrintableParts(value = state.artifact) {
  if (!isStandaloneStructuralArtifact(value)) return [];
  if (Array.isArray(value?.printable_parts)) return value.printable_parts;
  return Array.isArray(value?.design_state?.printable_parts) ? value.design_state.printable_parts : [];
}

function templateCasePrintableParts(value = state.artifact) {
  if (!isTemplateCaseArtifact(value)) return [];
  if (Array.isArray(value?.printable_parts)) return value.printable_parts;
  return Array.isArray(value?.design_state?.printable_parts) ? value.design_state.printable_parts : [];
}

function previewModes() {
  if (isTemplateCaseArtifact(state.artifact || state.draft)) {
    return [
      ['assembly', '整体'],
      ...templateCasePrintableParts(state.artifact || state.draft).map((part) => [
        `template_part:${part.id}`,
        part.label || part.name || part.id || '打印件',
      ]),
    ];
  }
  if (!isStandaloneStructuralArtifact(state.artifact || state.draft)) {
    return [
      ['assembly', '整体'],
      ['exploded', '爆炸'],
      ['lid', '上盖'],
      ['base', '底壳'],
      ['hardware', '硬件'],
    ];
  }
  return [
    ['assembly', '整体'],
    ...structuralPrintableParts(state.artifact || state.draft).map((part) => [
      `structural_part:${part.id}`,
      part.label || part.name || part.id || '结构件',
    ]),
  ];
}

function renderPreviewModeButtons() {
  if (!els.modeButtons) return;
  const modes = previewModes();
  if (!modes.some(([id]) => id === state.previewMode)) state.previewMode = 'assembly';
  els.modeButtons.innerHTML = modes.map(([id, label]) => `
    <button class="${id === state.previewMode ? 'active' : ''}" data-mode="${escapeHtml(id)}" type="button">
      ${escapeHtml(label)}
    </button>
  `).join('');
}

function renderRightPane() {
  if (!els.rightBomPanel) return;
  els.appShell.querySelector('.params-pane')?.setAttribute('data-right-tab', state.rightTab);
  els.bomTabButton?.classList.toggle('active', state.rightTab === 'bom');
  els.guiTabButton?.classList.toggle('active', state.rightTab === 'gui');
  const bom = state.artifact?.bom || state.draft?.bom || state.partialBom || [];
  const structural = isStandaloneStructuralArtifact(state.artifact || state.draft);
  if (els.bomTabButton) els.bomTabButton.textContent = structural ? '结构件' : 'BOM';
  if (els.guiTabButton) els.guiTabButton.textContent = structural ? '修改说明' : '模型参数';
  if (!bom.length) {
    els.rightBomPanel.innerHTML = `
      <div class="bom-summary-head">
        <strong>${structural ? '结构件清单' : '硬件 BOM'}</strong>
        <span>${structural ? '生成后显示结构件' : '分析后显示硬件清单'}</span>
      </div>
      <div class="bom-items">
        <span class="bom-empty">暂无 BOM</span>
      </div>
    `;
    return;
  }
  els.rightBomPanel.innerHTML = `
    <div class="bom-summary-head">
      <strong>${structural ? '结构件清单' : state.artifact ? '最终 BOM' : state.requirementAnalysis ? '分析 BOM' : '待确认 BOM'}</strong>
      <span>${bom.length} 项${structural ? '结构件' : '硬件'}</span>
    </div>
    <div class="bom-items">
      ${bom.map((item) => renderBomChip({
        name: item.name || item.hardware_id,
        role: item.role || 'required',
        quantity: item.quantity || 1,
        status: item.profile_status || item.required_or_optional || '',
      })).join('')}
    </div>
  `;
}

function renderConfirmation() {
  if (!els.confirmationView) return;
  const draft = state.draft;
  const needsInput = state.lastNeedsInput;
  const requirementAnalysis = state.requirementAnalysis;
  if (state.workflowStage === 'analyzing' && !draft) {
    els.confirmationView.classList.remove('hidden');
    els.confirmationView.innerHTML = renderPrecheckProgress(selectedHardwareAreStandaloneStructuralParts());
    return;
  }
  if (!draft && !needsInput && !requirementAnalysis) {
    els.confirmationView.classList.add('hidden');
    els.confirmationView.innerHTML = '';
    return;
  }
  els.confirmationView.classList.remove('hidden');
  if (requirementAnalysis && !draft) {
    els.confirmationView.innerHTML = renderRequirementAnalysisConfirmation(requirementAnalysis);
    return;
  }
  if (needsInput && !draft) {
    els.confirmationView.innerHTML = renderNeedsInputConfirmation(needsInput);
    return;
  }
  els.confirmationView.innerHTML = renderDraftConfirmation(draft);
}

function renderPrecheckProgress(structural = false) {
  const steps = structural
    ? ['确认结构件', '读取结构母版', '校验 CadQuery 契约', '规划并排预览', '准备项目源码副本']
    : ['理解需求', '匹配硬件库/BOM', '读取硬件 profile', '估算盒体尺寸', '预审布局/开孔/干涉'];
  const title = structural ? '正在检查结构件母版' : '正在进行第一步预审';
  const description = structural
    ? '系统正在校验通用件母版和独立导出条件，完成后会进入结构件确认。'
    : '系统正在把你的需求转成硬件 BOM 和可行布局，完成后会进入参数确认。';
  const note = structural
    ? '独立结构件流程不选择主控、不计算盒体，也不推导真实装配关系。'
    : '此阶段只做需求理解、硬件匹配和可行性预审，不会开始真实建模。';
  return `
    <div class="confirmation-card precheck-progress" aria-live="polite">
      <div class="precheck-progress-head">
        <span class="precheck-spinner" aria-hidden="true"></span>
        <div>
          <h2>${escapeHtml(title)}</h2>
          <p>${escapeHtml(description)}</p>
        </div>
      </div>
      <ol class="precheck-steps" aria-label="预审步骤">
        ${steps.map((step, index) => `
          <li class="precheck-step">
            <span class="precheck-step-index">${index + 1}</span>
            <span>${escapeHtml(step)}</span>
          </li>
        `).join('')}
      </ol>
      <p class="precheck-note">${escapeHtml(note)}</p>
    </div>
  `;
}

function renderNeedsInputConfirmation(result = {}) {
  if (result.status === 'deterministic_product') {
    return renderDeterministicProductConfirmation(result);
  }
  const bom = Array.isArray(result.partial_bom) ? result.partial_bom : [];
  const missing = Array.isArray(result.missing_hardware_requests) ? result.missing_hardware_requests : [];
  return `
    <div class="confirmation-card">
      <h2>${escapeHtml(result.title || '需要确认后继续')}</h2>
      <div class="confirmation-summary">
        <div>${escapeHtml(result.message || '')}</div>
        ${bom.length ? `<div><strong>可实现：</strong>${escapeHtml(bom.map((item) => item.name || item.hardware_id).join('、'))}</div>` : ''}
        ${missing.length ? `<div><strong>暂不可实现：</strong>${escapeHtml(missing.map((item) => item.label || item.role).join('、'))}</div>` : ''}
        ${renderResolutionActions(result.resolution_options || [])}
      </div>
    </div>
  `;
}

function renderDeterministicProductConfirmation(result = {}) {
  const product = result.deterministic_product || {};
  const bom = Array.isArray(result.partial_bom) ? result.partial_bom : [];
  return `
    <div class="confirmation-card requirement-analysis-card">
      <h2>${escapeHtml(result.title || '内置确定性产品')}</h2>
      <div class="confirmation-summary">
        <div>${escapeHtml(result.message || '')}</div>
        <div><strong>内置产品：</strong>${escapeHtml(product.product_name || product.name || '')}</div>
        <div><strong>硬件体系：</strong>${escapeHtml(product.hardware_system || '')}</div>
        <div><strong>固定 BOM：</strong>${escapeHtml(bom.map((item) => item.name || item.hardware_id).join('、') || '待补充')}</div>
        <div><strong>下一步：</strong>${escapeHtml(result.next_step || '后续补齐专用模型后继续。')}</div>
      </div>
    </div>
  `;
}

function renderRequirementAnalysisConfirmation(result = {}) {
  const report = result.requirement_analysis_report || {};
  const functions = Array.isArray(report.functions) ? report.functions : [];
  const missing = Array.isArray(report.missing_hardware_requests) ? report.missing_hardware_requests : [];
  const extraOptions = (result.resolution_options || [])
    .filter((option) => !['confirm_requirement_analysis', 'revise_requirement_analysis'].includes(option.id));
  return `
    <div class="confirmation-card requirement-analysis-card">
      <h2>${escapeHtml(result.title || '需求分析确认')}</h2>
      <div class="confirmation-summary">
        <div>${escapeHtml(report.user_message || result.message || '')}</div>
        <div><strong>功能：</strong>${escapeHtml(functions.map((item) => item.name).filter(Boolean).join('、') || '暂无')}</div>
        <div><strong>库内可做：</strong>${escapeHtml((report.available_functions || []).join('、') || '暂无')}</div>
        <div><strong>库内缺失：</strong>${escapeHtml(missing.map((item) => `${item.function || item.role} -> ${item.label || item.role}`).join('；') || '无')}</div>
      </div>
      <div class="confirmation-actions">
        <button class="primary" type="button" data-action="confirm-requirement-analysis">确认分析</button>
        <button type="button" data-action="edit-description">修改需求</button>
      </div>
      ${renderResolutionActions(extraOptions)}
    </div>
  `;
}

function deterministicProductBullets(result = {}) {
  const product = result.deterministic_product || {};
  const bom = Array.isArray(result.partial_bom) ? result.partial_bom : [];
  return [
    `内置产品：${product.product_name || product.name || '植物看护仪'}`,
    `硬件体系：${product.hardware_system || '未指定'}`,
    `固定 BOM：${bom.map((item) => item.name || item.hardware_id).filter(Boolean).join('、') || '待补充'}`,
    result.next_step || '',
  ].filter(Boolean);
}

function renderDeterministicProductDetails(result = {}) {
  const product = result.deterministic_product || {};
  const bom = Array.isArray(result.partial_bom) ? result.partial_bom : [];
  const assumptions = Array.isArray(result.assumptions) ? result.assumptions : [];
  return `
    <section class="needs-input-section requirement-analysis-details">
      <h2>内置确定性产品</h2>
      <dl>
        <div><dt>产品</dt><dd>${escapeHtml(product.product_name || product.name || '')}</dd></div>
        <div><dt>分支</dt><dd>${escapeHtml(product.id || '')}</dd></div>
        <div><dt>硬件体系</dt><dd>${escapeHtml(product.hardware_system || '')}</dd></div>
        <div><dt>命中原因</dt><dd>${escapeHtml(product.reason || '')}</dd></div>
      </dl>
      ${bom.length ? `
        <h3>固定 BOM</h3>
        <ul>${bom.map((item) => `<li>${escapeHtml(item.function || item.role || '')}: ${escapeHtml(item.name || item.hardware_id || '')}</li>`).join('')}</ul>
      ` : ''}
      ${assumptions.length ? `
        <h3>本次假设</h3>
        <ul>${assumptions.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
      ` : ''}
    </section>
  `;
}

function requirementAnalysisBullets(report = {}) {
  if (!report || typeof report !== 'object') return [];
  const functions = Array.isArray(report.functions) ? report.functions : [];
  const missing = Array.isArray(report.missing_hardware_requests) ? report.missing_hardware_requests : [];
  return [
    `功能：${functions.map((item) => item.name).filter(Boolean).join('、') || '暂无'}`,
    `库内已有：${(report.matched_hardware || []).map((item) => item.name || item.hardware_id).filter(Boolean).join('、') || '暂无'}`,
    `库内缺失：${missing.map((item) => `${item.function || item.role} -> ${item.label || item.role}`).join('；') || '无'}`,
    report.next_step || '',
  ].filter(Boolean);
}

function renderRequirementAnalysisDetails(report = {}) {
  if (!report || typeof report !== 'object') return '';
  const functions = Array.isArray(report.functions) ? report.functions : [];
  const hardware = Array.isArray(report.matched_hardware) ? report.matched_hardware : [];
  const missing = Array.isArray(report.missing_hardware_requests) ? report.missing_hardware_requests : [];
  return `
    <section class="needs-input-section requirement-analysis-details">
      <h2>需求-功能-选型分析</h2>
      <dl>
        <div><dt>产品</dt><dd>${escapeHtml(report.product_name || '')}</dd></div>
        <div><dt>分析来源</dt><dd>${escapeHtml(`${report.intent_source || ''} / ${report.model_status || ''}`)}</dd></div>
      </dl>
      ${functions.length ? `
        <h3>功能与硬件</h3>
        <ul>${functions.map((item) => `
          <li>${escapeHtml(item.name || '')}: ${escapeHtml(item.required_hardware || item.required_role || '')} / ${escapeHtml(item.library_status || '')}</li>
        `).join('')}</ul>
      ` : ''}
      ${hardware.length ? `
        <h3>库内已有</h3>
        <ul>${hardware.map((item) => `<li>${escapeHtml(item.function || item.role || '')}: ${escapeHtml(item.name || item.hardware_id || '')}</li>`).join('')}</ul>
      ` : ''}
      ${missing.length ? `
        <h3>库内缺失</h3>
        <ul>${missing.map((item) => `<li>${escapeHtml(item.function || item.role || '')}: ${escapeHtml(item.label || item.role || '')}</li>`).join('')}</ul>
      ` : ''}
    </section>
  `;
}

function renderDraftConfirmation(draft = {}) {
  if (isStandaloneStructuralArtifact(draft)) return renderStructuralDraftConfirmation(draft);
  const design = draft.design_state || {};
  const enclosure = design.enclosure_parameters || {};
  const inner = enclosure.inner_box_size || {};
  const outer = enclosure.outer_box_size || {};
  const transforms = design.layout_plan?.hardware_transforms || [];
  const validationStatus = summarizeChecks(draft.checks || []);
  return `
    <div class="confirmation-card">
      <h2>${escapeHtml(draft.title || '参数确认')}</h2>
      <div class="confirmation-summary">
        <div>${escapeHtml(draft.message || '')}</div>
        <div><strong>内腔尺寸：</strong>${formatSize(inner)} mm</div>
        <div><strong>外形尺寸：</strong>${formatSize(outer)} mm</div>
        <div><strong>预审：</strong>${escapeHtml(validationStatus || '暂无')}</div>
        <div class="confirmation-pills">
          ${transforms.map((item) => `
            <span class="confirmation-pill">${escapeHtml(item.name || item.hardware_id)} / ${escapeHtml(faceLabel(item.mount_surface || item.target_face))}</span>
          `).join('')}
        </div>
      </div>
      <div class="confirmation-actions">
        <button class="primary" type="button" data-action="build-confirmed">继续建模</button>
        <button type="button" data-action="edit-description">编辑描述</button>
      </div>
    </div>
  `;
}

function renderStructuralDraftConfirmation(draft = {}) {
  const design = draft.design_state || {};
  const parts = Array.isArray(design.structural_parts) ? design.structural_parts : [];
  const gap = Number(design.layout_plan?.gap_mm || 15);
  return `
    <div class="confirmation-card">
      <h2>${escapeHtml(draft.title || '结构件参数确认')}</h2>
      <div class="confirmation-summary">
        <div>${escapeHtml(draft.message || '')}</div>
        <div><strong>结构件：</strong>${escapeHtml(parts.map((item) => item.name || item.id).join('、') || '暂无')}</div>
        <div><strong>预览排列：</strong>沿 X 轴并排，间距 ${gap} mm；不表示真实装配关系。</div>
        <div><strong>控制器与盒体：</strong>不添加主控，不生成带盖盒体。</div>
        <div><strong>预审：</strong>${escapeHtml(summarizeChecks(draft.checks || []) || '暂无')}</div>
      </div>
      <div class="confirmation-actions">
        <button class="primary" type="button" data-action="build-confirmed">继续建模</button>
        <button type="button" data-action="edit-description">编辑描述</button>
      </div>
    </div>
  `;
}

function renderResolutionActions(options = []) {
  if (!Array.isArray(options) || !options.length) return '';
  return `
    <div class="confirmation-actions">
      ${options.map((option) => `
        <button
          type="button"
          data-resolution-option-id="${escapeHtml(option.id || '')}"
          data-resolution-action="${escapeHtml(option.action || '')}"
        >${escapeHtml(option.label || option.id || '选择')}</button>
      `).join('')}
    </div>
  `;
}

function formatSize(size = {}) {
  return `${Number(size.length_x || 0)} x ${Number(size.width_y || 0)} x ${Number(size.height_z || 0)}`;
}

function toggleHardwareDrawer() {
  state.hardwareDrawerOpen = !state.hardwareDrawerOpen;
  renderDrawerState();
}

function renderDrawerState() {
  els.appShell.classList.toggle('drawer-open', state.hardwareDrawerOpen);
  els.hardwareDrawer.classList.toggle('collapsed', !state.hardwareDrawerOpen);
  els.drawerToggle.setAttribute('aria-expanded', state.hardwareDrawerOpen ? 'true' : 'false');
  els.drawerToggle.textContent = state.hardwareDrawerOpen ? '收起硬件库' : '打开硬件库';
  els.selectedHardwareCount.textContent = `已选 ${state.selectedHardwareIds.size} 个`;
}

function hardwareSystemTabs() {
  return [
    {
      id: 'xiao',
      name: state.hardwareSystems?.xiao?.name || 'XIAO',
      count: countHardwareBySystem('xiao'),
    },
    {
      id: 'mpython',
      name: state.hardwareSystems?.mpython?.name || '掌控板',
      count: countHardwareBySystem('mpython'),
    },
    {
      id: 'unihiker',
      name: state.hardwareSystems?.unihiker?.name || '行空板',
      count: countHardwareBySystem('unihiker'),
    },
    {
      id: 'common',
      name: state.hardwareSystems?.common?.name || '通用件',
      count: countHardwareBySystem('common'),
    },
    {
      id: 'user_custom',
      name: state.hardwareSystems?.user_custom?.name || '用户自定义硬件',
      count: countHardwareBySystem('user_custom'),
    },
    {
      id: TEMPLATE_PROJECT_SYSTEM_ID,
      name: '模板项目',
      count: state.templateProjects.length,
    },
  ];
}

function hardwareModelTypeTabs() {
  return [
    { id: 'electronic_component', label: '电子元器件' },
    { id: 'structural_part', label: '结构件' },
  ];
}

function hardwareModelTypeOf(profile = {}) {
  const explicit = String(profile.model_type || '').trim().toLowerCase();
  if (explicit) return explicit;
  if (profile.custom_hardware_type === 'structural' || profile.category === 'structural_part') {
    return 'structural_part';
  }
  return 'electronic_component';
}

function hardwareModelTypeLabel(profile = {}) {
  return hardwareModelTypeOf(profile) === 'structural_part' ? '结构件' : '电子元器件';
}

function hardwareModelQualityLabel(profile = {}) {
  const quality = profile.model_quality;
  if (!quality || typeof quality !== 'object') return '';
  if (quality.grade === 'non_manufacturing' || quality.simplified === true) return '简化母版 · 非制造级';
  if (quality.manufacturing_ready === false) return '原型母版 · 制造前需复核';
  return '';
}

function countHardwareBySystem(systemId) {
  return state.hardware.filter((item) => hardwareSystemOf(item) === systemId).length;
}

function hardwareSystemOf(profile = {}) {
  return String(profile.hardware_system || 'common').trim().toLowerCase() || 'common';
}

function renderHardwareSystemTabs() {
  if (!els.hardwareSystemTabs) return;
  const tabs = hardwareSystemTabs();
  els.hardwareSystemTabs.innerHTML = tabs.map((tab) => `
    <button
      type="button"
      class="hardware-system-tab ${state.activeHardwareSystemTab === tab.id ? 'active' : ''}"
      data-hardware-system-tab="${escapeHtml(tab.id)}"
      aria-pressed="${state.activeHardwareSystemTab === tab.id ? 'true' : 'false'}"
    >
      <span>${escapeHtml(tab.name)}</span>
      <em>${tab.count}</em>
    </button>
  `).join('');
}

function hardwareForActiveSystem() {
  return state.hardware.filter((item) => hardwareSystemOf(item) === state.activeHardwareSystemTab);
}

function renderCategoryFilter() {
  if (!els.categoryFilter) return;
  if (state.activeHardwareSystemTab === TEMPLATE_PROJECT_SYSTEM_ID) {
    els.categoryFilter.innerHTML = '<option value="">模板项目</option>';
    els.categoryFilter.value = '';
    els.categoryFilter.disabled = true;
    return;
  }
  els.categoryFilter.disabled = false;
  const previous = els.categoryFilter.value;
  const activeProfiles = state.activeHardwareSystemTab === 'common'
    ? hardwareForActiveSystem().filter((item) => hardwareModelTypeOf(item) === state.activeHardwareModelType)
    : hardwareForActiveSystem();
  const categories = [...new Set(activeProfiles.map((item) => item.category).filter(Boolean))].sort();
  els.categoryFilter.innerHTML = '<option value="">全部类别</option>' + categories
    .map((category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`)
    .join('');
  els.categoryFilter.value = categories.includes(previous) ? previous : '';
}

function setPreviewZoom(value) {
  state.previewZoom = Math.min(2.2, Math.max(0.45, Number(value) || 1));
  els.zoomLabel.textContent = `${Math.round(state.previewZoom * 100)}%`;
  state.modelViewer?.setZoom(state.previewZoom);
  renderPreview();
}

function renderActiveView() {
  document.querySelectorAll('.segmented button').forEach((button) => {
    button.classList.toggle('active', button.dataset.view === state.activeView);
  });
  els.previewView.classList.toggle('hidden', state.activeView !== 'preview');
  els.codeView.classList.toggle('hidden', state.activeView !== 'code');
  els.checksView.classList.toggle('hidden', state.activeView !== 'checks');
}

function renderSvgPreview() {
  const svg = els.sceneSvg;
  if (isTemplateCaseArtifact(state.artifact || state.draft)) {
    renderTemplateCaseSvgPreview(svg, state.artifact || state.draft);
    return;
  }
  if (isStandaloneStructuralArtifact(state.artifact || state.draft)) {
    renderStructuralSvgPreview(svg, state.artifact || state.draft);
    return;
  }
  const scene = (state.artifact?.preview_assets || state.draft?.preview_assets || []).find((item) => item.type === 'layout_scene');
  svg.innerHTML = '';
  els.zoomLabel.textContent = `${Math.round(state.previewZoom * 100)}%`;
  if (!scene) {
    svg.innerHTML = emptySvg('等待生成模型');
    return;
  }
  const outer = scene.enclosure.outer_box_size;
  const bounds = scenePreviewBounds(scene, state.previewMode);
  const scale = Math.min(756 / bounds.width, 456 / bounds.height) * state.previewZoom;
  els.zoomLabel.textContent = `${Math.round(state.previewZoom * 100)}%`;
  const cx = 410 - bounds.center_x * scale;
  const cy = 260 + bounds.center_y * scale;
  const ox = outer.length_x * scale;
  const oy = outer.width_y * scale;

  addSvgRect(svg, cx - ox / 2, cy - oy / 2, ox, oy, 8, '#fefefe', '#26343d', 2);
  addSvgText(svg, cx - ox / 2 + 10, cy - oy / 2 + 20, `${outer.length_x} x ${outer.width_y} x ${outer.height_z} mm`, 'svg-label');

  if (['assembly', 'exploded', 'base'].includes(state.previewMode)) {
    for (const boss of scene.enclosure.screw_bosses) {
      addSvgCircle(svg, cx + boss.x * scale, cy - boss.y * scale, 5, '#dde5ea', '#5b6b76');
    }
  }

  for (const hw of visibleHardwareForMode(scene.hardware, state.previewMode)) {
    const offset = hardwareLayerOffset(hw, state.previewMode, outer, scale);
    drawHardware(svg, hw, cx + offset.x, cy + offset.y, scale, {
      dashed: state.previewMode === 'assembly' && hw.surface === 'base_floor',
      ghost: state.previewMode === 'assembly' && hw.surface === 'base_floor',
    });
  }

  if (['assembly', 'exploded'].includes(state.previewMode)) {
    for (const mount of scene.mounts || []) {
      drawMount(svg, mount, cx, cy, scale);
    }
  }

  if (['lid', 'assembly', 'exploded'].includes(state.previewMode)) {
    for (const opening of scene.openings) {
      const owner = scene.hardware.find((hw) => hw.id === opening.hardware_id);
      const offset = owner ? hardwareLayerOffset(owner, state.previewMode, outer, scale) : { x: 0, y: 0 };
      drawOpening(svg, opening, cx + offset.x, cy + offset.y, scale);
    }
  }

  if (state.previewMode === 'exploded') {
    addSvgText(svg, 28, 42, '爆炸图模式：仅抬高上盖，底壳和硬件保持原位', 'svg-label');
  }
}

function renderTemplateCaseSvgPreview(svg, value = {}) {
  const scene = (value?.preview_assets || value?.design_state?.preview_assets || [])
    .find((item) => item?.type === 'layout_scene' && item?.scene_kind === 'template_case');
  const allParts = Array.isArray(scene?.parts) ? scene.parts : [];
  const selectedPartId = String(state.previewMode || '').startsWith('template_part:')
    ? String(state.previewMode).slice('template_part:'.length)
    : '';
  const parts = selectedPartId
    ? allParts.filter((item) => item.id === selectedPartId)
    : allParts;
  svg.innerHTML = '';
  els.zoomLabel.textContent = `${Math.round(state.previewZoom * 100)}%`;
  if (!parts.length) {
    svg.innerHTML = emptySvg('等待生成模板案例');
    return;
  }

  const projected = parts.map((part, index) => {
    const dimensions = part.bbox_mm || part.dimensions_mm || {};
    const center = part.center_mm || part.center || {};
    return {
      part,
      length: Math.max(1, Number(dimensions.length_x || dimensions.length || 20)),
      width: Math.max(1, Number(dimensions.width_y || dimensions.width || 20)),
      x: Number.isFinite(Number(center.x)) ? Number(center.x) : index * 30,
      y: Number.isFinite(Number(center.y)) ? Number(center.y) : 0,
    };
  });
  const minX = Math.min(...projected.map((item) => item.x - item.length / 2));
  const maxX = Math.max(...projected.map((item) => item.x + item.length / 2));
  const minY = Math.min(...projected.map((item) => item.y - item.width / 2));
  const maxY = Math.max(...projected.map((item) => item.y + item.width / 2));
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const scale = Math.min(700 / spanX, 360 / spanY) * state.previewZoom;
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;

  for (const item of projected) {
    const reference = item.part.printable === false || item.part.kind === 'reference';
    const x = 410 + (item.x - centerX - item.length / 2) * scale;
    const y = 260 - (item.y - centerY + item.width / 2) * scale;
    addSvgRect(
      svg,
      x,
      y,
      item.length * scale,
      item.width * scale,
      6,
      reference ? '#eef2f4' : '#d9e7ee',
      reference ? '#7b8992' : '#304f5e',
      2,
      { dashed: reference, ghost: reference },
    );
    addSvgText(svg, x + 6, y + 18, item.part.label || item.part.name || item.part.id || '部件', 'svg-label');
  }
  addSvgText(svg, 28, 42, selectedPartId ? '当前显示单个可打印部件。' : '实线为可打印部件，虚线为硬件参考；整体场景不作为打印件导出。', 'svg-label');
}

function scenePreviewBounds(scene = {}, mode = 'assembly') {
  const outer = scene.enclosure?.outer_box_size || {};
  let minX = -Number(outer.length_x || 1) / 2;
  let maxX = Number(outer.length_x || 1) / 2;
  let minY = -Number(outer.width_y || 1) / 2;
  let maxY = Number(outer.width_y || 1) / 2;
  const includePointBox = (center = {}, size = {}) => {
    const x = Number(center.x || 0);
    const y = Number(center.y || 0);
    const width = Math.max(1, Number(size.length_x || size.width || 1));
    const height = Math.max(1, Number(size.width_y || size.height || 1));
    minX = Math.min(minX, x - width / 2);
    maxX = Math.max(maxX, x + width / 2);
    minY = Math.min(minY, y - height / 2);
    maxY = Math.max(maxY, y + height / 2);
  };

  for (const item of visibleHardwareForMode(scene.hardware || [], mode)) {
    includePointBox(item.center, item.size || item.dimensions_mm || {});
  }
  if (['lid', 'assembly', 'exploded'].includes(mode)) {
    for (const opening of scene.openings || []) {
      includePointBox(opening.center, openingPreviewSize(opening));
    }
  }
  if (['assembly', 'exploded'].includes(mode)) {
    for (const mount of scene.mounts || []) {
      includePointBox(mount.center, mount.size_mm || {});
    }
  }
  const padding = 12;
  minX -= padding;
  maxX += padding;
  minY -= padding;
  maxY += padding;
  return {
    min_x: minX,
    max_x: maxX,
    min_y: minY,
    max_y: maxY,
    width: Math.max(1, maxX - minX),
    height: Math.max(1, maxY - minY),
    center_x: (minX + maxX) / 2,
    center_y: (minY + maxY) / 2,
  };
}

function renderStructuralSvgPreview(svg, value = {}) {
  const items = Array.isArray(value?.structural_parts)
    ? value.structural_parts
    : Array.isArray(value?.design_state?.structural_parts)
      ? value.design_state.structural_parts
      : [];
  svg.innerHTML = '';
  els.zoomLabel.textContent = `${Math.round(state.previewZoom * 100)}%`;
  if (!items.length) {
    svg.innerHTML = emptySvg('等待生成结构件模型');
    return;
  }
  const gap = 15;
  const sizes = items.map((item) => {
    const d = item.dimensions_mm || item.size_mm || {};
    return {
      item,
      length: Math.max(1, Number(d.length_x || d.length || 20)),
      width: Math.max(1, Number(d.width_y || d.width || 20)),
    };
  });
  const totalLength = sizes.reduce((sum, item) => sum + item.length, 0) + gap * Math.max(0, sizes.length - 1);
  const maxWidth = Math.max(...sizes.map((item) => item.width), 1);
  const scale = Math.min(700 / totalLength, 360 / maxWidth) * state.previewZoom;
  let cursor = 410 - totalLength * scale / 2;
  for (const { item, length, width } of sizes) {
    const x = cursor;
    const y = 260 - width * scale / 2;
    addSvgRect(svg, x, y, length * scale, width * scale, 7, '#e8eef2', '#405764', 2);
    addSvgText(svg, x + 6, y + 18, item.name || item.label || item.id || '结构件', 'svg-label');
    cursor += (length + gap) * scale;
  }
  addSvgText(svg, 28, 42, '结构件按 15 mm 间距并排，仅用于预览，不表示装配关系。', 'svg-label');
}

function renderPreview() {
  if (!previewModes().some(([id]) => id === state.previewMode)) {
    state.previewMode = 'assembly';
  }
  els.zoomLabel.textContent = `${Math.round(state.previewZoom * 100)}%`;
  state.modelViewer?.setZoom(state.previewZoom);
  if (els.sceneSvg) {
    els.sceneSvg.style.display = 'none';
  }

  if (state.isCadqueryBuilding) {
    if (isTemplateCaseArtifact(state.artifact || state.draft) && els.sceneSvg) {
      state.modelViewer?.clear?.();
      state.viewerSourceKey = '';
      setModelViewerVisible(false);
      els.sceneSvg.style.display = 'block';
      renderSvgPreview();
    }
    setViewerStatus('thinking', '正在生成真实 CadQuery 三维模型，完成后会自动显示。', { thinking: true });
    return;
  }

  if (state.requirementAnalysis && !state.draft && !state.artifact) {
    state.modelViewer?.clear?.();
    state.viewerSourceKey = '';
    setModelViewerVisible(false);
    if (els.sceneSvg) {
      els.sceneSvg.style.display = 'block';
      els.sceneSvg.innerHTML = emptySvg('请先确认需求分析');
    }
    hideViewerStatus();
    return;
  }

  if (state.lastNeedsInput?.status === 'deterministic_product' && !state.draft && !state.artifact) {
    state.modelViewer?.clear?.();
    state.viewerSourceKey = '';
    setModelViewerVisible(false);
    if (els.sceneSvg) {
      els.sceneSvg.style.display = 'block';
      els.sceneSvg.innerHTML = emptySvg('已命中内置模型');
    }
    hideViewerStatus();
    return;
  }

  if (state.customHardwarePreviewFailure && !state.draft && !state.artifact) {
    state.modelViewer?.clear?.();
    state.viewerSourceKey = '';
    setModelViewerVisible(false);
    setViewerStatus(
      '自定义硬件预览未生成',
      customHardwarePreviewFailureMessage(state.customHardwarePreviewFailure),
    );
    return;
  }

  if (state.draft && !state.artifact) {
    state.modelViewer?.clear?.();
    state.viewerSourceKey = '';
    setModelViewerVisible(false);
    if (els.sceneSvg) {
      els.sceneSvg.style.display = 'block';
    }
    renderSvgPreview();
    hideViewerStatus();
    return;
  }

  if (isTemplateCaseArtifact(state.artifact) && !selectViewerSource(state.previewMode)) {
    state.modelViewer?.clear?.();
    state.viewerSourceKey = '';
    setModelViewerVisible(false);
    if (els.sceneSvg) {
      els.sceneSvg.style.display = 'block';
      renderSvgPreview();
    }
    hideViewerStatus();
    return;
  }

  if (state.modelViewerError) {
    setViewerStatus('3D 查看器未就绪', state.modelViewerError);
    return;
  }

  if (!state.modelViewer) {
    setViewerStatus('3D 查看器加载中', '正在载入本地 Three.js 模型查看器。', { thinking: true });
    return;
  }

  if (shouldRefreshCadqueryPreview(state.previewMode)) {
    const key = cadqueryPreviewBuildKey(state.previewMode);
    state.cadqueryPreviewBuildKeys.add(key);
    runCadQueryBuild({ automatic: true, quiet: true });
    setViewerStatus('生成真实 CadQuery 模型', '正在补充真实硬件/爆炸视图导出，完成后会自动刷新。', { thinking: true });
    return;
  }

  const source = selectViewerSource(state.previewMode);
  if (source) {
    setModelViewerVisible(true);
    const sourceKey = `${source.mode}:${source.format}:${source.url}`;
    if (state.viewerSourceKey === sourceKey) {
      if (state.viewerNotice) {
        setViewerStatus(state.viewerNotice.title, state.viewerNotice.body, state.viewerNotice.options || {});
      }
      return;
    }

    state.viewerSourceKey = sourceKey;
    setViewerStatus(viewerLoadingTitle(source), source.label || source.url, { thinking: true });
    state.modelViewer.load(source).catch((error) => {
      state.viewerSourceKey = '';
      setViewerStatus('模型加载失败', error instanceof Error ? error.message : String(error));
    });
    return;
  }

  state.viewerSourceKey = '';
  state.modelViewer?.clear?.();
  setModelViewerVisible(false);
  if (state.viewerNotice) {
    setViewerStatus(state.viewerNotice.title, state.viewerNotice.body, state.viewerNotice.options || {});
    return;
  }
  setViewerStatus(
    state.artifact ? '暂无真实 3D 模型' : '等待生成模型',
    state.artifact ? '当前模式没有可用的真实 CadQuery STL 导出；请检查 CadQuery 生成和导出报告。' : '提交需求后会在这里显示可旋转的 3D 模型。',
  );
}

function isDeterministicTemplateArtifact(result = {}) {
  return result?.source === 'deterministic_product_template'
    || result?.intent_analysis?.source === 'deterministic_product_template';
}

function deterministicTemplateUserMessage(result = {}, { regenerated = false } = {}) {
  const productName = deterministicProductDisplayName(result);
  return {
    title: regenerated ? '模型已按修改更新' : `${productName}模型已生成`,
    body: deterministicTemplateFriendlyBody(result),
    bullets: [
      '请拖动模型检查结构，满意后导出 STL；如果要优化，请直接输入修改建议。',
    ],
  };
}

const SURFACE_ENGRAVING_OVERRIDE_WARNING_ID = 'surface_engraving_original_feature_intersection_override';
const SURFACE_ENGRAVING_OVERRIDE_WARNING_MESSAGE = '已按你的明确确认强制应用刻字；文字可能被边界裁断或影响现有孔位。';

function surfaceEngravingOverrideRecords(...values) {
  const records = [];
  const seen = new Set();
  const roots = [];
  const addRoot = (value) => {
    if (!isPlainObject(value) || roots.includes(value)) return;
    roots.push(value);
    for (const nested of [value.artifact, value.result, value.design_state, value.designState]) {
      if (isPlainObject(nested) && !roots.includes(nested)) roots.push(nested);
    }
  };
  values.forEach(addRoot);

  const firstText = (...items) => items
    .find((item) => item !== undefined && item !== null && String(item).trim())
    ?.toString()
    .trim() || '';
  const firstNumber = (...items) => {
    const value = items.find((item) => Number.isFinite(Number(item)));
    return value === undefined ? null : Number(value);
  };
  const addRecord = (marker, context = {}, explicit = false) => {
    if (!isPlainObject(marker)) return;
    const code = firstText(marker.code, marker.id, marker.warning_id, marker.warningId).toLowerCase();
    const isOverride = marker.allow_original_feature_intersection === true
      || (explicit && marker.applied !== false)
      || (marker.applied === true && code.includes('original_feature_intersection'));
    if (!isOverride) return;
    const record = {
      engraving_id: firstText(
        marker.engraving_id,
        marker.engravingId,
        context.engraving_id,
        context.engravingId,
        context.id,
        marker.id,
      ),
      surface_id: firstText(marker.surface_id, marker.surfaceId, context.surface_id, context.surfaceId),
      surface_label: firstText(marker.surface_label, marker.surfaceLabel, context.surface_label, context.surfaceLabel),
      source_hash: firstText(marker.source_hash, marker.sourceHash, context.source_hash, context.sourceHash),
      reference_intersection_ratio: firstNumber(
        marker.reference_intersection_ratio,
        context.reference_intersection_ratio,
      ),
      intersection_ratio: firstNumber(
        marker.intersection_ratio,
        marker.current_intersection_ratio,
        context.intersection_ratio,
        context.current_intersection_ratio,
      ),
    };
    const key = [record.engraving_id, record.surface_id, record.source_hash].join('|') || 'override';
    if (seen.has(key)) return;
    seen.add(key);
    records.push(record);
  };

  for (const root of roots) {
    const engravingLists = [
      root.surface_engravings,
      root.surfaceEngravings,
      root.design_state?.surface_engravings,
      root.designState?.surface_engravings,
    ];
    for (const list of engravingLists) {
      if (!Array.isArray(list)) continue;
      for (const item of list) {
        if (isPlainObject(item) && item.allow_original_feature_intersection === true) {
          addRecord(item, item, true);
        }
      }
    }

    for (const marker of [root.original_feature_intersection_override, root.originalFeatureIntersectionOverride]) {
      addRecord(marker, root, true);
    }

    const preflights = [
      root.surface_engraving_preflight,
      root.surfaceEngravingPreflight,
      root.preflight,
      root.design_state?.surface_engraving_preflight,
      root.designState?.surface_engraving_preflight,
    ];
    for (const preflight of preflights) {
      if (!isPlainObject(preflight)) continue;
      for (const marker of [preflight.original_feature_intersection_override, preflight.originalFeatureIntersectionOverride]) {
        addRecord(marker, preflight, true);
      }
      if (Array.isArray(preflight.report)) {
        for (const report of preflight.report) {
          if (!isPlainObject(report)) continue;
          for (const marker of [report.original_feature_intersection_override, report.originalFeatureIntersectionOverride]) {
            addRecord(marker, report, true);
          }
          if (report.allow_original_feature_intersection === true) addRecord(report, report, true);
          if (Array.isArray(report.warnings)) {
            for (const warning of report.warnings) {
              if (!isPlainObject(warning)) continue;
              const code = firstText(warning.code, warning.id, warning.warning_id, warning.warningId).toLowerCase();
              const message = firstText(warning.message);
              if ((warning.applied === true && code.includes('original_feature_intersection'))
                || message.includes('文字可能被边界裁断')) {
                addRecord(warning, report, true);
              }
            }
          }
        }
      }
    }
  }
  return records;
}

function surfaceEngravingOverrideWarningMessage(...values) {
  const records = surfaceEngravingOverrideRecords(...values);
  if (!records.length) return '';
  const labels = [...new Set(records
    .map((item) => item.surface_label || item.surface_id)
    .filter(Boolean))];
  return `${SURFACE_ENGRAVING_OVERRIDE_WARNING_MESSAGE}${labels.length ? `涉及目标面：${labels.join('、')}。` : ''}`;
}

function surfaceEngravingUserMessage(result = {}) {
  const items = Array.isArray(result.surface_engravings) ? result.surface_engravings : [];
  if (!items.length) return '已删除全部模型表面刻字。';
  const message = `已应用 ${items.length} 条凹刻：${items.map((item) => {
    const lines = Array.isArray(item.lines) && item.lines.length ? item.lines : [item.text || ''];
    const content = lines.length > 1 ? `${lines.length} 行：${lines.join(' / ')}` : lines[0];
    return `${content}（字体高度 ${item.font_height_mm || '?'}mm，深度 0.6mm）`;
  }).join('、')}。真实模型构建完成后可在预览中检查效果。`;
  const warning = surfaceEngravingOverrideWarningMessage(result);
  return warning ? `${message}\n\n注意：${warning}` : message;
}

function deterministicProductDisplayName(result = {}) {
  const product = result.deterministic_product || {};
  const id = product.id || result.template_id || '';
  if (id === 'unihiker_photo_album' || result.template_id === 'unihiker_photo_album_v1') return '行空板相册';
  if (id === 'unihiker_plant_caregiver' || result.template_id === 'unihiker_smart_watering_system_v1') return '行空板植物养护系统';
  if (id === 'xiao_smart_pendant' || result.template_id === 'xiao_smart_pendant_v1') return 'XIAO 智能项链';
  return product.product_name || product.name || result.title || '模型';
}

function deterministicTemplateFriendlyBody(result = {}) {
  if (result.template_id === 'unihiker_photo_album_v1') {
    return '检测到适合行空板相册的成型设计方案，已为你调用对应的结构参数并生成模型。';
  }
  if (result.template_id === 'unihiker_smart_watering_system_v1') {
    return '检测到社区中存在植物养护系统的相似作品，正在调用合适的设计参数并生成模型。';
  }
  return '检测到已有相似的设计方案，已为你调用合适的设计参数并生成模型。';
}

function selectViewerSource(mode = 'assembly') {
  return selectViewerSourceFromExports(state.artifact?.exports || [], mode, {
    cacheKey: state.previewRevision ? String(state.previewRevision) : '',
    printableParts: isTemplateCaseArtifact(state.artifact)
      ? templateCasePrintableParts(state.artifact)
      : structuralPrintableParts(state.artifact),
  });
}

function hasUsableCustomHardwarePreview(artifact = null) {
  return Array.isArray(artifact?.exports)
    && artifact.exports.some((item) => item?.id === 'cadquery_stl' && item.url && item.status !== 'failed');
}

function customHardwarePreviewFailureMessage(result = {}) {
  const details = [
    result.message,
    result.blocking_reason ? `原因：${result.blocking_reason}` : '',
    ...(Array.isArray(result.missing_fields) ? result.missing_fields : []),
  ].filter(Boolean);
  return details.join(' | ') || '没有可加载的 CadQuery STL 导出，请检查自定义硬件描述或 CadQuery 运行环境。';
}

function bumpPreviewRevision() {
  state.previewRevision += 1;
  state.viewerSourceKey = '';
}

function shouldRefreshCadqueryPreview(mode = 'assembly') {
  if (!state.artifact || state.isCadqueryBuilding || state.cadqueryAutoBuildPromise) return false;
  if (!state.health?.environment?.cadqueryAvailable) return false;
  if (!['hardware', 'exploded'].includes(mode)) return false;
  const exports = state.artifact.exports || [];
  const hasHardware = exports.some((item) => item.id === 'cadquery_hardware_stl' && isUsableViewerExport(item));
  const hasBase = exports.some((item) => item.id === 'cadquery_base_stl' && isUsableViewerExport(item));
  const hasLid = exports.some((item) => item.id === 'cadquery_lid_stl' && isUsableViewerExport(item));
  const missingForMode = mode === 'hardware'
    ? !hasHardware
    : !(hasBase && hasLid && hasHardware);
  if (!missingForMode) return false;
  return !state.cadqueryPreviewBuildKeys.has(cadqueryPreviewBuildKey(mode));
}

function cadqueryPreviewBuildKey(mode = 'assembly') {
  return `${state.artifact?.design_state?.id || 'artifact'}:${mode}`;
}

function isUsableViewerExport(item = {}) {
  return Boolean(item?.url)
    && !['pending', 'pending_missing_cadquery', 'not_generated_yet', 'failed', 'failed_write'].includes(item.status);
}

function viewerLoadingTitle(source = {}) {
  if (isRealCadQuerySource(source)) return '加载真实 CadQuery 模型';
  return '加载模型';
}

function handleModelViewerStatus(event = {}) {
  const statusAction = viewerStatusActionForModelEvent(event, {
    viewerNotice: state.viewerNotice,
    isCadqueryBuilding: state.isCadqueryBuilding,
  });
  if (statusAction.action === 'hide') {
    hideViewerStatus();
  } else if (statusAction.action === 'show_notice') {
    setViewerStatus(statusAction.notice.title, statusAction.notice.body, statusAction.notice.options || {});
  } else if (statusAction.action === 'show_error') {
    setViewerStatus(statusAction.title, statusAction.body);
  } else if (statusAction.action === 'show_loading') {
    setViewerStatus(statusAction.title, statusAction.body, { thinking: statusAction.thinking });
  }
}

function setViewerStatus(title, body = '', options = {}) {
  if (!els.viewerStatus) return;
  els.viewerStatus.classList.remove('hidden');
  if (options.thinking) {
    els.viewerStatusTitle.innerHTML = `${escapeHtml(title)}<span class="thinking-dots" aria-hidden="true"><i>.</i><i>.</i><i>.</i></span>`;
  } else {
    els.viewerStatusTitle.textContent = title;
  }
  els.viewerStatusBody.textContent = body || '';
}

function hideViewerStatus() {
  els.viewerStatus?.classList.add('hidden');
}

function setModelViewerVisible(visible) {
  if (!els.modelViewer) return;
  els.modelViewer.classList.toggle('hidden', !visible);
}

function renderCode() {
  els.codeView.textContent = state.artifact?.cadquery_code || '生成后这里会显示后端固定程序输出的 CadQuery 代码文本。';
}

function renderChecks() {
  const validation = state.validationResult;
  const checks = [...(validation?.checks || state.artifact?.checks || [])];
  const exportReportCheck = buildExportReportCheck(validation?.export_report);
  if (exportReportCheck) checks.push(exportReportCheck);
  const warnings = validation
    ? [...collectArtifactWarnings(state.artifact), ...(validation.warnings || [])]
    : collectArtifactWarnings(state.artifact);
  const surfaceOverrideWarnings = buildSurfaceEngravingOverrideWarnings(
    state.artifact,
    validation,
    state.cadqueryBuild,
  );
  if (surfaceOverrideWarnings.length) {
    const retainedWarnings = warnings.filter((item) => !isSurfaceEngravingOverrideWarning(item));
    warnings.splice(0, warnings.length, ...retainedWarnings, ...surfaceOverrideWarnings);
  }
  checks.push(...buildWarningCheckItems(warnings, checks));
  const cadqueryBuildCheck = buildCadQueryBuildCheck(state.cadqueryBuild);
  if (cadqueryBuildCheck) checks.push(cadqueryBuildCheck);
  const controls = renderValidationControls(validation);
  const diagnostics = [
    renderHealthContent(state.health),
    renderSelfCheckContent(state.selfCheck),
    renderGenerationTraceContent(state.artifact?.generation_trace || state.artifact?.design_state?.generation_trace || state.lastNeedsInput?.generation_trace),
  ].join('');
  if (!checks.length && diagnostics) {
    els.checksView.innerHTML = `${controls}${diagnostics}<div class="check-item pending"><strong>暂无校验</strong><p>生成模型后会显示完整校验报告。</p></div>`;
    return;
  }
  if (!checks.length) {
    els.checksView.innerHTML = `${controls}<div class="check-item pending"><strong>暂无校验</strong><p>生成模型后会显示校验报告。</p></div>`;
    return;
  }
  els.checksView.innerHTML = controls + diagnostics + checks.map((check) => `
    <div class="check-item ${escapeHtml(check.status)}">
      <strong>${escapeHtml(check.label || check.id)}：${escapeHtml(check.status)}</strong>
      <p>${escapeHtml(check.message || '')}</p>
      ${renderCheckDetails(check)}
    </div>
  `).join('') + renderValidationResolutionOptions(validation?.resolution_options || []);
}

function renderValidationControls(validation) {
  const statusText = validation?.validation_status
    ? `最新校验：${validation.validation_status}`
    : '当前 artifact 校验';
  return `
    <div class="check-actions">
      <button type="button" data-action="run-self-check">运行自检</button>
      ${state.artifact?.design_state ? '<button type="button" data-action="validate-design">重新校验</button>' : ''}
      <span>${escapeHtml(statusText)}</span>
    </div>
  `;
}

function buildExportReportCheck(report) {
  if (!report || typeof report !== 'object') return null;
  const failed = Number(report.failed_count || 0);
  const pending = Number(report.pending_count || 0);
  const unavailable = Number(report.unavailable_count || 0);
  const status = failed ? 'fail' : pending ? 'pending' : unavailable ? 'warn' : 'pass';
  return {
    id: 'export_report',
    label: '导出报告',
    status,
    message: `导出项 ${report.total_count || 0} 个，可下载 ${report.available_count || 0} 个，pending ${pending} 个。`,
    details: Array.isArray(report.items) ? report.items : [],
  };
}

function renderValidationResolutionOptions(options = []) {
  if (!Array.isArray(options) || !options.length) return '';
  return `
    <section class="needs-input-section">
      <h2>可选处理</h2>
      <ul>
        ${options.map((option) => `
          <li class="resolution-option">
            <strong>${escapeHtml(option.label || option.id || '处理选项')}${option.recommended ? '（推荐）' : ''}</strong>
            <p>${escapeHtml(option.description || '')}</p>
            ${renderParameterOverrideHint(option.parameter_overrides)}
            <button type="button" data-resolution-option-id="${escapeHtml(option.id || '')}">选择</button>
          </li>
        `).join('')}
      </ul>
    </section>
  `;
}

function renderParameterOverrideHint(overrides = {}) {
  if (!overrides || typeof overrides !== 'object' || !Object.keys(overrides).length) return '';
  const text = Object.entries(overrides)
    .map(([key, value]) => `${key}: ${value}`)
    .join('，');
  return `<p>建议参数：${escapeHtml(text)}</p>`;
}

async function runDesignValidation() {
  if (!state.artifact?.design_state) return;
  setBusy(true);
  try {
    const result = await api('/api/design/validate', {
      method: 'POST',
      body: {
        currentDesignState: state.artifact.design_state,
        cadquery_code: state.artifact.cadquery_code,
        artifact: state.artifact,
      },
    });
    state.validationResult = result;
    addMessage('agent', '重新校验', `校验状态：${result.validation_status || result.status}`);
  } catch (error) {
    state.validationResult = {
      status: 'validation',
      validation_status: 'fail',
      checks: [
        {
          id: 'validation_request_failed',
          label: '重新校验请求',
          status: 'fail',
          message: error.message,
        },
      ],
      warnings: [],
    };
  } finally {
    setBusy(false);
    renderChecks();
  }
}

async function runSelfCheck() {
  setBusy(true);
  try {
    const result = await api('/api/self-check', {
      method: 'POST',
      body: {
        useModel: true,
        runCadQuery: false,
      },
    });
    state.selfCheck = result;
    state.activeView = 'checks';
    addMessage('agent', 'AI 自检', `overall_status: ${result.overall_status || result.status}`);
  } catch (error) {
    state.selfCheck = {
      status: 'self_check',
      overall_status: 'fail',
      probes: [
        {
          id: 'self_check_request_failed',
          status: 'fail',
          message: error.message,
        },
      ],
      recommendations: ['检查后端服务是否仍在运行，或刷新页面后重试。'],
    };
  } finally {
    setBusy(false);
    renderChecks();
    renderActiveView();
  }
}

function renderCheckDetails(check) {
  if (check?.id === 'mesh_validation' || check?.id === 'printability_basic') {
    const meshDetails = renderMeshCheckDetails(check.details);
    if (meshDetails) return meshDetails;
  }
  const lines = summarizeCheckDetails(check.details);
  if (!lines.length) return '';
  return `<ul class="check-details">${lines.map((line) => `<li>${escapeHtml(line)}</li>`).join('')}</ul>`;
}

function renderMeshCheckDetails(details) {
  if (!details || typeof details !== 'object') return '';
  const checks = Array.isArray(details.checks)
    ? details.checks
    : Array.isArray(details.risk_checks)
      ? details.risk_checks
      : Array.isArray(details.subchecks)
        ? details.subchecks.filter((item) => item.id === 'real_mesh_validation')
        : [];
  const lines = [];
  if (details.mesh_validation_status) lines.push(`mesh: ${details.mesh_validation_status}`);
  if (Array.isArray(details.checked_parts) && details.checked_parts.length) lines.push(`parts: ${details.checked_parts.join(', ')}`);
  for (const item of checks.slice(0, 5)) {
    lines.push(`${item.part_id || item.id || 'mesh'} / ${item.id || 'check'}: ${item.status || 'pending'}`);
  }
  if (!lines.length) return '';
  return `<ul class="check-details">${lines.map((line) => `<li>${escapeHtml(line)}</li>`).join('')}</ul>`;
}

function collectArtifactWarnings(artifact) {
  const warnings = [];
  const seen = new Set();
  for (const list of [artifact?.warnings, artifact?.design_state?.warnings]) {
    if (!Array.isArray(list)) continue;
    for (const warning of list) {
      if (!warning || typeof warning !== 'object') continue;
      const key = `${warning.id || ''}|${warning.message || ''}`;
      if (seen.has(key)) continue;
      seen.add(key);
      warnings.push(warning);
    }
  }
  return warnings;
}

function buildSurfaceEngravingOverrideWarnings(...values) {
  const records = surfaceEngravingOverrideRecords(...values);
  if (!records.length) return [];
  return [{
    id: SURFACE_ENGRAVING_OVERRIDE_WARNING_ID,
    label: '强制刻字风险',
    status: 'warn',
    message: surfaceEngravingOverrideWarningMessage(...values),
    details: {
      message: '此刻字使用了原模型特征相交覆盖。',
      affected: records,
    },
  }];
}

function isSurfaceEngravingOverrideWarning(value = {}) {
  if (!isPlainObject(value)) return false;
  const id = String(value.id || '').toLowerCase();
  const message = String(value.message || '');
  return id === SURFACE_ENGRAVING_OVERRIDE_WARNING_ID
    || id.startsWith('surface_engraving_override_')
    || (message.includes('强制刻字') && message.includes('文字可能被边界裁断'));
}

function buildWarningCheckItems(warnings, existingChecks = []) {
  const existingIds = new Set(existingChecks.map((check) => check.id).filter(Boolean));
  return warnings.map((warning, index) => {
    const warningId = warning.id || `warning_${index + 1}`;
    const details = warning.details || warningDetailsFromFields(warning);
    return {
      id: existingIds.has(warningId) ? `warning_${warningId}` : warningId,
      label: warning.label || `风险提示：${warningId}`,
      status: normalizeWarningStatus(warning.status),
      message: warning.message || '',
      details,
    };
  });
}

function normalizeWarningStatus(status) {
  if (['warn', 'pending', 'fail', 'pass'].includes(status)) return status;
  if (['failed', 'error'].includes(status)) return 'fail';
  return 'warn';
}

function warningDetailsFromFields(warning) {
  const details = {};
  for (const key of [
    'hardware_id',
    'blocking_reason',
    'code',
    'path',
    'name',
    'engraving_id',
    'surface_id',
    'surface_label',
  ]) {
    if (warning[key]) details[key] = warning[key];
  }
  return Object.keys(details).length ? details : null;
}

function summarizeCheckDetails(details) {
  if (!details) return [];
  if (Array.isArray(details)) return details.slice(0, 4).map(formatCheckDetailItem);
  if (typeof details !== 'object') return [String(details)];
  const lines = [];
  if (details.name) lines.push(`类型：${details.name}`);
  if (details.code) lines.push(`错误代码：${details.code}`);
  if (details.path) lines.push(`路径：${details.path}`);
  if (details.message) lines.push(`详情：${details.message}`);
  if (Array.isArray(details.affected) && details.affected.length) {
    const affected = details.affected.map((item) => item.surface_label || item.surface_id || item.engraving_id).filter(Boolean);
    if (affected.length) lines.push(`涉及：${[...new Set(affected)].join('、')}`);
  }
  if (details.surface_label) lines.push(`目标面：${details.surface_label}`);
  if (details.surface_id) lines.push(`目标面 ID：${details.surface_id}`);
  if (details.engraving_id) lines.push(`刻字：${details.engraving_id}`);
  if (details.hardware_id) lines.push(`硬件：${details.hardware_id}`);
  if (details.blocking_reason) lines.push(`原因：${details.blocking_reason}`);
  if ('required_openings' in details) lines.push(`需要开孔 ${details.required_openings} 个，已生成 ${details.generated_openings} 个`);
  if (Array.isArray(details.missing) && details.missing.length) lines.push(`缺失：${details.missing.join(', ')}`);
  if (Array.isArray(details.misaligned) && details.misaligned.length) lines.push(`未对齐：${details.misaligned.map((item) => item.id || item.face).join(', ')}`);
  if ('clearance_mm' in details && details.clearance_mm !== null) lines.push(`余量 ${details.clearance_mm} mm，要求 ${details.required_clearance_mm} mm`);
  return lines.slice(0, 4);
}

function formatCheckDetailItem(item) {
  if (!item || typeof item !== 'object') return String(item);
  if ('availability' in item && item.id) {
    return `${item.id}：${exportFormatLabel(item.format)}，${availabilityLabel(item.availability)}`;
  }
  if ('utilization' in item) {
    return `${faceLabel(item.face)}：占用 ${Math.round(Number(item.utilization || 0) * 100)}%，${item.used_area_mm2}/${item.capacity_area_mm2} mm²`;
  }
  if ('hardware_to_inner_wall_gap_mm' in item) {
    return `${item.opening_id || item.hardware_id}：${faceLabel(item.face)} 面，距内壁 ${item.hardware_to_inner_wall_gap_mm} mm，建议 ≤ ${item.max_recommended_gap_mm} mm`;
  }
  if (item.hardware_id && item.boss) return `${item.hardware_id} 与螺丝柱过近`;
  if (item.id && item.face) return `${item.id}：${faceLabel(item.face)} 面`;
  return Object.entries(item).slice(0, 3).map(([key, value]) => `${key}: ${JSON.stringify(value)}`).join('，');
}

function availabilityLabel(value) {
  return {
    available: '可下载',
    pending: '等待生成',
    failed: '写入失败',
    unavailable: '不可用',
  }[value] || value || '未知';
}

function renderParameters() {
  if (isTemplateCaseArtifact(state.artifact || state.draft)) {
    const value = state.artifact || state.draft;
    const parts = templateCasePrintableParts(value);
    els.parameterGroups.innerHTML = `
      <section class="param-group">
        <h2>模板案例</h2>
        <div class="check-item pass">${escapeHtml(parts.map((part) => part.label || part.id).join('、') || '案例打印件')}</div>
        <div class="check-item pending">当前模型保留案例原始几何。需要调整尺寸或结构时，请直接在左侧对话中描述修改要求；修改只作用于当前项目源码副本。</div>
      </section>
    `;
    return;
  }
  if (isStandaloneStructuralArtifact(state.artifact || state.draft)) {
    const parts = structuralPrintableParts(state.artifact || state.draft);
    els.parameterGroups.innerHTML = `
      <section class="param-group">
        <h2>结构件项目</h2>
        <div class="check-item pass">${escapeHtml(parts.map((part) => part.label || part.id).join('、') || '结构件模型')}</div>
        <div class="check-item pending">需要个性化修改时，请直接在左侧对话中说明尺寸、孔槽、圆角或其他结构要求。</div>
      </section>
    `;
    return;
  }
  if (isDeterministicTemplateArtifact(state.artifact || state.draft)) {
    renderDeterministicTemplateParameters(state.artifact || state.draft);
    return;
  }
  const groups = state.artifact?.parameters || state.draft?.parameters || {};
  if (!Object.keys(groups).length) {
    els.parameterGroups.innerHTML = '<div class="check-item pending">生成后这里会显示可调参数。</div>';
    return;
  }
  els.parameterGroups.innerHTML = Object.entries(groups).map(([groupName, values]) => `
    <section class="param-group">
      <h2>${escapeHtml(groupLabel(groupName))}</h2>
      ${Object.entries(values).map(([key, value]) => {
        const defaultInfo = parameterDefaultInfo(key, value);
        return `
        <div class="param-row ${defaultInfo.hasDefault && parameterValueChanged(value, defaultInfo.value) ? 'is-modified' : ''}">
          ${renderParameterRestoreButton(key, defaultInfo, value)}
          <label for="param_${escapeHtml(key)}">${escapeHtml(paramLabel(key))}</label>
          <input id="param_${escapeHtml(key)}" data-param="${escapeHtml(key)}" type="number" step="0.1" value="${Number(value)}" />
        </div>
      `;
      }).join('')}
    </section>
  `).join('') + renderHardwareFaceControls() + renderHardwareRotationControls();
  els.parameterGroups.querySelectorAll('input[data-param]').forEach((input) => {
    const update = () => {
      state.parameterOverrides[input.dataset.param] = Number(input.value);
      updateParameterRestoreState(input);
      scheduleParameterRegenerate();
    };
    input.addEventListener('input', update);
    input.addEventListener('change', update);
  });
  bindParameterRestoreButtons();
  els.parameterGroups.querySelectorAll('select[data-hardware-face]').forEach((select) => {
    select.addEventListener('change', () => {
      state.hardwareFaceOverrides[select.dataset.hardwareFace] = select.value;
      scheduleParameterRegenerate();
    });
  });
  els.parameterGroups.querySelectorAll('select[data-hardware-rotation]').forEach((select) => {
    select.addEventListener('change', () => {
      state.hardwareRotationOverrides[select.dataset.hardwareRotation] = Number(select.value);
      scheduleParameterRegenerate();
    });
  });
}

function renderDeterministicTemplateParameters(artifact = {}) {
  const params = deterministicTemplateGuiParameters(artifact);
  if (!params.length) {
    els.parameterGroups.innerHTML = '<div class="check-item pending">当前模板没有可展示的关键参数。</div>';
    return;
  }
  els.parameterGroups.innerHTML = `
    <section class="param-group template-param-group">
      <h2>${escapeHtml(deterministicProductDisplayName(artifact))}参数</h2>
      <p class="template-param-note">可在此处编辑模型参数</p>
      ${params.map((item) => {
        const defaultInfo = parameterDefaultInfo(item.key, item.value);
        return `
        <div class="param-row template-param-row ${defaultInfo.hasDefault && parameterValueChanged(item.value, defaultInfo.value) ? 'is-modified' : ''}">
          ${renderParameterRestoreButton(item.key, defaultInfo, item.value)}
          <label for="param_${escapeHtml(item.key)}">${escapeHtml(item.label)}</label>
          <span class="template-param-input-wrap">
            <input id="param_${escapeHtml(item.key)}" data-param="${escapeHtml(item.key)}" type="number" step="${escapeHtml(item.step || '0.1')}" value="${Number(item.value)}" />
            ${item.unit ? `<small>${escapeHtml(item.unit)}</small>` : ''}
          </span>
        </div>
      `;
      }).join('')}
    </section>
  `;
  els.parameterGroups.querySelectorAll('input[data-param]').forEach((input) => {
    const update = () => {
      state.parameterOverrides[input.dataset.param] = Number(input.value);
      updateParameterRestoreState(input);
      scheduleParameterRegenerate();
    };
    input.addEventListener('input', update);
    input.addEventListener('change', update);
  });
  bindParameterRestoreButtons();
}

function deterministicTemplateGuiParameters(artifact = {}) {
  if (artifact.template_id === 'unihiker_photo_album_v1') {
    const source = artifact.parameters?.photo_album || artifact.design_state?.cad_parameters?.geometry || {};
    return [
      ['base_length_x', '底座长度 X', source.base_length_x],
      ['base_width_y', '底座宽度 Y', source.base_width_y],
      ['base_thickness_z', '底座厚度 Z', source.base_thickness_z],
      ['slope_face_length', '斜面长度', source.slope_face_length],
      ['slope_thickness', '斜面厚度', source.slope_thickness],
      ['slope_angle_deg', '斜面角度', source.slope_angle_deg, '°'],
      ['clip_perpendicular_thickness', '前挡条垂直厚度', source.clip_perpendicular_thickness],
      ['clip_perpendicular_length', '前挡条垂直长度', source.clip_perpendicular_length],
      ['side_block_y_depth', '侧挡块深度', source.side_block_y_depth],
      ['rear_slope_block_s_length', '背部支撑块长度', source.rear_slope_block_s_length],
      ['rear_slope_block_normal_thickness', '背部支撑块厚度', source.rear_slope_block_normal_thickness],
      ['rear_slope_top_slot_width_n', '顶部长槽宽度', source.rear_slope_top_slot_width_n],
      ['rear_slope_top_slot_y_length', '顶部长槽长度', source.rear_slope_top_slot_y_length],
      ['narrow_stop_semicircle_diameter', '半圆避让直径', source.narrow_stop_semicircle_diameter],
      ['rear_slope_block_low_contact_fillet_radius', '低位接触圆角半径', source.rear_slope_block_low_contact_fillet_radius],
    ].filter(([, , value]) => Number.isFinite(Number(value)))
      .map(([key, label, value, unit = 'mm']) => ({ key, label, value, unit, step: unit === '°' ? '1' : '0.1' }));
  }
  if (artifact.template_id === 'unihiker_smart_watering_system_v1') {
    const source = artifact.parameters?.plant_care_box
      || artifact.design_state?.cad_parameters?.geometry
      || artifact.design_state?.enclosure_parameters?.outer_box_size
      || {};
    return [
      ['box_length_x', '盒体长度 X', source.box_length_x ?? source.length_x],
      ['box_width_y', '盒体宽度 Y', source.box_width_y ?? source.width_y],
      ['box_height_z', '盒体高度 Z', source.box_height_z ?? source.height_z],
    ].filter(([, , value]) => Number.isFinite(Number(value)))
      .map(([key, label, value]) => ({ key, label, value, unit: 'mm', step: '0.1' }));
  }
  const geometry = artifact.design_state?.cad_parameters?.geometry || {};
  return Object.entries(geometry)
    .filter(([, value]) => Number.isFinite(Number(value)))
    .slice(0, 16)
    .map(([key, value]) => ({ key, label: paramLabel(key), value, unit: 'mm', step: '0.1' }));
}

function renderParameterRestoreButton(key, defaultInfo, currentValue) {
  const info = defaultInfo && typeof defaultInfo === 'object' && 'hasDefault' in defaultInfo
    ? defaultInfo
    : parameterDefaultInfo(key, defaultInfo);
  const fallback = Number(info.value);
  const hasDefault = Boolean(info.hasDefault) && Number.isFinite(fallback);
  const changed = hasDefault && parameterValueChanged(currentValue, fallback);
  return `
    <button
      class="param-restore-button ${changed ? 'is-visible' : ''}"
      type="button"
      title="恢复默认值"
      aria-label="恢复默认值"
      data-restore-param="${escapeHtml(key)}"
      data-default-value="${escapeHtml(hasDefault ? fallback : '')}"
      data-has-default="${hasDefault ? 'true' : 'false'}"
      ${changed ? '' : 'tabindex="-1"'}
    ></button>
  `;
}

function bindParameterRestoreButtons() {
  els.parameterGroups.querySelectorAll('button[data-restore-param]').forEach((button) => {
    button.addEventListener('click', () => {
      const key = button.dataset.restoreParam || '';
      if (button.dataset.hasDefault !== 'true') return;
      const defaultValue = Number(button.dataset.defaultValue);
      if (!key || !Number.isFinite(defaultValue)) return;
      const input = els.parameterGroups.querySelector(`input[data-param="${cssEscape(key)}"]`);
      if (input) input.value = String(defaultValue);
      state.parameterOverrides[key] = defaultValue;
      button.classList.remove('is-visible');
      button.closest('.param-row')?.classList.remove('is-modified');
      scheduleParameterRegenerate();
    });
  });
}

function updateParameterRestoreState(input) {
  const key = input?.dataset?.param || '';
  if (!key) return;
  const row = input.closest('.param-row');
  const button = row?.querySelector(`button[data-restore-param="${cssEscape(key)}"]`);
  const hasDefault = button?.dataset.hasDefault === 'true';
  const defaultValue = Number(button?.dataset.defaultValue ?? '');
  const changed = hasDefault && parameterValueChanged(input.value, defaultValue);
  row?.classList.toggle('is-modified', changed);
  button?.classList.toggle('is-visible', changed);
  if (button) {
    if (changed) button.removeAttribute('tabindex');
    else button.setAttribute('tabindex', '-1');
  }
}

function cssEscape(value) {
  if (window.CSS?.escape) return window.CSS.escape(value);
  return String(value).replace(/["\\]/g, '\\$&');
}

function formatTemplateParamValue(value, unit = 'mm') {
  const number = Number(value);
  const text = Number.isFinite(number) ? String(Math.round(number * 1000) / 1000) : String(value ?? '');
  return unit ? `${text} ${unit}` : text;
}

function renderHardwareFaceControls() {
  const designState = state.artifact?.design_state || state.draft?.design_state;
  const transforms = designState?.layout_plan?.hardware_transforms || [];
  if (!transforms.length) return '';
  const namesById = new Map((state.artifact?.bom || state.draft?.bom || []).map((item) => [item.hardware_id, item.name || item.hardware_id]));
  return `
    <section class="param-group">
      <h2>安装层</h2>
      ${transforms.map((item) => {
        const value = state.hardwareFaceOverrides[item.hardware_id] || item.mount_surface || 'base_floor';
        return `
          <div class="param-row">
            <span class="param-restore-spacer" aria-hidden="true"></span>
            <label for="face_${escapeHtml(item.hardware_id)}">${escapeHtml(namesById.get(item.hardware_id) || item.hardware_id)}</label>
            <select id="face_${escapeHtml(item.hardware_id)}" data-hardware-face="${escapeHtml(item.hardware_id)}">
              <option value="base_floor" ${value === 'base_floor' ? 'selected' : ''}>底壳</option>
              <option value="lid_inner" ${value === 'lid_inner' ? 'selected' : ''}>上盖内侧</option>
              <option value="lid_outer" ${value === 'lid_outer' ? 'selected' : ''}>上盖外侧</option>
            </select>
          </div>
        `;
      }).join('')}
    </section>
  `;
}

function renderHardwareRotationControls() {
  const designState = state.artifact?.design_state || state.draft?.design_state;
  const transforms = designState?.layout_plan?.hardware_transforms || [];
  if (!transforms.length) return '';
  const namesById = new Map((state.artifact?.bom || state.draft?.bom || []).map((item) => [item.hardware_id, item.name || item.hardware_id]));
  return `
    <section class="param-group">
      <h2>朝向</h2>
      ${transforms.map((item) => {
        const value = Number(state.hardwareRotationOverrides[item.hardware_id] ?? item.layout_rotation_deg ?? 0);
        return `
          <div class="param-row">
            <span class="param-restore-spacer" aria-hidden="true"></span>
            <label for="rot_${escapeHtml(item.hardware_id)}">${escapeHtml(namesById.get(item.hardware_id) || item.hardware_id)}</label>
            <select id="rot_${escapeHtml(item.hardware_id)}" data-hardware-rotation="${escapeHtml(item.hardware_id)}">
              ${[0, 90, 180, 270].map((deg) => `<option value="${deg}" ${value === deg ? 'selected' : ''}>${deg}°</option>`).join('')}
            </select>
          </div>
        `;
      }).join('')}
    </section>
  `;
}

function renderExportLinks() {
  if (els.exportLinks) {
    els.exportLinks.innerHTML = '';
    els.exportLinks.classList.add('hidden');
    els.exportLinks.setAttribute('aria-hidden', 'true');
  }
  renderExportStlButton();
}

function renderExportStlButton() {
  if (!els.exportStlButton) return;
  const parts = printableStlExports();
  const hasArtifact = Boolean(state.artifact);
  els.exportStlButton.disabled = !hasArtifact || state.isCadqueryBuilding || !parts.length;
  els.exportStlButton.textContent = parts.length ? `导出 STL（${parts.length}）` : '导出 STL';
  els.exportStlButton.title = parts.length
    ? '选择当前项目中的 STL 部件并导出'
    : hasArtifact ? '当前还没有可导出的 STL，请等待模型生成完成。' : '生成模型后可以导出 STL。';
}

function printableStlExports() {
  const exports = state.exportResult?.exports || state.artifact?.exports || [];
  const declaredParts = Array.isArray(state.artifact?.printable_parts)
    ? state.artifact.printable_parts
    : Array.isArray(state.artifact?.design_state?.printable_parts)
      ? state.artifact.design_state.printable_parts
      : [];
  if (declaredParts.length) {
    const byId = new Map(exports.map((item) => [item.id, item]));
    return declaredParts
      .map((part) => {
        const exportItem = byId.get(part.source_export_id || part.export_id || part.id);
        if (!exportItem || normalizeFormat(exportItem.format) !== 'stl' || !exportItem.url || !isUsableViewerExport(exportItem)) {
          return null;
        }
        return {
          ...exportItem,
          id: part.id || exportItem.id,
          export_id: exportItem.id,
          source_export_id: part.source_export_id || exportItem.id,
          label: part.label || exportItem.label,
          printable_part: part,
        };
      })
      .filter(Boolean);
  }
  const preferredOrder = [
    'cadquery_base_stl',
    'cadquery_lid_stl',
  ];
  const rank = new Map(preferredOrder.map((id, index) => [id, index]));
  return exports
    .filter((item) => rank.has(item.id) && normalizeFormat(item.format) === 'stl' && item.url && isUsableViewerExport(item))
    .sort((a, b) => (rank.get(a.id) ?? 99) - (rank.get(b.id) ?? 99));
}

function openExportStlDialog() {
  const parts = printableStlExports();
  if (!parts.length) return;
  renderExportStlDialogParts(parts);
  setExportStlStatus('');
  if (els.exportStlPath) els.exportStlPath.textContent = state.exportDirectoryName || '未选择';
  els.exportStlDialog?.classList.remove('hidden');
}

function closeExportStlDialog() {
  els.exportStlDialog?.classList.add('hidden');
}

function renderExportStlDialogParts(parts = printableStlExports()) {
  if (!els.exportStlParts) return;
  els.exportStlParts.innerHTML = parts.map((item, index) => `
    <label class="export-stl-part">
      <input type="checkbox" data-export-stl-id="${escapeHtml(item.id || '')}" checked />
      <span>${escapeHtml(printablePartLabel(item))}</span>
    </label>
  `).join('');
}

function printablePartLabel(item = {}) {
  if (item.label) return item.label;
  if (item.printable_part?.label) return item.printable_part.label;
  const labels = {
    cadquery_stl: '整体模型',
    cadquery_base_stl: '底壳',
    cadquery_lid_stl: '上盖',
    cadquery_hardware_stl: '硬件参考',
    base_stl: '底壳简化预览',
    lid_stl: '上盖简化预览',
    hardware_reference_stl: '硬件参考简化预览',
    opening_reference_stl: '开孔参考简化预览',
  };
  return labels[item.id] || item.label || item.id || 'STL 部件';
}

async function chooseExportDirectory() {
  if (!window.showDirectoryPicker) {
    state.exportDirectoryHandle = null;
    state.exportDirectoryName = '';
    if (els.exportStlPath) els.exportStlPath.textContent = '当前浏览器不支持选择文件夹，将使用下载方式。';
    setExportStlStatus('当前浏览器不支持直接选择 PC 文件夹，确认导出时会逐个下载选中的 STL。', 'warn');
    return;
  }
  try {
    const handle = await window.showDirectoryPicker({ mode: 'readwrite' });
    state.exportDirectoryHandle = handle;
    state.exportDirectoryName = handle.name || '已选择文件夹';
    if (els.exportStlPath) els.exportStlPath.textContent = state.exportDirectoryName;
    setExportStlStatus('已选择导出位置。', 'success');
  } catch (error) {
    if (error?.name === 'AbortError') {
      setExportStlStatus('已取消选择导出位置。', '');
      return;
    }
    setExportStlStatus(`选择导出位置失败：${error.message || error}`, 'error');
  }
}

async function confirmExportStl() {
  const selected = selectedPrintableStlExports();
  if (!selected.length) {
    setExportStlStatus('请至少勾选一个需要导出的 STL 部件。', 'error');
    return;
  }
  try {
    if (state.exportDirectoryHandle) {
      await writeStlExportsToDirectory(selected, state.exportDirectoryHandle);
      setExportStlStatus(`已导出 ${selected.length} 个 STL 文件到所选文件夹。`, 'success');
      return;
    }
    downloadStlExports(selected);
    setExportStlStatus(`已开始下载 ${selected.length} 个 STL 文件。`, 'success');
  } catch (error) {
    setExportStlStatus(`导出失败：${error.message || error}`, 'error');
  }
}

function selectedPrintableStlExports() {
  const selectedIds = new Set(
    [...(els.exportStlParts?.querySelectorAll('input[data-export-stl-id]:checked') || [])]
      .map((input) => input.dataset.exportStlId)
      .filter(Boolean),
  );
  return printableStlExports().filter((item) => selectedIds.has(item.id || item.export_id));
}

async function writeStlExportsToDirectory(parts = [], directoryHandle) {
  for (const item of parts) {
    const response = await fetch(item.url);
    if (!response.ok) throw new Error(`${printablePartLabel(item)} 下载失败`);
    const blob = await response.blob();
    const fileHandle = await directoryHandle.getFileHandle(exportFilenameForItem(item), { create: true });
    const writable = await fileHandle.createWritable();
    await writable.write(blob);
    await writable.close();
  }
}

function downloadStlExports(parts = []) {
  for (const item of parts) {
    const link = document.createElement('a');
    link.href = item.url;
    link.download = exportFilenameForItem(item);
    document.body.appendChild(link);
    link.click();
    link.remove();
  }
}

function exportFilenameForItem(item = {}) {
  const fromUrl = String(item.url || '').split('/').filter(Boolean).pop() || '';
  const suffix = fromUrl.endsWith('.stl') ? fromUrl : `${item.id || 'part'}.stl`;
  const project = String(currentTaskId() || state.artifact?.design_state?.id || 'zwcad-project')
    .replace(/[^\w.-]+/g, '_')
    .slice(0, 80);
  const part = String(item.id || suffix.replace(/\.stl$/i, 'part'))
    .replace(/[^\w.-]+/g, '_')
    .slice(0, 48);
  return `${project}_${part}.stl`;
}

function setExportStlStatus(message, tone = '') {
  if (!els.exportStlStatus) return;
  els.exportStlStatus.textContent = message || '';
  els.exportStlStatus.className = ['export-stl-status', tone ? `is-${tone}` : ''].join(' ').trim();
}

function renderExportFilters(exports = []) {
  if (!exports.length) return '';
  const formats = ['all', ...new Set(exports.map((item) => normalizeFormat(item.format)).filter(Boolean))].sort((a, b) => {
    if (a === 'all') return -1;
    if (b === 'all') return 1;
    return exportFormatLabel(a).localeCompare(exportFormatLabel(b), 'zh-CN');
  });
  return `
    <div class="export-filter" role="group" aria-label="导出格式">
      ${formats.map((format) => {
        const value = format === 'all' ? '' : format;
        const active = state.exportFormat === value;
        return `<button class="${active ? 'active' : ''}" type="button" data-export-format="${escapeHtml(value)}">${escapeHtml(exportFormatLabel(format))}</button>`;
      }).join('')}
    </div>
  `;
}

async function setExportFormat(format) {
  state.exportFormat = normalizeFormat(format);
  if (!state.artifact) return;
  try {
    state.exportResult = await api('/api/export', {
      method: 'POST',
      body: {
        artifact: state.artifact,
        format: state.exportFormat || undefined,
      },
    });
  } catch (error) {
    state.exportResult = {
      status: 'export',
      exports: [],
      message: error.message,
    };
  }
  renderExportLinks();
}

async function runCadQueryBuild(options = {}) {
  if (!state.artifact) return null;
  if (state.cadqueryAutoBuildPromise) return state.cadqueryAutoBuildPromise;

  state.isCadqueryBuilding = true;
  state.viewerNotice = null;
  renderPreview();

  state.cadqueryAutoBuildPromise = (async () => {
    try {
      const result = await api('/api/cadquery/build', {
        method: 'POST',
        body: {
          designId: state.artifact.design_state?.id,
          artifact: state.artifact,
        },
      });
      state.cadqueryBuild = result;
      if (result.status === 'artifact_exports') {
        if (result.artifact) {
          state.artifact = result.artifact;
          state.currentTaskId = result.artifact.design_state?.id || state.currentTaskId;
        } else {
          state.artifact.exports = mergeExports(state.artifact.exports || [], result.exports || []);
        }
        if (result.warning) {
          state.artifact.warnings = [...(state.artifact.warnings || []), result.warning];
          if (state.artifact.design_state) {
            state.artifact.design_state.warnings = [...(state.artifact.design_state.warnings || []), result.warning];
          }
        }
        if (result.mesh_validation_report) {
          state.artifact.mesh_validation_report = result.mesh_validation_report;
          if (state.artifact.design_state) {
            state.artifact.design_state.mesh_validation_report = result.mesh_validation_report;
            state.artifact.design_state.exports = state.artifact.exports;
          }
        }
        bumpPreviewRevision();
        state.exportResult = null;
        state.viewerNotice = null;
        if (!options.quiet) {
          addMessage('agent', '模型已更新', '真实 3D 模型已经生成，可以继续检查结构或导出 STL。', cadqueryMessageBullets(result));
        }
        if (state.exportFormat) await setExportFormat(state.exportFormat);
        else renderExportLinks();
        renderChecks();
        return result;
      }

      const failureMessage = cadqueryFailureMessage(result);
      state.viewerNotice = {
        title: '真实模型暂不可用',
        body: failureMessage,
      };
      if (!options.quiet) {
        addMessage('agent', '真实模型暂不可用', failureMessage, cadqueryMessageBullets(result));
      }
      renderChecks();
      return result;
    } catch (error) {
      state.cadqueryBuild = {
        status: 'fail',
        blocking_reason: 'cadquery_request_failed',
        message: error.message,
      };
      state.viewerNotice = {
        title: '真实模型生成失败',
        body: `${error.message}。已显示简化 3D 预览。`,
      };
      if (!options.quiet) addMessage('agent', '真实模型生成失败', error.message);
      renderChecks();
      return state.cadqueryBuild;
    } finally {
      state.isCadqueryBuilding = false;
      state.cadqueryAutoBuildPromise = null;
      renderPreviewModeButtons();
      renderExportLinks();
      renderPreview();
    }
  })();

  return state.cadqueryAutoBuildPromise;
}

function mergeExports(existing = [], incoming = []) {
  const byKey = new Map();
  for (const item of [...existing, ...incoming]) {
    const key = item.id || item.url || item.path || JSON.stringify(item);
    byKey.set(key, item);
  }
  return [...byKey.values()];
}

function cadqueryFailureMessage(result = {}) {
  const stderr = summarizeCadqueryStderr(result.stderr);
  const preflightMessage = result.preflight?.message || result.preflight?.error || '';
  return [
    result.message || result.blocking_reason || '真实模型暂时没有生成完成。',
    result.blocking_reason ? `原因：${result.blocking_reason}` : '',
    stderr ? `错误摘要：${stderr}` : '',
    preflightMessage ? `预检信息：${preflightMessage}` : '',
  ].filter(Boolean).join(' ');
}

function summarizeCadqueryStderr(stderr = '') {
  const lines = String(stderr || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/^File ".*run-cadquery-export\.py"/.test(line));
  return lines.slice(-4).join(' | ');
}

function buildCadQueryBuildCheck(result) {
  if (!result) return null;
  const statusMap = {
    artifact_exports: 'pass',
    pending: 'pending',
    needs_input: 'pending',
    fail: 'fail',
  };
  const details = [];
  if (result.preflight?.status) details.push(`preflight: ${result.preflight.status}`);
  if (result.blocking_reason) details.push(`reason: ${result.blocking_reason}`);
  if (Array.isArray(result.requiredPythonPackages) && result.requiredPythonPackages.length) {
    details.push(`missing packages: ${result.requiredPythonPackages.join(', ')}`);
  }
  return {
    id: 'cadquery_build',
    label: '真实模型生成',
    status: statusMap[result.status] || 'pending',
    message: [result.message || result.status || '真实模型生成结果', ...details].join(' | '),
  };
}

function cadqueryMessageBullets(result) {
  const bullets = [];
  if (result.preflight?.status) bullets.push(`预检查：${result.preflight.status}`);
  if (result.blocking_reason) bullets.push(`原因：${result.blocking_reason}`);
  if (Array.isArray(result.requiredPythonPackages) && result.requiredPythonPackages.length) {
    bullets.push(`需要的 Python 包：${result.requiredPythonPackages.join(', ')}`);
  }
  return bullets;
}

function renderHardwareList() {
  const query = els.hardwareSearch.value.trim().toLowerCase();
  const category = els.categoryFilter.value;
  const activeSystem = state.activeHardwareSystemTab || 'xiao';
  const commonActive = activeSystem === 'common';
  const customActive = activeSystem === 'user_custom';
  const templateActive = activeSystem === TEMPLATE_PROJECT_SYSTEM_ID;
  const customWorkbenchOpen = customActive && state.customHardwareWorkbenchOpen;
  els.customHardwarePanel?.classList.toggle('hidden', !customWorkbenchOpen);
  els.hardwareList.classList.toggle('hidden', customWorkbenchOpen);
  renderCustomHardwareWorkbenchState();
  const filtered = hardwareForActiveSystem().filter((item) => {
    const matchesQuery = !query || `${item.id} ${item.name} ${item.category} ${hardwareModelTypeLabel(item)} ${(item.aliases || []).join(' ')} ${(item.roles || []).join(' ')}`.toLowerCase().includes(query);
    const matchesCategory = !category || item.category === category;
    const matchesModelType = !commonActive || hardwareModelTypeOf(item) === state.activeHardwareModelType;
    const matchesCustomType = !customActive || (item.custom_hardware_type || 'electronic') === state.activeCustomHardwareType;
    return matchesQuery && matchesCategory && matchesModelType && matchesCustomType;
  });
  if (customWorkbenchOpen) {
    return;
  }
  if (templateActive) {
    renderTemplateProjectList(query);
    return;
  }
  const modelTypeTabs = commonActive ? renderHardwareModelTypeTabs() : '';
  const customListTabs = customActive ? renderCustomHardwareListTabs() : '';
  const customAddCard = customActive ? renderCustomHardwareAddCard() : '';
  if (!filtered.length) {
    if (customActive) {
      els.hardwareList.innerHTML = `${modelTypeTabs}${customListTabs}${customAddCard}`;
      attachHardwareModelTypeTabListeners();
      attachCustomHardwareListTabListeners();
      attachCustomHardwareAddCardListeners();
      return;
    }
    els.hardwareList.innerHTML = `
      ${modelTypeTabs}
      ${customListTabs}
      ${customAddCard}
      <div class="hardware-empty">
        <strong>暂无硬件</strong>
        <span>${customActive ? '当前用户自定义分类还没有匹配硬件。' : '当前体系没有匹配的硬件 profile。'}</span>
      </div>
    `;
    attachHardwareModelTypeTabListeners();
    attachCustomHardwareListTabListeners();
    attachCustomHardwareAddCardListeners();
    return;
  }
  els.hardwareList.innerHTML = modelTypeTabs + customListTabs + customAddCard + filtered.map((item) => {
    const selected = state.selectedHardwareIds.has(item.id);
    const d = item.dimensions_mm || {};
    return `
      <article
        class="hardware-card ${selected ? 'selected' : ''}"
        data-hardware-card-id="${escapeHtml(item.id)}"
        tabindex="0"
        role="button"
        aria-pressed="${selected ? 'true' : 'false'}"
      >
        ${customActive ? `<button type="button" class="custom-hardware-delete-button" data-custom-hardware-delete-id="${escapeHtml(item.id)}" aria-label="删除 ${escapeHtml(item.name || item.id)}">×</button>` : ''}
        ${renderHardwareThumb(item)}
        <div class="hardware-card-body">
          <div class="hardware-card-title">
            <h3>${escapeHtml(item.name)}</h3>
            <span>${selected ? '已选' : '点击选择'}</span>
          </div>
          <p>${escapeHtml(hardwareModelTypeLabel(item))} · ${escapeHtml(item.category)} · ${escapeHtml((item.roles || []).join(', ') || 'hardware')}</p>
          <p>${Number(d.length_x || 0)} x ${Number(d.width_y || 0)} x ${Number(d.height_z || 0)} mm</p>
          ${hardwareModelQualityLabel(item) ? `<p class="hardware-source">${escapeHtml(hardwareModelQualityLabel(item))}</p>` : ''}
          <p class="hardware-source">${escapeHtml(item.source_status || '')}</p>
          ${renderHardwareProfileDetails(item)}
        </div>
        <button type="button" data-hardware-id="${escapeHtml(item.id)}">${selected ? '移除' : '加入 BOM'}</button>
      </article>
    `;
  }).join('');
  attachHardwareModelTypeTabListeners();
  attachCustomHardwareListTabListeners();
  els.hardwareList.querySelectorAll('[data-custom-hardware-delete-id]').forEach((button) => {
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      confirmDeleteCustomHardware(button.dataset.customHardwareDeleteId);
    });
  });
  els.hardwareList.querySelectorAll('button[data-hardware-id]').forEach((button) => {
    button.addEventListener('click', () => {
      toggleHardwareSelection(button.dataset.hardwareId);
    });
  });
  els.hardwareList.querySelectorAll('[data-hardware-card-id]').forEach((card) => {
    card.addEventListener('click', (event) => {
      if (event.target.closest('button, details, summary, input, select, textarea, a')) return;
      toggleHardwareSelection(card.dataset.hardwareCardId);
    });
    card.addEventListener('keydown', (event) => {
      if (!['Enter', ' '].includes(event.key)) return;
      if (event.target.closest('button, details, summary, input, select, textarea, a')) return;
      event.preventDefault();
      toggleHardwareSelection(card.dataset.hardwareCardId);
    });
  });
  attachCustomHardwareAddCardListeners();
  attachHardwareThumbFallbacks();
}

function renderTemplateProjectList(query = '') {
  const projects = state.templateProjects.filter((project) => {
    const hardwareNames = (project.hardware_ids || [])
      .map((id) => findHardwareProfile(id)?.name || id)
      .join(' ');
    return !query || `${project.id} ${project.name} ${project.summary} ${hardwareNames}`.toLowerCase().includes(query);
  });
  if (!projects.length) {
    els.hardwareList.innerHTML = `
      <div class="hardware-empty">
        <strong>暂无匹配模板</strong>
        <span>请调整搜索内容后重试。</span>
      </div>
    `;
    return;
  }
  els.hardwareList.innerHTML = projects.map((project) => `
    <article class="hardware-card template-project-card" data-template-project-card-id="${escapeHtml(project.id)}">
      ${renderTemplateProjectThumb(project)}
      <div class="hardware-card-body">
        <div class="hardware-card-title">
          <h3>${escapeHtml(project.name)}</h3>
          <span>项目模板</span>
        </div>
        <p>模板项目 · ${escapeHtml(project.hardware_system === 'unihiker' ? '行空板' : project.hardware_system || '')}</p>
        <p>${escapeHtml(project.summary || '')}</p>
        <p class="hardware-source">${escapeHtml(templateProjectHardwareSummary(project))}</p>
      </div>
      <button type="button" data-template-project-id="${escapeHtml(project.id)}">应用模板</button>
    </article>
  `).join('');
  els.hardwareList.querySelectorAll('button[data-template-project-id]').forEach((button) => {
    button.addEventListener('click', async () => {
      await applyTemplateProject(button.dataset.templateProjectId || '');
    });
  });
  attachHardwareThumbFallbacks();
}

function renderTemplateProjectThumb(project = {}) {
  if (project.thumbnail_url) {
    return `
      <div class="hardware-thumb template-project-thumb is-project-thumbnail">
        <img
          src="${escapeHtml(hardwareThumbnailSrc(project.thumbnail_url))}"
          alt="${escapeHtml(project.name || project.id)}"
          loading="lazy"
          referrerpolicy="no-referrer"
          data-fallback="${escapeHtml(hardwareInitials(project))}"
        />
      </div>
    `;
  }
  const profiles = (project.preview_hardware_ids || [])
    .map((id) => findHardwareProfile(id))
    .filter(Boolean);
  if (!profiles.length) {
    return `<div class="hardware-thumb template-project-thumb" aria-hidden="true">${escapeHtml(hardwareInitials(project))}</div>`;
  }
  return `
    <div class="hardware-thumb template-project-thumb" data-template-thumb-count="${profiles.length}">
      ${profiles.map((profile) => `
        <img
          src="${escapeHtml(hardwareThumbnailSrc(profile.thumbnail_url || ''))}"
          alt="${escapeHtml(profile.name || profile.id)}"
          loading="lazy"
          referrerpolicy="no-referrer"
          data-fallback="${escapeHtml(hardwareInitials(project))}"
        />
      `).join('')}
    </div>
  `;
}

function templateProjectHardwareSummary(project = {}) {
  const names = (project.hardware_ids || [])
    .map((id) => findHardwareProfile(id)?.name || id)
    .filter(Boolean);
  if (!names.length) return '应用后自动载入项目所需硬件。';
  const visible = names.slice(0, 3).join('、');
  return names.length > 3 ? `包含 ${visible} 等 ${names.length} 项硬件` : `包含 ${visible}`;
}

async function applyTemplateProject(id) {
  if (state.isBusy) return;
  const project = state.templateProjects.find((item) => item.id === id);
  if (!project?.prompt) return;
  state.selectedHardwareIds = new Set();
  els.promptInput.value = project.prompt;
  await handlePromptSubmit();
}

function attachHardwareThumbFallbacks() {
  els.hardwareList.querySelectorAll('.hardware-thumb img[data-fallback]').forEach((image) => {
    image.addEventListener('error', () => {
      const fallback = image.dataset.fallback || 'HW';
      const parent = image.parentElement;
      image.remove();
      if (parent) parent.textContent = fallback;
    });
  });
}

function renderCustomHardwareAddCard() {
  return `
    <article
      class="hardware-card custom-hardware-add-card"
      data-custom-hardware-add-card="true"
      tabindex="0"
      role="button"
      aria-label="自定义硬件"
    >
      <div class="custom-add-visual" aria-hidden="true">
        <span></span>
      </div>
      <div class="custom-add-label">自定义硬件</div>
    </article>
  `;
}

function renderCustomHardwareListTabs() {
  const tabs = [
    ['electronic', '电子器件'],
    ['structural', '结构件'],
  ];
  return `
    <div class="custom-hardware-list-tabs" role="tablist" aria-label="用户自定义硬件类型">
      ${tabs.map(([id, label]) => `
        <button
          type="button"
          class="${state.activeCustomHardwareType === id ? 'active' : ''}"
          data-custom-hardware-list-type="${id}"
          aria-pressed="${state.activeCustomHardwareType === id ? 'true' : 'false'}"
        >${label}</button>
      `).join('')}
    </div>
  `;
}

function renderHardwareModelTypeTabs() {
  return `
    <div class="custom-hardware-list-tabs" role="tablist" aria-label="通用件模型类型">
      ${hardwareModelTypeTabs().map(({ id, label }) => {
        const count = hardwareForActiveSystem().filter((item) => hardwareModelTypeOf(item) === id).length;
        return `
          <button
            type="button"
            class="${state.activeHardwareModelType === id ? 'active' : ''}"
            data-hardware-model-type="${id}"
            aria-pressed="${state.activeHardwareModelType === id ? 'true' : 'false'}"
          >${label}<span>${count}</span></button>
        `;
      }).join('')}
    </div>
  `;
}

function attachHardwareModelTypeTabListeners() {
  els.hardwareList.querySelectorAll('[data-hardware-model-type]').forEach((button) => {
    button.addEventListener('click', () => {
      state.activeHardwareModelType = button.dataset.hardwareModelType || 'electronic_component';
      els.categoryFilter.value = '';
      renderCategoryFilter();
      renderHardwareList();
    });
  });
}

function attachCustomHardwareListTabListeners() {
  els.hardwareList.querySelectorAll('[data-custom-hardware-list-type]').forEach((button) => {
    button.addEventListener('click', () => {
      const nextType = button.dataset.customHardwareListType || 'electronic';
      if (nextType !== state.activeCustomHardwareType) {
        state.activeCustomHardwareType = nextType;
        invalidateCustomHardwarePreview();
      }
      renderHardwareList();
    });
  });
}

function attachCustomHardwareAddCardListeners() {
  els.hardwareList.querySelectorAll('[data-custom-hardware-add-card]').forEach((card) => {
    card.addEventListener('click', openCustomHardwareWorkbench);
    card.addEventListener('keydown', (event) => {
      if (!['Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      openCustomHardwareWorkbench();
    });
  });
}

function toggleHardwareSelection(id) {
  if (!id) return;
  if (state.selectedHardwareIds.has(id)) state.selectedHardwareIds.delete(id);
  else state.selectedHardwareIds.add(id);
  state.draft = null;
  state.workflowStage = 'idle';
  state.artifact = null;
  state.cadqueryBuild = null;
  state.exportResult = null;
  state.partialBom = null;
  state.hardwareFaceOverrides = {};
  state.hardwareRotationOverrides = {};
  clearPendingParameterRegenerate();
  renderAll();
}

function renderHardwareThumb(profile) {
  const thumbnail = hardwareThumbnailSrc(profile.thumbnail_url || '');
  const initials = hardwareInitials(profile);
  const thumbId = escapeHtml(profile.id || '');
  if (!thumbnail) {
    return `<div class="hardware-thumb" data-hardware-thumb-id="${thumbId}" aria-hidden="true">${escapeHtml(initials)}</div>`;
  }
  return `
    <div class="hardware-thumb" data-hardware-thumb-id="${thumbId}">
      <img
        src="${escapeHtml(thumbnail)}"
        alt="${escapeHtml(profile.name || profile.id)}"
        loading="lazy"
        referrerpolicy="no-referrer"
        data-fallback="${escapeHtml(initials)}"
      />
    </div>
  `;
}

function hardwareThumbnailSrc(url) {
  if (!url || !url.startsWith('/assets/hardware/')) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}v=${encodeURIComponent(state.hardware.length || 'local')}`;
}

function hardwareInitials(profile = {}) {
  const text = String(profile.name || profile.id || 'HW').replace(/Seeed Studio|Grove|XIAO/gi, '').trim();
  const ascii = text.match(/[A-Za-z0-9]+/g);
  if (ascii?.length) return ascii.slice(0, 2).map((part) => part[0]).join('').toUpperCase();
  return text.slice(0, 2) || 'HW';
}

function renderBomSummary() {
  const bom = state.artifact?.bom || state.partialBom || [];
  const structural = isStandaloneStructuralArtifact(state.artifact || state.draft);
  if (bom.length) {
    const isPartial = !state.artifact && state.partialBom;
    els.bomSummary.innerHTML = `
      <div class="bom-summary-head">
        <strong>${structural ? '结构件清单' : isPartial ? '已确定 BOM' : '当前 BOM'}</strong>
        <span>${bom.length} 项${structural ? '结构件' : '硬件'}</span>
      </div>
      <div class="bom-items">
        ${bom.map((item) => renderBomChip({
          name: item.name || item.hardware_id,
          role: item.role || 'required',
          quantity: item.quantity || 1,
          status: item.profile_status || item.required_or_optional || '',
        })).join('')}
      </div>
    `;
    return;
  }

  const selectedProfiles = [...state.selectedHardwareIds]
    .map((id) => findHardwareProfile(id))
    .filter(Boolean);
  if (selectedProfiles.length) {
    els.bomSummary.innerHTML = `
      <div class="bom-summary-head">
        <strong>预选硬件</strong>
        <span>${selectedProfiles.length} 项已选择</span>
      </div>
      <div class="bom-items">
        ${selectedProfiles.map((profile) => renderBomChip({
          name: profile.name || profile.id,
          role: profile.category || 'hardware',
          quantity: 1,
          status: (profile.roles || []).slice(0, 2).join(', '),
        })).join('')}
      </div>
    `;
    return;
  }

  els.bomSummary.innerHTML = `
    <div class="bom-summary-head">
      <strong>当前 BOM</strong>
      <span>生成后显示参与建模的硬件</span>
    </div>
    <div class="bom-items">
      <span class="bom-empty">暂无硬件</span>
    </div>
  `;
}

function renderBomChip({ name, role, quantity, status }) {
  return `
    <span class="bom-chip">
      <strong>${escapeHtml(name)}${Number(quantity) > 1 ? ` x${Number(quantity)}` : ''}</strong>
      <em>${escapeHtml([role, status].filter(Boolean).join(' · '))}</em>
    </span>
  `;
}

function findHardwareProfile(id) {
  return state.hardware.find((item) => item.id === id);
}

function renderHardwareProfileDetails(profile) {
  return `
    <details class="hardware-profile-details">
      <summary>Profile 详情</summary>
      <dl>
        <div>
          <dt>ID</dt>
          <dd>${escapeHtml(profile.id)}</dd>
        </div>
        <div>
          <dt>坐标系</dt>
          <dd>${escapeHtml(formatCoordinateSystem(profile.coordinate_system))}</dd>
        </div>
        <div>
          <dt>安装</dt>
          <dd>${escapeHtml(formatMounting(profile.mounting))}</dd>
        </div>
        <div>
          <dt>开孔</dt>
          <dd>${escapeHtml(formatOpenings(profile.opening))}</dd>
        </div>
        <div>
          <dt>避让</dt>
          <dd>${escapeHtml(formatKeepouts(profile.keepouts))}</dd>
        </div>
        <div>
          <dt>参考模型</dt>
          <dd>${escapeHtml(formatCadReference(profile.cad_reference))}</dd>
        </div>
      </dl>
      <pre>${escapeHtml(JSON.stringify(compactProfileForCopy(profile), null, 2))}</pre>
    </details>
  `;
}

function formatCoordinateSystem(coordinateSystem = {}) {
  if (!coordinateSystem || typeof coordinateSystem !== 'object') return '未填写';
  return [
    coordinateSystem.origin ? `原点 ${coordinateSystem.origin}` : '',
    coordinateSystem.x_axis ? `X: ${coordinateSystem.x_axis}` : '',
    coordinateSystem.y_axis ? `Y: ${coordinateSystem.y_axis}` : '',
    coordinateSystem.positive_z ? `+Z: ${coordinateSystem.positive_z}` : '',
  ].filter(Boolean).join('；') || '未填写';
}

function formatMounting(mounting = {}) {
  if (!mounting || typeof mounting !== 'object') return '未填写';
  return [
    mounting.mode ? `方式 ${mounting.mode}` : '',
    mounting.preferred_enclosure_surface ? `优先安装面 ${mounting.preferred_enclosure_surface}` : '',
    mounting.mating_hardware_face ? `贴合面 ${mounting.mating_hardware_face}` : '',
    Number.isFinite(Number(mounting.clearance_mm)) ? `间隙 ${Number(mounting.clearance_mm)} mm` : '',
  ].filter(Boolean).join('；') || '未填写';
}

function formatOpenings(openings = []) {
  if (!Array.isArray(openings) || !openings.length) return '无';
  return openings.map((opening) => {
    const size = openingSizeText(opening);
    return `${opening.id || opening.type || 'opening'}：${opening.type || 'unknown'}，${opening.preferred_face || '未指定面'}${size ? `，${size}` : ''}`;
  }).join('；');
}

function formatKeepouts(keepouts = []) {
  if (!Array.isArray(keepouts) || !keepouts.length) return '无';
  return keepouts.map((keepout) => {
    const size = keepout.size_mm
      ? `${Number(keepout.size_mm.length_x || 0)} x ${Number(keepout.size_mm.width_y || 0)} x ${Number(keepout.size_mm.height_z || 0)} mm`
      : keepout.diameter_mm
        ? `直径 ${Number(keepout.diameter_mm)} mm，高 ${Number(keepout.height_z || 0)} mm`
        : '';
    return `${keepout.id || keepout.shape || 'keepout'}：${keepout.shape || 'unknown'}${size ? `，${size}` : ''}`;
  }).join('；');
}

function formatCadReference(cadReference = {}) {
  if (!cadReference || typeof cadReference !== 'object') return '未填写';
  return [
    cadReference.shape ? `shape ${cadReference.shape}` : '',
    cadReference.color ? `color ${cadReference.color}` : '',
  ].filter(Boolean).join('；') || '未填写';
}

function openingSizeText(opening = {}) {
  if (opening.size_mm) {
    return `${Number(opening.size_mm.width || opening.size_mm.length_x || 0)} x ${Number(opening.size_mm.height || opening.size_mm.width_y || 0)} mm`;
  }
  if (opening.diameter_mm) return `直径 ${Number(opening.diameter_mm)} mm`;
  if (opening.slot_mm) {
    return `槽 ${Number(opening.slot_mm.width || 0)} x ${Number(opening.slot_mm.length || 0)} mm`;
  }
  return '';
}

function compactProfileForCopy(profile) {
  return {
    id: profile.id,
    name: profile.name,
    category: profile.category,
    roles: profile.roles || [],
    hardware_system: profile.hardware_system || 'common',
    model_type: profile.model_type || hardwareModelTypeOf(profile),
    aliases: profile.aliases || [],
    model_quality: profile.model_quality || null,
    dimensions_mm: profile.dimensions_mm || {},
    coordinate_system: profile.coordinate_system || {},
    mounting: profile.mounting || {},
    opening: profile.opening || [],
    keepouts: profile.keepouts || [],
    cad_reference: profile.cad_reference || {},
    source_status: profile.source_status || '',
  };
}

function openCustomHardwareLibrary() {
  state.hardwareDrawerOpen = true;
  state.activeHardwareSystemTab = 'user_custom';
  state.customHardwareWorkbenchOpen = false;
  renderDrawerState();
  renderHardwareSystemTabs();
  renderCategoryFilter();
  renderHardwareList();
}

function openCustomHardwareWorkbench() {
  state.hardwareDrawerOpen = true;
  state.activeHardwareSystemTab = 'user_custom';
  state.customHardwareWorkbenchOpen = true;
  renderDrawerState();
  renderHardwareSystemTabs();
  renderCategoryFilter();
  renderHardwareList();
  els.customHardwareName?.focus();
}

function handleCustomHardwarePanelClick(event) {
  const typeButton = event.target.closest('[data-custom-hardware-type]');
  if (typeButton) {
    const nextType = typeButton.dataset.customHardwareType || 'electronic';
    if (nextType !== state.activeCustomHardwareType) {
      state.activeCustomHardwareType = nextType;
      invalidateCustomHardwarePreview();
    }
    renderCustomHardwareList();
    renderHardwareList();
    return;
  }
  if (event.target.closest('#customHardwareBackButton')) {
    state.customHardwareWorkbenchOpen = false;
    renderHardwareSystemTabs();
    renderCategoryFilter();
    renderHardwareList();
    return;
  }
  if (event.target.closest('#previewCustomHardwareButton')) {
    previewCustomHardware();
    return;
  }
  if (event.target.closest('#confirmCustomHardwareButton')) {
    confirmCustomHardware();
  }
}

async function previewCustomHardware() {
  if (state.isBusy) return;
  const body = buildCustomHardwareRequestBody();
  if (!body.name || !body.description) {
    setCustomHardwareStatus('请先填写硬件名称和自然语言描述。', 'error');
    return;
  }
  const formRevision = state.customHardwareFormRevision;
  state.isBusy = true;
  setCustomHardwareStatus('正在生成预览...', 'loading');
  renderCustomHardwareWorkbenchState();
  try {
    const result = await api('/api/custom-hardware/preview', {
      method: 'POST',
      body,
    });
    if (formRevision !== state.customHardwareFormRevision) {
      setCustomHardwareStatus('硬件信息已修改，刚才的预览结果已失效，请重新预览。', 'warning');
      return;
    }
    const hasPreviewStl = hasUsableCustomHardwarePreview(result.preview_artifact);
    state.customHardwarePreview = result.status === 'custom_hardware_preview' && hasPreviewStl ? result : null;
    state.customHardwarePreviewFailure = hasPreviewStl ? null : result;
    const statusTone = state.customHardwarePreview
      ? (isCustomHardwareCommitReady(state.customHardwarePreview) ? 'success' : 'warning')
      : 'error';
    setCustomHardwareStatus(customHardwareFeedbackText(result), statusTone);
    if (state.customHardwarePreview) {
      state.viewerNotice = null;
      state.viewerSourceKey = '';
      state.exportResult = null;
      state.artifact = result.preview_artifact;
      state.draft = null;
      state.requirementAnalysis = null;
      state.partialBom = result.preview_artifact.bom || [];
      state.cadqueryBuild = { status: 'artifact_exports', message: '自定义硬件预览已生成。' };
      state.activeView = 'preview';
      state.previewMode = 'assembly';
      bumpPreviewRevision();
      renderAll();
    } else {
      state.artifact = null;
      state.cadqueryBuild = {
        status: result.status || 'needs_input',
        message: result.message || '自定义硬件预览未生成。',
        blocking_reason: result.blocking_reason || '',
      };
      state.activeView = 'preview';
      clearModelPreview();
      renderPreview();
      renderChecks();
    }
  } catch (error) {
    setCustomHardwareStatus(humanizeCustomHardwareFeedback(error.message), 'error');
  } finally {
    state.isBusy = false;
    renderCustomHardwareWorkbenchState();
  }
}

async function confirmCustomHardware() {
  if (state.isBusy) return;
  const preview = state.customHardwarePreview;
  if (!preview) {
    setCustomHardwareStatus('请先生成可预览的自定义硬件模型，再确认写入。', 'error');
    return;
  }
  if (!isCustomHardwareCommitReady(preview)) {
    setCustomHardwareStatus('模型可预览，资料尚不可入库。请补充缺失信息并重新预览。', 'warning');
    renderCustomHardwareWorkbenchState();
    return;
  }
  state.isBusy = true;
  setCustomHardwareStatus('正在写入用户自定义硬件库...', 'loading');
  renderCustomHardwareWorkbenchState();
  try {
    const result = await api('/api/custom-hardware/commit', {
      method: 'POST',
      body: {
        profile: preview.profile_draft,
        cadquery_code: preview.cadquery_code,
        thumbnail_data_url: state.customHardwareThumbnailDataUrl,
      },
    });
    setCustomHardwareStatus(result.message || '已写入用户自定义硬件库。', 'success');
    if (result.profile?.id) state.selectedHardwareIds.add(result.profile.id);
    state.customHardwarePreview = null;
    state.customHardwarePreviewFailure = null;
    state.customHardwareWorkbenchOpen = false;
    await loadHardwareLibrary();
    state.activeHardwareSystemTab = 'user_custom';
    renderAll();
  } catch (error) {
    setCustomHardwareStatus(humanizeCustomHardwareFeedback(error.message), 'error');
  } finally {
    state.isBusy = false;
    renderCustomHardwareWorkbenchState();
  }
}

async function confirmDeleteCustomHardware(id) {
  if (!id || !id.startsWith('user_custom_')) return;
  const profile = state.hardware.find((item) => item.id === id);
  const name = profile?.name || id;
  const ok = window.confirm(`确定彻底删除用户自定义硬件“${name}”吗？此操作会从自定义硬件库移除该硬件。`);
  if (!ok) return;
  try {
    const result = await api(`/api/custom-hardware/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
    state.selectedHardwareIds.delete(id);
    if (state.customHardwarePreview?.profile_draft?.id === id) state.customHardwarePreview = null;
    if (state.artifact?.bom?.some((item) => item.hardware_id === id)) {
      state.artifact = null;
      state.partialBom = null;
      state.cadqueryBuild = null;
      clearModelPreview();
    }
    await loadHardwareLibrary();
    state.activeHardwareSystemTab = 'user_custom';
    state.customHardwareWorkbenchOpen = false;
    setCustomHardwareStatus(result.message || '已删除用户自定义硬件。', 'success');
    renderAll();
  } catch (error) {
    setCustomHardwareStatus(error.message, 'error');
  }
}

function buildCustomHardwareRequestBody() {
  return {
    name: els.customHardwareName?.value.trim() || '',
    custom_hardware_type: state.activeCustomHardwareType,
    description: els.customHardwareInput?.value.trim() || '',
    thumbnail_data_url: state.customHardwareThumbnailDataUrl || '',
    conversation: state.customHardwareConversation,
  };
}

function invalidateCustomHardwarePreview() {
  const hadPreview = Boolean(state.customHardwarePreview || state.customHardwarePreviewFailure);
  state.customHardwareFormRevision += 1;
  state.customHardwarePreview = null;
  state.customHardwarePreviewFailure = null;
  if (hadPreview) {
    if (state.artifact?.source === 'custom_hardware_builder') {
      state.artifact = null;
      state.partialBom = null;
      state.cadqueryBuild = null;
      state.exportResult = null;
      state.viewerSourceKey = '';
      clearModelPreview();
      renderBomSummary();
      renderRightPane();
      renderPreview();
      renderChecks();
      renderExportLinks();
    }
    setCustomHardwareStatus('硬件名称、类型或描述已修改，请重新生成预览。', 'warning');
  }
  renderCustomHardwareWorkbenchState();
}

function isCustomHardwareCommitReady(preview = state.customHardwarePreview) {
  return Boolean(
    preview
    && preview.commit_ready === true
    && isPlainObject(preview.profile_draft)
    && typeof preview.cadquery_code === 'string'
    && preview.cadquery_code.trim(),
  );
}

function setCustomHardwareStatus(text, tone = '') {
  if (!els.customHardwareStatus) return;
  const validTone = ['loading', 'success', 'warning', 'error'].includes(tone) ? tone : '';
  els.customHardwareStatus.textContent = text || '';
  els.customHardwareStatus.className = ['custom-hardware-status', validTone ? `is-${validTone}` : ''].filter(Boolean).join(' ');
}

function customHardwareFeedbackText(result = {}) {
  const base = humanizeCustomHardwareFeedback(result.user_feedback || result.message || '');
  const missing = Array.isArray(result.commit_missing_fields)
    ? result.commit_missing_fields.map(humanizeCustomHardwareIssue).filter(Boolean)
    : [];
  if (result.status === 'custom_hardware_preview' && !isCustomHardwareCommitReady(result)) {
    const details = missing.length
      ? `还需要补齐：${missing.join('、')}`
      : base || '入库草案或模型源码不完整，请重新生成预览。';
    return `模型可预览，资料尚不可入库。 ${details}`;
  }
  return base;
}

function humanizeCustomHardwareFeedback(text) {
  let result = String(text || '').trim();
  if (!result) return '';
  const replacements = [
    [/mounting\.clearance_mm/g, '固定结构与外壳或安装面之间预留的安装间隙'],
    [/mounting\.preferred_enclosure_surface/g, '硬件默认固定在盒子的哪个位置'],
    [/mounting\.mating_hardware_face/g, '硬件本体贴合外壳或固定结构的那一面'],
    [/mounting\.holes\[(\d+)\]\.x/g, (_, index) => `第 ${Number(index) + 1} 个固定孔相对硬件中心的 X 坐标`],
    [/mounting\.holes\[(\d+)\]\.y/g, (_, index) => `第 ${Number(index) + 1} 个固定孔相对硬件中心的 Y 坐标`],
    [/mounting\.holes\[(\d+)\]\.diameter_mm/g, (_, index) => `第 ${Number(index) + 1} 个固定孔的直径`],
    [/opening\[(\d+)\]\.preferred_face/g, (_, index) => `第 ${Number(index) + 1} 个外壳开孔所在的盒子面`],
    [/opening\[(\d+)\]\.clearance_mm/g, (_, index) => `第 ${Number(index) + 1} 个外壳开孔四周的装配余量`],
    [/opening\[(\d+)\]\.size_mm\.width/g, (_, index) => `第 ${Number(index) + 1} 个外壳开孔的宽度`],
    [/opening\[(\d+)\]\.size_mm\.height/g, (_, index) => `第 ${Number(index) + 1} 个外壳开孔的高度`],
    [/keepouts\[(\d+)\]\.center_mm/g, (_, index) => `第 ${Number(index) + 1} 个避让空间的位置`],
    [/keepouts\[(\d+)\]\.size_mm/g, (_, index) => `第 ${Number(index) + 1} 个避让空间的尺寸`],
  ];
  for (const [pattern, replacement] of replacements) {
    result = result.replace(pattern, replacement);
  }
  if (containsCustomHardwareFieldPath(result)) {
    return '还需要补充写入硬件库所需的尺寸、安装、开孔或避让信息，请用自然语言描述。';
  }
  return result;
}

function humanizeCustomHardwareIssue(issue) {
  const text = String(issue || '').trim();
  if (!text) return '';
  if (/mounting\.clearance_mm/.test(text)) return '还需要说明固定结构与外壳或安装面之间预留多少安装间隙，单位 mm。';
  if (/mounting\.preferred_enclosure_surface/.test(text)) return '还需要说明这个硬件默认固定在盒子的哪个位置，例如底部、上盖内侧或上盖外侧。';
  if (/mounting\.mating_hardware_face/.test(text)) return '还需要说明硬件本体的哪一面贴合外壳或固定结构，例如底面、背面或侧面。';
  if (/mounting\.holes(?:\[\d+\]|\[\])?\.(?:x|y)/.test(text)) return '还需要说明固定孔相对硬件中心的 X/Y 坐标，单位 mm。';
  if (/opening(?:\[\d+\])?\.size_mm\.(?:width|height)/.test(text)) return '还需要说明外壳开孔的宽度和高度，单位 mm。';
  if (/keepouts(?:\[\d+\])?\.(?:center_mm|size_mm)/.test(text)) return '还需要说明避让空间的位置和尺寸，单位 mm。';
  return humanizeCustomHardwareFeedback(text);
}

function containsCustomHardwareFieldPath(text) {
  return /(?:mounting|opening|keepouts|dimensions_mm|coordinate_system|cadquery_model|cadquery_code|hardware_system|custom_hardware_type|source_status|cad_reference)(?:[\w.[\]]*)?/.test(String(text || ''));
}

async function handleCustomHardwareThumbnailChange() {
  const file = els.customHardwareThumbnail?.files?.[0];
  state.customHardwareThumbnailDataUrl = '';
  if (!file) return;
  if (file.type !== 'image/png') {
    setCustomHardwareStatus('缩略图请上传 PNG 文件。', 'error');
    els.customHardwareThumbnail.value = '';
    return;
  }
  state.customHardwareThumbnailDataUrl = await readFileAsDataUrl(file);
  setCustomHardwareStatus('缩略图已选择。', 'success');
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('读取缩略图失败。'));
    reader.readAsDataURL(file);
  });
}

function validateCustomProfile(profile) {
  if (!isPlainObject(profile)) throw new Error('profile 必须是 JSON 对象');
  for (const key of ['id', 'name', 'category', 'dimensions_mm', 'coordinate_system', 'mounting', 'opening', 'keepouts', 'cad_reference', 'source_status']) {
    if (!(key in profile)) throw new Error(`缺少字段：${key}`);
  }
  for (const key of ['id', 'name', 'category', 'source_status']) {
    requireNonEmptyString(profile[key], key);
  }
  if (!isPlainObject(profile.dimensions_mm)) throw new Error('dimensions_mm 必须是对象');
  for (const key of ['length_x', 'width_y', 'height_z']) {
    requirePositiveNumber(profile.dimensions_mm?.[key], `dimensions_mm.${key}`);
  }
  if (!isPlainObject(profile.coordinate_system)) throw new Error('coordinate_system 必须是对象');
  for (const key of ['origin', 'x_axis', 'y_axis', 'positive_z']) {
    requireNonEmptyString(profile.coordinate_system?.[key], `coordinate_system.${key}`);
  }
  if (!isPlainObject(profile.mounting)) throw new Error('mounting 必须是对象');
  if (!Array.isArray(profile.opening)) throw new Error('opening 必须是数组');
  validateCustomMounting(profile.mounting);
  profile.opening.forEach(validateCustomOpening);
  if (Array.isArray(profile.keepouts)) profile.keepouts.forEach(validateCustomKeepout);
  if (!Array.isArray(profile.keepouts)) throw new Error('keepouts 必须是数组');
  if (!isPlainObject(profile.cad_reference)) throw new Error('cad_reference 必须是对象');
}

function validateCustomOpening(opening, index) {
  const path = `opening[${index}]`;
  if (!isPlainObject(opening)) throw new Error(`${path} 必须是对象`);
  requireNonEmptyString(opening.id, `${path}.id`);
  requireNonEmptyString(opening.type, `${path}.type`);
  requireNonEmptyString(opening.basis, `${path}.basis`);
  requireNonEmptyString(opening.preferred_face, `${path}.preferred_face`);
  requireNonNegativeNumber(opening.clearance_mm, `${path}.clearance_mm`);
  validateOptionalVector3(opening.center_mm, `${path}.center_mm`);
  validateOptionalVector3(opening.offset_mm, `${path}.offset_mm`);
  if (['rectangular_cutout', 'rectangular_window'].includes(opening.type)) {
    requirePositiveNumber(opening.size_mm?.width, `${path}.size_mm.width`);
    requirePositiveNumber(opening.size_mm?.height, `${path}.size_mm.height`);
  } else if (opening.type === 'round_hole') {
    requirePositiveNumber(opening.diameter_mm ?? opening.size_mm?.diameter, `${path}.diameter_mm`);
  } else if (opening.type === 'hole_array') {
    requirePositiveNumber(opening.diameter_mm ?? opening.size_mm?.diameter, `${path}.diameter_mm`);
    requirePositiveNumber(opening.count ?? opening.size_mm?.count, `${path}.count`);
    requirePositiveNumber(opening.pitch_mm ?? opening.size_mm?.pitch, `${path}.pitch_mm`);
  } else if (opening.type === 'slot_array') {
    requirePositiveNumber(opening.slot_mm?.length ?? opening.size_mm?.length ?? opening.size_mm?.length_x, `${path}.slot_mm.length`);
    requirePositiveNumber(opening.slot_mm?.width ?? opening.size_mm?.width ?? opening.size_mm?.width_y, `${path}.slot_mm.width`);
    requirePositiveNumber(opening.count ?? opening.size_mm?.count, `${path}.count`);
    requirePositiveNumber(opening.pitch_mm ?? opening.size_mm?.pitch, `${path}.pitch_mm`);
  } else {
    throw new Error(`${path}.type 不受支持`);
  }
}

function validateOptionalVector3(value, label) {
  if (value === undefined || value === null) return;
  if (!isPlainObject(value)) throw new Error(`${label} must be a JSON object`);
  for (const key of ['x', 'y', 'z']) {
    requireFiniteNumber(value?.[key], `${label}.${key}`);
  }
}

function validateCustomMounting(mounting) {
  for (const key of ['mode', 'mating_hardware_face', 'preferred_enclosure_surface']) {
    requireNonEmptyString(mounting?.[key], `mounting.${key}`);
  }
  if (!['base_floor', 'lid_inner', 'lid_outer'].includes(String(mounting.preferred_enclosure_surface || ''))) {
    throw new Error('mounting.preferred_enclosure_surface must be base_floor, lid_inner or lid_outer');
  }
  requirePositiveNumber(mounting.clearance_mm, 'mounting.clearance_mm');
  if ('retainer_height_mm' in mounting) requireNonNegativeNumber(mounting.retainer_height_mm, 'mounting.retainer_height_mm');
}

function validateCustomKeepout(keepout, index) {
  const path = `keepouts[${index}]`;
  if (!isPlainObject(keepout)) throw new Error(`${path} must be a JSON object`);
  requireNonEmptyString(keepout.id, `${path}.id`);
  requireNonEmptyString(keepout.shape, `${path}.shape`);
  if (!isPlainObject(keepout.center_mm)) throw new Error(`${path}.center_mm must be an object`);
  for (const key of ['x', 'y', 'z']) {
    requireFiniteNumber(keepout.center_mm?.[key], `${path}.center_mm.${key}`);
  }
  if (keepout.shape === 'box') {
    if (!isPlainObject(keepout.size_mm)) throw new Error(`${path}.size_mm must be an object`);
    for (const key of ['length_x', 'width_y', 'height_z']) {
      requirePositiveNumber(keepout.size_mm?.[key], `${path}.size_mm.${key}`);
    }
  } else if (keepout.shape === 'cylinder') {
    requirePositiveNumber(keepout.diameter_mm, `${path}.diameter_mm`);
    requirePositiveNumber(keepout.height_z, `${path}.height_z`);
  } else {
    throw new Error(`${path}.shape is not supported`);
  }
}

function requireNonEmptyString(value, label) {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label} 必须是非空文本`);
}

function requirePositiveNumber(value, label) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) throw new Error(`${label} 必须是大于 0 的数字`);
}

function requireNonNegativeNumber(value, label) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) throw new Error(`${label} must be a number >= 0`);
}

function requireFiniteNumber(value, label) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error(`${label} must be a number`);
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function renderCustomHardwareList() {
  if (!els.customHardwareList) return;
  renderCustomHardwareWorkbenchState();
  const profiles = state.hardware
    .filter((profile) => hardwareSystemOf(profile) === 'user_custom')
    .filter((profile) => (profile.custom_hardware_type || 'electronic') === state.activeCustomHardwareType);
  if (!profiles.length) {
    els.customHardwareList.innerHTML = '';
    return;
  }
  els.customHardwareList.innerHTML = profiles
    .map((profile) => {
      const selected = state.selectedHardwareIds.has(profile.id);
      const d = profile.dimensions_mm || {};
      return `
        <article class="custom-profile-row ${selected ? 'selected' : ''}">
          <div>
            <strong>${escapeHtml(profile.name || profile.id)}</strong>
            <span>${escapeHtml(profile.category || 'custom')} · ${Number(d.length_x || 0)} x ${Number(d.width_y || 0)} x ${Number(d.height_z || 0)} mm</span>
          </div>
          <button type="button" data-hardware-id="${escapeHtml(profile.id)}">${selected ? '移除' : '加入 BOM'}</button>
        </article>
      `;
    })
    .join('');
  els.customHardwareList.querySelectorAll('button[data-hardware-id]').forEach((button) => {
    button.addEventListener('click', () => {
      toggleHardwareSelection(button.dataset.hardwareId);
    });
  });
}

function renderCustomHardwareWorkbenchState() {
  els.customHardwarePanel?.querySelectorAll('[data-custom-hardware-type]').forEach((button) => {
    button.classList.toggle('active', button.dataset.customHardwareType === state.activeCustomHardwareType);
  });
  if (els.customHardwareHints) {
    els.customHardwareHints.innerHTML = state.activeCustomHardwareType === 'structural'
      ? '<strong>关键信息</strong><span>结构件请说明用途、外形尺寸、壁厚、连接方式、孔槽/卡扣/口袋、受力或可拆装方向。</span>'
      : '<strong>关键信息</strong><span>电子器件请说明长宽厚、主体形状、固定孔/卡槽、接口或开孔、安装面、线缆/接线座避让。</span>';
  }
  if (els.previewCustomHardwareButton) {
    els.previewCustomHardwareButton.disabled = state.isBusy;
  }
  if (els.confirmCustomHardwareButton) {
    const commitEnabled = !state.isBusy && isCustomHardwareCommitReady();
    els.confirmCustomHardwareButton.disabled = !commitEnabled;
    els.confirmCustomHardwareButton.setAttribute('aria-disabled', commitEnabled ? 'false' : 'true');
    els.confirmCustomHardwareButton.title = commitEnabled
      ? '将当前预览写入硬件库'
      : '请先生成资料完整、可写入硬件库的预览';
  }
}

function renderNeedsInput(result) {
  els.checksView.innerHTML = renderNeedsInputContent(result);
  state.activeView = isSurfaceEngravingResponse(result) && state.artifact
    ? 'preview'
    : 'checks';
  renderActiveView();
}

function visibleHardwareForMode(hardware, mode) {
  if (mode === 'base') return hardware.filter((item) => item.surface === 'base_floor');
  if (mode === 'lid') return hardware.filter((item) => ['lid_inner', 'lid_outer'].includes(item.surface));
  return [...hardware].sort((a, b) => {
    if (a.surface === b.surface) return 0;
    return a.surface === 'base_floor' ? 1 : -1;
  });
}

function hardwareLayerOffset(hw, mode, outer, scale) {
  return { x: 0, y: 0 };
}

function drawHardware(svg, hw, cx, cy, scale, options = {}) {
  const colors = {
    controller: '#68a67d',
    controller_expansion: '#b79b5b',
    '主控扩展版': '#b79b5b',
    display: '#4b93a5',
    sensor_expansion_board: '#7dbbc4',
    actuator: '#d48664',
    button: '#c3a35b',
    speaker: '#9d7bb0',
    sensor: '#d48664',
    power: '#7b8790',
  };
  const w = hw.size.length_x * scale;
  const h = hw.size.width_y * scale;
  const x = cx + hw.center.x * scale - w / 2;
  const y = cy - hw.center.y * scale - h / 2;
  addSvgRect(svg, x, y, w, h, 5, colors[hw.category] || '#9aa7b0', '#26343d', 1, options);
  addSvgText(svg, x + 5, y + Math.min(18, h - 3), hw.name.replace(/^Seeed Studio /, ''), 'svg-label');
}

function drawOpening(svg, opening, cx, cy, scale) {
  const x = cx + (opening.center.x || 0) * scale;
  const y = cy - (opening.center.y || 0) * scale;
  const size = openingPreviewSize(opening);
  if (/round|hole_array/.test(opening.type)) {
    addSvgCircle(svg, x, y, Math.max(4, size.width_y * scale / 2), '#ffffff', '#b44a3c');
  } else {
    const width = Math.max(8, size.length_x * scale);
    const height = Math.max(6, size.width_y * scale);
    addSvgRect(svg, x - width / 2, y - height / 2, width, height, 2, '#ffffff', '#b44a3c', 2);
  }
}

function drawMount(svg, mount, cx, cy, scale) {
  const size = mount.size_mm || {};
  const width = Math.max(8, Number(size.length_x || 0) * scale);
  const height = Math.max(6, Number(size.width_y || 0) * scale);
  const x = cx + Number(mount.center?.x || 0) * scale - width / 2;
  const y = cy - Number(mount.center?.y || 0) * scale - height / 2;
  addSvgRect(svg, x, y, width, height, 3, '#f2d47a', '#7a6120', 1);
}

function openingPreviewSize(opening) {
  const size = opening.size_mm || {};
  const diameter = Number(size.diameter || opening.diameter_mm || 0);
  if (diameter > 0) {
    const count = Number(size.count || opening.count || 1);
    const pitch = Number(size.pitch || size.pitch_mm || opening.pitch_mm || diameter || 1);
    return {
      length_x: diameter + Math.max(0, count - 1) * pitch,
      width_y: diameter,
    };
  }
  const footprint = {
    length_x: Number(size.width || size.length_x || opening.width_mm || opening.slot_mm?.width || 10),
    width_y: Number(size.height || size.width_y || opening.height_mm || opening.slot_mm?.height || 6),
  };
  if (Number(opening.layout_rotation_deg || 0) % 180 !== 0) {
    return {
      length_x: footprint.width_y,
      width_y: footprint.length_x,
    };
  }
  return footprint;
}

function addMessage(kind, title, body, bullets = [], extraHtml = '') {
  const item = document.createElement('div');
  item.className = `message ${kind}`;
  item.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    <div>${escapeHtml(body || '').replace(/\n/g, '<br />')}</div>
    ${bullets.length ? `<ul>${bullets.map((bullet) => `<li>${escapeHtml(bullet)}</li>`).join('')}</ul>` : ''}
    ${extraHtml}
  `;
  els.messages.appendChild(item);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function addSvgRect(svg, x, y, width, height, radius, fill, stroke, strokeWidth, options = {}) {
  const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  rect.setAttribute('x', x);
  rect.setAttribute('y', y);
  rect.setAttribute('width', Math.max(1, width));
  rect.setAttribute('height', Math.max(1, height));
  rect.setAttribute('rx', radius);
  rect.setAttribute('fill', fill);
  rect.setAttribute('stroke', stroke);
  rect.setAttribute('stroke-width', strokeWidth);
  if (options.dashed) rect.setAttribute('stroke-dasharray', '6 4');
  if (options.ghost) rect.setAttribute('fill-opacity', '0.74');
  svg.appendChild(rect);
}

function addSvgCircle(svg, x, y, radius, fill, stroke) {
  const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  circle.setAttribute('cx', x);
  circle.setAttribute('cy', y);
  circle.setAttribute('r', radius);
  circle.setAttribute('fill', fill);
  circle.setAttribute('stroke', stroke);
  svg.appendChild(circle);
}

function addSvgText(svg, x, y, text, className) {
  const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  label.setAttribute('x', x);
  label.setAttribute('y', y);
  label.setAttribute('class', className);
  label.textContent = text;
  svg.appendChild(label);
}

function emptySvg(text) {
  return `
    <rect x="20" y="20" width="780" height="480" rx="8" fill="#f8fafb" stroke="#d5dde3" />
    <text x="410" y="260" text-anchor="middle" class="svg-label">${escapeHtml(text)}</text>
  `;
}

async function api(path, options = {}) {
  let response = null;
  try {
    response = await fetch(path, {
      method: options.method || 'GET',
      headers: options.body ? { 'Content-Type': 'application/json' } : {},
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch (error) {
    const message = normalizeRequestError(error);
    throw new Error(message);
  }
  const text = await response.text().catch(() => '');
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text };
  }
  if (!response.ok) {
    const reason = data.blocking_reason ? `（${data.blocking_reason}）` : '';
    throw new Error(data.message || data.error || `后端返回异常${reason}：HTTP ${response.status}`);
  }
  return data;
}

function normalizeRequestError(error) {
  const text = error instanceof Error ? `${error.message || ''} ${error.name || ''}`.trim() : String(error || '');
  if (/AbortError|aborted/i.test(text)) {
    return '请求被中断或超时，请重试，或检查模型服务响应时间与网络。';
  }
  if (/Failed to fetch|NetworkError|fetch/i.test(text)) {
    return '请求失败：前端无法连接到后端服务，请检查 ZW-CAD-intent 是否已启动，以及浏览器是否能访问当前地址。';
  }
  return `请求失败：${error instanceof Error ? error.message : String(error)}`;
}

function flattenParameters(groups) {
  const result = {};
  for (const [key, values] of Object.entries(groups || {})) {
    if (values && typeof values === 'object' && !Array.isArray(values)) {
      Object.assign(result, values);
    } else {
      result[key] = values;
    }
  }
  return result;
}

function currentDefaultParameterValues() {
  const source = state.artifact?.project_default_parameters
    || state.artifact?.default_parameters
    || state.artifact?.design_state?.project_default_parameters
    || state.artifact?.design_state?.default_parameters
    || state.draft?.design_state?.project_default_parameters
    || state.draft?.design_state?.default_parameters
    || null;
  return flattenParameters(source || {});
}

function parameterDefaultInfo(key, fallbackValue) {
  const defaults = currentDefaultParameterValues();
  const hasDefault = Object.prototype.hasOwnProperty.call(defaults, key);
  const value = Number(defaults[key]);
  const fallback = Number(fallbackValue);
  if (!hasDefault || !Number.isFinite(value) || !isValidParameterDefault(key, value, fallback)) {
    return {
      hasDefault: false,
      value: Number.isFinite(fallback) ? fallback : value,
    };
  }
  return { hasDefault: true, value };
}

function defaultValueForParameter(key, fallbackValue) {
  return parameterDefaultInfo(key, fallbackValue).value;
}

function isValidParameterDefault(key, defaultValue, currentValue) {
  const current = Number(currentValue);
  if (POSITIVE_DEFAULT_PARAMETER_KEYS.has(key) && Number.isFinite(current) && current > 0) {
    return Number(defaultValue) > 0;
  }
  return true;
}

function parameterValueChanged(currentValue, defaultValue) {
  const current = Number(currentValue);
  const fallback = Number(defaultValue);
  if (!Number.isFinite(current) || !Number.isFinite(fallback)) return false;
  return Math.abs(current - fallback) > 0.000001;
}

function collectParameterOverridesFromInputs() {
  els.parameterGroups.querySelectorAll('input[data-param]').forEach((input) => {
    state.parameterOverrides[input.dataset.param] = Number(input.value);
  });
}

function scheduleParameterRegenerate() {
  if (!state.artifact?.design_state && !state.draft?.design_state) return;
  clearPendingParameterRegenerate();
  state.parameterRegenerateTimer = window.setTimeout(() => {
    state.parameterRegenerateTimer = null;
    if (state.draft?.design_state && !state.artifact) {
      collectParameterOverridesFromInputs();
      prepare(state.lastPrompt || state.draft.design_state.intent?.product_name || '', {
        keepUserAnswers: true,
        automatic: true,
        currentDesignState: state.draft.design_state,
        taskId: currentTaskId(),
      });
      return;
    }
    regenerate({ automatic: true });
  }, PARAMETER_REGENERATE_DELAY_MS);
}

function clearPendingParameterRegenerate() {
  if (!state.parameterRegenerateTimer) return;
  window.clearTimeout(state.parameterRegenerateTimer);
  state.parameterRegenerateTimer = null;
}

function summarizeChecks(checks = []) {
  const counts = checks.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(counts).map(([key, count]) => `${key} ${count}`).join('，');
}

function summarizeFunctionVerification(report = null) {
  if (!report || typeof report !== 'object') return '';
  const status = report.verification_status || report.status || '';
  const attempts = report.attempts_used ? `，尝试 ${report.attempts_used}/${report.max_attempts || 3}` : '';
  const missing = Array.isArray(report.missing_functions) && report.missing_functions.length
    ? `，缺失功能：${report.missing_functions.join('、')}`
    : '';
  const missingHardware = Array.isArray(report.missing_hardware) && report.missing_hardware.length
    ? `，缺失硬件：${report.missing_hardware.map((item) => item.label || item.role || item.hardware_id || item).filter(Boolean).join('、')}`
    : '';
  return `功能验证：${status || 'unknown'}${attempts}${missing}${missingHardware}`;
}

function setBusy(busy) {
  state.isBusy = busy;
  els.promptForm.querySelector('button[type="submit"]').disabled = busy;
  if (els.newTaskButton) els.newTaskButton.disabled = busy;
  els.regenerateButton.disabled = busy || (!state.artifact && !state.draft);
}

function groupLabel(name) {
  return {
    box: '盒体',
    lid: '盖子',
    printing: '打印',
    openings: '开孔',
    layout: '布局',
    hardware: '硬件',
  }[name] || name;
}

function faceLabel(name) {
  return {
    top: '顶部',
    left: '左侧',
    right: '右侧',
    front: '前侧',
    back: '后侧',
    base_floor: '底壳',
    lid_inner: '上盖内侧',
    lid_outer: '上盖外侧',
    external_right: '盒体右侧旁置',
    external_scene: '盒外场景旁置',
  }[name] || name || '未知面';
}

function paramLabel(name) {
  const hardwareOffset = name.match(/^hw_(.+)_offset_([xy])$/);
  if (hardwareOffset) {
    return `${hardwareOffset[1]} ${hardwareOffset[2].toUpperCase()} 偏移`;
  }
  return {
    inner_length_x: '内腔长 X',
    inner_width_y: '内腔宽 Y',
    inner_height_z: '内腔高 Z',
    wall_thickness: '壁厚',
    corner_radius: '圆角半径',
    lid_thickness: '盖厚',
    lid_lip_height: '唇边高度',
    lid_clearance: '盖子配合间隙',
    min_wall_thickness: '最小壁厚',
    clearance: '装配间隙',
    screw_boss_diameter: '螺丝柱直径',
    screw_hole_diameter: '螺丝孔直径',
    usb_c_margin: 'USB-C 开孔余量',
    screen_window_margin: '屏幕窗口余量',
    button_hole_margin: '按钮孔余量',
    vent_count: '通风孔数量',
    hardware_gap: '硬件间距',
    edge_clearance: '边缘安全距离',
  }[name] || name.replace(/_/g, ' ');
}

function normalizeFormat(value) {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}

function exportFormatLabel(format) {
  return {
    all: '全部',
    stl: 'STL',
    gltf: 'glTF',
    json: 'JSON',
    py: '代码',
    step: 'STEP',
  }[format] || format.toUpperCase();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
