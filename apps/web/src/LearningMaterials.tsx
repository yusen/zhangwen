import { BookOpen, ChevronRight, ClipboardList, FileText, Flag, FolderOpen, ImagePlus, Lightbulb, Plus, Target, Trophy, UploadCloud } from 'lucide-react';

export type LearningRole = 'teacher' | 'student';
export type Material = 'plan' | 'task' | 'rubric' | 'portfolio' | 'record' | 'work' | 'reflection' | 'poster' | 'competition';
export type PosterTemplate = 'activity' | 'class' | 'work' | 'science' | 'contest';
export type CompetitionPage = 'requirements' | 'archive';
export const roleMaterials: Record<LearningRole, {id: Material; label: string}[]> = {
  teacher: [
    {id:'plan', label:'学习方案'}, {id:'task', label:'学生任务单'}, {id:'rubric', label:'评价量规'},
    {id:'portfolio', label:'学习档案'}, {id:'poster', label:'成果海报'}, {id:'competition', label:'赛事资料'},
  ],
  student: [
    {id:'task', label:'我的任务'}, {id:'record', label:'探究记录'}, {id:'work', label:'作品说明'},
    {id:'reflection', label:'自评与反思'}, {id:'poster', label:'作品海报'}, {id:'competition', label:'参赛材料'},
  ],
};

export const stages = [
  {name: '探索发现', title: '从生活中发现问题', description: '观察使用场景，提出值得解决的问题，说明自己的初步想法。', evidence: '问题清单 · 观察记录'},
  {name: '创意物化', title: '把想法做出来、试一试', description: '设计方案并制作原型，用测试结果解释哪些部分有效、哪些需要调整。', evidence: '设计草图 · 测试记录'},
  {name: '拔尖创新', title: '比较方案，继续改进', description: '比较不同实现方法，依据证据优化作品，提出新的应用方向。', evidence: '方案对比 · 改进说明'},
];
export const goals = ['说清作品要解决的问题，以及判断成功的依据。', '通过制作、实验与调试验证想法，解释调整的理由。', '与同伴分工协作，记录遇到的困难和自己的收获。'];
export const pending = '待开发：当前仅展示界面，不生成或保存学习内容。';

export function PlanPreview() {
  return <>
    <div className="learning-paper-heading"><small>项目式学习 · 方案示例</small><h1>从一个想法，到可以解释的作品</h1><p>让学生经历发现问题、动手验证和反思改进的完整过程。</p></div>
    <div className="learning-meta"><div><span>适用学段</span><strong>待设置</strong></div><div><span>课时安排</span><strong>待设置</strong></div><div><span>组织方式</span><strong>小组探究 · 示例</strong></div></div>
    <section className="learning-paper-section"><h2><span>01</span>学生将学会什么</h2><div className="learning-goal-list">{goals.map((goal, i) => <div key={goal}><span>{i + 1}</span><p>{goal}</p></div>)}</div></section>
    <section className="learning-paper-section"><h2><span>02</span>如何组织学习活动</h2><div className="learning-stage-cards">{stages.map((stage, i) => <article key={stage.name}><div><span className="learning-stage-number">0{i + 1}</span><small>{stage.name}</small></div><h3>{stage.title}</h3><p>{stage.description}</p><footer><FileText size={13} />{stage.evidence}</footer></article>)}</div></section>
    <section className="learning-paper-section"><h2><span>03</span>留下哪些学习证据</h2><div className="learning-evidence-summary"><span><Target size={16} />目标与问题</span><span><ClipboardList size={16} />过程与测试</span><span><BookOpen size={16} />解释与反思</span></div><p className="learning-caption">将评价观察点与学生的真实表现关联，支持教师反馈、学生自评与同伴互评。</p></section>
  </>;
}

