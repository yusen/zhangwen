import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, BookOpen } from 'lucide-react';
import { Dialog } from './Dialog';
import type { LearningRole } from './LearningMaterials';
import { smartHomeCase as caseStudy, smartHomeLessons } from './learning-cases/ai-smart-home';
import './learning-case.css';

function TextList({ items }: { items: readonly string[] }) {
  return <ul>{items.map(item => <li key={item}>{item}</li>)}</ul>;
}

/** Read-only curriculum content. No project, hardware, model or device mutations. */
export function LearningCaseDialog({ role, onClose }: { role: LearningRole; onClose: () => void }) {
  const [page, setPage] = useState(0);
  const content = useRef<HTMLElement>(null);
  const lesson = smartHomeLessons[page - 1];
  useEffect(() => { content.current?.scrollTo({ top: 0 }); }, [page]);
  const studentTasks = lesson && <section aria-labelledby="case-tasks"><h3 id="case-tasks">学生任务</h3><ol>{lesson.tasks.map(task => <li key={task}>{task}</li>)}</ol></section>;
  const teacherPrompts = lesson && <section aria-labelledby="case-prompts"><h3 id="case-prompts">教师提示</h3><TextList items={lesson.teacherPrompts} /></section>;

  return <Dialog title="AI智能家居 · 五课时案例" className="learning-case-dialog" onClose={onClose}
    footer={<><span>内置教学案例 · 阅读材料</span><div className="learning-case-paging">
      <button disabled={page === 0} onClick={() => setPage(value => value - 1)}><ArrowLeft size={15} />上一页</button>
      {page < smartHomeLessons.length
        ? <button className="primary" onClick={() => setPage(value => value + 1)}>{page === 0 ? '查看第1课时' : '下一课时'}<ArrowRight size={15} /></button>
        : <button onClick={() => setPage(0)}>回到概览</button>}
    </div></>}>
    <div className="learning-case-layout">
      <nav className="learning-case-nav" aria-label="案例课时导航">
        <p><BookOpen size={17} />{caseStudy.audience} · {caseStudy.duration}</p>
        <button aria-current={page === 0 ? 'page' : undefined} data-dialog-autofocus onClick={() => setPage(0)}><strong>案例概览</strong><small>准备、分工与三阶六维</small></button>
        {smartHomeLessons.map(item => <button key={item.number} aria-current={page === item.number ? 'page' : undefined} onClick={() => setPage(item.number)}>
          <small>第{item.number}课时 · {item.stage}</small><strong>{item.title}</strong>
        </button>)}
      </nav>
      <article className="learning-case-content" ref={content} aria-labelledby="learning-case-heading" tabIndex={0}>
        {lesson ? <>
          <header><small>第{lesson.number}课时 · {lesson.stage} · {lesson.dimensions.join(' / ')}</small><h2 id="learning-case-heading">{lesson.title}</h2><p>{lesson.goal}</p></header>
          {role === 'teacher' ? <>{teacherPrompts}{studentTasks}</> : <>{studentTasks}{teacherPrompts}</>}
          <section aria-labelledby="case-platform"><h3 id="case-platform">掌问可以怎样支持</h3><p>{lesson.platformSupport}</p></section>
          <section aria-labelledby="case-evidence"><h3 id="case-evidence">本课需留存的证据</h3><TextList items={lesson.evidence} /></section>
          <section className="learning-case-review"><h3>课末核对</h3><p>{lesson.review}</p></section>
        </> : <>
          <header><small>内置案例 · 探索 / 造物 / 迭代</small><h2 id="learning-case-heading">{caseStudy.subtitle}</h2><p>{caseStudy.introduction}</p></header>
          <section><h3>三阶六维与课时安排</h3><div className="learning-case-phases">{caseStudy.phases.map(phase => <div key={phase.name}><small>{phase.hours}</small><h4>{phase.name} <span>{phase.dimensions}</span></h4><p>{phase.purpose}</p></div>)}</div></section>
          <section><h3>课前准备</h3><TextList items={caseStudy.preparation} /></section>
          <section><h3>作品目标卡要写清什么</h3><TextList items={caseStudy.definition} /></section>
          <section><h3>师生与掌问的分工</h3><dl className="learning-case-roles">{caseStudy.collaboration.map(item => <div key={item.role}><dt>{item.role}</dt><dd>{item.task}</dd></div>)}</dl></section>
          <section><h3>使用与评价说明</h3><TextList items={caseStudy.boundaries} /></section>
          <details className="learning-case-source"><summary>案例来源</summary><p>{caseStudy.source.author}《{caseStudy.source.title}》</p><p>{caseStudy.source.note}</p></details>
        </>}
      </article>
    </div>
  </Dialog>;
}
