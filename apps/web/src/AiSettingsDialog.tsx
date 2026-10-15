import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, CircleMinus, LoaderCircle, TriangleAlert, XCircle } from 'lucide-react';
import type { AiDiagnosticCheck, AiDiagnosticReport, AiSettings, SaveAiSettings } from '../../../packages/contracts/src/mu';
import { DEEPSEEK_MODELS } from '../../../packages/contracts/src/mu';
import { api, bootstrap, testAiSettings } from './api';
import { Dialog } from './Dialog';

export function AiSettingsDialog({ settings, onSaved, onClose }: {
  settings: AiSettings; onSaved: (settings: AiSettings) => void; onClose: () => void;
}) {
  const [key, setKey] = useState('');
  const [model, setModel] = useState(settings.aiModel);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [testing, setTesting] = useState(false);
  const [checks, setChecks] = useState<AiDiagnosticCheck[]>([]);
  const [report, setReport] = useState<AiDiagnosticReport | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => { controller.current?.abort(); controller.current = null; }, []);
  const resetTest = () => { setReport(null); setChecks([]); setError(''); };
  const close = () => { if (!saving) { controller.current?.abort(); controller.current = null; setKey(''); onClose(); } };
  const test = async () => {
    if (testing || saving) return;
    const request = new AbortController(); controller.current = request;
    setTesting(true); resetTest();
    try {
      await bootstrap(request.signal);
      if (request.signal.aborted) return;
      const result = await testAiSettings({ apiKey: key.trim() || null, model }, request.signal, event => {
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
    const body: SaveAiSettings = { apiKey: clear ? '' : key.trim() || null, model: model.trim() };
    try {
      const result = await api<AiSettings>('/settings/ai', 'POST', body);
      setKey(''); onSaved(result);
    } catch (err) { setError(err instanceof Error ? err.message : 'API 设置保存失败，请重试。'); }
    finally { setSaving(false); }
  };
  return <Dialog title="API 设置" onClose={close}>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <p className="muted">使用 DeepSeek API。保存后立即生效，重启服务仍会保留。</p>
      <div className="field">API 地址<code>https://api.deepseek.com</code></div>
      <label className="field">API Key<input autoFocus type="password" value={key} maxLength={500} onChange={event => { setKey(event.target.value); resetTest(); }} placeholder={settings.aiConfigured ? '已配置，留空保持不变' : '输入你的 DeepSeek API Key'} autoComplete="off" spellCheck={false} disabled={saving || testing} /></label>
      <label className="field">模型名称<select value={model} onChange={event => { setModel(event.target.value); resetTest(); }} disabled={saving || testing}>
        {DEEPSEEK_MODELS.map(id => <option key={id} value={id}>{id}</option>)}
        {!DEEPSEEK_MODELS.some(id => id === model) && <option value={model}>{model}</option>}
      </select></label>
      <p className="muted">{settings.aiConfigured ? '已配置 Key，完整密钥不会回显。' : '尚未配置 Key。'} 可先测试当前填写的 Key 和模型，检测不会保存设置。</p>
      <div className="ai-test-controls"><button type="button" onClick={testing ? () => controller.current?.abort() : () => void test()} disabled={saving || (!settings.aiConfigured && !key.trim())}>{testing ? '取消检测' : '测试连接'}</button><span>包含一次简短生成测试，会产生少量 API 用量；不发送项目内容。</span></div>
      {!!checks.length && <section className="ai-diagnostics" aria-label="AI 检测结果" aria-live="polite">
        <ol>{checks.map(item => {
          const Icon = item.status === 'running' ? LoaderCircle : item.status === 'passed' ? CheckCircle2 : item.status === 'failed' ? XCircle : item.status === 'warning' ? TriangleAlert : CircleMinus;
          const status = { running: '检测中', passed: '通过', failed: '未通过', warning: '待确认', skipped: '未执行' }[item.status];
          return <li key={item.id} className={`ai-check ${item.status}`}><Icon size={17} className={item.status === 'running' ? 'spin' : ''} /><div><strong>{item.label}<span>{status}</span></strong><p>{item.detail}</p>{item.elapsedMs !== undefined && <small>用时 {(item.elapsedMs / 1000).toFixed(1)} 秒{item.firstTokenMs !== undefined && ` · 首字 ${(item.firstTokenMs / 1000).toFixed(1)} 秒`}{!!item.keepAlives && ` · 保活 ${item.keepAlives} 次`}</small>}</div></li>;
        })}</ol>
        {report && <div className={`ai-test-summary ${report.healthy ? 'passed' : 'failed'}`}><strong>{report.healthy ? '实际生成检测通过' : '检测未通过'}</strong><p>{report.suggestion}</p><small>{report.model} · {new Date(report.checkedAt).toLocaleTimeString()}</small></div>}
      </section>}
      <p className="muted">Key 保存在本机 .data/mu-settings.json（明文），不会存入浏览器草稿或项目。发送对话时，当前代码与所选硬件资料会提交给 DeepSeek。</p>
      {error && <p className="settings-error" role="alert">{error}</p>}
      <div className="dialog-actions">
        <button type="button" onClick={close} disabled={saving}>取消</button>
        <button type="button" onClick={() => void save(true)} disabled={saving || testing || !settings.aiConfigured}>清除 Key</button>
        <button className="primary" disabled={saving || testing || (!settings.aiConfigured && !key.trim())}>{saving ? '保存中…' : '保存设置'}</button>
      </div>
    </form>
  </Dialog>;
}