export function TaskPreview({role = 'teacher'}: {role?: LearningRole}) {
  return <>
    <div className="learning-paper-heading"><small>{role === 'teacher' ? '面向学生 · 任务单示例' : '我的任务 · 示例预览'}</small><h1>{role === 'teacher' ? '我的作品探究记录' : '从一个问题开始我的探究'}</h1><p>{role === 'teacher' ? '不只展示做出了什么，也说明为什么这样设计。' : '这里是任务版式示例，实际任务待教师分配。'}</p></div>
    <div className="learning-student-line"><span>姓名 / 小组 <i /></span><span>日期 <i /></span></div>
    {[
      ['发现问题', '我观察到了什么？这个作品想帮助谁？', '画一画或写下你的发现……'],
      ['提出方案', '我的方案是什么？我预计它会怎样工作？', '记录设计草图、材料和你的预测……'],
      ['测试与改进', '测试结果支持我的想法吗？我准备怎样修改？', '留下测试条件、结果与改进依据……'],
    ].map(([title, question, placeholder], i) => <section className="learning-paper-section" key={title}><h2><span>0{i + 1}</span>{title}</h2><p>{question}</p><div className="learning-writing-space">{placeholder}</div></section>)}
  </>;
}

export function RubricPreview() {
  return <>
    <div className="learning-paper-heading"><small>关注学习过程 · 评价示例</small><h1>让评价有可以观察的依据</h1><p>围绕目标选择观察点，用具体证据支持反馈。</p></div>
    <div className="learning-rubric" role="table" aria-label="评价量规示例"><div role="row" className="learning-rubric-head"><span role="columnheader">观察点</span><span role="columnheader">可观察的表现</span><span role="columnheader">证据来源</span></div>{[
      ['问题与目标', '能结合真实场景说明需求，提出判断作品有效的条件。', '观察记录、问题清单'],
      ['验证与解释', '能比较预测和测试结果，并据此解释设计取舍。', '实验数据、调试说明'],
      ['协作与反思', '能说明自己的贡献，并提出有依据的改进建议。', '分工记录、学生反思'],
    ].map(row => <div role="row" key={row[0]}>{row.map(cell => <span role="cell" key={cell}>{cell}</span>)}</div>)}</div>
    <section className="learning-paper-section"><h2><span>01</span>谁来参与评价</h2><div className="learning-evaluation-roles"><span>学生自评</span><span>同伴互评</span><span>教师反馈</span></div></section>
    <section className="learning-paper-section"><h2><span>02</span>三阶六维观察点</h2><p>根据学情和学习目标选择关注维度，将观察点安排到相应活动中。</p><div className="learning-empty-note"><Flag size={18} /><span>维度配置与证据关联待开发</span></div></section>
  </>;
}

export function PortfolioPreview() {
  return <>
    <div className="learning-paper-heading"><small>与作品一起成长 · 档案预览</small><h1>留住学习发生的过程</h1><p>把讨论、尝试和改进整理成能够回看的学习记录。</p></div>
    <div className="learning-portfolio-empty"><BookOpen size={40} strokeWidth={1.4} /><h2>还没有学习证据</h2><p>这里将呈现学生解释、实验数据、作品照片与反思。</p><button disabled title={pending}><Plus size={16} />记录学习证据</button></div>
    <div className="learning-evidence-types">{[{icon: FileText, name: '讨论与解释'}, {icon: ClipboardList, name: '实验与调试'}, {icon: ImagePlus, name: '作品与反思'}].map(({icon: Icon, name}) => <div key={name}><Icon size={18} /><span>{name}</span><small>未记录</small></div>)}</div>
  </>;
}

export function StudentPreview({material}: {material: 'record' | 'work' | 'reflection'}) {
  const content = {
    record: {tag:'边做边记录 · 探究示例', title:'把每一次尝试留下来', intro:'先写下预测，再用测试结果解释你的发现。',
      prompts:[['我的问题与预测','我想验证什么？我预计会出现什么结果？'],['我的测试方法','我改变了什么条件？怎样让比较更公平？'],['结果与下一步','结果和预测一样吗？下一次准备怎样改进？']]},
    work: {tag:'说明我的作品 · 版式示例', title:'让别人看懂我的设计', intro:'结合程序、结构和测试证据，说明作品如何解决问题。',
      prompts:[['作品要解决什么问题','谁会使用它？什么情况下需要它？'],['我是怎样实现的','硬件、程序与结构分别起什么作用？'],['测试与改进','用什么证据说明它有效？还可以怎样改进？']]},
    reflection: {tag:'回看学习过程 · 反思示例', title:'看见自己的进步', intro:'用具体经历和证据，说明你学会了什么。',
      prompts:[['我的收获','我现在能解释或完成哪些之前不会的事情？'],['合作与反馈','我承担了什么任务？同伴的建议帮助了我什么？'],['下一次挑战','最想改进哪一点？我准备怎样继续验证？']]},
  }[material];
  return <>
    <div className="learning-paper-heading"><small>{content.tag}</small><h1>{content.title}</h1><p>{content.intro}</p></div>
    {material === 'reflection' && <div className="learning-empty-note learning-student-note"><Flag size={18} /><span>这里展示反思问题示例，尚无自评结果或教师反馈。</span></div>}
    {content.prompts.map(([title, question], i) => <section className="learning-paper-section" key={title}><h2><span>0{i+1}</span>{title}</h2><p>{question}</p><div className="learning-writing-space">{material === 'work' ? '在这里整理说明、图片与证据……' : '在这里留下你的想法与记录……'}</div></section>)}
    <p className="learning-caption">填写、添加图片与保存功能待开发，当前仅预览材料格式。</p>
  </>;
}

