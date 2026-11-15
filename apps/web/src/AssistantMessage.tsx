import { FileCode2 } from 'lucide-react';
import { replyView } from './assistantReply';

export function AssistantMessage({ content, revision, disabled, onCode, onReply, hasProgram = false, isCurrentCode = false }: {
  content: string; revision?: number; disabled: boolean; onCode: (code: string) => void; onReply?: (answer: string) => void; hasProgram?: boolean; isCurrentCode?: boolean;
}) {
  const reply = replyView(content);
  const missingClaim=reply.code===null&&/代码|程序|main\.py/i.test(reply.summary)&&/已(?:经)?(?:生成|完成|提供|输出|写好)|准备好/.test(reply.summary);
  const observesProgram = hasProgram && !!reply.question && /运行后|运行之后|测试后|测试结果|实物现象/.test(reply.question.text);
  return <div className="assistant-answer">
    {reply.code===null&&<p className="answer-no-code" role="note">{reply.formatIssue?'本轮回复不完整，未生成可用代码候选，右侧程序保持。可缩小本轮功能后再次发送。':'本轮为文字回复，未生成代码候选，右侧程序保持。'}</p>}
    <p className="answer-summary">{missingClaim?'本轮没有附带完整代码；可继续要求生成当前主控的完整程序。':reply.summary}</p>
    {reply.code !== null && <button className="answer-code-link" disabled={disabled} onClick={() => onCode(reply.code!)}><FileCode2 size={16} />main.py{revision ? ` · v${revision}` : ''} · 查看代码{isCurrentCode ? ' · 与右侧代码一致' : ' · 点击在右侧预览'}</button>}
    {(missingClaim || reply.points.length > 0 || reply.details || ((reply.code !== null || observesProgram) && onReply)) && <details className="answer-details"><summary>查看说明</summary>
      {missingClaim&&<p>模型原说明（未交付代码）：{reply.summary}</p>}
      {reply.points.length > 0 && <ul className="answer-points">{reply.points.map((point, index) => <li key={index}>{point}</li>)}</ul>}
      {reply.details && <pre>{reply.details}</pre>}
      {(reply.code !== null || observesProgram) && onReply && <p className="answer-run-hint" role="note"><strong>下一步：上传并运行</strong><br />{reply.code !== null && !isCurrentCode && '先点击本条「查看代码」，核对并采用此代码。'}核对接线和右侧程序后，点击顶部「上传并运行」。回读校验通过后会自动运行，再根据串口输出与实物现象回复；运行中可点击「停止」。</p>}
    </details>}
    {reply.question && <section className="answer-question" aria-label="需要你确认"><strong>需要你确认</strong><p>{reply.question.text}</p>{onReply && reply.question.options.length > 0 && <><div className="answer-choices">{reply.question.options.map((option, index) => <button key={index} disabled={disabled} onClick={() => onReply(option)} aria-label={`填入回复：${option}`}>{option}</button>)}</div><small>选择后填入输入框，点击发送继续。</small></>}</section>}
  </div>;
}
