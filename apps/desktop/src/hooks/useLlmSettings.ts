import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ConnectionTestRequest,
  ConnectionTestResult,
  LLMConfig,
  ModelConfig,
  SaveLLMConfigRequest,
} from "@zhangwen/contracts";
import {
  clearLlmApiKey,
  getLlmConfig,
  getLlmModels,
  saveLlmConfig,
  testLlmConnection,
} from "../services/llmApi";
import { ApiError } from "../services/api";

interface LlmSettingsState {
  config: LLMConfig | null;
  models: ModelConfig[];
  loading: boolean;
  saving: boolean;
  testing: boolean;
  message: string | null;
  error: string | null;
  refresh: () => Promise<void>;
  save: (request: SaveLLMConfigRequest) => Promise<void>;
  clearKey: () => Promise<void>;
  test: (request: ConnectionTestRequest) => Promise<ConnectionTestResult>;
}

export function useLlmSettings(): LlmSettingsState {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [configResponse, modelsResponse] = await Promise.all([
        getLlmConfig(),
        getLlmModels(),
      ]);
      if (!mountedRef.current) return;
      setConfig(configResponse.config);
      setModels(modelsResponse.models);
      setError(null);
    } catch {
      if (!mountedRef.current) return;
      setError("本地后端未连接，请启动 FastAPI Sidecar 后重试。");
    } finally {
      if (!mountedRef.current) return;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refresh();
    return () => {
      mountedRef.current = false;
    };
  }, [refresh]);

  const save = useCallback(async (request: SaveLLMConfigRequest) => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const response = await saveLlmConfig(request);
      setConfig(response.config);
      setMessage("设置已保存。");
    } catch (error) {
      setError(apiErrorMessage(error, "设置保存失败，请稍后重试。"));
      throw error;
    } finally {
      setSaving(false);
    }
  }, []);

  const clearKey = useCallback(async () => {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const response = await clearLlmApiKey();
      setConfig(response.config);
      setMessage("API Key 已清除。");
    } catch {
      setError("清除配置失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  }, []);

  const test = useCallback(async (request: ConnectionTestRequest) => {
    setTesting(true);
    setMessage(null);
    setError(null);
    try {
      const result = await testLlmConnection(request);
      if (result.ok) {
        setMessage(
          usesUnsavedConfig(request, config)
            ? "当前表单连接测试成功；请先保存设置，之后对话才会使用该配置。"
            : "云端 LLM 连接测试成功。",
        );
      } else {
        setError(result.error?.message ?? result.message);
      }
      return result;
    } catch {
      const result: ConnectionTestResult = {
        ok: false,
        message: "本地后端未连接，请启动 FastAPI Sidecar 后重试。",
        provider: request.config?.provider ?? config?.provider ?? "deepseek",
        model: request.config?.defaultModel ?? config?.defaultModel ?? "deepseek-v4-flash",
        error: {
          code: "SIDECAR_UNAVAILABLE",
          message: "本地后端未连接，请启动 FastAPI Sidecar 后重试。",
          retryable: true,
          userActions: [{ id: "retry", label: "重试" }],
        },
      };
      setError(result.message);
      return result;
    } finally {
      setTesting(false);
    }
  }, [config]);

  return {
    config,
    models,
    loading,
    saving,
    testing,
    message,
    error,
    refresh,
    save,
    clearKey,
    test,
  };
}

function apiErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;
  const prefix = error.code ? `${error.code}: ` : "";
  return prefix && error.message.startsWith(prefix)
    ? error.message.slice(prefix.length)
    : error.message;
}

function usesUnsavedConfig(
  request: ConnectionTestRequest,
  persisted: LLMConfig | null,
): boolean {
  if (request.apiKey?.trim() || request.config?.apiKey?.trim()) return true;
  const candidate = request.config;
  if (!candidate || !persisted) return false;
  return (
    candidate.provider !== persisted.provider ||
    candidate.baseUrl.replace(/\/+$/, "") !== persisted.baseUrl.replace(/\/+$/, "") ||
    candidate.defaultModel !== persisted.defaultModel ||
    !sameCustomModels(candidate.customModels, persisted.customModels) ||
    candidate.thinkingMode !== persisted.thinkingMode ||
    candidate.reasoningEffort !== persisted.reasoningEffort ||
    candidate.timeoutSeconds !== persisted.timeoutSeconds
  );
}

function sameCustomModels(
  candidate: ModelConfig[] | undefined,
  persisted: ModelConfig[] | undefined,
): boolean {
  const normalize = (models: ModelConfig[] | undefined) =>
    (models ?? [])
      .map(({ id, label, provider, isCustom }) => ({ id, label, provider, isCustom: Boolean(isCustom) }))
      .sort((left, right) => `${left.provider}:${left.id}`.localeCompare(`${right.provider}:${right.id}`));
  return JSON.stringify(normalize(candidate)) === JSON.stringify(normalize(persisted));
}