const posterTemplates: {id: PosterTemplate; name: string; roles: LearningRole[]; eyebrow: string; title: string; intro: string}[] = [
  {id:'activity', name:'活动海报', roles:['teacher'], eyebrow:'一起探索 · 项目式学习', title:'把好奇变成一件作品', intro:'从一个真实问题出发，一起设计、制作、测试与分享。'},
  {id:'class', name:'班级成果', roles:['teacher'], eyebrow:'我们的创意 · 班级成果展', title:'每一个想法，都值得被看见', intro:'展示作品，也分享尝试、合作与改进的过程。'},
  {id:'work', name:'作品介绍', roles:['student'], eyebrow:'我的创意 · 作品介绍', title:'让想法成为可以展示的作品', intro:'讲清问题、设计与证据，让别人理解你的创造。'},
  {id:'science', name:'科学探究', roles:['student'], eyebrow:'提出问题 · 用证据解释', title:'用实验回答一个好问题', intro:'留下预测、方法和发现，分享有依据的结论。'},
  {id:'contest', name:'赛事展示', roles:['teacher','student'], eyebrow:'创意表达 · 赛事展示', title:'用作品讲述我们的解决方案', intro:'用清晰的设计说明与测试证据，呈现项目的价值。'},
];

export function PosterPreview({role, template, projectName}: {role: LearningRole; template: PosterTemplate; projectName: string}) {
  const options=posterTemplates.filter(item=>item.roles.includes(role));
  const selected=options.find(item=>item.id === template) ?? options[0];
  return <>
    <div className="learning-paper-heading"><small>{role === 'teacher' ? '教学展示' : '作品表达'} · 海报预览</small><h1>{role === 'teacher' ? '让学习成果被看见' : '为我的作品做一张海报'}</h1><p>先选择版式，后续可引用项目图片、设计说明与测试结果。</p></div>
    <div className={`learning-poster learning-poster-${selected.id}`} aria-label={`${selected.name}版式示例`}>
      <header><span>掌问 · {role === 'teacher' ? '一起学，一起创造' : '我的项目，我来讲述'}</span><small>版式示例</small></header>
      <div className="learning-poster-title"><small>{selected.eyebrow}</small><h2>{selected.title}</h2><p>{selected.intro}</p></div>
      <div className="learning-poster-art" aria-hidden="true"><svg viewBox="0 0 480 170"><path d="M65 115 165 55 285 105 410 45" /><circle cx="65" cy="115" r="20" /><circle cx="165" cy="55" r="35" /><circle cx="285" cy="105" r="25" /><circle cx="410" cy="45" r="18" /><path d="M65 115 285 105 410 45M165 55 410 45" className="learning-poster-art-secondary" /></svg><span><Lightbulb size={37} strokeWidth={1.4}/></span><small>观察 · 创造 · 验证</small></div>
      <div className="learning-poster-project"><small>当前项目</small><strong>{projectName}</strong></div>
      <div className="learning-poster-highlights">{(selected.id === 'science' ? ['探究问题','实验方法','证据与发现'] : selected.id === 'activity' ? ['发现问题','动手制作','分享收获'] : ['我们的问题','设计与实现','测试与改进']).map((label,i)=><section key={label}><span>0{i+1}</span><h3>{label}</h3><p>说明与图片待补充</p></section>)}</div>
      <footer><span>{role === 'teacher' ? '活动对象 / 时间 / 地点：待设置' : '创作小组 / 指导教师：待补充'}</span><small>图片位置预留</small></footer>
    </div>
    <div className="learning-poster-actions"><span>模板仅切换预览，尚未生成海报</span><button disabled title={pending}><ImagePlus size={15}/>添加项目图片</button></div>
  </>;
}

