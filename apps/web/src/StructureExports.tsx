import { Download } from 'lucide-react';
import type { CadExport } from '../../../packages/contracts/src/structure';

export function StructureExports({files,laser}:{files:CadExport[];laser:boolean}) {
  const available=files.filter(f=>f.url);
  const ready=(f:CadExport)=>laser ? ['svg','dxf','pdf'].includes(f.format.toLowerCase()) && !/preview|预览/i.test(f.id+' '+f.label+' '+f.url) : ['stl','step','stp','3mf'].includes(f.format.toLowerCase()) && (f.fidelity==='cadquery'||f.id.startsWith('cadquery_')) && !/参考|非打印|reference/i.test(f.label);
  const models=available.filter(ready),details=available.filter(f=>!ready(f));
  const list=(entries:CadExport[])=> <div className="structure-export-list">{entries.map((f,i)=><a key={`${f.id}-${i}`} href={f.url} download><Download size={17}/><span><strong>{f.label}</strong><small>{f.format.toUpperCase()}</small></span></a>)}</div>;
  return <><p className="muted">{laser?'下载图纸后，在加工软件中核对尺寸、材料和刀缝。':'STL 用于准备3D打印，STEP 可继续编辑。制作前请核对尺寸并试装。'}</p><h3>制作文件</h3>{models.length?list(models):<p>还没有可制作的文件。请先完成模型或图纸生成，并查看检查结果。</p>}{details.length>0&&<details className="classroom-details"><summary>{laser?'设计预览与详细资料':'参考模型与详细资料'}（{details.length}）</summary>{list(details)}</details>}</>;
}
