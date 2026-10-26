import { FileCode2 } from 'lucide-react';
import { replyView } from './assistantReply';

export function AssistantMessage({ content, revision, disabled, onCode, onReply, hasProgram = false, isCurrentCode = false }: {
  content: string; revision?: number; disabled: boolean; onCode: (code: string) => void; onReply?: (answer: string) => void; hasProgram?: boolean; isCurrentCode?: boolean;
}) {
  const reply = replyView(content);
  const observesProgram = hasProgram && !!reply.question && /运行后|运行之后|测试后|测试结果|实物现象/.test(reply.question.text);
  return <div className="assistant-answer">
    <p className="answer-summary">{reply.summary}</p>
    {reply.points.length > 0 && <ul className="answer-points">{reply.points.map((point, index) => <li key={index}>{point}</li>)}</ul>}
    {reply.code !== null && <button className="answer-code-link" disabled={disabled} onClick={() => onCode(reply.code!)}><FileCode2 size={16} />main.py{revision ? ` · v${revision}` : ''} · 查看代码{isCurrentCode ? ' · 与右侧代码一致' : ' · 点击在右侧预览'}</button>}
    {reply.code === null && <p className="muted answer-no-code">{reply.question ? '请先回答下方问题，再继续生成代码。' : reply.formatIssue ? '回复格式异常，未能提取代码。请重新发送，原始回复已保留。' : '本条回复未附代码。'}</p>}
    {reply.details && <details className="answer-details"><summary>展开详情</summary><pre>{reply.details}</pre></details>}
    {(reply.code !== null || observesProgram) && onReply && <p className="answer-run-hint" role="note"><strong>下一步：上传并运行</strong><br />{reply.code !== null && !isCurrentCode && '先点击本条「查看代码」，核对并采用此代码。'}核对接线和右侧程序后，点击顶部「上传并运行」。回读校验通过后会自动运行，再根据串口输出与实物现象回复；运行中可点击「停止」。</p>}
    {reply.question && <section className="answer-question" aria-label="需要你确认"><strong>需要你确认</strong><p>{reply.question.text}</p>{onReply && reply.question.options.length > 0 && <><div className="answer-choices">{reply.question.options.map((option, index) => <button key={index} disabled={disabled} onClick={() => onReply(option)} aria-label={`填入回复：${option}`}>{option}</button>)}</div><small>选择后填入输入框，点击发送继续。</small></>}</section>}
    <details className="answer-original"><summary>原始回复</summary><pre>{reply.original}</pre></details>
  </div>;
}
