import { useEffect, useMemo, useState } from "react";
import {
  LLMModelId,
  LLMProviderId,
  ThinkingMode,
  type ConnectionTestRequest,
  type ConnectionTestResult,
  type LLMConfig,
  type LLMModelIdType,
  type LLMProviderIdType,
  type ModelConfig,
  type SaveLLMConfigRequest,
  type ThinkingModeType,
} from "@zhangwen/contracts";
import { useHostAdapter } from "../../platform";

interface LlmSettingsPanelProps {
  config: LLMConfig | null;
  models: ModelConfig[];
  saving: boolean;
  testing: boolean;
  message: string | null;
  error: string | null;
  professionalMode: boolean;
  onSave: (request: SaveLLMConfigRequest) => Promise<void>;
  onClearKey: () => Promise<void>;
  onTest: (request: ConnectionTestRequest) => Promise<ConnectionTestResult>;
}

interface ProviderInfo {
  id: LLMProviderIdType;
  label: string;
  baseUrl: string;
  defaultModel: LLMModelIdType;
  environmentKey: string;
}

const DEFAULT_PROVIDER: ProviderInfo = {
  id: LLMProviderId.DEEPSEEK,
  label: "DeepSeek",
  baseUrl: "https://api.deepseek.com",
  defaultModel: LLMModelId.DEEPSEEK_V4_FLASH,
  environmentKey: "ZHANGWEN_DEEPSEEK_API_KEY",
};

const PROVIDERS: ProviderInfo[] = [
  DEFAULT_PROVIDER,
  {
    id: LLMProviderId.QWEN,
    label: "千问（Qwen）",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    defaultModel: LLMModelId.QWEN_3_7_MAX,
    environmentKey: "ZHANGWEN_QWEN_API_KEY",
  },
  {
    id: LLMProviderId.GLM,
    label: "智谱 GLM",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    defaultModel: LLMModelId.GLM_5_2,
    environmentKey: "ZHANGWEN_GLM_API_KEY",
  },
  {
    id: LLMProviderId.KIMI,
    label: "Kimi",
    baseUrl: "https://api.moonshot.cn/v1",
    defaultModel: LLMModelId.KIMI_K3,
    environmentKey: "ZHANGWEN_KIMI_API_KEY",
  },
];

const FALLBACK_MODELS: ModelConfig[] = [
  model(LLMModelId.DEEPSEEK_V4_FLASH, "DeepSeek V4 Flash", LLMProviderId.DEEPSEEK),
  model(LLMModelId.DEEPSEEK_V4_PRO, "DeepSeek V4 Pro", LLMProviderId.DEEPSEEK),
  model(LLMModelId.QWEN_3_7_MAX, "Qwen 3.7 Max", LLMProviderId.QWEN),
  model(LLMModelId.QWEN_PLUS, "Qwen Plus", LLMProviderId.QWEN),
  model(LLMModelId.GLM_5_2, "GLM-5.2", LLMProviderId.GLM),
  model(LLMModelId.GLM_5_1, "GLM-5.1", LLMProviderId.GLM),
  model(LLMModelId.KIMI_K3, "Kimi K3", LLMProviderId.KIMI),
  model(LLMModelId.KIMI_K2_7_CODE, "Kimi K2.7 Code", LLMProviderId.KIMI),
  model(
    LLMModelId.KIMI_K2_7_CODE_HIGHSPEED,
    "Kimi K2.7 Code Highspeed",
    LLMProviderId.KIMI,
  ),
];

