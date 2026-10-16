import { BookOpen, ClipboardList, FileText, Flag, Image, LayoutTemplate } from 'lucide-react';
import { PlanPreview, TaskPreview, RubricPreview, PortfolioPreview, StudentPreview, PosterPreview, CompetitionPreview, type LearningRole, type Material, type PosterTemplate, type CompetitionPage } from './LearningMaterials';

export type LearningTemplate = {id: string; name: string; description: string; layout: 'overview' | 'sheet' | 'table' | 'timeline' | 'poster'};
const templates: Record<Material, LearningTemplate[]> = {
  plan: [{id:'standard', name:'活动总览', description:'目标、任务阶段与学习证据', layout:'overview'}, {id:'lessons', name:'课时安排', description:'按课时梳理活动、支持与产出', layout:'table'}],
  task: [{id:'standard', name:'引导任务单', description:'用问题引导发现、方案与验证', layout:'sheet'}, {id:'checklist', name:'步骤清单', description:'逐步呈现行动与完成要求', layout:'table'}],
  rubric: [{id:'standard', name:'观察量规', description:'观察点、具体表现与证据来源', layout:'table'}, {id:'feedback', name:'反馈卡', description:'用证据组织肯定、问题和建议', layout:'sheet'}],
  portfolio: [{id:'standard', name:'证据分类', description:'按讨论、实验与作品整理证据', layout:'overview'}, {id:'timeline', name:'成长时间线', description:'按探索、制作、改进回看过程', layout:'timeline'}],
  record: [{id:'standard', name:'问题引导', description:'依次记录预测、方法与发现', layout:'sheet'}, {id:'experiment', name:'实验记录表', description:'对照条件、预测、结果与解释', layout:'table'}],
  work: [{id:'standard', name:'完整说明', description:'问题、实现过程与测试改进', layout:'sheet'}, {id:'showcase', name:'作品展示卡', description:'预留主图并突出作品亮点', layout:'overview'}],
  reflection: [{id:'standard', name:'引导反思', description:'回看收获、合作与下一次挑战', layout:'sheet'}, {id:'review', name:'复盘卡', description:'围绕事实、解释和下一步复盘', layout:'overview'}],
  poster: [],
  competition: [{id:'standard', name:'材料清单', description:'赛事要求、待补材料与归档', layout:'table'}, {id:'submission', name:'申报准备', description:'按项目概况、创新和证据组织', layout:'sheet'}],
};
export function learningTemplates(role: LearningRole, material: Material): LearningTemplate[] {
  if (material !== 'poster') return templates[material];
  return (role === 'teacher' ? [
    {id:'activity', name:'活动海报', description:'面向课堂活动与项目招募', layout:'poster'},
    {id:'class', name:'班级成果', description:'展示全班作品与合作过程', layout:'poster'},
  ] : [
    {id:'work', name:'作品介绍', description:'讲清作品的问题、设计与证据', layout:'poster'},
    {id:'science', name:'科学探究', description:'突出探究问题、方法与发现', layout:'poster'},
  ]).concat([{id:'contest', name:'赛事展示', description:'呈现项目价值与测试依据', layout:'poster'}]) as LearningTemplate[];
}
export const templateIcons = {overview:LayoutTemplate, sheet:FileText, table:ClipboardList, timeline:BookOpen, poster:Image};

