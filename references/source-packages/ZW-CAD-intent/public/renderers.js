export function renderNeedsInputContent(result = {}) {
  return `
    <div class="check-item pending">
      <strong>${escapeHtml(result.title || '需要补充信息')}</strong>
      <p>${escapeHtml(result.message || '')}</p>
      ${renderNeedsInputDetails(result)}
    </div>
  `;
}

export function renderNeedsInputDetails(result = {}) {
  return `
    ${renderNeedsInputQuestions(result.questions)}
    ${renderResolutionOptions(result.resolution_options)}
    ${renderProfileValidationReport(result.profile_validation_report)}
    ${renderGenerationTraceContent(result.generation_trace)}
    ${renderProfileTemplate(result.profile_template, result.required_profile_fields)}
    ${renderPartialBom(result.partial_bom)}
    ${renderMissingHardwareRequests(result.missing_hardware_requests)}
  `;
}

export function renderGenerationTraceContent(trace = null) {
  if (!trace || typeof trace !== 'object') return '';
  const markers = trace.feature_markers && typeof trace.feature_markers === 'object'
    ? trace.feature_markers
    : {};
  const mountingRows = Array.isArray(trace.mounting_by_hardware)
    ? trace.mounting_by_hardware.slice(0, 6)
    : [];
  return `
    <section class="needs-input-section">
      <h2>AI 自检/生成追踪</h2>
      <dl>
        <div><dt>generation_trace</dt><dd>${escapeHtml(trace.schema_version || '')}</dd></div>
        <div><dt>stage</dt><dd>${escapeHtml(trace.stage || '')}</dd></div>
        <div><dt>intent</dt><dd>${escapeHtml(`${trace.intent?.source || ''} / ${trace.intent?.model_status || trace.intent?.status || ''}`)}</dd></div>
        <div><dt>hardware</dt><dd>${escapeHtml(`${trace.hardware?.bom_count ?? trace.hardware?.partial_bom_count ?? 0}`)}</dd></div>
        <div><dt>open/mount/hole</dt><dd>${escapeHtml(`${trace.layout?.opening_count ?? 0} / ${trace.layout?.mounting_count ?? 0} / ${trace.layout?.mounting_hole_count ?? 0}`)}</dd></div>
        <div><dt>validation</dt><dd>${escapeHtml(trace.validation?.validation_status || JSON.stringify(trace.validation?.status_counts || {}))}</dd></div>
      </dl>
      ${renderFeatureMarkers(markers)}
      ${mountingRows.length ? `<ul>${mountingRows.map((item) => `
        <li>${escapeHtml(item.hardware_id || '')}: ${escapeHtml((item.types || []).join(', ') || item.strategy || '')}${item.mounting_hole_count ? ` / holes ${escapeHtml(item.mounting_hole_count)}` : ''}</li>
      `).join('')}</ul>` : ''}
    </section>
  `;
}

