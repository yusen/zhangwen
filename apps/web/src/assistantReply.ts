import type { AssistantReply } from '../../../packages/contracts/src/mu';

const text = (value: unknown, max: number): value is string => typeof value === 'string' && value.trim().length > 0 && [...value].length <= max;
const strings = (value: unknown, count: number, max: number): value is string[] => Array.isArray(value) && value.length <= count && value.every(item => text(item, max) && item.trim());
export function structuredReply(content: string): AssistantReply | null {
  const source = content.trim().replace(/^```(?:json|zhangwen)\s*\n([\s\S]*?)\s*```$/, '$1');
  try {
    const value = JSON.parse(source) as Record<string, unknown>;
    if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).sort().join() !== 'code,details,points,question,summary') return null;
    if (!text(value.summary, 240) || !strings(value.points, 3, 240) || typeof value.details !== 'string' || [...value.details].length > 12000) return null;
    if (value.question !== null) {
      const question = value.question as Record<string, unknown>;
      if (!question || Object.keys(question).sort().join() !== 'options,text' || !text(question.text, 240) || !strings(question.options, 4, 60)) return null;
    }
    if (value.code !== null && (typeof value.code !== 'string' || value.code.includes('\0') || new TextEncoder().encode(value.code).length > 65536)) return null;
    return value as unknown as AssistantReply;
  } catch { return null; }
}

export function replyCode(content: string): string | null {
  const reply = structuredReply(content);
  if (reply) return reply.code;
  const match = /```(?:python|micropython|py)\s*\n([\s\S]*?)```/.exec(content);
  const code = match ? match[1].trimEnd() + '\n' : null;
  return code !== null && !code.includes('\0') && new TextEncoder().encode(code).length <= 65536 ? code : null;
}

export function replyView(content: string): AssistantReply & { structured: boolean; original: string } {
  const reply = structuredReply(content);
  if (reply) return { ...reply, structured: true, original: content };
  // Preserve the full original text behind disclosure. Never infer missing facts.
  const prose = content.replace(/```[\s\S]*?```/g, '').trim();
  const paragraphs = prose.split(/\n\s*\n/).filter(Boolean);
  const first = paragraphs[0]?.trim() ?? '';
  const summary = first.length > 0 && first.length <= 240 ? first : '回复已就绪，展开查看完整说明。';
  return { summary, points: [], question: null, details: paragraphs.length > 1 || first.length > 240 ? prose : '', code: replyCode(content), structured: false, original: content };
}

export function streamText(content: string): string {
  if (/^\s*(?:\{|```(?:json|zhangwen))/.test(content)) return '正在整理要点和代码，完成后显示。';
  // Avoid duplicating incomplete code in the dialogue during generation.
  return content.split(/```/)[0];
}
