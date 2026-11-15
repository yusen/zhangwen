import type { WorkflowView } from '../../../packages/contracts/src/workflow';
import { lastConfirmed } from './workflowUtils';

/** A read-only next step from existing records; never a completion or dispatch record. */
export function makingStep(view: WorkflowView, selectedId = '') {
  if (!lastConfirmed(view.checkpoint)) return {
    title:'一起确定要做的作品',
    steps:['根据已选器件，和学习设计师一起确定要做的作品。','明确目标、动作规则和完成条件，核对后确认作品目标。'],
    expected:'对话已整理作品说明，核对目标、动作和完成条件后确认。',
    test:null, status:null, reasons:[],
  };
  const active = view.checkpoint.cases.filter(item => item.active);
  const stateOf = (id: string) => view.caseStates.find(item => item.id === id);
  if (!selectedId && active.length && active.every(item => stateOf(item.id)?.status === 'passed')) return {
    title:'核对整体效果，整理制作发现',
    steps:['对照作品目标，检查已有测试是否覆盖基本功能与装配效果。','还有遗漏就补一次测试；已经覆盖的部分，可以整理发现、问题和下一步。'],
    expected:'现有要求都有当前适用的用户通过记录；整体作品是否完成，仍由你结合实物核对。',
    test:null, status:null, reasons:[],
  };
  const priority = {stale:0, failed:1, blocked:2, unrecorded:3, passed:4};
  const next = active.find(item => item.id === selectedId) ?? [...active].sort((a,b) =>
    (priority[stateOf(a.id)?.status ?? 'unrecorded']) - (priority[stateOf(b.id)?.status ?? 'unrecorded']))[0];
  if (next) return {
    title: next.title, steps: [next.procedure], expected: next.expected, test: next,
    status: stateOf(next.id)?.status ?? 'unrecorded', reasons: stateOf(next.id)?.reasons ?? [],
  };
  if (!view.current.code.revision) return {
    title:'先让需要的器件完成一个基本动作',
    steps:['核对本次使用器件的接线、供电与活动空间。','需要程序时，请智能工程师帮助验证一个输入或输出；已完成的部分可以跳过。','保存并运行后，观察读数或动作，再继续组合功能。'],
    expected:'实际看到了预期读数或动作；记录现象，保存程序本身不代表这一步通过。',
    test:null, status:null, reasons:[],
  };
  return {
    title:'把已完成的部分组合起来验证',
    steps:['对照目标检查程序与实物的配合，需要外壳或机构时再请结构工程师帮助。','从一个基本效果开始测试，记录实际现象和遇到的问题。'],
    expected:'有一份与当前作品相符的测试要求和实际观察，能判断基本效果是否达到。',
    test:null, status:null, reasons:[],
  };
}

export function learningTaskText(view: WorkflowView, title: string, steps: string[], expected: string) {
  const goal = lastConfirmed(view.checkpoint);
  return `请帮助我完成当前制作任务：${title}\n${goal ? `已确认目标：${goal.goal}\n动作规则：${goal.behavior}\n` : '目标尚未确认，请结合已有器件帮助我讨论方案。\n'}建议做法：${steps.join('\n')}\n完成标志：${expected}\n请结合当前已保存的项目资料，给出本角色的具体做法和验证步骤；未知条件明确指出。`;
}

/** Keep an unsent prompt intact and reject overflow instead of truncating it. */
export function appendLearningTask(original: string, task: string, limit = 4000): string | null {
  const next = original.trim() ? original + '\n\n' + task : task;
  return next.length <= limit ? next : null;
}
