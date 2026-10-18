import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, CircleMinus, LoaderCircle, TriangleAlert, XCircle } from 'lucide-react';
import type { AiDiagnosticCheck, AiDiagnosticReport, AiSettings, SaveAiSettings, WorkspaceMode } from '../../../packages/contracts/src/mu';
import { DEEPSEEK_MODELS } from '../../../packages/contracts/src/mu';
import { api, bootstrap, testAiSettings } from './api';
import { Dialog } from './Dialog';

const providers = [
  { id: 'deepseek', name: 'DeepSeek', url: 'https://api.deepseek.com', models: [...DEEPSEEK_MODELS] as string[] },
  { id: 'glm', name: 'GLM · 智谱', url: 'https://open.bigmodel.cn/api/paas/v4', models: ['glm-5.3', 'glm-5.3-flash', 'glm-5.2'] },
  { id: 'qwen', name: 'Qwen · 通义千问', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', models: ['qwen-plus', 'qwen3.5-flash', 'qwen-max'] },
  { id: 'kimi', name: 'Kimi · 月之暗面', url: 'https://api.moonshot.cn/v1', models: ['kimi-k3', 'kimi-k2.6', 'kimi-k2.7-code-highspeed'] },
];
const modeNames: Record<WorkspaceMode, string> = {engineer: '智能工程师', structure: '结构设计师', learning: '学习设计师'};

export function AiSettingsDialog({ settings: initial, initialMode = 'engineer', onSaved, onClose }: {
  settings: AiSettings; initialMode?: WorkspaceMode; onSaved: (settings: AiSettings) => void; onClose: () => void;
}) {
  const [settings, setSettings] = useState(initial);
  const [mode, setMode] = useState<WorkspaceMode>(initialMode);
  const [loading, setLoading] = useState(initialMode !== 'engineer');
  const [provider, setProvider] = useState(providers.find(item => item.url === initial.aiBaseUrl)?.id ?? 'custom');
  const [key, setKey] = useState('');
  const [model, setModel] = useState(settings.aiModel);
  const [baseUrl, setBaseUrl] = useState(settings.aiBaseUrl ?? 'https://api.deepseek.com');
  const [noKey, setNoKey] = useState(false);
  const changedEndpoint = baseUrl.replace(/\/+$/, '') !== (settings.aiBaseUrl ?? 'https://api.deepseek.com');
  const localEndpoint = /^http:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?:\/|$)/.test(baseUrl);
  const canRequest = !!baseUrl.trim() && !!model.trim() && (!!key.trim() || (noKey && localEndpoint) || (!changedEndpoint && settings.aiConfigured));
  const requestBody = (): SaveAiSettings => ({ apiKey: noKey ? '' : key.trim() || null, model: model.trim(), baseUrl: baseUrl.trim(), mode });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [testing, setTesting] = useState(false);
  const [checks, setChecks] = useState<AiDiagnosticCheck[]>([]);
  const [report, setReport] = useState<AiDiagnosticReport | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { controller.current?.abort(); controller.current = null; }, []);
  useEffect(() => {
    let live = true; setLoading(true); setKey(''); setError(''); setChecks([]); setReport(null); setNoKey(false);
    void api<AiSettings>('/settings/ai?mode=' + mode).then(value => {
      if (!live) return;
      setSettings(value); setModel(value.aiModel); setBaseUrl(value.aiBaseUrl ?? 'https://api.deepseek.com');
      setProvider(providers.find(item => item.url === value.aiBaseUrl)?.id ?? 'custom');
    }).catch(err => { if (live) setError(String(err)); }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [mode]);
  const resetTest = () => { setReport(null); setChecks([]); setError(''); };
  const close = () => { if (!saving) { controller.current?.abort(); controller.current = null; setKey(''); onClose(); } };
  const test = async () => {
    if (testing || saving) return;
    const request = new AbortController(); controller.current = request;
    setTesting(true); resetTest();
    try {
      await bootstrap(request.signal);
      if (request.signal.aborted) return;
      const result = await testAiSettings(requestBody(), request.signal, event => {
        if (controller.current !== request) return;
        if (event.type === 'check') setChecks(value => [...value.filter(item => item.id !== event.check.id), event.check]);
      });
      if (controller.current === request) { setReport(result); setChecks(result.checks); }
    } catch (err) {
      if (controller.current === request) {
        setError(request.signal.aborted ? '检测已取消，设置未保存。' : err instanceof Error ? err.message : '检测失败，请重试。');
        setChecks(value => value.map(item => item.status === 'running' ? { ...item, status: 'skipped', detail: '检测已中断，未获得结论。' } : item));
      }
    } finally {
      if (controller.current === request) { controller.current = null; setTesting(false); }
    }
  };
  const save = async (clear = false) => {
    if (saving || testing) return;
    setSaving(true); setError('');
    const body: SaveAiSettings = { ...requestBody(), ...(clear ? { apiKey: '' } : {}) };
    try {
      const result = await api<AiSettings>('/settings/ai', 'POST', body);
      setKey(''); onSaved(result);
    } catch (err) { setError(err instanceof Error ? err.message : 'API 设置保存失败，请重试。'); }
    finally { setSaving(false); }
  };
  return <Dialog title="API 设置" onClose={close}>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <p className="muted">三个模式可分别配置模型。保存后仅对所选模式生效。</p>
      <label className="field">配置模式<select aria-label="配置模式" value={mode} disabled={saving || testing} onChange={event => setMode(event.target.value as WorkspaceMode)}>{Object.entries(modeNames).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
      {settings.inherited && <p className="muted">此模式尚未单独配置，当前沿用智能工程师设置。保存后独立使用。</p>}
      <fieldset disabled={loading || saving || testing} className="ai-provider-fields">
      <label className="field">模型服务商<select aria-label="模型服务商" value={provider} onChange={event => {
        setProvider(event.target.value); const next = providers.find(item => item.id === event.target.value);
        if (next) { setBaseUrl(next.url); setModel(next.models[0]); setKey(''); setNoKey(false); } resetTest();
      }}>{providers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}<option value="custom">其他 / 本机 OpenAI 兼容服务</option></select></label>
      <label className="field">API 地址<input value={baseUrl} maxLength={500} placeholder="https://api.example.com/v1" onChange={event => { setBaseUrl(event.target.value); setKey(''); setNoKey(false); resetTest(); }} disabled={saving || testing} spellCheck={false} /></label>
      <p className="muted">填写基础地址（如 https://api.example.com/v1），不包含 /chat/completions。更换地址后须填写新 Key。</p>
      <label className="field">API Key<input autoFocus data-dialog-autofocus type="password" value={key} maxLength={500} onChange={event => { setKey(event.target.value); setNoKey(false); resetTest(); }} placeholder={settings.aiConfigured ? '已配置，留空保持不变' : '输入当前服务的 API Key'} autoComplete="off" spellCheck={false} disabled={saving || testing} /></label>
      <label className="field">模型名称<input list="ai-model-options" value={model} maxLength={100} onChange={event => { setModel(event.target.value); resetTest(); }} disabled={saving || testing} placeholder="填写服务商提供的模型 ID" spellCheck={false} /><datalist id="ai-model-options">{(providers.find(item => item.id === provider)?.models ?? providers.flatMap(item => item.models)).map(id => <option key={id} value={id} />)}</datalist></label>
      </fieldset>
      {localEndpoint && <label className="confirm"><input type="checkbox" checked={noKey} disabled={saving || testing} onChange={event => { setNoKey(event.target.checked); setKey(''); resetTest(); }} />本机服务无需 Key（清除旧 Key）</label>}
      <p className="muted">{settings.aiConfigured ? '当前服务已配置，完整密钥不会回显。' : '尚未配置模型服务。'} 可先测试当前填写的 Key 和模型，检测不会保存设置。</p>
      <div className="ai-test-controls"><button type="button" onClick={testing ? () => controller.current?.abort() : () => void test()} disabled={loading || saving || (!testing && !canRequest)}>{testing ? '取消检测' : '测试连接'}</button><span>包含一次简短生成测试，会产生少量 API 用量；不发送项目内容。</span></div>
      {!!checks.length && <section className="ai-diagnostics" aria-label="AI 检测结果" aria-live="polite">
        <ol>{checks.map(item => {
          const Icon = item.status === 'running' ? LoaderCircle : item.status === 'passed' ? CheckCircle2 : item.status === 'failed' ? XCircle : item.status === 'warning' ? TriangleAlert : CircleMinus;
          const status = { running: '检测中', passed: '通过', failed: '未通过', warning: '待确认', skipped: '未执行' }[item.status];
          return <li key={item.id} className={`ai-check ${item.status}`}><Icon size={17} className={item.status === 'running' ? 'spin' : ''} /><div><strong>{item.label}<span>{status}</span></strong><p>{item.detail}</p>{item.elapsedMs !== undefined && <small>用时 {(item.elapsedMs / 1000).toFixed(1)} 秒{item.firstTokenMs !== undefined && ` · 首字 ${(item.firstTokenMs / 1000).toFixed(1)} 秒`}{!!item.keepAlives && ` · 保活 ${item.keepAlives} 次`}</small>}</div></li>;
        })}</ol>
        {report && <div className={`ai-test-summary ${report.healthy ? 'passed' : 'failed'}`}><strong>{report.healthy ? '实际生成检测通过' : '检测未通过'}</strong><p>{report.suggestion}</p><small>{report.model} · {new Date(report.checkedAt).toLocaleTimeString()}</small></div>}
      </section>}
      <p className="muted">Key 保存在本机 .data/mu-settings.json（明文），不会存入浏览器草稿或项目。发送对话时，当前代码与所选硬件资料会提交给所填服务。</p>
      {error && <p className="settings-error" role="alert">{error}</p>}
      <div className="dialog-actions">
        <button type="button" onClick={close} disabled={saving}>取消</button>
        <button type="button" onClick={() => void save(true)} disabled={loading || saving || testing || !settings.aiConfigured}>清除 Key</button>
        <button className="primary" disabled={loading || saving || testing || !canRequest}>{saving ? '保存中…' : '保存设置'}</button>
      </div>
    </form>
  </Dialog>;
}
