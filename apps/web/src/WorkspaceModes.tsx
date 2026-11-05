import { Box, ChevronRight, CircuitBoard, ClipboardCheck } from 'lucide-react';
import type { WorkspaceMode } from '../../../packages/contracts/src/platform';
import { Dialog } from './Dialog';

export const workspaceModes = [
  { id: 'engineer', name: '智能工程师', icon: CircuitBoard, summary: '选器件、写程序，让作品动起来', available: true },
  { id: 'structure', name: '结构工程师', icon: Box, summary: '设计外形、材料和安装方式，准备制作文件', available: true },
  { id: 'learning', name: '造物统筹师', icon: ClipboardCheck, summary: '接住想法、整理方案，按你的安排协作并检查整体成果', available: true },
] as const;

export function ModePicker({ current, onSelect, onClose }: { current: WorkspaceMode; onSelect: (mode: WorkspaceMode) => void; onClose: () => void }) {
  return <Dialog title="切换角色" onClose={onClose} className="mode-picker-dialog">
    <p className="muted mode-picker-intro">你来决定做什么、请谁帮忙。可以先找造物统筹师整理想法，也可以直接找结构工程师或智能工程师。</p>
    <div className="mode-options">{workspaceModes.map(({ id, name, icon: Icon, summary, available }) => <button key={id} aria-pressed={id === current} onClick={() => onSelect(id)} data-dialog-autofocus={id === current || undefined}>
      <span className={`mode-mark mode-${id}`}><Icon size={25} /></span><span><strong>{name}</strong><small>{summary}</small></span><em>{available ? id === current ? '当前角色' : '进入工作台' : '待开放'}</em><ChevronRight size={16} />
    </button>)}</div>
    <p className="mode-picker-note">切换角色会保留当前项目、代码草稿与对话。</p>
  </Dialog>;
}