export function LlmSettingsPanel({
  config,
  models,
  saving,
  testing,
  message,
  error,
  professionalMode,
  onSave,
  onClearKey,
  onTest,
}: LlmSettingsPanelProps) {
  const { capabilities, unsupportedMessage } = useHostAdapter();
  const [provider, setProvider] = useState<LLMProviderIdType>(LLMProviderId.DEEPSEEK);
  const [baseUrl, setBaseUrl] = useState(DEFAULT_PROVIDER.baseUrl);
  const [apiKey, setApiKey] = useState("");
  const [defaultModel, setDefaultModel] = useState<LLMModelIdType>(
    LLMModelId.DEEPSEEK_V4_FLASH,
  );
  const [thinkingMode, setThinkingMode] = useState<ThinkingModeType>(ThinkingMode.AUTO);
  const [timeoutSeconds, setTimeoutSeconds] = useState(60);
  const [customModels, setCustomModels] = useState<ModelConfig[]>([]);
  const [customModelId, setCustomModelId] = useState("");
  const [customModelError, setCustomModelError] = useState<string | null>(null);

  const availableModels = useMemo(() => {
    const catalog = models.length ? models : FALLBACK_MODELS;
    const merged = [...catalog, ...customModels].filter((item) => item.provider === provider);
    return merged.filter(
      (item, index) => merged.findIndex((candidate) => candidate.id === item.id) === index,
    );
  }, [customModels, models, provider]);
  const currentCustomModels = customModels.filter((item) => item.provider === provider);
  const providerInfo = PROVIDERS.find((item) => item.id === provider) ?? DEFAULT_PROVIDER;
  const keyConfigured = config?.provider === provider && config.keySaved;

  useEffect(() => {
    if (!config) return;
    setProvider(config.provider);
    setBaseUrl(config.baseUrl);
    setDefaultModel(config.defaultModel);
    setThinkingMode(config.thinkingMode);
    setTimeoutSeconds(config.timeoutSeconds);
    setCustomModels(config.customModels ?? []);
    setCustomModelId("");
    setCustomModelError(null);
    setApiKey("");
  }, [config]);

  useEffect(() => {
    if (availableModels.some((item) => item.id === defaultModel)) return;
    setDefaultModel(availableModels[0]?.id ?? providerInfo.defaultModel);
  }, [availableModels, defaultModel, providerInfo.defaultModel]);

  const request = (): SaveLLMConfigRequest => ({
    provider,
    baseUrl,
    defaultModel,
    customModels,
    thinkingMode,
    reasoningEffort: thinkingMode === ThinkingMode.ENABLED ? "high" : null,
    timeoutSeconds,
    ...(capabilities.credentialStore && apiKey.trim() ? { apiKey: apiKey.trim() } : {}),
  });

  return (
    <form
      className="settings-form"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave(request()).then(
          () => setApiKey(""),
          () => undefined,
        );
      }}
    >
      <section className="settings-service-summary" aria-label="模型服务状态">
        <div>
          <strong>{professionalMode ? providerInfo.label : "云端 LLM"}</strong>
          <span
            className={`settings-service-status settings-service-status-${keyConfigured ? "ready" : "pending"}`}
          >
            {keyConfigured ? "已配置" : "待配置"}
          </span>
        </div>
        <p>
          {keyConfigured
            ? "服务凭据已安全保存，可以测试连接。"
            : professionalMode
              ? "选择服务商并保存 API Key。不同服务商的密钥相互隔离。"
              : "保存服务密钥后即可连接云端模型。服务商与模型参数在专业模式中管理。"}
        </p>
      </section>

      {professionalMode && (
        <div className="settings-primary-grid">
          <label className="settings-field">
            <span>服务商</span>
            <select
              aria-label="服务商"
              value={provider}
              onChange={(event) => {
                const next = PROVIDERS.find((item) => item.id === event.target.value) ?? DEFAULT_PROVIDER;
                setProvider(next.id);
                setBaseUrl(next.baseUrl);
                setDefaultModel(next.defaultModel);
                setApiKey("");
                setCustomModelId("");
                setCustomModelError(null);
              }}
            >
              {PROVIDERS.map((item) => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </select>
          </label>

          <label className="settings-field">
            <span>默认模型</span>
            <select
              aria-label="默认模型"
              value={defaultModel}
              onChange={(event) => setDefaultModel(event.target.value as LLMModelIdType)}
            >
              {availableModels.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}{item.isCustom ? "（自定义）" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {capabilities.credentialStore ? (
        <>
          <label className="settings-field">
            <span>{professionalMode ? "API Key" : "服务密钥"}</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={
                keyConfigured && config?.maskedApiKey
                  ? config.maskedApiKey
                  : professionalMode
                    ? `输入 ${providerInfo.label} API Key`
                    : "输入服务密钥"
              }
              autoComplete="off"
            />
          </label>
          {keyConfigured && <p className="settings-hint">已保存：{config?.maskedApiKey}</p>}
        </>
      ) : (
        <p className="settings-hint" role="status">
          {unsupportedMessage("credentialStore")}
          {professionalMode
            ? ` 后端可通过 ${providerInfo.environmentKey} 配置密钥后重启本地服务。`
            : ""}
        </p>
      )}

      {professionalMode && (
        <details className="settings-advanced">
          <summary>高级参数</summary>
          <div className="settings-advanced-fields">
            <label className="settings-field">
              <span>API Base URL</span>
              <input
                aria-label="API Base URL"
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder={providerInfo.baseUrl}
              />
            </label>

            <label className="settings-field">
              <span>思考模式</span>
              <select
                value={thinkingMode}
                onChange={(event) => setThinkingMode(event.target.value as ThinkingModeType)}
              >
                <option value={ThinkingMode.AUTO}>自动</option>
                <option value={ThinkingMode.DISABLED}>关闭</option>
                <option value={ThinkingMode.ENABLED}>开启</option>
              </select>
            </label>

            <label className="settings-field">
              <span>请求超时（秒）</span>
              <input
                type="number"
                min={5}
                max={300}
                value={timeoutSeconds}
                onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
              />
            </label>

            <section className="settings-custom-models" aria-label="自定义模型">
              <div>
                <strong>自定义模型</strong>
                <p className="settings-hint">输入当前服务商官方提供的模型 ID。</p>
              </div>
              <div className="settings-custom-model-add">
                <label className="settings-field">
                  <span>模型 ID</span>
                  <input
                    aria-label="自定义模型 ID"
                    value={customModelId}
                    maxLength={128}
                    placeholder={`${providerInfo.id}-model-id`}
                    onChange={(event) => {
                      setCustomModelId(event.target.value);
                      setCustomModelError(null);
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => {
                    const nextId = customModelId.trim();
                    if (!/^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$/.test(nextId)) {
                      setCustomModelError("模型 ID 仅支持字母、数字、点、下划线、斜杠和连字符。");
                      return;
                    }
                    if (availableModels.some((item) => item.id === nextId)) {
                      setCustomModelError("当前服务商已存在这个模型 ID。");
                      return;
                    }
                    const custom = model(nextId, nextId, provider, true);
                    setCustomModels((current) => [...current, custom]);
                    setDefaultModel(nextId);
                    setCustomModelId("");
                    setCustomModelError(null);
                  }}
                >
                  添加模型
                </button>
              </div>
              {customModelError && (
                <p className="settings-feedback settings-feedback-error" role="alert">
                  {customModelError}
                </p>
              )}
              {currentCustomModels.length > 0 && (
                <ul className="settings-custom-model-list" aria-label="已添加的自定义模型">
                  {currentCustomModels.map((item) => (
                    <li key={`${item.provider}:${item.id}`}>
                      <code>{item.id}</code>
                      <button
                        type="button"
                        className="text-action"
                        aria-label={`移除自定义模型 ${item.id}`}
                        onClick={() => {
                          setCustomModels((current) => current.filter(
                            (candidate) => !(
                              candidate.provider === item.provider && candidate.id === item.id
                            ),
                          ));
                          if (defaultModel === item.id) {
                            setDefaultModel(providerInfo.defaultModel);
                          }
                        }}
                      >
                        移除
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </details>
      )}

      {message && <p className="settings-feedback settings-feedback-ok" role="status">{message}</p>}
      {error && <p className="settings-feedback settings-feedback-error" role="alert">{error}</p>}

      <div className="settings-actions">
        {(professionalMode || capabilities.credentialStore) && (
          <button type="submit" disabled={saving}>{saving ? "保存中..." : "保存"}</button>
        )}
        <button
          type="button"
          className="secondary-btn"
          disabled={testing}
          onClick={() => void onTest({ config: request(), ...(apiKey ? { apiKey } : {}) })}
        >
          {testing ? "测试中..." : "测试云端连接"}
        </button>
        {capabilities.credentialStore && keyConfigured && (
          <button type="button" className="danger-btn" disabled={saving} onClick={() => void onClearKey()}>
            清除当前服务商密钥
          </button>
        )}
      </div>
    </form>
  );
}

function model(
  id: LLMModelIdType,
  label: string,
  provider: LLMProviderIdType,
  isCustom = false,
): ModelConfig {
  return {
    id,
    label,
    provider,
    supportsThinking: true,
    supportsStreaming: true,
    isCustom,
  };
}
