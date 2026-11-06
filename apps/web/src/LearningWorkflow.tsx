import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUp, BookOpen, Check, CircuitBoard, ClipboardCheck, Download, FileText, FolderOpen, ImagePlus, LoaderCircle, PanelLeftClose, Plus, RefreshCw, Save, Sparkles } from 'lucide-react';
import type { HardwareSummary, Project, ProjectSnapshot } from '../../../packages/contracts/src/platform';
import type { CodeReference, TestObservation, TestStage, WorkflowProposal, WorkflowView, ProjectConditions, ProjectDefinition } from '../../../packages/contracts/src/workflow';
import { api, ApiError } from './api';
import { Dialog } from './Dialog';
import { LearningWorkspace } from './LearningWorkspace';
import type { LearningRole } from './LearningMaterials';
import { type LearningSection } from './LearningSections';
import { definitionContent, definitionLabel, emptyConditions, emptyDefinition, lastConfirmed, stages, testLabels, workflowReportHtml } from './workflowUtils';
import { draftKey, newTestSuggestions, projectProposal, readDrafts, type WorkflowDrafts as Drafts } from './workflowDrafts';
import { WorkflowTestDrafts } from './WorkflowTestDrafts';
import { CollaborationChoice } from './CollaborationChoice';
import { ProjectReviewPanel } from './ProjectReviewPanel';
import { LearningTaskGuide } from './LearningTaskGuide';
import { appendLearningTask } from './workflowGuide';
import { LearningDocuments } from './LearningDocuments';
import { BoardArtwork } from './BoardArtwork';
import { asksDefinitionConfirmation, criteriaFromTests, definitionIssues, definitionProgress, latestSuggestedDefinition, latestSuggestedTests, sharedDefinitionStatus } from './definitionFeedback';
import './learning.css';
import './workflow.css';

