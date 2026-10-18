import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowUp, BookOpen, Check, ChevronRight, Download, FilePenLine, FileText, GraduationCap, Image, Layers3, LayoutTemplate, Lightbulb, Link2, Maximize, Minimize, NotebookPen, PanelLeftClose, PanelLeftOpen, Settings2, Sparkles, Target, UploadCloud, UserRound } from 'lucide-react';
import type { HardwareSummary, Project } from '../../../packages/contracts/src/platform';
import { Dialog } from './Dialog';
import { goals, pending, stages, type LearningRole, type Material, type CompetitionPage } from './LearningMaterials';
import { learningTemplates, LearningMaterialPreview, templateIcons } from './LearningTemplates';
import { learningSections, sectionMaterials, sectionNavigation, type LearningSection, type PreviewDialog } from './LearningSections';
import './learning.css';

const materialActions: Record<Material, string> = {definition:'确认项目定义卡', questions:'保存问题记录', plan:'生成任务单', task:'整理任务记录', rubric:'生成评价量规', portfolio:'记录学习证据', record:'保存探究记录', work:'整理作品说明', reflection:'保存自评反思', poster:'生成海报', competition:'导出材料包'};

/** UI preview only. No API, file picker, model call, or persisted learning state. */
export function LearningWorkspace({active, projectName, project, board, modules, role, onRole, section, onSection, roleDialog, onCloseRole}: {
  active: boolean; projectName: string; project: Project | null; board?: HardwareSummary; modules: HardwareSummary[];
  role: LearningRole; onRole: (role: LearningRole) => void; roleDialog: boolean; onCloseRole: () => void;
  section: LearningSection; onSection: (section: LearningSection) => void;
}) {
  const [selectedMaterials, setSelectedMaterials] = useState<Record<LearningRole, Record<LearningSection, Material>>>({
    teacher:{guidance:'definition', project:'plan', outcomes:'portfolio'},
    student:{guidance:'definition', project:'task', outcomes:'work'},
  });
  const [templateChoices, setTemplateChoices] = useState<Record<string, string>>({});
  const [templateDraft, setTemplateDraft] = useState<string | null>(null);
  const [templatePage, setTemplatePage] = useState<CompetitionPage>('requirements');
  const [competitionPages, setCompetitionPages] = useState<Record<LearningRole, CompetitionPage>>({teacher:'requirements', student:'requirements'});
  const material=selectedMaterials[role][section], materials=sectionMaterials[section][role], teacher=role === 'teacher';
  const sectionInfo=learningSections.find(item=>item.id === section)!;
  const roleName=teacher ? '教师工作台' : '学生工作台';
  const sideTitle=section === 'guidance' ? '梳理想法' : section === 'outcomes' ? (teacher ? '成果整理' : '我的成果') : (teacher ? '教学准备' : '我的任务');
  const setMaterial = (id: Material) => setSelectedMaterials(value=>({...value, [role]:{...value[role], [section]:id}}));
  const changeSection = (id: LearningSection) => onSection(id);
  const welcome=section === 'guidance' ? {
    tag:'先把问题想清楚', title:<>从一个想法<br/>找到值得做的项目</>, intro:'从兴趣或生活中的困惑出发，澄清需求，整理当前推荐方案与待确认事项。',
    step:'从一个真实问题开始', question:'这个想法，想帮助谁？', detail:'观察他们在什么场景遇到困难，再想想怎样知道作品有效。还没有想法也可以从身边的问题开始。',
    button:'查看项目定义卡示例', flow:'创意 → 追问 → 整理 → 方案 → 确认', generate:'整理项目定义卡',
  } : section === 'outcomes' ? {
    tag:teacher ? '让学习成果被看见' : '把我的作品讲清楚', title:<>整理作品与证据<br/>分享创造的价值</>, intro:teacher ? '回看班级作品与学习证据，准备成果展示和赛事材料。' : '整理作品说明、图片和测试记录，准备海报与参赛材料。',
    step:'从已有作品与证据开始', question:teacher ? '这次想展示哪些学习成果？' : '你最想展示作品的哪一点？', detail:'先整理做了什么、为什么这样设计，以及能够说明效果的测试证据。',
    button:teacher ? '查看成果总览示例' : '查看作品说明示例', flow:'整理作品 → 补充证据 → 展示与参赛', generate:'整理成果材料',
  } : {
    tag:teacher ? '陪你设计学习' : '陪你发现与创造', title:teacher ? <>让作品成为一次<br/>有目标的学习</> : <>把我的想法<br/>变成有证据的作品</>, intro:teacher ? '从学生需要学会什么出发，组织探索、实践与反思。' : '一起提出问题、动手验证，记录发现并分享你的创造。',
    step:teacher ? '先了解学习条件' : '从一个好问题开始', question:teacher ? '这次学习面向哪些学生？' : '你的作品想解决什么问题？', detail:teacher ? '先确认学段、课时与已有基础，再细化目标和任务。' : '先说清想帮助谁、为什么需要它，再看看可以怎样验证。',
    button:teacher ? '查看学习设置' : '查看我的任务示例', flow:teacher ? '确认目标 → 设计活动 → 整理材料' : '提出问题 → 动手验证 → 分享收获', generate:teacher ? '生成学习方案' : '开始我的探究',
  };
  const options=learningTemplates(role, material), templateKey=`${role}:${material}`;
  const selectedTemplate=options.find(item=>item.id === templateChoices[templateKey]) ?? options[0];
  const draftTemplate=options.find(item=>item.id === templateDraft) ?? selectedTemplate;
  const [collapsed, setCollapsed] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [dialog, setDialog] = useState<PreviewDialog | null>(null);
  const documentPane=useRef<HTMLDivElement>(null);
  const conditionsPane=useRef<HTMLDivElement>(null), conversationPane=useRef<HTMLDivElement>(null);
  const templatePane=useRef<HTMLDivElement>(null);
  useEffect(()=>{documentPane.current?.scrollTo({top:0});},[role, material, selectedTemplate.id, competitionPages[role]]);
  useEffect(()=>{templatePane.current?.scrollTo({top:0});},[templateDraft, templatePage]);
  useEffect(()=>{conditionsPane.current?.scrollTo({top:0}); conversationPane.current?.scrollTo({top:0}); documentPane.current?.scrollTo({top:0});},[role, section]);
  useEffect(()=>{setDialog(null); setTemplateDraft(null);},[section]);
  useEffect(() => { if (!active) {setDialog(null); setTemplateDraft(null); setFullscreen(false);} }, [active]);
  useEffect(() => {
    if (!active || !fullscreen) return;
    const outside=Array.from(document.querySelectorAll<HTMLElement>('.workspace-titlebar, .zhangwen-toolbar, .learning-conditions, .learning-restore, .learning-chat, .statusbar')).map(node=>({node, inert:node.inert}));
    outside.forEach(({node})=>{node.inert=true;});
    const close = (e: globalThis.KeyboardEvent) => {if (e.key === 'Escape' && !document.querySelector('dialog[open]')) setFullscreen(false);};
    window.addEventListener('keydown', close);
    return () => {window.removeEventListener('keydown', close); outside.forEach(({node,inert})=>{node.inert=inert;});};
  }, [active, fullscreen]);
  const showMaterial = (id: Material) => setMaterial(id);
  const switchTab = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? materials.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + materials.length) % materials.length;
    setMaterial(materials[next].id);
    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  };
  const dialogTitles = {settings:'学习设置', goals:'目标与任务', resources:'添加教学资料', project:'关联项目成果'};
  return <div className={`learning-surface ${collapsed ? 'learning-collapsed' : ''} ${fullscreen ? 'learning-fullscreen' : ''}`} hidden={!active}>
    <p className="sr-only" id="learning-section-description">{sectionInfo.description}</p>
    <main className="learning-workbench" id="learning-section-content" aria-label="学习设计师工作区" aria-describedby="learning-section-description">
      <aside className="panel learning-conditions">
        <div className="panel-head"><h2>{teacher ? <GraduationCap size={18}/> : <UserRound size={18}/>} {sideTitle}</h2><button className="icon-button" aria-label="收起学习侧栏" onClick={() => setCollapsed(true)}><PanelLeftClose size={17} /></button></div>
        <div className="learning-conditions-scroll" ref={conditionsPane}><div className="learning-project"><small>当前项目</small><strong>{projectName}</strong><span>{teacher ? '围绕作品设计学习与评价' : '围绕作品探索、记录与表达'}</span><button onClick={()=>setDialog('project')}><Link2 size={13}/>查看项目成果<ChevronRight size={12}/></button></div>
          <nav className="learning-condition-actions" aria-label={`${roleName}操作`}>{sectionNavigation[section][role].map(({icon:Icon,title,hint,material:target,dialog:targetDialog,pending:unavailable}) => <button key={title} disabled={unavailable} title={unavailable ? pending : undefined} aria-current={target && material === target ? 'page' : undefined} onClick={() => {if(target)showMaterial(target); else if(targetDialog)setDialog(targetDialog);}}><Icon size={17} /><span><strong>{title}</strong><small>{unavailable ? `${hint} · 待开发` : hint}</small></span>{!unavailable && <ChevronRight size={13} />}</button>)}</nav>
          {section === 'project' && (teacher ? <section className="learning-condition-summary"><h3>学习概况</h3><dl><div><dt>适用学段</dt><dd>待设置</dd></div><div><dt>课时安排</dt><dd>待设置</dd></div><div><dt>学生基础</dt><dd>待补充</dd></div></dl></section> : <section className="learning-condition-summary"><h3>我的学习进度</h3><p className="learning-caption">尚未分配学习任务。可先查看右侧示例，了解怎样记录与展示。</p></section>)}
          <section className="learning-stage-guide"><h3>{section === 'guidance' ? '从想法到定义' : section === 'outcomes' ? '成果整理路径' : teacher ? '任务阶段' : '我的探究路径'}</h3>{(section === 'project' ? stages.map(stage=>stage.name) : section === 'guidance' ? ['接收创意，追问澄清','整合事实，收敛方案','确认项目定义卡'] : ['回看作品与过程','整理说明与测试证据','准备展示与参赛材料']).map((name,i) => <div key={name}><span>0{i + 1}</span><strong>{name}</strong></div>)}<p>{section === 'guidance' ? '先澄清问题与条件，再进入项目学习。' : section === 'outcomes' ? '模板仅作预览，尚未核验或归档项目产物。' : teacher ? '各阶段围绕学习目标安排，六维观察点在评价中配置。' : '提出问题，动手验证，再把收获讲给别人听。'}</p></section>
        </div><footer className="learning-side-foot"><span className="learning-preview-dot" />界面预览 · 功能待开发</footer>
      </aside>
      <button className="learning-restore" aria-label="展开学习侧栏" onClick={() => setCollapsed(false)}><PanelLeftOpen size={18} /></button>
      <section className="panel ai-panel learning-chat">
        <div className="panel-head"><h2><Sparkles size={18} />掌问 AI</h2><span className="learning-preview-tag" aria-label="当前学习视角" role="status">{roleName} · 预览</span></div>
        <div className="learning-conversation" ref={conversationPane}><div className="learning-welcome"><span>{section === 'guidance' ? <Lightbulb size={30} strokeWidth={1.5}/> : <sectionInfo.icon size={30} strokeWidth={1.5}/>}</span><small>掌问 · {welcome.tag}</small><h2>{welcome.title}</h2><p>{welcome.intro}</p></div>
          <section className="learning-next-step" aria-label="学习设计下一步"><span><Target size={14}/>{welcome.step}</span><h3>{welcome.question}</h3><p>{welcome.detail}</p><button onClick={() => section === 'guidance' ? showMaterial('definition') : section === 'outcomes' ? showMaterial(teacher ? 'portfolio' : 'work') : teacher ? setDialog('settings') : showMaterial('task')}>{welcome.button}<ChevronRight size={15}/></button></section>
          <div className="learning-example-links"><small>先看看材料的呈现方式</small><div>{section === 'guidance' ? <><button onClick={()=>showMaterial('questions')}><NotebookPen size={14}/>问题记录示例</button><button onClick={()=>changeSection('project')}><BookOpen size={14}/>查看项目学习</button></> : section === 'outcomes' ? <><button onClick={()=>showMaterial('poster')}><Image size={14}/>海报示例</button><button onClick={()=>showMaterial('competition')}><FileText size={14}/>赛事材料示例</button></> : <><button onClick={() => showMaterial(teacher ? 'plan' : 'record')}><NotebookPen size={14}/>{teacher ? '方案示例' : '记录一次尝试'}</button><button onClick={() => showMaterial(teacher ? 'rubric' : 'reflection')}><FileText size={14}/>{teacher ? '评价示例' : '反思示例'}</button></>}</div></div>
        </div>
        <div className="chat-form learning-composer"><label className="sr-only" htmlFor="learning-message">发送给学习设计师</label><textarea id="learning-message" disabled placeholder={`${sectionInfo.label}对话待接入，可先查看右侧材料示例…`}/><div><span>{welcome.flow}</span><button className="primary icon-button" aria-label="发送学习需求（待开发）" disabled title={pending}><ArrowUp size={19}/></button></div><button className="learning-generate" disabled title={pending}><Sparkles size={15}/>{welcome.generate}<span>待开发</span></button></div>
      </section>
      <section className="panel learning-materials">
        <div className="filebar learning-filebar"><span><BookOpen size={16} />学习材料</span><label className="sr-only" htmlFor="learning-version">学习材料版本</label><select id="learning-version" disabled title="版本管理待开发"><option>示例 · 未保存</option></select><span className="filebar-space" /><button className="learning-choose-template" onClick={()=>{setTemplatePage('requirements'); setTemplateDraft(selectedTemplate.id);}}><LayoutTemplate size={15}/>选择模板</button><button className="icon-button" aria-label={fullscreen ? '退出学习材料全屏' : '学习材料全屏'} title={fullscreen ? '退出全屏' : '全屏预览'} onClick={() => setFullscreen(v => !v)}>{fullscreen ? <Minimize size={16} /> : <Maximize size={16} />}</button><button disabled title={pending}><Download size={15} />导出</button></div>
        <div className="learning-material-tabs" role="tablist" aria-label="学习材料类型">{materials.map((item,i) => <button key={item.id} id={`learning-tab-${item.id}`} role="tab" aria-selected={material === item.id} aria-controls="learning-material-panel" tabIndex={material === item.id ? 0 : -1} onKeyDown={e => switchTab(e,i)} onClick={() => setMaterial(item.id)}>{item.label}</button>)}</div>
        <div className="learning-preview-notice"><span className="learning-preview-dot" />示例预览 · {selectedTemplate.name}<span>尚未生成当前项目的学习材料</span></div>
        <div className="learning-document-scroll" ref={documentPane} id="learning-material-panel" role="tabpanel" aria-labelledby={`learning-tab-${material}`} tabIndex={0}><article className="learning-paper">
          <LearningMaterialPreview role={role} material={material} template={selectedTemplate.id} projectName={projectName} competitionPage={competitionPages[role]} onCompetitionPage={value=>setCompetitionPages(previous=>({...previous,[role]:value}))}/>
        </article></div>
        <footer className="learning-material-footer"><span>{teacher ? '教师 · 设计与指导' : '学生 · 探索与表达'}</span><button disabled title={pending}><FilePenLine size={15}/>{materialActions[material]}<small>待开发</small></button></footer>
      </section>
    </main>
    {active && roleDialog && <Dialog title="切换学习视角" className="learning-dialog learning-role-dialog" onClose={onCloseRole} footer={<><span>仅切换工作台预览，当前选择会保留</span><button onClick={onCloseRole}>取消</button></>}>
      <p className="learning-dialog-intro">选择这次以谁的视角开展学习。</p><div className="learning-role-options" role="group" aria-label="学习工作台视角">{([{id:'teacher', label:'教师工作台', hint:'设计学习目标、组织任务与评价，整理班级成果。', icon:GraduationCap}, {id:'student', label:'学生工作台', hint:'查看任务、记录探究、表达作品与反思收获。', icon:UserRound}] as const).map(({id,label,hint,icon:Icon})=><button key={id} aria-pressed={role === id} onClick={()=>{onRole(id); onCloseRole();}}><Icon size={25} strokeWidth={1.5}/><span><strong>{label}</strong><small>{hint}</small></span>{role === id ? <Check size={18}/> : <ChevronRight size={18}/>}</button>)}</div>
    </Dialog>}
    {active && templateDraft !== null && <Dialog title="选择学习材料模板" className="learning-dialog learning-template-dialog" onClose={()=>setTemplateDraft(null)} footer={<><span>仅替换当前材料的临时预览</span><button onClick={()=>setTemplateDraft(null)}>取消</button><button className="primary" onClick={()=>{setTemplateChoices(previous=>({...previous,[templateKey]:draftTemplate.id})); setTemplateDraft(null);}}>使用模板</button></>}>
      <div className="learning-template-picker"><div className="learning-template-library"><p>{roleName} / {materials.find(item=>item.id === material)?.label}</p><div className="learning-template-cards" role="group" aria-label="可选材料模板">{options.map(item=>{const Icon=templateIcons[item.layout]; return <button key={item.id} aria-pressed={draftTemplate.id === item.id} onClick={()=>{setTemplateDraft(item.id); setTemplatePage('requirements');}}><span className={`learning-template-thumbnail learning-thumbnail-${item.layout}`} aria-hidden="true"><Icon size={25} strokeWidth={1.4}/><i/><i/><i/></span><span><strong>{item.name}{selectedTemplate.id === item.id && <small>当前</small>}</strong><span>{item.description}</span></span>{draftTemplate.id === item.id && <Check size={16}/>}</button>;})}</div></div><section className="learning-template-detail" aria-label="模板预览"><header><span>{draftTemplate.name}</span><small>版式示例</small></header><div ref={templatePane} className="learning-template-preview-scroll"><article className="learning-paper"><LearningMaterialPreview role={role} material={material} template={draftTemplate.id} projectName={projectName} competitionPage={templatePage} onCompetitionPage={setTemplatePage}/></article></div></section></div>
    </Dialog>}
    {active && dialog && <Dialog title={dialogTitles[dialog]} className="learning-dialog" onClose={() => setDialog(null)} footer={<><span>界面预览 · 设置暂不保存</span><button onClick={() => setDialog(null)}>关闭预览</button><button className="primary" disabled title={pending}>{dialog === 'resources' ? '加入资料' : dialog === 'project' ? '确认关联' : '应用设置'}</button></>}>
      {dialog === 'settings' && <><p className="learning-dialog-intro">先了解学生与课堂条件，让活动难度和节奏更合适。</p><div className="learning-form-grid"><label className="field">适用学段<select defaultValue="" data-dialog-autofocus><option value="" disabled>选择学段</option><option>小学</option><option>初中</option><option>高中</option><option>其他</option></select></label><label className="field">年级<input placeholder="例如：五年级" /></label><label className="field">课时数量<input type="number" min={1} max={100} placeholder="例如：4" /></label><label className="field">每课时（分钟）<input type="number" min={1} max={240} placeholder="例如：40" /></label><label className="field">学生人数<input type="number" min={1} max={200} placeholder="例如：30" /></label><label className="field">组织方式<select defaultValue="group"><option value="group">小组合作</option><option>个人探究</option><option>全班共同探究</option></select></label></div><label className="field">已有基础<textarea rows={3} placeholder="学生已经学习过什么？哪些操作还需要引导？" /></label></>}
      {dialog === 'goals' && <><p className="learning-dialog-intro">把目标写成可以观察、解释或展示的学习表现。</p>{['理解与知识','实践与能力','反思与协作'].map((label,i) => <label className="field" key={label}>{label}<textarea rows={3} placeholder={goals[i]} data-dialog-autofocus={i === 0 || undefined}/></label>)}<label className="field">活动与任务<textarea rows={3} placeholder="学生将完成什么任务？留下哪些可以观察的学习证据？"/></label><p className="learning-caption">后续可将目标关联到任务阶段、评价观察点与学习证据。</p></>}
      {dialog === 'resources' && <><p className="learning-dialog-intro">为学习设计提供教材、课程要求或已有教学材料。</p><div className="learning-upload-preview"><UploadCloud size={30} strokeWidth={1.5} /><strong>添加课程参考资料</strong><span>教材文档 · 参考图片 · 学习材料</span><button disabled title={pending}>选择本地文件（待开发）</button></div><label className="field">文本参考<textarea rows={4} placeholder="在这里补充课程要求、活动约束或参考内容…" /></label></>}
      {dialog === 'project' && <><p className="learning-dialog-intro">当前项目：<strong>{projectName}</strong></p><p className="learning-caption">以下为当前工程信息与引用入口预览，尚未建立学习关联。</p><div className="learning-source-list"><article><Settings2 size={20} /><div><strong>硬件配置</strong><p>{board?.displayName ?? '尚未选择主控'} · {modules.length} 个模块</p>{modules.length > 0 && <small>{modules.map(m => m.displayName).join('、')}</small>}</div><button disabled title={pending}>选择</button></article><article><FileText size={20} /><div><strong>程序版本</strong><p>{project ? `已保存工程代码 v${project.revision}` : '尚无已保存版本'}</p></div><button disabled title={pending}>选择</button></article><article><Layers3 size={20} /><div><strong>结构模型</strong><p>后续可引用已保存的结构版本</p></div><button disabled title={pending}>选择</button></article></div></>}
    </Dialog>}
  </div>;
}
