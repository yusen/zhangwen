/** Edit the original profile object without discarding advanced mechanical facts. */
type Data = Record<string, unknown>;
const object = (v: unknown): Data => v && typeof v === 'object' && !Array.isArray(v) ? v as Data : {};
const entries = (v: unknown): Data[] => Array.isArray(v) ? v.map(object) : [];
const number = (v: unknown) => typeof v === 'number' && Number.isFinite(v) ? v : '';
const value = (s: string) => s === '' ? null : Number(s);
export function MechanicalFields({text, onChange, disabled}: {text: string; onChange: (v: string) => void; disabled: boolean}) {
  let profile: Data;
  try { profile = object(JSON.parse(text)); } catch { return <p role="alert">JSON 尚未完整，请先在高级编辑中修正，再使用表单。</p>; }
  const dimensions = object(profile.dimensions), mounting = object(profile.mounting);
  const holes = entries(mounting.holes), openings = entries(profile.openings);
  const update = (patch: Data) => onChange(JSON.stringify({...profile, ...patch}, null, 2));
  const mount = (patch: Data) => update({mounting: {...mounting, ...patch}});
  const hole = (index: number, patch: Data) => mount({holes: holes.map((h,i) => i === index ? {...h,...patch} : h)});
  const opening = (index: number, patch: Data) => update({openings: openings.map((o,i) => i === index ? {...o,...patch} : o)});
  const nextId = (prefix: string, rows: Data[], key: string) => { let n=1; while(rows.some(r=>r[key]===prefix+n)) n++; return prefix+n; };
  return <fieldset className="mechanical-form" disabled={disabled}><legend>填写机械尺寸（mm）</legend>
    <p className="muted">按准确型号的尺寸图或实测填写。空白表示未知；坐标原点默认是外形包络中心，X 为长、Y 为宽。</p>
    <div className="structure-param-grid">{[['length_x','外形长度 X'],['width_y','外形宽度 Y'],['height_z','外形高度 Z']].map(([key,label])=><label key={key}>{label}<input aria-label={label} type="number" min="0.1" max="500" step="0.1" value={number(dimensions[key]) || ''} onChange={e=>update({dimensions:{...dimensions,[key]:value(e.target.value)}})} /></label>)}</div>
    <label className="field">坐标原点<select value={String(object(profile.coordinate_system).origin ?? 'envelope_center')} onChange={e=>update({coordinate_system:{...object(profile.coordinate_system),origin:e.target.value}})}><option value="envelope_center">包络中心（支持安装图）</option><option value="pcb_center">PCB 中心（需进一步转换）</option></select></label>
    <label className="field">档案固定策略<select value={String(mounting.strategy ?? 'none')} onChange={e=>mount({strategy:e.target.value})}><option value="none">尚未声明孔固定 / 无孔安装</option><option value="hole_fastened">按安装孔固定</option><option value="edge_retainer">边缘卡持（需另设计卡持件）</option></select></label>
    <label className="field">外形装配间隙<input type="number" min="0" max="10" step="0.1" value={number(mounting.clearance)} onChange={e=>mount({clearance:value(e.target.value)})} /></label>
    <h4>安装孔</h4><p className="muted">孔中心以所选原点计，负坐标有效。孔径为名义通孔尺寸；螺钉与垫柱另配。无孔或未测量时保留空列表。</p>
    {holes.map((h,i)=><fieldset key={String(h.hole_id)}><legend>安装孔 {i+1}</legend><div className="structure-param-grid">{[['x','孔中心 X'],['y','孔中心 Y']].map(([key,label])=><label key={key}>{label}<input aria-label={`安装孔${i+1}${label}`} type="number" step="0.1" value={number(object(h.center)[key])} onChange={e=>hole(i,{center:{...object(h.center),[key]:value(e.target.value)}})} /></label>)}<label>孔径<input aria-label={`安装孔${i+1}孔径`} type="number" min="1" max="20" step="0.1" value={number(h.diameter)} onChange={e=>hole(i,{diameter:value(e.target.value)})}/></label><label>紧固件型号<input aria-label={`安装孔${i+1}紧固件`} value={String(h.fastener??'')} maxLength={32} onChange={e=>hole(i,{fastener:e.target.value})}/></label></div><button type="button" onClick={()=>mount({holes:holes.filter((_,n)=>n!==i)})}>移除安装孔 {i+1}</button></fieldset>)}
    <button type="button" disabled={disabled || holes.length>=32} onClick={()=>mount({holes:[...holes,{hole_id:nextId('h',holes,'hole_id'),center:{x:0,y:0},diameter:null,fastener:'M3'}]})}>添加安装孔</button>
    <h4>面板开口</h4><p className="muted">只在有资料时添加。圆孔用于按钮/探头等，矩形用于屏幕/窗口等；不能以器件外形代替开口。此处 top/bottom 指器件局部 XY 平面；在安装图中投影到所选盒面。</p>
    {openings.map((o,i)=><fieldset key={String(o.opening_id)}><legend>开口 {i+1}</legend><label className="field">开口形状<select aria-label={`开口${i+1}形状`} value={String(o.kind)} onChange={e=>{const next: Data={...o,kind:e.target.value}; delete next[e.target.value==='circle'?'size_u':'diameter']; if(e.target.value==='circle'){delete next.size_v;delete next.corner_radius;next.diameter=null;}else{next.size_u=null;next.size_v=null;next.corner_radius=0;} update({openings:openings.map((v,n)=>n===i?next:v)});}}><option value="circle">圆孔</option><option value="rectangle">直角矩形</option></select></label><div className="structure-param-grid">{[['x','中心 X'],['y','中心 Y']].map(([key,label])=><label key={key}>{label}<input aria-label={`开口${i+1}${label}`} type="number" step="0.1" value={number(object(o.center)[key])} onChange={e=>opening(i,{center:{...object(o.center),[key]:value(e.target.value)}})}/></label>)}{(o.kind==='circle'?[['diameter','直径']]:[['size_u','宽度'],['size_v','高度']]).map(([key,label])=><label key={key}>{label}<input aria-label={`开口${i+1}${label}`} type="number" min="0.8" max="200" step="0.1" value={number(o[key])} onChange={e=>opening(i,{[key]:value(e.target.value)})}/></label>)}<label>每边开口余量<input aria-label={`开口${i+1}余量`} type="number" min="0" max="10" step="0.1" value={number(o.clearance)} onChange={e=>opening(i,{clearance:value(e.target.value)})}/></label></div><p className="muted">局部朝向：{String(o.preferred_face)}{Number(o.corner_radius)>0?'；已有圆角，安装图暂不支持，请保留原资料另行设计。':''}</p><button type="button" onClick={()=>update({openings:openings.filter((_,n)=>n!==i)})}>移除开口 {i+1}</button></fieldset>)}
    <button type="button" disabled={disabled || openings.length>=32} onClick={()=>update({openings:[...openings,{opening_id:nextId('opening',openings,'opening_id'),kind:'circle',center:{x:0,y:0},diameter:null,preferred_face:'top',clearance:0}]})}>添加面板开口</button>
    <p className="muted">插头、线缆和非矩形轮廓等已有高级资料会保留，可在下方 JSON 编辑 keepouts 等字段。保存尺寸并不等于通过实物装配。</p>
  </fieldset>;
}
