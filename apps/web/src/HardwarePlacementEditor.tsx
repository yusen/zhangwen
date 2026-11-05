import type { HardwareSummary } from '../../../packages/contracts/src/platform';
import type { CadProfile, DesignSpec, HardwarePlacement } from '../../../packages/contracts/src/structure';

export const panelNames = {top:'顶盖',bottom:'底盖',front:'前面',back:'后面',left:'左侧',right:'右侧'};
export function HardwarePlacementEditor({hardware, profiles, placements, onChange, onDetail, spec, disabled}: {
  hardware: HardwareSummary[]; profiles: CadProfile[]; placements: HardwarePlacement[];
  onChange: (v: HardwarePlacement[]) => void; onDetail: (item: HardwareSummary) => void;
  spec: DesignSpec; disabled: boolean;
}) {
  const box = spec.roundedBox ?? spec.fingerBox;
  if (!box) return null;
  const update = (id: string, patch: Partial<HardwarePlacement>) => onChange(placements.map(p=>p.componentId===id?{...p,...patch}:p));
  const rows = [...hardware.map(h=>({id:h.componentId,name:h.displayName,hardware:h})),
    ...placements.filter(p=>!hardware.some(h=>h.componentId===p.componentId)).map(p=>({id:p.componentId,name:'历史器件 '+p.componentId,hardware:undefined}))];
  return <details open className="hardware-installation-editor"><summary>电子件安装 · {placements.length} 个参与图纸</summary>
    <p className="structure-caption">勾选需要安装的器件。X/Y 是该板加工图左上角到器件包络中心的 mm 坐标，X 向右、Y 向下，旋转为顺时针，不自动镜像。蓝色轮廓为安装参考，红色为实际切口。</p>
    {spec.roundedBox && <p className="structure-caption">顶/底盖按盒体外宽深定位；侧面仅使用去掉两端圆角的直边（前后 {(box.width-2*spec.roundedBox.corner_radius).toFixed(1)} mm，左右 {(box.depth-2*spec.roundedBox.corner_radius).toFixed(1)} mm）。前面中间有胶合接缝，不能跨缝安装。</p>}
    {!rows.length && <p className="structure-caption">先在智能工程师中选择主控与模块，再回到这里安排安装位置。</p>}
    {rows.map(row=>{
      const p=placements.find(p=>p.componentId===row.id);
      const profile=profiles.find(p=>p.componentId===row.id && p.skillRevision);
      const stale=!!p && !!profile && p.skillRevision!==profile.skillRevision;
      return <fieldset disabled={disabled} className="hardware-installation-row" key={row.id}><legend>{row.name}</legend>
        <label className="structure-param-toggle"><input aria-label={`安装到图纸：${row.name}`} type="checkbox" checked={!!p} disabled={disabled || (!p && !profile?.skillRevision)} onChange={e=>onChange(e.target.checked?[...placements,{componentId:row.id,skillRevision:profile!.skillRevision!,panel:'bottom',x:box.width/2,y:box.depth/2,rotation:0,method:'screw',includeOpenings:false}]:placements.filter(p=>p.componentId!==row.id))}/>参与本张安装图</label>
        {!profile && !p && <p className="structure-caption">缺少机械档案：请先补充外形、孔位或开口。不会自动猜测尺寸。</p>}
        {row.hardware && <button type="button" onClick={()=>onDetail(row.hardware!)}>尺寸与安装资料</button>}
        {p && <>
          {stale && <p role="status" className="structure-caption">原模块资料已更新；当前图纸仍使用原修订。<button type="button" onClick={()=>update(row.id,{skillRevision:profile!.skillRevision!})}>使用最新资料修订</button></p>}
          {!profile && <p className="structure-caption">使用此结构版本保存的资料项目备份；调整位置前需恢复原模块资料。</p>}
          <div className="structure-param-grid"><label>安装面<select aria-label={`${row.name}安装面`} value={p.panel} onChange={e=>update(row.id,{panel:e.target.value as HardwarePlacement['panel']})}>{Object.entries(panelNames).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
            <label>中心 X<input aria-label={`${row.name}安装中心 X`} type="number" min="0" max="1000" step="0.1" value={Number.isFinite(p.x)?p.x:''} onChange={e=>update(row.id,{x:e.target.value===''?NaN:Number(e.target.value)})}/></label>
            <label>中心 Y<input aria-label={`${row.name}安装中心 Y`} type="number" min="0" max="1000" step="0.1" value={Number.isFinite(p.y)?p.y:''} onChange={e=>update(row.id,{y:e.target.value===''?NaN:Number(e.target.value)})}/></label>
            <label>平面旋转<select aria-label={`${row.name}安装旋转`} value={p.rotation} onChange={e=>update(row.id,{rotation:Number(e.target.value) as HardwarePlacement['rotation']})}>{[0,90,180,270].map(n=><option key={n} value={n}>{n}°</option>)}</select></label></div>
          <label className="field">安装方式<select aria-label={`${row.name}安装方式`} value={p.method} onChange={e=>update(row.id,{method:e.target.value as HardwarePlacement['method']})}><option value="screw">螺钉固定 · 按档案生成通孔</option><option value="adhesive">胶垫固定 · 仅雕刻安装轮廓</option><option value="opening_only">仅开口 · 固定结构另行设计</option></select></label>
          <label className="structure-param-toggle"><input aria-label={`${row.name}生成开口`} type="checkbox" checked={p.includeOpenings} onChange={e=>update(row.id,{includeOpenings:e.target.checked})}/>按档案生成开口</label>
          <p className="structure-caption">{p.method==='screw'?'螺钉、螺母与垫柱另配；不会生成螺柱。':p.method==='adhesive'?'不生成固定件；需自行确认胶垫位置、耐久和绝缘。':'本选项没有生成固定结构。'}{!p.includeOpenings?' 当前未生成探头、按钮或接口开口，需要时请勾选并补齐开口尺寸。':''}</p>
        </>}
      </fieldset>;
    })}
  </details>;
}