export function renderSelfCheckContent(result = null) {
  if (!result || typeof result !== 'object') return '';
  const probes = Array.isArray(result.probes) ? result.probes : [];
  return `
    <section class="needs-input-section">
      <h2>运行自检</h2>
      <dl>
        <div><dt>overall</dt><dd>${escapeHtml(result.overall_status || '')}</dd></div>
        <div><dt>fingerprint</dt><dd>${escapeHtml(result.source_fingerprint?.combined_hash || '')}</dd></div>
      </dl>
      ${renderFeatureMarkers(result.feature_markers)}
      ${probes.length ? `<ul>${probes.map((probe) => `
        <li>${escapeHtml(probe.id || probe.label || '')}: ${escapeHtml(probe.status || '')}${probe.message ? ` - ${escapeHtml(probe.message)}` : ''}</li>
      `).join('')}</ul>` : ''}
      ${Array.isArray(result.recommendations) && result.recommendations.length
        ? `<ul>${result.recommendations.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : ''}
    </section>
  `;
}

export function renderHealthContent(health = null) {
  if (!health || typeof health !== 'object') return '';
  return `
    <section class="needs-input-section">
      <h2>运行状态</h2>
      <dl>
        <div><dt>service</dt><dd>${escapeHtml(`${health.service_identity?.project || health.project || ''} : ${health.service_identity?.port || health.port || ''}`)}</dd></div>
        <div><dt>LLM</dt><dd>${escapeHtml(health.llmConnection?.status || (health.intentModel?.enabled ? 'configured' : 'not_configured'))}</dd></div>
        <div><dt>CadQuery</dt><dd>${escapeHtml(health.environment?.cadqueryAvailable ? 'available' : 'pending')}</dd></div>
        <div><dt>fingerprint</dt><dd>${escapeHtml(health.source_fingerprint?.combined_hash || '')}</dd></div>
      </dl>
      ${renderFeatureMarkers(health.feature_flags)}
    </section>
  `;
}

function renderNeedsInputQuestions(questions = []) {
  if (!Array.isArray(questions) || !questions.length) return '';
  return `
    <section class="needs-input-section">
      <h2>下一步</h2>
      <ul>${questions.map((question) => `<li>${escapeHtml(question)}</li>`).join('')}</ul>
    </section>
  `;
}

function renderResolutionOptions(options = []) {
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
            <button
              type="button"
              data-resolution-option-id="${escapeHtml(option.id || '')}"
              data-resolution-action="${escapeHtml(option.action || '')}"
            >选择</button>
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

function renderPartialBom(partialBom = []) {
  if (!Array.isArray(partialBom) || !partialBom.length) return '';
  return `
    <section class="needs-input-section">
      <h2>已确定 BOM</h2>
      <ul>
        ${partialBom.map((item) => `
          <li>${escapeHtml(item.name || item.hardware_id)}：${escapeHtml(item.role || 'required')}</li>
        `).join('')}
      </ul>
    </section>
  `;
}

function renderProfileValidationReport(report = null) {
  if (!report || typeof report !== 'object' || !Array.isArray(report.profiles) || !report.profiles.length) return '';
  return `
    <section class="needs-input-section">
      <h2>Profile 校验报告</h2>
      ${report.profiles.map((profile) => `
        <article class="missing-hardware-card">
          <h3>${escapeHtml(profile.name || profile.hardware_id || 'profile')}</h3>
          <p>status: ${escapeHtml(profile.status || '')}</p>
          ${renderIssueCategories(profile.issue_categories)}
        </article>
      `).join('')}
    </section>
  `;
}

function renderIssueCategories(categories = {}) {
  if (!categories || typeof categories !== 'object') return '';
  const rows = Object.entries(categories).filter(([, issues]) => Array.isArray(issues) && issues.length);
  if (!rows.length) return '<p>没有发现阻断性字段问题。</p>';
  return `
    <dl>
      ${rows.map(([name, issues]) => `
        <div>
          <dt>${escapeHtml(name)}</dt>
          <dd>${escapeHtml(issues.join(', '))}</dd>
        </div>
      `).join('')}
    </dl>
  `;
}

function renderProfileTemplate(template = null, requiredFields = []) {
  if (!template || typeof template !== 'object') return '';
  return `
    <section class="needs-input-section missing-hardware-list">
      <h2>可填写 Profile 模板</h2>
      ${Array.isArray(requiredFields) && requiredFields.length
        ? `<p>必填字段：${escapeHtml(requiredFields.join(', '))}</p>`
        : ''}
      <details open>
        <summary>Profile JSON</summary>
        <pre>${escapeHtml(JSON.stringify(template, null, 2))}</pre>
      </details>
    </section>
  `;
}

function renderMissingHardwareRequests(requests = []) {
  if (!Array.isArray(requests) || !requests.length) return '';
  return `
    <section class="needs-input-section missing-hardware-list">
      <h2>缺失硬件 Profile</h2>
      ${requests.map((request) => `
        <article class="missing-hardware-card">
          <h3>${escapeHtml(request.label || request.role || '未知硬件')}</h3>
          <p>${escapeHtml(request.why_needed || '')}</p>
          <dl>
            <div>
              <dt>缺失功能</dt>
              <dd>${escapeHtml(request.function || '')}</dd>
            </div>
            <div>
              <dt>角色</dt>
              <dd>${escapeHtml(request.role || '')}</dd>
            </div>
            <div>
              <dt>类别</dt>
              <dd>${escapeHtml(request.category || '')}</dd>
            </div>
            <div>
              <dt>必填字段</dt>
              <dd>${escapeHtml((request.required_profile_fields || []).join(', '))}</dd>
            </div>
          </dl>
          <details>
            <summary>Profile 模板</summary>
            <pre>${escapeHtml(JSON.stringify(request.profile_template || {}, null, 2))}</pre>
          </details>
        </article>
      `).join('')}
    </section>
  `;
}

function renderFeatureMarkers(markers = {}) {
  if (!markers || typeof markers !== 'object') return '';
  const rows = Object.entries(markers)
    .filter(([, value]) => typeof value !== 'object' || value === null)
    .map(([key, value]) => `${key}: ${value}`);
  if (!rows.length) return '';
  return `<ul>${rows.map((line) => `<li>${escapeHtml(line)}</li>`).join('')}</ul>`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