export function LearningMaterialPreview({role, material, template, projectName, competitionPage, onCompetitionPage}: {
  role: LearningRole; material: Material; template: string; projectName: string;
  competitionPage: CompetitionPage; onCompetitionPage: (value: CompetitionPage) => void;
}) {
  if (material === 'poster') return <PosterPreview role={role} template={template as PosterTemplate} projectName={projectName}/>;
  if (template === 'standard') {
    if (material === 'plan') return <PlanPreview/>;
    if (material === 'task') return <TaskPreview role={role}/>;
    if (material === 'rubric') return <RubricPreview/>;
    if (material === 'portfolio') return <PortfolioPreview/>;
    if (material === 'competition') return <CompetitionPreview role={role} page={competitionPage} onPage={onCompetitionPage}/>;
    return <StudentPreview material={material}/>;
  }
  const selected=learningTemplates(role, material).find(item=>item.id === template)!;
  return <>
    <div className="learning-paper-heading"><small>{role === 'teacher' ? '教师材料' : '我的学习材料'} · {selected.name}示例</small><h1>{selected.name}</h1><p>{selected.description}。以下为可替换的版式示例，内容待补充。</p></div>
    {material === 'plan' && <div className="learning-template-table" role="table" aria-label="课时安排示例"><div role="row" className="learning-rubric-head">{['课时','学习活动','支持与证据'].map(v=><span role="columnheader" key={v}>{v}</span>)}</div>{[['第 1 课时','观察场景，提出问题','参考资料 / 问题记录'],['第 2 课时','设计与制作原型','材料支持 / 设计草图'],['第 3 课时','测试、改进与分享','测试记录 / 作品说明']].map(row=><div role="row" key={row[0]}>{row.map(v=><span role="cell" key={v}>{v}</span>)}</div>)}</div>}
    {material === 'task' && <div className="learning-task-checklist">{['说清想解决的问题与成功标准','画出方案并列出需要的材料','动手制作，留下测试记录','用证据说明改进，分享作品'].map((v,i)=><section key={v}><span aria-hidden="true"/><div><h2>0{i+1} · {v}</h2><p>完成要求与证据：待补充</p></div></section>)}</div>}
    {material === 'record' && <><div className="learning-student-line"><span>测试主题 <i/></span><span>日期 <i/></span></div><div className="learning-template-table learning-experiment-table" role="table" aria-label="实验记录表示例"><div role="row" className="learning-rubric-head">{['测试条件','我的预测','观察结果'].map(v=><span role="columnheader" key={v}>{v}</span>)}</div>{[1,2,3].map(i=><div role="row" key={i}><span role="cell">第 {i} 次 · 待填写</span><span role="cell">待记录</span><span role="cell">待记录</span></div>)}</div><Prompt title="我的解释与下一步" text="哪些结果支持预测？还需要怎样验证？"/></>}
    {material === 'portfolio' && <div className="learning-timeline">{['探索：问题与最初想法','制作：设计与测试过程','改进：变化与学习收获'].map((v,i)=><section key={v}><span>0{i+1}</span><div><h2>{v}</h2><p>尚无记录 · 证据与日期待补充</p><div className="learning-writing-space">预留照片、说明与证据引用</div></div></section>)}</div>}
    {material === 'rubric' && <>{[['我看到的亮点','用具体表现或作品证据说明做得好的地方。'],['我想追问的问题','哪些设计选择还需要解释？还缺少什么证据？'],['可以尝试的下一步','给出一条可以行动、可以验证的建议。']].map(([title,text])=><Prompt key={title} title={title} text={text}/>)}<div className="learning-empty-note learning-student-note"><Flag size={18}/><span>反馈人 / 反馈日期：待填写 · 尚无评价结果</span></div></>}
    {material === 'work' && <><div className="learning-work-image"><Image size={32} strokeWidth={1.4}/><span>作品主图预留 · 尚未添加图片</span></div><div className="learning-meta"><div><span>作品名称</span><strong>{projectName}</strong></div><div><span>创作者</span><strong>待填写</strong></div><div><span>使用场景</span><strong>待说明</strong></div></div>{[['解决的问题','这件作品帮助谁？'],['设计亮点','最想展示哪个设计选择？'],['验证依据','什么测试结果说明作品有效？']].map(([title,text])=><Prompt key={title} title={title} text={text}/>)}</>}
    {material === 'reflection' && <div className="learning-review-grid">{[['做了什么','记录一次具体的尝试或合作。'],['发现什么','结合结果解释新的理解。'],['还想问什么','留下尚未解决的问题。'],['下一步做什么','提出可以验证的小行动。']].map(([title,text])=><Prompt key={title} title={title} text={text}/>)}</div>}
    {material === 'competition' && <>{[['项目概况','项目名称、参赛组别、团队分工：待补充。'],['问题与创新','结合使用场景，说明问题及方案的不同之处。'],['验证与附件','列出测试依据和需要提供的程序、模型、图片。'],['提交前核对','以官方通知为准确认字数、格式、授权与截止时间。']].map(([title,text])=><Prompt key={title} title={title} text={text}/>)}</>}
    <p className="learning-caption">仅预览模板；填写、生成、保存与导出待开发。</p>
  </>;
}
function Prompt({title, text}: {title: string; text: string}) {
  return <section className="learning-paper-section"><h2>{title}</h2><p>{text}</p><div className="learning-writing-space">内容待补充……</div></section>;
}
