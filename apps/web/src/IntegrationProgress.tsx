import { ArrowRight } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/platform';
import type { integrationSession } from './integrationSession';

export function IntegrationProgress({ state, componentIds, hardware, disabled, onSelect, onDevelop }: {
  state: NonNullable<ReturnType<typeof integrationSession>>; componentIds: string[]; hardware: HardwareSummary[];
  disabled: boolean; onSelect: (id: string) => void; onDevelop: () => void;
}) {
  const label = (id: string) => hardware.find(m => m.componentId === id)?.displayName ?? id;
  return <section className="integration-progress" aria-label="逐项器件测试">
    <div className="integration-progress-current"><strong>逐个测试 · {state.index + 1}/{state.total}</strong><label className="sr-only" htmlFor="integration-module">切换测试模块</label><select id="integration-module" value={state.targetId} disabled={disabled} title="选择要测试的模块" onChange={e => onSelect(e.target.value)}>{componentIds.map(id => <option key={id} value={id}>{label(id)}</option>)}</select></div>
    <p>{state.nextId ? `下一项：${label(state.nextId)}` : '已到最后一项；如有漏测，可从列表切换。'}</p>
    <div className="integration-progress-actions">{state.nextId && <button className="primary" disabled={disabled} onClick={() => onSelect(state.nextId!)}>测试下一个模块<ArrowRight size={14}/></button>}<button disabled={disabled} onClick={onDevelop}>直接做作品</button><small>切换仅生成建议，实测结果由你反馈</small></div>
  </section>;
}
