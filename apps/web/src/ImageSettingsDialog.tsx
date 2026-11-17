import { useEffect, useState } from 'react';
import type { ImageSettings, SaveImageSettings } from '../../../packages/contracts/src/images';
import { api } from './api';
import { Dialog } from './Dialog';

export function ImageSettingsDialog({onClose}:{onClose:()=>void}) {
  const [saved,setSaved]=useState<ImageSettings|null>(null);
  const [baseUrl,setBaseUrl]=useState(''),[model,setModel]=useState(''),[key,setKey]=useState('');
  const [format,setFormat]=useState<SaveImageSettings['responseFormat']>('auto');
  const [noKey,setNoKey]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let live=true;void api<ImageSettings>('/settings/images').then(s=>{if(live){setSaved(s);setBaseUrl(s.baseUrl);setModel(s.model);setFormat(s.responseFormat);}}).catch(e=>{if(live)setError(String(e));});return()=>{live=false;};},[]);
  const local=/^http:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?:\/|$)/.test(baseUrl);
  const save=async(clear=false)=>{
    if(busy)return;setBusy(true);setError('');
    try {await api<ImageSettings>('/settings/images','POST',{baseUrl:baseUrl.trim(),model:model.trim(),responseFormat:format,apiKey:clear||noKey?'':key.trim()||null} satisfies SaveImageSettings);setKey('');onClose();}
    catch(e){setError(e instanceof Error?e.message:'图片设置保存失败。');}finally{setBusy(false);}
  };
  return <Dialog title="图片模型 API 设置" onClose={()=>{if(!busy)onClose();}}>
    <form onSubmit={e=>{e.preventDefault();void save();}}>
      <p className="muted">线路方框图和项目方案图使用独立图片模型，与三个角色的文字模型分别配置。</p>
      <fieldset disabled={!saved||busy} className="ai-provider-fields">
        <label className="field">图片服务基础地址<input data-dialog-autofocus value={baseUrl} maxLength={500} spellCheck={false} placeholder="https://api.example.com/v1" onChange={e=>{setBaseUrl(e.target.value);setKey('');setNoKey(false);}}/></label>
        <small className="muted">使用兼容 OpenAI Images 的接口。填写基础地址，不包含 /images/generations。</small>
        <label className="field">图片模型名称<input value={model} maxLength={100} spellCheck={false} placeholder="填写图片服务商提供的模型 ID" onChange={e=>setModel(e.target.value)}/></label>
        <label className="field">图片 API Key<input type="password" value={key} maxLength={500} autoComplete="off" spellCheck={false} placeholder={saved?.configured?'已配置，留空保持不变':'输入图片服务的 API Key'} onChange={e=>{setKey(e.target.value);setNoKey(false);}}/></label>
        <label className="field">图片返回格式<select value={format} onChange={e=>setFormat(e.target.value as SaveImageSettings['responseFormat'])}><option value="auto">服务默认（须返回 Base64 图片）</option><option value="b64_json">明确请求 b64_json（兼容服务）</option></select></label>
        {local&&<label className="confirm"><input type="checkbox" checked={noKey} onChange={e=>{setNoKey(e.target.checked);setKey('');}}/>本机图片服务无需 Key（清除旧 Key）</label>}
      </fieldset>
      <p className="muted">保存设置不会生成图片。点击“生成图示”会发送画图要求及当前项目已保存的目标、器件、条件、结构说明和相关资料文字，按图片服务计费。</p>
      <details className="classroom-details"><summary>配置与兼容说明</summary><p>Key仅保存在本机 .data/zhangwen-image-settings.json，不回显、不放入项目。更换地址需填写新 Key。接口需支持 /images/generations 和 Base64 返回；仅返回图片 URL 的服务暂不支持。尺寸和模型能力以服务商说明为准。</p></details>
      {error&&<p role="alert" className="settings-error">{error}</p>}
      <div className="dialog-actions"><button type="button" disabled={busy} onClick={onClose}>取消</button><button type="button" disabled={busy||!saved?.configured||!model.trim()} onClick={()=>void save(true)}>清除图片 Key</button><button className="primary" disabled={busy||!saved||!model.trim()||!baseUrl.trim()}>{busy?'保存中…':'保存图片设置'}</button></div>
    </form>
  </Dialog>;
}
