import { BookOpen, ChevronRight, Plus, Save, X } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/platform';
import { BoardArtwork } from './BoardArtwork';
import { Dialog } from './Dialog';
import './projectHardware.css';

export function ProjectHardwareDialog({ boardId, board, componentIds, hardware, dirty, savedProject, blocked, error, busy, onClose, onChooseBoard, onAdd, onRemove, onDetail, onSave }: {
  boardId: string; board?: HardwareSummary; componentIds: string[]; hardware: HardwareSummary[];
  dirty: boolean; savedProject: boolean; blocked: boolean; error: string; busy: string;
  onClose: () => void; onChooseBoard: () => void; onAdd: () => void; onRemove: (id: string) => void;
  onDetail: (item: HardwareSummary) => void; onSave: () => void;
}) {
  return <Dialog title="项目器件" className="project-hardware-dialog" onClose={onClose} footer={<>
    <span role="status">{busy || (!savedProject ? '当前选择尚未保存到项目' : dirty ? '器件选择有更改，尚未保存' : '器件选择已保存，三师共用')}</span>
    <button className="primary" disabled={blocked || (savedProject && !dirty)} onClick={onSave}><Save size={17}/>{savedProject ? '保存器件选择' : '保存项目'}</button>
  </>}>
    <p className="project-hardware-intro">主控和模块由整个项目统一管理，学习设计师、结构工程师、智能工程师共用。修改会同步显示，保存后用于后续建议与测试。</p>
    {error && <p className="settings-error" role="alert">{error}</p>}
    <section aria-label="项目主控" className="project-hardware-board">
      <h3>主控板</h3>
      <button data-dialog-autofocus className="workflow-board" aria-label="主控板" disabled={blocked} onClick={onChooseBoard}><BoardArtwork board={board}/><span>{board?.displayName || (boardId ? `资料不可用：${boardId}` : '选择主控板')}</span><ChevronRight size={17}/></button>
      {board && <button className="project-hardware-reference" disabled={blocked} onClick={() => onDetail(board)}><BookOpen size={16}/>查看主控使用资料</button>}
    </section>
    <section aria-label="项目模块" className="project-hardware-modules">
      <div className="project-hardware-heading"><h3>模块 <small>{componentIds.length} / 32</small></h3><button disabled={blocked || !boardId || componentIds.length >= 32} onClick={onAdd}><Plus size={17}/>添加模块</button></div>
      {!boardId && <p className="muted">先选择主控板，再添加模块。</p>}
      {!!boardId && !componentIds.length && <p className="muted">还没有添加模块。只用主控自带功能时，可以直接保存。</p>}
      <div className="project-hardware-list">{componentIds.map(id => {
        const item = hardware.find(value => value.componentId === id);
        const label = item?.displayName ?? id;
        return <article key={id} className="project-hardware-module"><div><strong>{label}</strong>{item ? <button className="project-hardware-reference" disabled={blocked} aria-label={`查看${label}资料`} onClick={() => onDetail(item)}><BookOpen size={15}/>查看资料</button> : <small>资料暂不可用，可移出项目</small>}</div><button className="icon-button" aria-label={`移除${label}`} title={`移除${label}`} disabled={blocked} onClick={() => onRemove(id)}><X size={18}/></button></article>;
      })}</div>
    </section>
    <p className="project-hardware-note">结构页面另设安装清单，用于尺寸、孔位与安装位置。器件变更后，原程序、结构和观察记录仍保留，需要重新核对与测试。</p>
  </Dialog>;
}
