// Platform adapter: credentials arrive over the worker pipe, never on disk/argv.
let settings = {};
export function configurePlatformModel(value) { settings = value || {}; }
export function getIntentModelConfig() {
  return { ...settings, enabled: Boolean(settings.baseUrl && settings.model), sourceId: 'platform', sourceName: '掌问 API 设置' };
}
export const getFunctionVerifierConfig = getIntentModelConfig;
export async function requestChatCompletionJson({ messages, temperature = 0, responseFormat, config = getIntentModelConfig() }) {
  if (!config.enabled) throw new Error('请先在掌问 API 设置中配置模型。');
  const deepseek = new URL(config.baseUrl).hostname === 'api.deepseek.com';
  const response = await fetch(config.baseUrl + '/chat/completions', {
    method: 'POST', signal: AbortSignal.timeout(120000),
    headers: { 'Content-Type': 'application/json', ...(config.apiKey ? {Authorization: `Bearer ${config.apiKey}`} : {}) },
    body: JSON.stringify({ model: config.model, messages, temperature, max_tokens: 4096,
      response_format: responseFormat, ...(deepseek ? {thinking: {type: 'disabled'}} : {}) }),
  });
  if (!response.ok) throw new Error(`模型请求失败（${response.status}），请检查 API 设置或稍后重试。`);
  const data = await response.json();
  if (data.choices?.[0]?.finish_reason === 'length') throw new Error('模型回答被截断，请缩小本次需求。');
  const content = data.choices?.[0]?.message?.content;
  if (typeof content !== 'string' || content.length > 80000) throw new Error('模型回答为空或过长。');
  try { return JSON.parse(content); } catch { throw new Error('模型没有返回完整的结构化意图，请重试。'); }
}
export function buildModelNeedsInput(error) {
  return { status: 'needs_input', title: '需要检查模型连接', message: error.message,
    questions: ['请点击 API 设置检查模型连接，然后重新发送。'], blocking_reason: 'llm_unavailable' };
}