function download(name: string, value: string, type='application/json') {
  const url=URL.createObjectURL(new Blob([value],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
const codeKey = (c: Pick<CodeReference,'mode'|'revision'>) => `${c.mode}:${c.revision ?? ''}`;

function Conditions({value}:{value:ProjectConditions}) {
  return <dl className="classroom-record-details">{Object.entries({实际接线:value.wiring,供电方式:value.power,装配条件:value.assembly,固件与库版本:value.firmware}).map(([label,text])=><div key={label}><dt>{label}</dt><dd>{text||'未记录'}</dd></div>)}</dl>;
}
function Definition({value}:{value?:ProjectDefinition}) {
  return value?<dl className="classroom-record-details">{Object.entries({问题:value.problem,使用者:value.audience,项目目标:value.goal,动作规则:value.behavior,验收条件:value.criteria.join('\n'),关键参数:value.parameters,异常处理:value.exceptionPolicy,制作要求:value.constraints}).map(([label,text])=><div key={label}><dt>{label}</dt><dd>{text||'未填写'}</dd></div>)}</dl>:<p>尚未保存目标。</p>;
}
export function LearningWorkflow({active,project,board,modules,section,sectionSelection,onSection,onSaved,onBusy,onDirty,onRegisterSave,onNew,blocked,engineeringDirty,hardwareDirty,onManageHardware,onHardwareDetail,refreshKey,reviewChange,onReviewConsumed,onCollaborate,onTask}: {
  active:boolean;project:Project|null;board?:HardwareSummary;modules:HardwareSummary[];
  section:LearningSection;sectionSelection:number;onSection:(section:LearningSection)=>void;
  onSaved:(id:string)=>Promise<void>;onBusy:(busy:boolean)=>void;onDirty:(dirty:boolean)=>void;onRegisterSave:(save:(()=>Promise<void>)|null)=>void;
  onNew:()=>void;blocked:boolean;engineeringDirty:boolean;refreshKey:number;
  hardwareDirty:boolean;onManageHardware:()=>void;onHardwareDetail:(item:HardwareSummary)=>void;
  reviewChange?:{projectId:string;id:string}|null;onReviewConsumed?:()=>void;onCollaborate:()=>void; onTask:(role:'engineer'|'structure',text:string)=>boolean;
}) {
  const pid=project?.id ?? 'scratch';
  const [mobileArea,setMobileArea]=useState<'records'|'chat'|'navigation'>('records');
  useEffect(()=>setMobileArea('records'),[section]);
  const [documentDirty,setDocumentDirty]=useState({teaching:false,archive:false});
  const teachingDirty=useCallback((v:boolean)=>setDocumentDirty(p=>p.teaching===v?p:{...p,teaching:v}),[]);
  const archiveDirty=useCallback((v:boolean)=>setDocumentDirty(p=>p.archive===v?p:{...p,archive:v}),[]);
  const documentSave=useRef<{teaching:(()=>Promise<void>)|null;archive:(()=>Promise<void>)|null}>({teaching:null,archive:null});
  const [hardwareConfirmed,setHardwareConfirmed]=useState('');
  const hardwareSignature=JSON.stringify([board?.componentId,board?.revision,modules.map(m=>[m.componentId,m.revision])]);
  const [view,setView]=useState<WorkflowView|null>(null), viewRef=useRef(view);viewRef.current=view;
  const [drafts,setDrafts]=useState<Drafts>(()=>readDrafts(pid));const draftRef=useRef(drafts);draftRef.current=drafts;
  // Keep the identity of an existing unsaved reflection without a view switch.
  const role:LearningRole=drafts.reflection?.role??'teacher';
  const [busy,setBusy]=useState(''),busyRef=useRef(false),[processing,setProcessing]=useState(false),processingRef=useRef(false);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[conflict,setConflict]=useState(false),[storageError,setStorageError]=useState('');
  const [selected,setSelected]=useState(''),[stage,setStage]=useState<TestStage>('module'),[collapsed,setCollapsed]=useState(true),[preview,setPreview]=useState(false);
  const [caption,setCaption]=useState(''),[showConditions,setShowConditions]=useState(false),[history,setHistory]=useState(false);
  const [editingGoal,setEditingGoal]=useState(false);
  const [showTests,setShowTests]=useState(()=>!!(drafts.test||drafts.generatedTests.length||Object.keys(drafts.observations).length));
  const [needsRead,setNeedsRead]=useState(false);
  const entered=useRef(false);
  const initialSelection=useRef(sectionSelection),latestSelection=useRef(sectionSelection);latestSelection.current=sectionSelection;
  const alive=useRef(true),loadingRequest=useRef(0),chatScroll=useRef<HTMLDivElement>(null),initialStage=useRef(false);
  const recordDirty=!!(drafts.changeId||drafts.definition||drafts.pendingDefinition||drafts.generatedTests.length||drafts.conditions||drafts.test||drafts.reflection||Object.keys(drafts.observations).length);
  const makingDirty=recordDirty||!!drafts.prompt.trim();
  const dirty=makingDirty||documentDirty.teaching||documentDirty.archive;
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;onRegisterSave(null);onDirty(false);};},[]);
  useEffect(()=>{onDirty(dirty);try{if(makingDirty)localStorage.setItem(draftKey(pid),JSON.stringify(drafts));else localStorage.removeItem(draftKey(pid));setStorageError('');}catch{setStorageError('浏览器未能备份草稿，请保存到项目或导出草稿后再离开。');}},[drafts,dirty,pid,onDirty]);
  useEffect(()=>{if(!dirty)return;const prevent=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue='';};window.addEventListener('beforeunload',prevent);return()=>window.removeEventListener('beforeunload',prevent);},[dirty]);
  const refresh = async () => {
    if(!project)return;
    const request=++loadingRequest.current;
    try {const result=await api<WorkflowView>(`/projects/${pid}/workflow`);if(alive.current&&request===loadingRequest.current){viewRef.current=result;setView(result);setError('');setNeedsRead(false);
      if(active&&!entered.current){
        entered.current=true;
        const pending=draftRef.current;
        const hasDraft=!!(pending.changeId||pending.definition||pending.pendingDefinition||pending.generatedTests.length||pending.conditions||pending.test||pending.reflection||Object.keys(pending.observations).length||pending.prompt.trim());
        if(latestSelection.current===initialSelection.current&&section==='guidance'&&!hasDraft&&result.checkpoint.definitions.at(-1)?.confirmed)onSection('project');
      }
      if(!initialStage.current){const activeCases=result.checkpoint.cases.filter(c=>c.active);setStage(draftRef.current.test?.stage??draftRef.current.generatedTests[0]?.stage??(activeCases.some(c=>c.stage==='module')?'module':activeCases[0]?.stage)??'module');initialStage.current=true;}
    }}
    catch(e){if(alive.current&&request===loadingRequest.current)setError(e instanceof Error?e.message:String(e));}
  };
  useEffect(()=>{if(!busyRef.current)void refresh();},[pid,project?.revision,refreshKey,active]);
  useEffect(()=>{
    if(!active||!view||!reviewChange||reviewChange.projectId!==pid)return;
    const change=view.checkpoint.changes?.find(c=>c.id===reviewChange.id);if(!change)return;
    if(change.status!=='proposed'){setError('这项变更已处理，请刷新记录。');onReviewConsumed?.();return;}
    if((draftRef.current.definition||draftRef.current.pendingDefinition)&&draftRef.current.changeId!==change.id){setError('已收到变更，请先保存当前定义草稿，再从“需求与同步”打开整理；原稿保持。');onReviewConsumed?.();return;}
    const prompt=`请整理作品目标，保留当前已确认定义中没有要求改变的部分，并落实这项需求变更：\n${change.summary}`;
    const previous=draftRef.current.prompt;const next=previous.trim()?previous+'\n\n'+prompt:prompt;
    if(next.length>4000){setError('当前输入较长，请先处理原输入，再打开变更。原输入保持。');onReviewConsumed?.();return;}
    setDrafts(p=>({...p,changeId:change.id,prompt:next,baseRevision:recordDirty?p.baseRevision:view.checkpoint.revision}));
    setNotice('调整内容已带入输入框。可发送给学习设计师整理，或手工修改右侧目标；确认后成为共用目标，再由你选择协作。');onSection('guidance');onReviewConsumed?.();
  },[active,pid,reviewChange,view]);
  useEffect(()=>{if(active)chatScroll.current?.scrollTo({top:chatScroll.current.scrollHeight,behavior:'smooth'});},[view?.checkpoint.messages.length,busy,active]);
  const edit = (update: Partial<Drafts>) => setDrafts(previous=>({...previous,...update,...('definition' in update?{definitionEdited:!!update.definition}:{}),baseRevision:previous.baseRevision ?? viewRef.current?.checkpoint.revision ?? null}));
  const working=!!busy||processing||blocked||!view||!project;
  const mutate=async(path:string,body:Record<string,unknown>,method='POST',onResult?:(result:WorkflowView)=>void):Promise<boolean>=>{
    if(!alive.current||busyRef.current||blocked||!project||!viewRef.current||needsRead)return false;
    busyRef.current=true;setBusy(path==='/guide'?'正在整理建议…':'正在保存…');onBusy(true);setError('');setNotice('');
    try{
      const result=await api<WorkflowView>(`/projects/${pid}/workflow${path}`,method,{...body,expectedRevision:draftRef.current.baseRevision ?? viewRef.current.checkpoint.revision});
      if(!alive.current)return false;
      loadingRequest.current++;viewRef.current=result;setView(result);setConflict(false);
      setDrafts(previous=>({...previous,baseRevision:result.checkpoint.revision}));
      setNotice(path==='/guide'?'回复已记录；生成内容已放入右侧，核对后保存。':'已保存到本机项目。');
      onResult?.(result);
      try{await onSaved(pid);}catch(e){if(alive.current)setError(`本机记录已保存，项目文件夹同步未完成：${e instanceof Error?e.message:String(e)}。请重试同步，无需重新发送或保存。`);}
      return true;
    }catch(e){if(alive.current){const uncertain=!(e instanceof ApiError);setNeedsRead(uncertain||e.status===409);setError((e instanceof Error?e.message:String(e))+(uncertain?'。保存结果未知，请先刷新记录核对，勿直接重发。':''));setConflict(uncertain||e.status===409);}return false;}
    finally{busyRef.current=false;if(alive.current)setBusy('');onBusy(false);}
  };
  const value=view?.checkpoint, definition=drafts.definition ?? (value?.definitions.at(-1) ? definitionContent(value.definitions.at(-1)!) : emptyDefinition);
  const historicalDefinition=latestSuggestedDefinition(value?.messages??[]);
  const restoreDefinition=(suggestion:ProjectDefinition)=>{
    if(!value)return;
    setDrafts(previous=>({...projectProposal(previous,{summary:'',question:null,definition:suggestion,tests:[],review:null},value.cases,value.revision),prompt:previous.prompt,baseRevision:previous.baseRevision??value.revision}));
    onSection('guidance');setMobileArea('records');
    setNotice('建议已载入目标卡，手工修改保留。请核对后点击「确认作品目标」，才会成为共用目标。');
    requestAnimationFrame(()=>jumpTo('workflow-definition-start'));
  };
  const conditions=drafts.conditions ?? value?.conditions ?? emptyConditions;
  const cases=value?.cases.filter(c=>c.active) ?? [], selectedCase=cases.find(c=>c.id===selected) ?? cases.find(c=>c.stage===stage);
  const emptyObservation=():TestObservation=>({caseId:selectedCase?.id??'',result:'blocked',observer:'',prediction:'',observed:'',explanation:'',changes:'',evidenceIds:[],code:{mode:view?.current.code.mode??'none',revision:view?.current.code.revision??null},structureRevision:view?.current.structure?.revision??null,expectedBaseline:view?.current.fingerprint??''});
  const observation=selectedCase ? drafts.observations[selectedCase.id] ?? emptyObservation() : emptyObservation();
  const updateObservation=(change:Partial<TestObservation>)=>{if(selectedCase)edit({observations:{...drafts.observations,[selectedCase.id]:{...observation,...change}}});};
  const reflection=drafts.reflection??{role,author:'',summary:'',learned:'',nextStep:''};
  const saveDefinition=async(confirmed=false)=>{if(confirmed&&definitionIssues(definition).length){setError('确认前请补充：'+definitionIssues(definition).map(i=>i.message).join('、'));focusField(definitionIssues(definition)[0].label);return;}if(await mutate('/definition',{definition:{...definition,criteria:definition.criteria.map(c=>c.trim()).filter(Boolean)},confirmed,...(drafts.changeId?{changeId:drafts.changeId}:{})})){setDrafts(p=>({...p,definition:null,definitionEdited:false,...(confirmed?{changeId:undefined}:{})}));if(confirmed){setEditingGoal(false);setNotice('作品说明已确认，可以继续动手制作。');}}};
  const saveConditions=async()=>{if(await mutate('/conditions',{conditions},'PUT'))setDrafts(p=>({...p,conditions:null}));};
  const saveCase=async()=>{if(!draftRef.current.test)return;if(!draftRef.current.test.title.trim()||!draftRef.current.test.procedure.trim()||!draftRef.current.test.expected.trim()){setError('请填写测试名称、步骤和预期结果。');return;}if(await mutate('/cases',{id:draftRef.current.test.id,title:draftRef.current.test.title,stage:draftRef.current.test.stage,componentId:draftRef.current.test.componentId,procedure:draftRef.current.test.procedure,expected:draftRef.current.test.expected,active:draftRef.current.test.active}))setDrafts(p=>({...p,test:null}));};
  const saveGeneratedTests=async()=>{
    const tests=newTestSuggestions(draftRef.current.generatedTests,viewRef.current?.checkpoint.cases??[]);
    if(!tests.length){edit({generatedTests:[]});setNotice('这些测试已经保存，未重复添加。');return;}
    if(tests.some(t=>!t.title.trim()||!t.procedure.trim()||!t.expected.trim())){setError('请补齐每项测试的名称、步骤和预期结果。');return;}
    if(tests.length>30||(viewRef.current?.checkpoint.cases.length??0)+tests.length>60){setError('每次最多保存30项，每个项目最多60项测试。请精简待保存清单后再保存，草稿已保留。');return;}
    if(await mutate('/case-batch',{tests})){edit({generatedTests:[]});setStage(tests[0].stage);setSelected('');onSection('project');}
  };
  const saveObservation=async()=>{if(engineeringDirty){setError('请先保存工程中的代码与硬件修改，再核对本次测试版本。');return;}if(await mutate('/runs',{...observation})){setDrafts(p=>{const rest={...p.observations};delete rest[observation.caseId];return {...p,observations:rest};});setSelected('');}};
  const saveReflection=async()=>{if(await mutate('/reflection',{...reflection,role:reflection.role??role}))setDrafts(p=>({...p,reflection:null}));};
  const saveCurrent=async()=>{
    if(section==='teaching'){await documentSave.current.teaching?.();return;}
    if(section==='outcomes'&&documentDirty.archive){await documentSave.current.archive?.();return;}
    if(draftRef.current.conditions){await saveConditions();return;}
    if(section==='guidance'&&draftRef.current.definition){await saveDefinition();return;}
    if(section==='project'&&draftRef.current.test){await saveCase();return;}
    if(section==='project'&&draftRef.current.generatedTests.length){await saveGeneratedTests();return;}
    if(section==='project'&&selectedCase&&draftRef.current.observations[selectedCase.id]){await saveObservation();return;}
    if(section==='outcomes'&&draftRef.current.reflection){await saveReflection();return;}
    if(project){await onSaved(pid);setNotice('项目记录已保存，文件夹状态见顶部提示。对话输入请点击发送，其他栏目的草稿仍保留。');}
  };
  useEffect(()=>{onRegisterSave(saveCurrent);});
  const send=async(answer?:string,testing=false)=>{
    if(hardwareDirty){setError('器件选择尚未保存，请先保存后再整理建议。');return;}
    const message=(answer??draftRef.current.prompt).trim();if(!message)return;
    const oldMessages=new Set(viewRef.current?.checkpoint.messages.map(m=>m.id));
    await mutate('/guide',{message,role,...(draftRef.current.changeId?{changeId:draftRef.current.changeId}:{})},'POST',result=>{
      const reply=[...result.checkpoint.messages].reverse().find(m=>m.role==='assistant'&&!oldMessages.has(m.id));
      if(!reply){setError('回复已记录，但未找到本轮建议，右侧原稿保留。');return;}
      let proposal:WorkflowProposal;
      try{proposal=JSON.parse(reply.content) as WorkflowProposal;}catch{setError('回复格式无法显示，右侧原稿保留。');return;}
      setDrafts(previous=>({...projectProposal(previous,proposal,result.checkpoint.cases,result.checkpoint.revision),prompt:previous.prompt.trim()===message?'':previous.prompt}));
      if(testing&&proposal.tests.length){onSection('project');setShowTests(true);setStage(proposal.tests[0].stage);}else if(proposal.definition)onSection('guidance');else if(proposal.tests.length){onSection('project');setShowTests(true);setStage(proposal.tests[0].stage);}
      setNotice(proposal.definition||proposal.tests.length?'已生成到右侧，可直接修改并保存。':'回复已记录，请继续补充。');
    });
  };
  const reviewProject=async()=>{
    if(engineeringDirty){setError('请先保存程序和器件选择，再检查整体成果。');return;}
    onSection('outcomes');setMobileArea('records');
    await mutate('/guide',{message:'请检查整体成果：对照已保存的目标、程序、结构和实际观察，给我整体状态、缺口、下一步和需要我决定的事项。',role,purpose:'review'},'POST',()=>setNotice('整体成果检查已保存。其他未保存草稿仍保留，请结合实际作品核对。'));
  };
  const addCriteria=async()=>{
    const d=value&&lastConfirmed(value);if(!d){setError('请先确认作品目标，再建立验收清单。');return;}
    const tests=d.criteria.map((expected,i)=>({title:`验收 ${i+1} · ${expected.slice(0,70)}`,stage:'system',componentId:'',procedure:'按本项条件操作，记录实际现象并与预期对照。',expected})).filter(t=>!cases.some(c=>c.stage==='system'&&c.expected===t.expected));
    if(!tests.length){setStage('system');setSelected('');setNotice('这些验收条件已在清单中，可直接选择测试。');return;}
    if(await mutate('/case-batch',{tests})){setStage('system');setSelected('');}
  };
  const uploadEvidence=async(file?:File)=>{
    if(!file||working||processingRef.current)return;
    processingRef.current=true;setProcessing(true);onBusy(true);setError('');
    try{
      if(file.size>12*1024*1024)throw new Error('请选择12MiB以内的图片，或500KiB以内的UTF-8日志。');
      let mime:'image/jpeg'|'text/plain',bytes:Uint8Array;
      if(['image/png','image/jpeg','image/webp'].includes(file.type)){
        const bitmap=await createImageBitmap(file);const ratio=Math.min(1,1400/Math.max(bitmap.width,bitmap.height));const canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*ratio);canvas.height=Math.round(bitmap.height*ratio);const ctx=canvas.getContext('2d');if(!ctx)throw new Error('无法处理图片。');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
        const blob=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(v=>v?resolve(v):reject(new Error('图片压缩失败。')),'image/jpeg',.75));bytes=new Uint8Array(await blob.arrayBuffer());mime='image/jpeg';
      }else if(/\.(txt|log|md|csv)$/i.test(file.name)){bytes=new Uint8Array(await file.arrayBuffer());new TextDecoder('utf-8',{fatal:true}).decode(bytes);mime='text/plain';}
      else throw new Error('支持JPG、PNG、WebP图片及UTF-8文本日志。');
      if(bytes.length>512000)throw new Error('附件仍超过500KiB，请裁剪图片或缩短日志。');
      let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
      const before=viewRef.current?.checkpoint.evidence.length??0;
      if(await mutate('/evidence',{name:file.name.replace(/[<>:"/\\\x00-\x1f]/g,'_').slice(0,95)+(mime==='image/jpeg'&&!/\.jpe?g$/i.test(file.name)?'.jpg':''),mime,content:btoa(binary),caption})){
        const added=viewRef.current?.checkpoint.evidence[before];setCaption('');if(added&&selectedCase)updateObservation({evidenceIds:[...observation.evidenceIds,added.id]});
      }
    }catch(e){if(alive.current)setError(e instanceof Error?e.message:String(e));}
    finally{processingRef.current=false;if(alive.current)setProcessing(false);onBusy(false);}
  };
  const exportProject=async()=>{try{const snapshot=await api<ProjectSnapshot>(`/projects/${pid}/snapshot`);download('zhangwen.project.json',JSON.stringify(snapshot,null,2));setNotice('已导出已保存的完整项目；本浏览器草稿未包含。');}catch(e){setError(e instanceof Error?e.message:String(e));}};
  const field=(label:string,text:string,onChange:(text:string)=>void,options:{rows?:number;placeholder?:string;maxLength?:number}={})=><label className="field" htmlFor={'workflow-field-'+encodeURIComponent(label)}>{label}<textarea id={'workflow-field-'+encodeURIComponent(label)} aria-label={label} aria-describedby={['项目目标 *','动作规则 *','验收条件 *（每行一条）'].includes(label)?'workflow-definition-hint':undefined} rows={options.rows??2} maxLength={options.maxLength??1500} value={text} placeholder={options.placeholder} disabled={working} onChange={e=>onChange(e.target.value)}/></label>;
  const confirmedDefinition=value&&lastConfirmed(value);
  const currentChange=value?.changes?.find(c=>c.status==='confirmed'&&c.definitionRevision===confirmedDefinition?.revision);
  const definitionProblems=definitionIssues(definition),definitionStatus=value?definitionProgress(value.definitions,drafts.definition):'正在读取';
  const proposedCriteria=criteriaFromTests(drafts.generatedTests).length?criteriaFromTests(drafts.generatedTests):criteriaFromTests(cases).length?criteriaFromTests(cases):criteriaFromTests(latestSuggestedTests(value?.messages??[]));
  const criteriaFit=proposedCriteria.length<=30&&proposedCriteria.every(c=>c.length<=500);
  const showGoalEditor=editingGoal||!!drafts.definition||!!drafts.pendingDefinition||!!drafts.changeId||!value?.definitions.at(-1)?.confirmed;
  const discussStep=(text:string)=>{const next=appendLearningTask(draftRef.current.prompt,text);if(next===null){setError('当前输入较长，请先处理原输入，再带入制作任务；原输入保持。');return;}edit({prompt:next});setMobileArea('chat');requestAnimationFrame(()=>document.getElementById('workflow-message')?.focus());};
  const recordTest=(id?:string)=>{const item=cases.find(c=>c.id===id);if(item){setStage(item.stage);setSelected(item.id);}setShowTests(true);setMobileArea('records');requestAnimationFrame(()=>jumpTo('workflow-tests'));};
  const jumpTo=(id:string)=>{const target=document.getElementById(id);let parent=target?.parentElement;while(parent){if(parent instanceof HTMLDetailsElement)parent.open=true;parent=parent.parentElement;}target?.scrollIntoView({block:'start'});target?.focus({preventScroll:true});};
  const focusField=(label:string)=>jumpTo('workflow-field-'+encodeURIComponent(label));
  const definitionHint=busy||processing?'正在处理，请稍候…':!project?'请先新建或加载项目。':!view?'尚未读取项目记录，请先刷新记录。':blocked?'其他操作进行中，请完成后继续。':definitionProblems.length?'确认前还需补充：'+definitionProblems.map(i=>i.message).join('、')+'。':drafts.definition?'内容已齐全，可保存草稿或确认作品目标。':value?.definitions.at(-1)?.confirmed?'当前定义已确认；修改内容后可保存新版本。':'定义草稿已保存，可直接确认；修改内容后才能再次保存草稿。';
  return <div hidden={!active} className={`learning-surface workflow-surface workflow-mobile-${mobileArea} ${collapsed?'learning-collapsed':''}`}>
    {section!=='teaching'&&<nav className="workflow-mobile-tabs" aria-label="学习设计师工作区切换">{([['records','项目记录'],['chat','和掌问讨论'],['navigation','项目导航']] as const).map(([id,label])=><button key={id} aria-pressed={mobileArea===id} onClick={()=>setMobileArea(id)}>{label}</button>)}</nav>}
    <LearningDocuments projectId={project?.id} teaching active={active&&section==='teaching'} disabled={blocked||!!busy||processing} onNew={onNew} onSaved={async id=>{await refresh();await onSaved(id);}} onDirty={teachingDirty} onBusy={onBusy} onRegisterSave={fn=>{documentSave.current.teaching=fn;}} refreshKey={value?.revision}/>
    <main hidden={section==='teaching'} className="learning-workbench" id="learning-section-content" aria-label="学习设计师工作区">
      <aside className="panel learning-conditions"><div className="panel-head"><h2><BookOpen size={17}/> 项目资料与工具</h2><button className="icon-button" aria-label="收起学习侧栏" onClick={()=>{setCollapsed(true);setMobileArea('records');}}><PanelLeftClose size={16}/></button></div><div className="learning-conditions-scroll">
        <div className="learning-project"><small>当前项目</small><strong>{project?.name??'尚未创建项目'}</strong></div>
        <section className="workflow-hardware" aria-label="项目器件">
          <h3>项目器件</h3><div className="project-hardware-summary"><BoardArtwork board={board}/><strong>{board?.displayName??'未选择主控板'}</strong></div>
          <button className="project-hardware-manage" disabled={blocked} onClick={onManageHardware}><CircuitBoard size={17}/>管理项目器件</button>
          <details className="compact-disclosure workflow-hardware-details"><summary>器件资料 · {modules.length} 个模块</summary>{board&&<button className="workflow-hardware-reference" disabled={working} onClick={()=>onHardwareDetail(board)}>查看主控使用资料</button>}
          {!board&&<p className="muted">可在这里选择主控，也可以先讨论作品或切换角色。</p>}
          {!!board&&!modules.length&&<p className="muted">还没有添加模块。只用主控自带功能时，可以直接开始。</p>}
          {modules.map(m=><div className="workflow-hardware-module" key={m.componentId}><button className="workflow-module-detail" aria-label={`查看${m.displayName}资料`} disabled={working} onClick={()=>onHardwareDetail(m)}><span>{m.displayName}</span><small>{cases.filter(c=>c.componentId===m.componentId).length} 项测试 · 查看资料</small></button></div>)}
          </details>{hardwareDirty&&<small className="workflow-hardware-note" role="status">器件选择有更改，请点“管理项目器件”核对并保存。</small>}
        </section>
        <button className="workflow-side-button" disabled={working} onClick={()=>{onSection('outcomes');setMobileArea('records');}}><ClipboardCheck size={15}/>查看整体成果</button>
        <button className="workflow-side-button" onClick={()=>setShowConditions(true)}><FileText size={15}/>实际接线与条件</button><button className="workflow-side-button" onClick={()=>setPreview(true)}><BookOpen size={15}/>材料模板与案例<small>预览</small></button>
        {dirty&&<button className="workflow-side-button" onClick={()=>download('掌问-学习草稿.json',JSON.stringify(drafts,null,2))}><Download size={15}/>导出当前草稿</button>}
      </div></aside>
      <section className="panel learning-chat"><div className="panel-head"><h2><Sparkles size={17}/>学习设计师</h2><small>陪你一步步完成作品</small></div>
        <details className="workflow-shared-goal compact-disclosure"><summary><span role="status">{project?sharedDefinitionStatus(value?.definitions):'请先打开项目'}</span><small>目标说明</small></summary><p>对话会逐步整理目标、功能与完成条件。你确认后的作品说明会供三师共同参考；具体协作仍由你决定。</p></details>
        <div className="workflow-conversation" ref={chatScroll}>{project&&section!=='outcomes'&&<section className="conversation-hardware-confirm" aria-label="确认制作器件">
          <strong>{!board?'先一起选一块主控板':hardwareDirty?'器件选择尚未保存':hardwareConfirmed===hardwareSignature?'本轮器件已确认':'这些器件适合这次作品吗？'}</strong>
          <div className="project-hardware-summary"><BoardArtwork board={board}/><strong>{board?.displayName??'未选择主控板'}</strong></div><p>{!board?'主控负责读取传感器、控制作品动作。':''}{modules.length?' · '+modules.map(m=>m.displayName).join('、'):board?' · 可以先用主控自带功能，也可以添加模块。':''}</p>
          <div className="workflow-actions"><button disabled={blocked} onClick={onManageHardware}>{!board?'选择主控':'调整器件'}</button>{board&&!hardwareDirty&&hardwareConfirmed!==hardwareSignature&&<button disabled={working} onClick={()=>{setHardwareConfirmed(hardwareSignature);setNotice('已确认本轮器件。可继续讨论作品，或逐项检查读数与动作。');}}>确认这些器件</button>}{board&&!hardwareDirty&&hardwareConfirmed===hardwareSignature&&<button disabled={working} onClick={()=>void send('请为已选主控和每个模块分别整理简单测试，说明接线、操作和应观察到的结果。未知条件写待确认，测试不代表已经通过。',true)}>逐个模块测试</button>}</div>
          {board&&!hardwareDirty&&hardwareConfirmed===hardwareSignature&&modules.map(m=><button key={m.componentId} disabled={working} onClick={()=>discussStep('请单独指导测试'+m.displayName+'，先核对接线与供电，再给出操作步骤和观察方法。')}>测试 {m.displayName}</button>)}
        </section>}{!project?<div className="workflow-empty"><FolderOpen size={32}/><h3>从一个项目开始</h3><p>项目会保留需求、测试、版本和学习记录。</p><button onClick={onNew}>新建项目</button></div>:<>
          {!value?.messages.length&&<div className="workflow-welcome"><h3>{section==='project'?'一起完成眼前这一步':'从想法开始，做出你的作品'}</h3><p>{!confirmedDefinition?'先说说想做什么，我会和你一起选器件、整理作品说明，再一步步指导制作。':'说说你想做什么、已经做到哪里，或遇到了什么问题。我会帮你拆成能动手的小任务，说明做法和完成标志。'}</p><div className="workflow-prompts">{(section==='guidance'?['根据已选器件，帮我确定要做的作品并整理项目目标']:section==='project'?['根据当前项目，告诉我下一步做什么、怎么做、怎样验证','根据最近观察，帮我分析问题并解释原因']:['帮我检查作品还缺什么，整理制作中的发现']).map(text=><button key={text} disabled={working} onClick={()=>edit({prompt:text})}>{text}</button>)}</div></div>}
          {value?.messages.map(m=>{
            if(m.role==='user')return <div className="workflow-chat-user" key={m.id}>{m.content}</div>;
            let reply:WorkflowProposal;try{reply=JSON.parse(m.content) as WorkflowProposal;}catch{return <p key={m.id}>历史建议格式无法显示，原记录保留。</p>;}
            const latest=m.id===value.messages.at(-1)?.id;
            return <article className="workflow-chat-reply" key={m.id}>
              <strong>掌问 · 建议</strong><p>{reply.summary}</p>
              {(reply.definition||!!reply.tests.length)&&<div className="workflow-reply-receipt"><ClipboardCheck size={14}/><span>{[reply.definition?'作品目标':'',reply.tests.length?`${reply.tests.length} 项测试`:''].filter(Boolean).join(' · ')}{latest?' · 在右侧核对与编辑':' · 建议已记入对话'}</span></div>}
              {reply.question&&latest&&<div className="answer-question"><strong>{reply.question.text}</strong><div className="answer-choices">{asksDefinitionConfirmation(reply)?<button disabled={working||!latest} onClick={()=>restoreDefinition(reply.definition!)}>核对并确认作品目标</button>:reply.question.options.map((o,i)=><button key={i} disabled={working||hardwareDirty||!latest} onClick={()=>void send(o)}>{o}</button>)}</div></div>}
              {reply.question&&!latest&&<details className="workflow-reply-history"><summary>当时讨论的问题</summary><p>{reply.question.text}</p></details>}
              {(reply.definition||!!reply.tests.length)&&<details className="workflow-reply-history"><summary>查看本轮原始建议</summary>{reply.definition&&<><strong>{reply.definition.goal}</strong><p>{reply.definition.behavior}</p><ul>{reply.definition.criteria.map((c,i)=><li key={i}>{c}</li>)}</ul></>}{reply.tests.map((t,i)=><div className="workflow-test-suggestion" key={i}><strong>{t.title}</strong><p>{t.procedure}</p><p>预期：{t.expected}</p></div>)}<button disabled={working} onClick={()=>{setDrafts(p=>({...projectProposal(p,reply,value.cases,value.revision),prompt:p.prompt,baseRevision:p.baseRevision??value.revision}));onSection(reply.definition?'guidance':'project');if(reply.tests.length)setShowTests(true);setNotice('已在右侧重新打开这轮内容，已保存记录与手工修改保留。');}}>在右侧重新编辑</button></details>}
            </article>;
          })}
        </>}{busy&&<p role="status"><LoaderCircle size={14} className="spin"/> {busy}</p>}</div>
        <div className="chat-form workflow-composer">{hardwareDirty&&<div className="workflow-hardware-prompt"><small>器件选择尚未保存，先保存再让掌问整理。</small><button disabled={working} onClick={onManageHardware}>打开项目器件</button></div>}<label className="sr-only" htmlFor="workflow-message">项目讨论</label><textarea id="workflow-message" rows={3} maxLength={4000} disabled={working} value={drafts.prompt} placeholder="说说想做什么、做到哪一步，或遇到了什么问题…" onChange={e=>edit({prompt:e.target.value})}/><div><small>目标与测试建议需核对保存</small><button className="primary icon-button" aria-label="发送项目讨论" disabled={working||hardwareDirty||!drafts.prompt.trim()} onClick={()=>void send()}><ArrowUp size={17}/></button></div></div>
      </section>
      <section className="panel learning-materials"><div className="filebar learning-filebar"><span><ClipboardCheck size={16}/>{section==='guidance'?'作品说明':section==='project'?'造物指导':'成果档案'}</span><small aria-label="当前栏目保存状态">{!project?'尚未打开项目':!value?'正在读取':section==='guidance'?(value.definitions.length?definitionStatus:drafts.definition?'编辑中 · 尚未保存目标':'尚未保存目标'):recordDirty?'有待保存内容':'已保存记录'}{section==='guidance'&&recordDirty&&!drafts.definition?' · 有待保存内容':''}</small><span className="filebar-space"/><button aria-label="刷新记录" disabled={working} onClick={()=>void refresh()}><RefreshCw size={15}/></button><button onClick={()=>{setCollapsed(false);setMobileArea('navigation');}} aria-expanded={!collapsed}>资料与工具</button>{section==='outcomes'&&<><button disabled={working} onClick={()=>void exportProject()}>导出完整项目</button><button disabled={working||!value?.revision} onClick={()=>value&&download('掌问-成果档案.html',workflowReportHtml(project?.name??'项目',value),'text/html;charset=utf-8')}><Download size={15}/>导出可打印报告</button></>}</div>
        <div className="workflow-feedback" aria-live="polite">{error&&<p className="chat-error" role="alert">{error}</p>}{storageError&&<p role="alert">{storageError}</p>}{notice&&<p role="status">{notice}</p>}{conflict&&<div><button disabled={working} onClick={()=>void refresh()}>刷新记录，保留草稿</button><details><summary>对照最新已保存记录</summary><Definition value={value?.definitions.at(-1)}/>{value&&<Conditions value={value.conditions}/>}<h4>已保存测试</h4>{value?.cases.map(c=><p key={c.id}>{c.title}：{c.expected}</p>)}</details><button disabled={working||drafts.baseRevision===value?.revision} onClick={()=>{setDrafts(p=>({...p,baseRevision:view?.checkpoint.revision??null}));setConflict(false);setError('');setNotice('已按你核对后的最新记录继续编辑；尚未覆盖或保存。');}}>已核对差异，继续编辑当前草稿</button></div>}</div>
        <div className="workflow-document">
          {section==='guidance'&&value&&!value.definitions.length&&historicalDefinition&&(!drafts.definition||drafts.definitionEdited)&&!drafts.pendingDefinition&&<section className="workflow-goal-recovery" aria-label="找回目标建议"><strong>有一份尚未保存的目标建议</strong><button title="载入后核对并确认；已有手工修改会保留供你对照" disabled={working} onClick={()=>restoreDefinition(historicalDefinition)}>载入最近目标建议</button></section>}
          {section==='guidance'&&drafts.changeId&&<section className="workflow-change-context"><strong>正在整理需求变更</strong><p>{value?.changes?.find(c=>c.id===drafts.changeId)?.summary??'正在读取变更内容…'}</p><p>请核对调整后的完整目标。确认后由你选择结构工程师、智能工程师、两位或暂不协作。</p><button disabled={working} onClick={()=>setDrafts(p=>({...p,changeId:undefined}))}>暂不关联此变更，保留当前草稿</button></section>}
          {!!drafts.generatedTests.length&&section==='guidance'&&<div className="workflow-draft-link"><span>同时生成了 {drafts.generatedTests.length} 项测试，已放入右侧清单。</span><button onClick={()=>{onSection('project');setShowTests(true);}}>查看测试清单</button></div>}
          {section==='guidance'&&drafts.pendingDefinition&&<section className="workflow-pending-definition" aria-label="新的定义建议"><p>已保留你的手工修改。新生成的定义可在下方对照。</p><details><summary>查看新的定义建议</summary><dl>{Object.entries({问题:drafts.pendingDefinition.problem,使用者:drafts.pendingDefinition.audience,目标:drafts.pendingDefinition.goal,动作规则:drafts.pendingDefinition.behavior,关键参数:drafts.pendingDefinition.parameters,异常处理:drafts.pendingDefinition.exceptionPolicy,制作约束:drafts.pendingDefinition.constraints,验收条件:drafts.pendingDefinition.criteria.join('\n')}).map(([label,text])=><div key={label}><dt>{label}</dt><dd>{text||'未填写'}</dd></div>)}</dl><div className="workflow-actions"><button disabled={working} onClick={()=>setDrafts(p=>({...p,definition:p.pendingDefinition,pendingDefinition:null,definitionEdited:false}))}>替换为新建议</button><button disabled={working} onClick={()=>edit({pendingDefinition:null})}>保留我的修改</button></div></details></section>}
          {section==='guidance'&&!showGoalEditor&&confirmedDefinition&&<section className="making-goal-summary" aria-label="已确认作品目标"><small>V{confirmedDefinition.revision} · 已确认</small><h3>{confirmedDefinition.goal}</h3><p>{confirmedDefinition.behavior}</p><details className="classroom-details"><summary>查看完成条件与完整目标</summary><Definition value={confirmedDefinition}/></details><div className="workflow-actions"><button className="primary" onClick={()=>onSection('project')}>继续制作</button><button disabled={working} onClick={()=>{setEditingGoal(true);requestAnimationFrame(()=>focusField('项目目标 *'));}}>调整作品目标</button></div></section>}
          {section==='guidance'&&showGoalEditor&&<><p className="muted">可以继续对话整理作品说明，核对后确认；需要时再展开手工补充。</p>{definition.goal&&<Definition value={definition}/>}<details className="classroom-details" open={editingGoal}><summary>手工补充作品说明</summary><div className="workflow-record-anchor" id="workflow-definition-start" tabIndex={-1} aria-label="作品目标填写区"/>
{field('项目目标 *',definition.goal,text=>edit({definition:{...definition,goal:text}}))}{field('动作规则 *',definition.behavior,text=>edit({definition:{...definition,behavior:text}}),{maxLength:2000,placeholder:'例如：靠近时打开盒盖，离开3秒后关闭'})}
            {field('验收条件 *（每行一条）',definition.criteria.join('\n'),text=>edit({definition:{...definition,criteria:text.split('\n')}}),{rows:3,maxLength:15000,placeholder:'持续停留时保持打开\n等待关闭时再次靠近应取消计时'})}
            <details className="classroom-details"><summary>补充使用场景、参数和制作要求（选填）</summary>            {field('要解决的问题',definition.problem,text=>edit({definition:{...definition,problem:text}}),{placeholder:'例如：双手拿着物品时，不方便手动开盖'})}{field('使用者与场景',definition.audience,text=>edit({definition:{...definition,audience:text}}),{rows:1,maxLength:500})}<div className="workflow-two-fields">{field('关键参数',definition.parameters,text=>edit({definition:{...definition,parameters:text}}),{maxLength:1000,placeholder:'距离、时间、角度等；未测量写待确认'})}{field('异常处理',definition.exceptionPolicy,text=>edit({definition:{...definition,exceptionPolicy:text}}),{maxLength:1000,placeholder:'读数无效或动作未到位时怎么办？'})}</div>{field('制作与学习约束',definition.constraints,text=>edit({definition:{...definition,constraints:text}}),{placeholder:'材料、尺寸、课时、已有基础或预算'})}</details>
            </details><section className="workflow-definition-check" aria-label="作品目标状态"><p id="workflow-definition-hint" role="status">{definitionHint}</p>{!drafts.definition&&!!value?.definitions.length&&!value.definitions.at(-1)?.confirmed&&<small>当前草稿已保存；补齐后确认，才会用于工程与结构设计。</small>}<div className="workflow-actions">{definitionProblems.length>0&&<button disabled={working} onClick={()=>focusField(definitionProblems[0].label)}>填写缺失内容</button>}{!definition.criteria.some(c=>c.trim())&&proposedCriteria.length>0&&<button disabled={working||!criteriaFit} title={criteriaFit?'将已有整机测试的预期填入定义草稿，核对后再确认':'测试预期较长，请手工整理为每条500字以内、最多30条'} onClick={()=>{edit({definition:{...definition,criteria:proposedCriteria}});setNotice('已将整机测试预期补入验收条件草稿，请核对后确认；未记录实测通过。');focusField('验收条件 *（每行一条）');}}>从测试预期补充（{proposedCriteria.length}条）</button>}</div></section>
            <div className="workflow-actions"><button aria-describedby="workflow-definition-hint" title={!drafts.definition?'当前没有新的定义修改；已保存草稿可补齐后直接确认':undefined} disabled={working||!drafts.definition} onClick={()=>void saveDefinition(false)}><Save size={15}/>保存定义草稿</button><button className="primary" aria-describedby="workflow-definition-hint" disabled={working||definitionProblems.length>0} onClick={()=>void saveDefinition(true)}><Check size={15}/>确认作品目标</button></div>

          </>}
          {section==='guidance'&&!!value?.definitions.length&&<details className="classroom-details"><summary>查看以前的目标</summary>{value&&value.definitions.length>0&&<label className="field">查看历史定义<select id="workflow-definition-history" aria-label="作品目标历史" value="" onChange={e=>{const d=value.definitions.find(v=>v.revision===Number(e.target.value));if(d){if(drafts.definition){setError('请先保存当前定义草稿，历史版本保持。');return;}edit({definition:definitionContent(d)});setNotice(`已载入 V${d.revision} 为草稿，确认前不会替换现行定义。`);}}}><option value="">当前：{definitionLabel(value.definitions.at(-1))}</option>{[...value.definitions].reverse().map(d=><option value={d.revision} key={d.revision}>{definitionLabel(d)} · {d.goal.slice(0,25)}</option>)}</select></label>}</details>}
          {section==='guidance'&&currentChange&&<details className="classroom-details"><summary>选择协作伙伴</summary>{currentChange&&<><CollaborationChoice key={currentChange.id} projectId={pid} change={currentChange} disabled={working||needsRead} onSave={roles=>mutate(`/changes/${currentChange.id}/collaboration`,{roles},'PUT')}/><button className="workflow-side-button" onClick={onCollaborate}>查看协作任务与处理记录</button></>}</details>}
          {section==='project'&&<><div className="workflow-actions"><button onClick={()=>onSection('guidance')}>查看作品说明</button><button disabled={working} onClick={()=>discussStep('请结合我们的讨论整理一份完整的作品需求说明（PRD），包括背景、使用者、目标、功能流程、参数、范围限制、异常处理和完成条件；未知项注明待确认。')}>从讨论整理作品说明</button></div><LearningTaskGuide view={view} disabled={working||needsRead||hardwareDirty} selected={selected} pendingTests={drafts.generatedTests.length} onDefine={()=>onSection('guidance')} onRecord={recordTest} onSummary={()=>onSection('outcomes')} onTask={(role,text)=>{if(!onTask(role,text))setError('对应输入较长或当前状态不允许切换，请先处理原输入；制作任务与草稿保留。');}} onDiscuss={discussStep} onConditions={()=>setShowConditions(true)} onCollaborate={onCollaborate}/><details className="making-tests classroom-details" open={showTests} onToggle={e=>setShowTests(e.currentTarget.open)}><summary id="workflow-tests">测试要求与实际记录{drafts.generatedTests.length?` · ${drafts.generatedTests.length} 项待保存`:''}</summary><WorkflowTestDrafts tests={drafts.generatedTests} modules={view?.current.modules??[]} disabled={working} onChange={generatedTests=>edit({generatedTests})} onSave={()=>void saveGeneratedTests()}/><div className="workflow-tabs" role="group" aria-label="测试阶段">{Object.entries(stages).map(([key,label])=><button key={key} aria-pressed={stage===key} onClick={()=>{setStage(key as TestStage);setSelected('');}}>{label}</button>)}</div><div className="workflow-actions"><button disabled={working||!!drafts.test} onClick={()=>edit({test:{title:'',stage,componentId:'',procedure:'',expected:'',active:true}})}><Plus size={14}/>添加测试项</button><button disabled={working||!confirmedDefinition} onClick={()=>void addCriteria()}>从已确认条件建立清单</button></div>
            {drafts.test&&<fieldset className="workflow-case-form" disabled={working}><legend>{drafts.test.id?'修改测试项':'新测试项'}</legend>{field('测试名称 *',drafts.test.title,text=>edit({test:{...drafts.test!,title:text}}),{rows:1,maxLength:100})}<div className="workflow-two-fields"><label className="field">阶段<select value={drafts.test.stage} onChange={e=>edit({test:{...drafts.test!,stage:e.target.value as TestStage}})}>{Object.entries(stages).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label><label className="field">关联器件<select value={drafts.test.componentId} onChange={e=>edit({test:{...drafts.test!,componentId:e.target.value}})}><option value="">整机 / 不指定模块</option>{drafts.test.componentId&&!view?.current.modules.some(m=>m.id===drafts.test!.componentId)&&<option value={drafts.test.componentId}>原关联器件（已移出项目）</option>}{view?.current.modules.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label></div>{field('测试步骤 *',drafts.test.procedure,text=>edit({test:{...drafts.test!,procedure:text}}))}{field('预期结果 *',drafts.test.expected,text=>edit({test:{...drafts.test!,expected:text}}))}<div className="workflow-actions"><button onClick={()=>edit({test:null})}>取消编辑</button><label className="workflow-checkbox"><input type="checkbox" checked={drafts.test.active} onChange={e=>edit({test:{...drafts.test!,active:e.target.checked}})}/>启用此测试项</label><button className="primary" onClick={()=>void saveCase()}>保存测试项</button></div></fieldset>}
            <div className="workflow-test-list">{cases.filter(c=>c.stage===stage).map(c=>{const state=view?.caseStates.find(s=>s.id===c.id);return <button key={c.id} className={selectedCase?.id===c.id?'selected':''} onClick={()=>setSelected(c.id)}><span>{c.title}</span><small className={`workflow-status ${state?.status??'unrecorded'}`}>{testLabels[state?.status??'unrecorded']}</small></button>;})}</div>
            {!!value?.cases.some(c=>!c.active&&c.stage===stage)&&<details><summary>已停用的测试项</summary>{value.cases.filter(c=>!c.active&&c.stage===stage).map(c=><button key={c.id} disabled={working||!!drafts.test} onClick={()=>edit({test:{...c}})}>{c.title} · 查看与恢复</button>)}</details>}{!cases.some(c=>c.stage===stage)&&<p className="muted">这一阶段还没有测试项。可新增一项，或请掌问协助整理。</p>}
            {selectedCase&&<section className="workflow-observation"><header><h3>{selectedCase.title}</h3><button disabled={working||!!drafts.test} onClick={()=>edit({test:{...selectedCase}})}>修改要求</button></header><p><strong>操作：</strong>{selectedCase.procedure}</p><p><strong>预期：</strong>{selectedCase.expected}</p>{view?.caseStates.find(s=>s.id===selectedCase.id)?.reasons.map(reason=><p className="workflow-warning" key={reason}>{reason}，请重新测试。</p>)}
              <details className="workflow-versions"><summary>本次使用的版本与条件</summary><label className="field">程序版本<select value={codeKey(observation.code)} disabled={working} onChange={e=>{const [mode,revision]=e.target.value.split(':');updateObservation({code:{mode:mode as CodeReference['mode'],revision:revision?Number(revision):null}});}}><option value="none:">不关联程序</option>{view?.codeVersions.map(c=><option key={codeKey(c)} value={codeKey(c)}>{c.mode} · V{c.revision} · {c.name}</option>)}</select></label><label className="field">结构版本<select value={observation.structureRevision??''} disabled={working} onChange={e=>updateObservation({structureRevision:e.target.value?Number(e.target.value):null})}><option value="">不关联结构</option>{view?.structureVersions.map(s=><option key={s.revision} value={s.revision}>V{s.revision} · {s.name}</option>)}</select></label><p>{view?.current.boardName} · 需求{view?.current.definitionRevision ? `V${view.current.definitionRevision}`:'未确认'}</p><button onClick={()=>setShowConditions(true)}>查看接线与供电条件</button></details>
              {observation.expectedBaseline!==view?.current.fingerprint&&<div className="workflow-warning"><p>填写期间项目条件发生变化，请核对实际测试版本。</p><button onClick={()=>updateObservation({expectedBaseline:view!.current.fingerprint,code:{mode:view!.current.code.mode,revision:view!.current.code.revision},structureRevision:view!.current.structure?.revision??null})}>本次使用当前已保存版本</button></div>}
              {field('实际现象 *',observation.observed,text=>updateObservation({observed:text}),{rows:3,maxLength:3000,placeholder:'记录读数、动作或报错；不能用上传成功代替实物观察'})}<div className="workflow-two-fields"><label className="field">实测结果<select disabled={working} value={observation.result} onChange={e=>updateObservation({result:e.target.value as TestObservation['result']})}><option value="blocked">暂时无法测试</option><option value="passed">我已观察，确认通过</option><option value="failed">我已观察，未通过</option></select></label><label className="field">观察人 *<input disabled={working} maxLength={100} value={observation.observer} onChange={e=>updateObservation({observer:e.target.value})}/></label></div><details className="classroom-details" open={!!(observation.prediction||observation.explanation||observation.changes)||undefined}><summary>补充预测、解释与下一步（选填）</summary>{field('我的预测',observation.prediction,text=>updateObservation({prediction:text}))}{field('我的解释',observation.explanation,text=>updateObservation({explanation:text}),{maxLength:2000})}{field('修改原因与下一步',observation.changes,text=>updateObservation({changes:text}))}</details>
              {!!value?.evidence.length&&<fieldset className="workflow-evidence-choice"><legend>关联图片与日志</legend>{value.evidence.map(e=><label key={e.id}><input type="checkbox" disabled={working} checked={observation.evidenceIds.includes(e.id)} onChange={event=>updateObservation({evidenceIds:event.target.checked?[...observation.evidenceIds,e.id]:observation.evidenceIds.filter(id=>id!==e.id)})}/>{e.name}</label>)}</fieldset>}
              <button className="primary" disabled={working||engineeringDirty||!observation.observed.trim()||!observation.observer.trim()} onClick={()=>void saveObservation()}>保存本次观察</button>{engineeringDirty&&<p className="workflow-warning">工程中还有未保存的代码或硬件修改，请先保存后再记录测试版本。</p>}
            </section>}
            {!!value?.runs.length&&<button className="workflow-history-toggle" onClick={()=>setHistory(!history)}>{history?'收起':'查看'}测试历史 · {value?.runs.length??0} 次</button>}{history&&[...(value?.runs??[])].reverse().map(r=><details className="workflow-run" key={r.id}><summary>{r.test.title} · {testLabels[r.result]} · {new Date(r.createdAt).toLocaleString()}</summary><p>{r.observer}：{r.observed}</p><p>{r.changes}</p><p>需求 V{r.baseline.definitionRevision??'未确认'} · {r.baseline.code.mode} V{r.baseline.code.revision??'无'} · 结构 V{r.baseline.structure?.revision??'无'}</p><Conditions value={r.baseline.conditions}/><p>关联证据：{r.evidenceIds.map(id=>value?.evidence.find(e=>e.id===id)?.name??id).join('、')||'无'}</p></details>)}
          </details></>}
          <LearningDocuments projectId={project?.id} teaching={false} active={active&&section==='outcomes'} disabled={blocked||!!busy||processing} onNew={onNew} onSaved={async id=>{await refresh();await onSaved(id);}} onDirty={archiveDirty} onBusy={onBusy} onRegisterSave={fn=>{documentSave.current.archive=fn;}} refreshKey={value?.revision}/>
          {section==='outcomes'&&<><details className="classroom-details"><summary>作品检查、制作反思与反馈</summary><ProjectReviewPanel view={view} disabled={working||needsRead} unsaved={engineeringDirty} onReview={()=>void reviewProject()}/><div id="workflow-overview" className="making-outcome-summary"><p>{value?.runs.length?`已记录 ${value.runs.length} 次观察；保存和检查不能代替实物验收。`:'还没有实际观察。可以先检查资料缺口，或到制作指导记录一次测试。'}</p><button onClick={()=>onSection('project')}>返回制作指导</button></div>
            <details className="classroom-details" open={!!drafts.reflection||undefined}><summary>补充制作反思与反馈</summary><div id="workflow-reflection" tabIndex={-1} className="workflow-record-anchor"><label className="field">记录人 *<input maxLength={100} disabled={working} value={reflection.author} onChange={e=>edit({reflection:{...reflection,author:e.target.value}})}/></label>{field('制作中的发现与反馈 *',reflection.summary,text=>edit({reflection:{...reflection,summary:text}}),{rows:3,maxLength:3000})}{field('发现与依据',reflection.learned,text=>edit({reflection:{...reflection,learned:text}}),{maxLength:3000,placeholder:'例如：这次调整解决了什么问题，有什么现象支持？'})}{field('下一步',reflection.nextStep,text=>edit({reflection:{...reflection,nextStep:text}}))}<button className="primary" disabled={working||!reflection.author.trim()||!reflection.summary.trim()} onClick={()=>void saveReflection()}>保存反思与反馈</button></div></details>
            {[...(value?.reflections??[])].reverse().map(r=><details key={r.revision} className="workflow-run"><summary>{r.role==='teacher'?'教师反馈':'学生反思'} · {r.author} · V{r.revision}</summary><p>{r.summary}</p><p>{r.learned}</p><p>{r.nextStep}</p></details>)}
          </details></>}
          {(section==='project'||section==='outcomes')&&<details className="classroom-details"><summary>图片与日志{value?.evidence.length?` · ${value.evidence.length} 份`:""}</summary><section id="workflow-evidence" tabIndex={-1} className="workflow-evidence workflow-record-anchor"><h3>图片与日志</h3><label className="field">证据说明<input maxLength={1000} value={caption} disabled={working} placeholder="例如：探头接线近照、第三次测试串口输出" onChange={e=>setCaption(e.target.value)}/></label><label className={`workflow-upload ${working?'disabled':''}`}><ImagePlus size={16}/>添加图片或日志<input type="file" aria-label="添加图片或日志" accept="image/png,image/jpeg,image/webp,.txt,.log,.md,.csv" disabled={working} onChange={e=>{const f=e.target.files?.[0];e.target.value='';void uploadEvidence(f);}}/></label><small>图片会自动压缩，每份最多500 KiB，只保存在当前项目中。</small><div className="workflow-evidence-grid">{value?.evidence.map(e=><figure key={e.id}>{e.mime.startsWith('image/')?<a href={`data:${e.mime};base64,${e.content}`} download={e.name}><img src={`data:${e.mime};base64,${e.content}`} alt={e.caption||e.name}/></a>:<FileText size={24}/>}<figcaption>{e.name}<small>{e.caption}</small></figcaption></figure>)}</div></section></details>}
        </div>
        {dirty&&<footer className="learning-material-footer"><span>有草稿 · 本浏览器保留{drafts.definition&&section!=='guidance'?' · 目标修改待保存':''}{drafts.reflection&&section!=='outcomes'?' · 反思待保存':''}{Object.keys(drafts.observations).length&&section!=='project'?' · 观察待保存':''}</span></footer>}
      </section>
    </main>
    {active&&showConditions&&<Dialog title="本项目的实际条件" onClose={()=>setShowConditions(false)}><p className="muted">记录本次实际使用的条件；模块资料中的默认案例不会自动替代这里的记录。</p>{field('固件与库版本',conditions.firmware,text=>edit({conditions:{...conditions,firmware:text}}),{maxLength:1000})}{field('实际接线',conditions.wiring,text=>edit({conditions:{...conditions,wiring:text}}),{maxLength:2000,placeholder:'模块 → 接口/引脚；I²C地址与总线'})}{field('供电方式',conditions.power,text=>edit({conditions:{...conditions,power:text}}),{maxLength:1000,placeholder:'电源电压、供电对象、独立供电和共地；未确认写待确认'})}{field('装配条件',conditions.assembly,text=>edit({conditions:{...conditions,assembly:text}}),{placeholder:'空载/带载、固定方式、开合空间和实测尺寸'})}<div aria-live="polite">{error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}{conflict&&<button onClick={()=>setShowConditions(false)}>返回记录，核对保存冲突</button>}</div><button className="primary" disabled={working||!drafts.conditions} onClick={()=>void saveConditions()}>保存实际条件</button></Dialog>}
    {active&&preview&&<Dialog title="学习材料与案例预览" className="workflow-template-dialog" onClose={()=>setPreview(false)}><LearningWorkspace active projectName={project?.name??'项目'} project={project} board={board} modules={modules} role={role} section={section} onSection={onSection}/></Dialog>}
  </div>;
}
