import type { AssistantReply } from '../../../packages/contracts/src/mu';

const text = (value: unknown, max: number): value is string => typeof value === 'string' && value.trim().length > 0 && [...value].length <= max;
const strings = (value: unknown, count: number, max: number): value is string[] => Array.isArray(value) && value.length <= count && value.every(item => text(item, max) && item.trim());
function replyQuestion(value: unknown): AssistantReply['question'] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const question = value as Record<string, unknown>;
  return Object.keys(question).sort().join() === 'options,text' && text(question.text, 240) && strings(question.options, 4, 60)
    ? question as unknown as NonNullable<AssistantReply['question']> : null;
}

// Recover only complete presentation fields before a formatting error. This is
// deliberately separate from replyCode: never repair or execute malformed JSON.
function presentationPrefix(content: string): Record<string, unknown> {
  const source = content.trim().replace(/^```(?:json|zhangwen)\s*\n/, '');
  const fields: Record<string, unknown> = {};
  if (!source.startsWith('{')) return fields;
  let offset = 1;
  const whitespace = () => { while (/\s/.test(source[offset] ?? '') && offset < source.length) offset++; };
  function valueEnd(start: number): number {
    let quoted = false; let escaped = false;
    const stack: string[] = [];
    if (source.startsWith('null', start)) return start + 4;
    if (!['"', '[', '{'].includes(source[start])) return -1;
    for (let i = start; i < source.length; i++) {
      const char = source[i];
      if (quoted) {
        if (escaped) escaped = false;
        else if (char === '\\') escaped = true;
        else if (char === '"') { quoted = false; if (stack.length === 0) return i + 1; }
      } else if (char === '"') quoted = true;
      else if (char === '[' || char === '{') stack.push(char === '[' ? ']' : '}');
      else if (char === ']' || char === '}') {
        if (stack.pop() !== char) return -1;
        if (stack.length === 0) return i + 1;
      }
    }
    return -1;
  }
  while (offset < source.length) {
    whitespace();
    const key = /^"(summary|points|question|details)"\s*:/.exec(source.slice(offset));
    if (!key) break;
    if (Object.hasOwn(fields, key[1])) return {};
    offset += key[0].length; whitespace();
    const end = valueEnd(offset);
    if (end < 0) break;
    try { fields[key[1]] = JSON.parse(source.slice(offset, end)) as unknown; }
    catch { break; }
    offset = end; whitespace();
    if (source[offset] !== ',') break;
    offset++;
  }
  return fields;
}

function replyData(content: string): Record<string, unknown> | null {
  const source = content.trim().replace(/^```(?:json|zhangwen)\s*\n([\s\S]*?)\s*```$/, '$1');
  if (!source.startsWith('{')) return null;
  let depth = 0; let quoted = false; let escaped = false;
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (quoted) {
      if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '"') quoted = false;
    } else if (char === '"') quoted = true;
    else if (char === '{') depth++;
    else if (char === '}' && --depth === 0) {
      if (/^(?:\{|\[|```)/.test(source.slice(i + 1).trimStart())) return null;
      try { return JSON.parse(source.slice(0, i + 1)) as Record<string, unknown>; }
      catch { return null; }
    }
  }
  return null;
}

export function structuredReply(content: string): AssistantReply | null {
  try {
    const value = replyData(content);
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
  const data = replyData(content);
  if (data) {
    const code = data.code;
    return typeof code === 'string' && code.trim() && !code.includes('\0') && new TextEncoder().encode(code).length <= 65536 ? code : null;
  }
  if (/^\s*(?:\{|```(?:json|zhangwen))/.test(content)) return null;
  const match = /```(?:python|micropython|py)\s*\n([\s\S]*?)```/.exec(content);
  const code = match ? match[1].trimEnd() + '\n' : null;
  return code !== null && code.trim() && !code.includes('\0') && new TextEncoder().encode(code).length <= 65536 ? code : null;
}

export function replyView(content: string): AssistantReply & { structured: boolean; formatIssue: boolean; original: string } {
  const reply = structuredReply(content);
  if (reply) return { ...reply, code: replyCode(content), structured: true, formatIssue: false, original: content };
  const complete = replyData(content);
  const data = complete ?? presentationPrefix(content);
  if (data && text(data.summary, 240) && strings(data.points, 12, 240) && typeof data.details === 'string' && [...data.details].length <= 12000) {
    const points = data.points.slice(0, 3);
    if (data.points.length > 3) points[2] = data.points.slice(2).join('；');
    return { summary: data.summary, points, question: replyQuestion(data.question),
      details: data.details, code: replyCode(content), structured: false, formatIssue: complete === null, original: content };
  }
  if (!complete && text(data.summary, 240)) return { summary: data.summary,
    points: strings(data.points, 3, 240) ? data.points : [], question: replyQuestion(data.question),
    details: '', code: null, structured: false, formatIssue: true, original: content };
  // Preserve the full original text behind disclosure. Never infer missing facts.
  const prose = content.replace(/```[\s\S]*?```/g, '').trim();
  const paragraphs = prose.split(/\n\s*\n/).filter(Boolean);
  const first = paragraphs[0]?.trim() ?? '';
  const summary = first.length > 0 && first.length <= 240 ? first : '回复已就绪，展开查看完整说明。';
  return { summary, points: [], question: null, details: paragraphs.length > 1 || first.length > 240 ? prose : '', code: replyCode(content), structured: false, formatIssue: /^\s*(?:\{|```(?:json|zhangwen))/.test(content), original: content };
}

export function streamText(content: string): string {
  if (/^\s*(?:\{|```(?:json|zhangwen))/.test(content)) return '正在整理要点和代码，完成后显示。';
  // Avoid duplicating incomplete code in the dialogue during generation.
  return content.split(/```/)[0];
}
