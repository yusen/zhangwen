import { Box, ChevronRight, CircuitBoard, GraduationCap } from 'lucide-react';
import type { WorkspaceMode } from '../../../packages/contracts/src/mu';
import { Dialog } from './Dialog';

export const workspaceModes = [
  { id: 'engineer', name: '智能工程师', icon: CircuitBoard, summary: '硬件选型、AI 编程与设备联调', available: true },
  { id: 'structure', name: '结构设计师', icon: Box, summary: '外壳需求、尺寸布局、模型预览与导出', available: true },
  { id: 'learning', name: '学习设计师', icon: GraduationCap, summary: '围绕作品组织学习与探究活动', available: false },
] as const;

export function ModePicker({ current, onSelect, onClose }: { current: WorkspaceMode; onSelect: (mode: WorkspaceMode) => void; onClose: () => void }) {
  return <Dialog title="切换三师模式" onClose={onClose} className="mode-picker-dialog">
    <p className="muted mode-picker-intro">围绕同一个项目，在三师之间切换。</p>
    <div className="mode-options">{workspaceModes.map(({ id, name, icon: Icon, summary, available }) => <button key={id} aria-pressed={id === current} onClick={() => onSelect(id)} data-dialog-autofocus={id === current || undefined}>
      <span className={`mode-mark mode-${id}`}><Icon size={25} /></span><span><strong>{name}</strong><small>{summary}</small></span><em>{id === 'learning' ? '界面预览' : available ? id === current ? '当前模式' : '进入工作台' : '待开放'}</em><ChevronRight size={16} />
    </button>)}</div>
    <p className="mode-picker-note">切换模式会保留当前项目、代码草稿与对话。</p>
  </Dialog>;
}
