import { ArrowRight } from 'lucide-react';
import { useId, useState } from 'react';
import type { HardwareSummary } from '../../../packages/contracts/src/platform';
import type { integrationSession } from './integrationSession';

export function IntegrationProgress({ state, componentIds, hardware, disabled, onSelect, onDevelop }: {
  state: NonNullable<ReturnType<typeof integrationSession>>; componentIds: string[]; hardware: HardwareSummary[];
  disabled: boolean; onSelect: (id: string) => void; onDevelop: () => void;
}) {
  const label = (id: string) => hardware.find(m => m.componentId === id)?.displayName ?? id;
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  return <section className="integration-progress" aria-label="逐项器件测试">
    <div className="integration-progress-current"><strong>测试 {state.index + 1}/{state.total}</strong><label className="sr-only" htmlFor="integration-module">切换测试模块</label><select id="integration-module" value={state.targetId} disabled={disabled} title={label(state.targetId)} onChange={e => onSelect(e.target.value)}>{componentIds.map(id => <option key={id} value={id}>{label(id)}</option>)}</select>
      {state.nextId && <button className="integration-next" disabled={disabled} aria-label="测试下一个模块" title={`下一项：${label(state.nextId)}`} onClick={() => onSelect(state.nextId!)}>下一项<ArrowRight size={14} aria-hidden="true" /></button>}
      <button className="integration-more" aria-expanded={expanded} aria-controls={detailsId} onClick={() => setExpanded(value => !value)}>{expanded ? '收起' : '更多'}</button>
    </div>
    <div id={detailsId} hidden={!expanded} className="integration-progress-details">
      <p>{state.nextId ? `下一项：${label(state.nextId)}` : '已到最后一项；如有漏测，可从列表切换。'}</p>
      <div className="integration-progress-actions"><button disabled={disabled} onClick={onDevelop}>直接做作品</button><small>切换仅生成建议，实测结果由你反馈</small></div>
    </div>
  </section>;
}
