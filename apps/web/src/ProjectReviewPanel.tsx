import type { WorkflowCheckpoint, WorkflowProposal, WorkflowView } from '../../../packages/contracts/src/workflow';

export function savedReviews(value?:WorkflowCheckpoint) {
  return (value?.messages??[]).flatMap(m=>{if(m.role!=='assistant')return [];try{const p=JSON.parse(m.content) as WorkflowProposal;return p.review?.source?[{id:m.id,review:p.review}]:[];}catch{return [];}});
}

export function ProjectReviewPanel({view,disabled,unsaved,onReview}:{view:WorkflowView|null;disabled:boolean;unsaved:boolean;onReview:()=>void}) {
  const reviews=savedReviews(view?.checkpoint),latest=reviews.at(-1)?.review;
  const stale=!!latest?.source&&(latest.source.baseline.fingerprint!==view?.current.fingerprint||latest.source.records!==view?.reviewRecords);
  return <section className="project-review" aria-label="整体成果检查">
    <header><h3>整体成果</h3><button className="primary" disabled={disabled||unsaved} onClick={onReview}>检查整体成果</button></header>
    <p className="muted">造物统筹师会核对已保存的程序、结构说明和测试记录，说明进展、缺口和下一步。未配置 AI 时先核对记录。</p>
    {unsaved&&<p role="status">程序或器件还有未保存修改，请先保存再检查。</p>}
    {!latest?<p>还没有检查记录。完成一部分制作后，也可以检查接下来还缺什么。</p>:<>
      <p className={stale?'workflow-warning':'muted'} role="status">{stale?'作品或测试记录有变化，请重新检查。以下为上次结果。':'以下结果对应检查时已保存的版本与观察记录。'}</p>
      <p className="project-review-conclusion"><strong>{latest.conclusion}</strong></p>
      {([['还缺什么',latest.gaps],['下一步怎么做',latest.nextSteps],['请你决定',latest.decisions]] as const).map(([title,items])=><div key={title}><h4>{title}</h4>{items.length?<ul>{items.map((text,i)=><li key={i}>{text}</li>)}</ul>:<p>本次未列出，请结合实物继续核对。</p>}</div>)}
      <details className="classroom-details"><summary>程序与结构怎样配合</summary><p>{latest.comparison}</p></details>
      <details className="classroom-details"><summary>查看检查依据</summary><p>{latest.source?.method==='records'?'本次为记录核对，未使用 AI 阅读程序逻辑与结构尺寸。':'本次由 AI 阅读已保存资料并提出建议，仍需动手验证。'}</p><ul>{latest.source?.facts.map((f,i)=><li key={i}>{f}</li>)}</ul><small>{latest.source&&new Date(latest.source.checkedAt).toLocaleString()} · 目标 V{latest.source?.baseline.definitionRevision??'未确认'} · 程序 V{latest.source?.baseline.code.revision??'无'} · 结构 V{latest.source?.baseline.structure?.revision??'无'}</small></details>
      {reviews.length>1&&<details className="classroom-details"><summary>以前的检查（{reviews.length-1}次）</summary>{reviews.slice(0,-1).reverse().map(({id,review})=><article key={id}><small>{review.source&&new Date(review.source.checkedAt).toLocaleString()} · 历史结果</small><p>{review.conclusion}</p></article>)}</details>}
    </>}
  </section>;
}
