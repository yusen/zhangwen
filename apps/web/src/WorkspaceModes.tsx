import { Box, ChevronRight, CircuitBoard, GraduationCap, Layers3, LockKeyhole } from 'lucide-react';
import type { WorkspaceMode } from '../../../packages/contracts/src/mu';
import { Dialog } from './Dialog';

export const workspaceModes = [
  { id: 'engineer', name: '智能工程师', icon: CircuitBoard, summary: '硬件选型、AI 编程与设备联调', available: true },
  { id: 'structure', name: '结构设计师', icon: Box, summary: '把作品想法变成可装配的结构', available: false },
  { id: 'learning', name: '学习设计师', icon: GraduationCap, summary: '围绕作品组织学习与探究活动', available: false },
] as const;

export function ModePicker({ current, onSelect, onClose }: { current: WorkspaceMode; onSelect: (mode: WorkspaceMode) => void; onClose: () => void }) {
  return <Dialog title="切换三师模式" onClose={onClose} className="mode-picker-dialog">
    <p className="muted mode-picker-intro">围绕同一个项目，在三师之间切换。</p>
    <div className="mode-options">{workspaceModes.map(({ id, name, icon: Icon, summary, available }) => <button key={id} aria-pressed={id === current} onClick={() => onSelect(id)} data-dialog-autofocus={id === current || undefined}>
      <span className={`mode-mark mode-${id}`}><Icon size={25} /></span><span><strong>{name}</strong><small>{summary}</small></span><em>{available ? id === current ? '当前模式' : '进入工作台' : '待开放'}</em><ChevronRight size={16} />
    </button>)}</div>
    <p className="mode-picker-note">切换模式会保留当前项目、代码草稿与对话。</p>
  </Dialog>;
}

export function PlannedWorkspace({ mode, projectName, onEngineer }: { mode: Exclude<WorkspaceMode, 'engineer'>; projectName: string; onEngineer: () => void }) {
  const structural = mode === 'structure';
  const info = workspaceModes.find(item => item.id === mode)!;
  const Icon = info.icon;
  const steps = structural ? ['结构需求', '布局与尺寸', '模型与装配'] : ['学习目标', '探究活动', '评价与反馈'];
  return <main className={`planned-workspace planned-${mode}`} aria-label={`${info.name}工作区`}>
    <aside className="planned-navigation"><h2><Icon size={18} />{structural ? '结构设计' : '学习设计'}</h2><p>项目 · {projectName}</p><ol>{steps.map((step, i) => <li key={step}><span>0{i + 1}</span>{step}<LockKeyhole size={13} /></li>)}</ol><span className="planned-navigation-note">功能开放后可在这里继续项目</span></aside>
    <section className="planned-content"><div className="planned-heading"><span><Layers3 size={16} />三师协同</span><span className="planned-badge">待开放</span></div>
      <div className="planned-empty"><span className={`mode-mark mode-${mode}`}><Icon size={42} strokeWidth={1.5} /></span><h1>{info.name}</h1><p>{info.summary}</p><span className="planned-badge">功能正在筹备，尚未开放</span><button className="primary" onClick={onEngineer}>返回智能工程师<ChevronRight size={16} /></button></div>
      <div className="planned-preview" aria-label="规划方向">{steps.map((step, index) => <article key={step}><span>0{index + 1}</span><h3>{step}</h3><p>{structural ? ['确认外壳、固定与接口需求', '安排主控和模块的装配位置', '预览结构并准备加工文件'][index] : ['明确学段、主题与学习目标', '组织任务、问题与实践过程', '设计学习证据与评价方式'][index]}</p><small>规划中</small></article>)}</div>
    </section>
  </main>;
}
