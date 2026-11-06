import type { DefinitionVersion, ProjectDefinition, ProjectConditions, RequirementChange, WorkflowCheckpoint, ProjectTestRun, TestStage, WorkflowProposal } from '../../../packages/contracts/src/workflow';
import type { ProjectFolderFile } from './projectFolderLayout';
import { sha256 } from './serial';

export const emptyDefinition: ProjectDefinition = {problem:'',audience:'',goal:'',behavior:'',parameters:'',exceptionPolicy:'',constraints:'',criteria:[]};
export const emptyConditions: ProjectConditions = {firmware:'',wiring:'',power:'',assembly:''};
export const stages: Record<TestStage,string> = {module:'器件测试',system:'作品测试',assembly:'装好后再测'};
export const testLabels = {unrecorded:'待测试',passed:'用户确认通过',failed:'用户确认未通过',blocked:'暂时无法测试',stale:'需复测'};
export const lastConfirmed = (value: WorkflowCheckpoint) => [...value.definitions].reverse().find(d=>d.confirmed);
export function definitionContent(value: ProjectDefinition): ProjectDefinition {
  return Object.fromEntries(Object.keys(emptyDefinition).map(k=>[k,value[k as keyof ProjectDefinition]])) as unknown as ProjectDefinition;
}
export const definitionLabel = (value?: DefinitionVersion) => value ? `V${value.revision} · ${value.confirmed?'已确认':'草稿'}` : '尚未定义';
export const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const line = (title: string, value: unknown) => `<dt>${escapeHtml(title)}</dt><dd>${escapeHtml(value || '未记录')}</dd>`;
function runHtml(r: ProjectTestRun): string {
  const b=r.baseline;
  return `<section><h3>${escapeHtml(r.test.title)} · ${testLabels[r.result]}</h3><p>${escapeHtml(r.createdAt)} · 观察人：${escapeHtml(r.observer)}</p><dl>${line('测试阶段',stages[r.test.stage])}${line('测试步骤',r.test.procedure)}${line('预期',r.test.expected)}${line('我的预测',r.prediction)}${line('实际现象',r.observed)}${line('解释',r.explanation)}${line('修改原因与下一步',r.changes)}${line('需求版本',b.definitionRevision ? 'V'+b.definitionRevision:'未确认')}${line('主控',b.boardName)}${line('硬件资料',b.modules.map(m=>`${m.name}（${m.revision}）`).join('\n'))}${line('程序',`${b.code.name} ${b.code.revision ? 'V'+b.code.revision:''} ${b.code.checksum}`)}${line('结构',b.structure ? `V${b.structure.revision} ${b.structure.name} ${b.structure.checksum}`:'未关联')}${Object.entries(b.conditions).map(([k,v])=>line(({firmware:'固件',wiring:'实际接线',power:'供电',assembly:'装配条件'} as Record<string,string>)[k],v)).join('')}${line('附件编号',r.evidenceIds.join('、'))}</dl></section>`;
}
function changeHtml(c:RequirementChange):string {
  const role={engineer:'智能工程师',structure:'结构工程师',learning:'学习设计师'};
  const status={proposed:'待整理',confirmed:'已确认，待处理与实测',completed:'已记录当时验收',cancelled:'已撤销'};
  const taskStatus={pending:'待处理',working:'处理中',delivered:'已关联成果版本',not_needed:'已说明无需调整'};
  return `<section><h3>${escapeHtml(c.summary)}</h3><dl>${line('状态',status[c.status])}${line('来源',role[c.sourceMode])}${line('协作选择',c.tasks.length?c.tasks.map(t=>role[t.role]).join('、'):c.collaborationDecided?'暂不协作':'尚未选择')}${line('需求版本',`${c.baseDefinitionRevision?'V'+c.baseDefinitionRevision:'未确认'} → ${c.definitionRevision?'V'+c.definitionRevision:'待确认'}`)}${line('交接编号',c.id)}${c.tasks.map(t=>line(role[t.role],`${taskStatus[t.status]}\n${t.note}\n${t.code?`${t.code.name} V${t.code.revision} ${t.code.checksum}`:''}${t.structure?`${t.structure.name} V${t.structure.revision} ${t.structure.checksum}`:''}`)).join('')}${line('当时验收观察编号',c.verificationRunIds.join('、'))}${line('验收时间',c.completedAt)}</dl></section>`;
}
function reviewHtml(value:WorkflowCheckpoint):string {
  return value.messages.filter(m=>m.role==='assistant').map(m=>{let p:WorkflowProposal;try{p=JSON.parse(m.content) as WorkflowProposal;}catch{return '';}
    const r=p.review;if(!r?.source)return '';
    return `<section><h3>${escapeHtml(r.conclusion)}</h3><p>${escapeHtml(r.source.checkedAt)} · ${r.source.method==='records'?'记录核对':'AI 资料检查'}；检查后若有修改，请重新检查。</p><dl>${line('还缺什么',r.gaps.join('\n'))}${line('下一步怎么做',r.nextSteps.join('\n'))}${line('请你决定',r.decisions.join('\n'))}${line('程序与结构怎样配合',r.comparison)}${line('检查依据',r.source.facts.join('\n'))}</dl></section>`;
  }).filter(Boolean).reverse().join('')||'<p>尚无整体成果检查</p>';
}
/** Inert standalone report: user text is escaped, no scripts or external resources. */
export function workflowReportHtml(name: string, value: WorkflowCheckpoint): string {
  const definition=value.definitions.at(-1);
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'"><title>${escapeHtml(name)} · 成果档案</title><style>body{font:16px/1.8 system-ui,sans-serif;color:#223047;max-width:920px;margin:40px auto;padding:0 24px}h1,h2,h3{line-height:1.4}h2{margin-top:36px}section{border-top:1px solid #ccd3dd;padding:12px 0}dt{font-weight:bold}dd{margin:0 0 14px;white-space:pre-wrap;overflow-wrap:anywhere}img{max-width:100%;max-height:650px}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#526074}@media print{body{margin:0;max-width:none}h2,h3{break-after:avoid}img{max-height:400px}}</style></head><body><h1>${escapeHtml(name)} · 成果档案</h1><p>掌问 · 项目记录第${value.revision}次保存</p><p>以下实测结论由记录人填写，仅适用于记录中的版本与条件。文件回读、运行提交和实际观察分别核对。</p><h2>教学与成果文档</h2>${(value.documents??[]).map(d=>`<section><h3>${escapeHtml(d.title)} · V${d.revision}</h3><p>${d.generated?'AI 生成草稿，请核对':'手工保存内容'}</p><pre>${escapeHtml(d.content)}</pre></section>`).join('')||'<p>尚未保存</p>'}<h2>整体成果检查</h2>${reviewHtml(value)}<h2>作品目标</h2><p>${definitionLabel(definition)}</p>${value.definitions.map(d=>`<section><h3>${definitionLabel(d)}</h3><dl>${Object.entries({问题:d.problem,使用者:d.audience,目标:d.goal,动作规则:d.behavior,关键参数:d.parameters,异常策略:d.exceptionPolicy,制作约束:d.constraints,验收条件:d.criteria.join('\n')}).map(([k,v])=>line(k,v)).join('')}</dl></section>`).join('')||'<p>尚未填写</p>'}<h2>目标调整与伙伴分工</h2>${(value.changes??[]).map(changeHtml).join('')||'<p>尚无变更记录</p>'}<h2>测试清单</h2>${value.cases.map(c=>`<section><h3>${escapeHtml(c.title)}${c.active?'':'（已停用）'}</h3><dl>${line('阶段',stages[c.stage])}${line('步骤',c.procedure)}${line('预期',c.expected)}</dl></section>`).join('')||'<p>尚未建立</p>'}<h2>观察与复测历史</h2>${value.runs.map(runHtml).join('')||'<p>尚无实测记录</p>'}<h2>图片与日志</h2>${value.evidence.map(e=>`<section><h3>${escapeHtml(e.name)}</h3><p>${escapeHtml(e.caption)}</p><small>编号 ${e.id} · SHA256 ${e.checksum}</small>${e.mime.startsWith('image/')?`<p><img alt="${escapeHtml(e.caption||e.name)}" src="data:${e.mime};base64,${e.content}"></p>`:`<pre>${escapeHtml(new TextDecoder().decode(Uint8Array.from(atob(e.content),c=>c.charCodeAt(0))))}</pre>`}</section>`).join('')||'<p>尚未添加</p>'}<h2>反思与教师反馈</h2>${value.reflections.map(r=>`<section><h3>${r.role==='teacher'?'教师反馈':'学生反思'} V${r.revision} · ${escapeHtml(r.author)}</h3><p>${escapeHtml(r.createdAt)}</p><dl>${line('内容',r.summary)}${line('发现与依据',r.learned)}${line('下一步',r.nextStep)}</dl></section>`).join('')||'<p>尚未记录</p>'}</body></html>`;
}
export async function workflowFolderFiles(name: string, value?: WorkflowCheckpoint): Promise<ProjectFolderFile[]> {
  if (!value) return [];
  const folder=`V${String(value.revision).padStart(3,'0')}_项目记录`;
  const files: ProjectFolderFile[]=[];
  for (const [filename,text] of [['项目记录.json',JSON.stringify(value,null,2)+'\n'],['成果档案.html',workflowReportHtml(name,value)]]) {
    files.push({path:['成果档案',folder,filename],sha256:await sha256(new TextEncoder().encode(text)),data:{text}});
  }
  const safe=(text:string)=>text.replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').replace(/[. ]+$/g,'').slice(0,70)||'文档';
  for(const doc of value.documents??[]){
    if(!/^[a-f0-9]{32}$/.test(doc.id)||!Number.isSafeInteger(doc.revision)||doc.revision<1)throw new Error('文档版本记录不完整。');
    const text=doc.content+'\n';
    files.push({path:[doc.kind==='teaching'?'教学设计':'成果档案',`${doc.id}`,`V${doc.revision}_${safe(doc.title)}.md`],sha256:await sha256(new TextEncoder().encode(text)),data:{text}});
  }
  for(const d of value.definitions){
    const text=`# ${name} · 作品需求说明\n\n状态：${d.confirmed?'已确认':'草稿'} · V${d.revision}\n\n`+Object.entries({背景与问题:d.problem,使用者与场景:d.audience,作品目标:d.goal,功能与流程:d.behavior,关键参数:d.parameters,异常处理:d.exceptionPolicy,范围与限制:d.constraints,完成条件:d.criteria.map(c=>'- '+c).join('\n')}).map(([title,content])=>`## ${title}\n${content||'待确认'}`).join('\n\n')+'\n';
    files.push({path:['作品说明',`V${d.revision}_作品需求说明.md`],sha256:await sha256(new TextEncoder().encode(text)),data:{text}});
  }
  for (const e of value.evidence) {
    if (!/^[a-f0-9]{32}$/.test(e.id) || !/^[a-f0-9]{64}$/.test(e.checksum)) throw new Error('项目证据标识无效。');
    const suffix=({'image/png':'png','image/jpeg':'jpg','image/webp':'webp','text/plain':'txt'} as const)[e.mime];
    if (!suffix) throw new Error('项目证据格式无效。');
    files.push({path:['成果档案','图片与日志',`${e.id}.${suffix}`],sha256:e.checksum,data:{base64:e.content}});
  }
  return files;
}
