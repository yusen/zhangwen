import { useState } from 'react';
import type { AiSettings, SaveAiSettings } from '../../../packages/contracts/src/mu';
import { DEEPSEEK_MODELS } from '../../../packages/contracts/src/mu';
import { api } from './api';
import { Dialog } from './Dialog';

export function AiSettingsDialog({ settings, onSaved, onClose }: {
  settings: AiSettings; onSaved: (settings: AiSettings) => void; onClose: () => void;
}) {
  const [key, setKey] = useState('');
  const [model, setModel] = useState(settings.aiModel);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const save = async (clear = false) => {
    if (saving) return;
    setSaving(true); setError('');
    const body: SaveAiSettings = { apiKey: clear ? '' : key.trim() || null, model: model.trim() };
    try {
      const result = await api<AiSettings>('/settings/ai', 'POST', body);
      setKey(''); onSaved(result);
    } catch (err) { setError(err instanceof Error ? err.message : 'API 设置保存失败，请重试。'); }
    finally { setSaving(false); }
  };
  return <Dialog title="API 设置" onClose={() => { if (!saving) { setKey(''); onClose(); } }}>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <p className="muted">使用 DeepSeek API。保存后立即生效，重启服务仍会保留。</p>
      <div className="field">API 地址<code>https://api.deepseek.com</code></div>
      <label className="field">API Key<input autoFocus type="password" value={key} maxLength={500} onChange={event => setKey(event.target.value)} placeholder={settings.aiConfigured ? '已配置，留空保持不变' : '输入你的 DeepSeek API Key'} autoComplete="off" spellCheck={false} disabled={saving} /></label>
      <label className="field">模型名称<select value={model} onChange={event => setModel(event.target.value)} disabled={saving}>
        {DEEPSEEK_MODELS.map(id => <option key={id} value={id}>{id}</option>)}
        {!DEEPSEEK_MODELS.some(id => id === model) && <option value={model}>{model}</option>}
      </select></label>
      <p className="muted">{settings.aiConfigured ? '已配置 Key，完整密钥不会回显。' : '尚未配置 Key。'} 保存设置不代表连接验证通过，发送对话后可查看实际结果。</p>
      <p className="muted">Key 保存在本机 .data/mu-settings.json（明文），不会存入浏览器草稿或项目。发送对话时，当前代码与所选硬件资料会提交给 DeepSeek。</p>
      {error && <p className="settings-error" role="alert">{error}</p>}
      <div className="dialog-actions">
        <button type="button" onClick={onClose} disabled={saving}>取消</button>
        <button type="button" onClick={() => void save(true)} disabled={saving || !settings.aiConfigured}>清除 Key</button>
        <button className="primary" disabled={saving || (!settings.aiConfigured && !key.trim())}>{saving ? '保存中…' : '保存设置'}</button>
      </div>
    </form>
  </Dialog>;
}
