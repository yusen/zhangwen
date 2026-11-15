import { useEffect, useRef, useState } from 'react';
import type { ProjectReference } from '../../../packages/contracts/src/platform';
import { api } from './api';

export type ImageReferenceInput=Pick<ProjectReference,'name'|'original'|'encoding'|'imageDescription'>;

/** Videos remain local. Only an explicitly captured and reviewed frame is saved. */
export function ReferenceImageImport({projectId,disabled,onSave}:{projectId:string;disabled:boolean;onSave:(input:ImageReferenceInput)=>Promise<void>}) {
  const [image,setImage]=useState<ImageReferenceInput|null>(null);
  const [video,setVideo]=useState<{url:string;name:string}|null>(null);
  const [videoReady,setVideoReady]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const player=useRef<HTMLVideoElement>(null);
  useEffect(()=>()=>{if(video)URL.revokeObjectURL(video.url);},[video]);
  const capture=(source:CanvasImageSource,width:number,height:number,name:string)=>{
    if(!width||!height)throw new Error('画面还未就绪，请等待加载或拖动到具体时刻。');
    const scale=Math.min(1,1280/Math.max(width,height)),canvas=document.createElement('canvas');canvas.width=Math.round(width*scale);canvas.height=Math.round(height*scale);
    const context=canvas.getContext('2d');if(!context)throw new Error('浏览器无法生成关键帧。');context.drawImage(source,0,0,canvas.width,canvas.height);
    const original=canvas.toDataURL('image/jpeg',0.82).split(',')[1];if(original.length>1_333_000)throw new Error('图片过大，请先缩小图片。');
    setImage({name,original,encoding:'base64',imageDescription:''});setError('');setNotice('请填写画面说明，或点击读图后核对；保存后才加入共用资料。');
  };
  return <section className="reference-image-import" aria-label="图片与视频关键帧">
    <h3>图片与视频关键帧</h3><p className="muted">视频在本机预览，拖动到所需画面后截取。只将核对的关键帧和说明加入共用资料。</p>
    <label className="reference-file-button">选择图片或视频<input aria-label="选择参考图片或视频" type="file" accept="image/png,image/jpeg,image/webp,video/mp4,video/webm" disabled={disabled||busy} onChange={e=>{
      const file=e.target.files?.[0];e.target.value='';if(!file)return;setError('');setNotice('');
      if(/\.(mp4|webm)$/i.test(file.name)){if(file.size>200_000_000){setError('视频最多200MB，请先截取片段。');return;}setVideoReady(false);setVideo({url:URL.createObjectURL(file),name:file.name});return;}
      if(!/\.(png|jpe?g|webp)$/i.test(file.name)||file.size>20_000_000){setError('请选择20MB以内的PNG/JPEG/WebP图片。');return;}
      const url=URL.createObjectURL(file),element=new Image();setBusy(true);
      element.onload=()=>{try{capture(element,element.naturalWidth,element.naturalHeight,file.name.replace(/\.[^.]+$/,'.jpg'));}catch(err){setError(String(err));}finally{URL.revokeObjectURL(url);setBusy(false);}};
      element.onerror=()=>{URL.revokeObjectURL(url);setBusy(false);setError('图片无法解码，请更换文件。');};element.src=url;
    }}/></label>
    {video&&<div><video ref={player} src={video.url} controls preload="auto" onLoadedData={()=>setVideoReady(true)} onError={()=>{setVideoReady(false);setError('浏览器无法解码此视频，请转换为常见MP4/WebM，或先导出一张图片再选择。视频未上传。');}} aria-label="参考视频本机预览" style={{width:'100%',maxHeight:260}}/>
      <button disabled={disabled||busy||!videoReady} onClick={()=>{const v=player.current;if(!v)return;try{capture(v,v.videoWidth,v.videoHeight,video.name.replace(/\.[^.]+$/,'')+`-关键帧-${v.currentTime.toFixed(2)}秒.jpg`);}catch(err){setError(String(err));}}}>截取当前关键帧</button></div>}
    {image&&<div><img src={`data:image/jpeg;base64,${image.original}`} alt="待核对的参考关键帧" style={{maxWidth:'100%',maxHeight:280}}/>
      <label className="reference-field">图片名称<input maxLength={200} value={image.name} disabled={busy} onChange={e=>setImage({...image,name:e.target.value})}/></label>
      <label className="reference-field">画面说明（核对后保存）<textarea aria-label="画面说明" rows={5} maxLength={12000} value={image.imageDescription??''} disabled={busy} onChange={e=>setImage({...image,imageDescription:e.target.value})}/></label>
      <div className="reference-actions"><button disabled={disabled||busy} onClick={()=>{setBusy(true);setError('');void api<{description:string;notice:string}>(`/projects/${projectId}/references/analyze-image`,'POST',image).then(v=>{setImage({...image,imageDescription:v.description});setNotice(v.notice);}).catch(err=>setError(String(err))).finally(()=>setBusy(false));}}>让模型读这张图</button>
      <button className="primary" disabled={disabled||busy||!image.imageDescription?.trim()} onClick={()=>{setBusy(true);setError('');void onSave(image).then(()=>{setImage(null);setNotice('关键帧及核对说明已保存为共用资料。');}).catch(err=>setError(String(err))).finally(()=>setBusy(false));}}>保存关键帧资料</button></div>
      <small className="muted">读图会把这一张图片发送给学习设计师配置的模型；不支持读图时可手工填写。AI推测的型号和尺寸请纠正。</small></div>}
    {busy&&<p role="status">正在处理图片…</p>}{error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  </section>;
}