export function CompetitionPreview({role, page, onPage}: {role: LearningRole; page: CompetitionPage; onPage: (value: CompetitionPage) => void}) {
  const checklist=role === 'teacher' ? [
    ['赛事通知与模板','核对官方通知、申报模板与授权要求'], ['作品申报书','整理项目概况、创新点与指导说明'],
    ['作品介绍海报','准备符合要求的展示材料'], ['程序与结构文件','核对项目版本及命名'], ['图片与测试记录','汇总作品图片、测试证据与视频说明'],
  ] : [
    ['作品说明','讲清问题、方案和改进依据'], ['作品海报','整理作品亮点和图片'], ['程序与结构文件','准备要求的程序与模型版本'],
    ['图片与测试记录','补充测试结果与制作过程'], ['参赛表格与视频说明','按照官方模板准备个人或小组材料'],
  ];
  return <>
    <div className="learning-paper-heading"><small>围绕同一项目 · {role === 'teacher' ? '赛事资料整理' : '参赛材料准备'}</small><h1>{role === 'teacher' ? '把赛事要求变成一份清单' : '跟着清单，准备参赛材料'}</h1><p>{role === 'teacher' ? '确认官方要求，再组织学生和小组补齐材料。' : '先看清要求，再逐项整理作品说明、文件与证据。'}</p></div>
    <div className="learning-contest-flow" aria-label="赛事材料整理流程">{['导入要求','确认清单','补齐材料','检查导出'].map((label,i)=><span key={label}><i>{i+1}</i>{label}{i<3 && <ChevronRight size={12}/>}</span>)}</div>
    <div className="learning-template-options" role="group" aria-label="赛事资料页面"><button aria-pressed={page === 'requirements'} onClick={()=>onPage('requirements')}>要求与清单</button><button aria-pressed={page === 'archive'} onClick={()=>onPage('archive')}>文件归档</button></div>
    {page === 'requirements' ? <>
      <div className="learning-contest-import"><Trophy size={24} strokeWidth={1.5}/><div><strong>尚未导入赛事通知</strong><p>通知、申报模板和规则确认后，才能核对实际材料。</p></div><button disabled title={pending}><UploadCloud size={14}/>导入通知<small>待开发</small></button></div>
      <section className="learning-paper-section"><h2><span>01</span>先确认参赛要求</h2><div className="learning-contest-requirements">{['参赛对象','截止时间','文件格式','命名规则'].map(label=><div key={label}><span>{label}</span><strong>待确认</strong></div>)}</div></section>
      <section className="learning-paper-section"><h2><span>02</span>{role === 'teacher' ? '材料清单示例' : '我要准备的材料 · 示例'}</h2><div className="learning-contest-checklist">{checklist.map(([title,hint])=><article key={title}><FileText size={17}/><div><strong>{title}</strong><p>{hint}</p></div><span>待补充</span></article>)}</div><p className="learning-caption">清单为版式示例，以赛事官方通知为准。状态后续支持：待补充 / 待确认 / 已齐备。</p></section>
    </> : <>
      <div className="learning-empty-note learning-student-note"><FolderOpen size={18}/><span>目录示例 · 尚未创建文件夹或整理项目文件</span></div>
      <div className="learning-contest-directory" aria-label="参赛归档目录示例"><strong><FolderOpen size={18}/>参赛材料 /</strong>{['01_赛事要求与模板','02_作品说明','03_成果海报','04_程序与结构','05_图片与测试记录','06_表格与视频说明'].map(label=><div key={label}><FolderOpen size={15}/>{label}<small>待整理</small></div>)}</div>
      <p className="learning-caption">后续按赛事要求整理副本并核对命名、格式和缺失项，保留原项目文件。</p>
      <div className="learning-poster-actions"><span>材料核对与打包待开发</span><button disabled title={pending}><FolderOpen size={15}/>整理材料</button></div>
    </>}
  </>;
}

