import { useState } from 'react';
import { Cable, CircuitBoard, FileCode2 } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/mu';
import { moduleDirection } from './hardwareLibrary';

export function HardwareGuide({ board, componentIds, hardware, disabled, onTest, onDevelop }: {
  board: HardwareSummary | undefined;
  componentIds: string[];
  hardware: HardwareSummary[];
  disabled: boolean;
  onTest: () => void;
  onDevelop: () => void;
}) {
  const [path, setPath] = useState<'test' | 'develop' | null>(null);
  return <>
    <strong>掌问 · 确认项目硬件</strong>
    <dl className="hardware-guide-summary">
      <dt>当前主控</dt><dd><CircuitBoard size={16} aria-hidden="true" />{board?.displayName ?? '尚未选择主控'}</dd>
      <dt>已加入模块 · {componentIds.length} 个</dt>
      <dd><ul className="hardware-guide-modules">{componentIds.map(id => {
        const item = hardware.find(value => value.componentId === id);
        const direction = item && moduleDirection(item);
        return <li key={id}>{direction && <span>{direction === 'input' ? '输入' : '输出'}</span>}{item?.displayName ?? `资料不可用（${id}）`}</li>;
      })}</ul></dd>
    </dl>
    <p className="hardware-guide-question">需要先做模块与主控的联调测试吗？</p>
    <div className="hardware-guide-actions" role="group" aria-label="选择开发方式">
      <button type="button" className="primary" disabled={disabled} aria-pressed={path === 'test'} onClick={() => { setPath('test'); onTest(); }}><Cable size={17} aria-hidden="true" />联调测试</button>
      <button type="button" disabled={disabled} aria-pressed={path === 'develop'} onClick={() => { setPath('develop'); onDevelop(); }}><FileCode2 size={17} aria-hidden="true" />直接开发</button>
    </div>
    <p className="hardware-guide-hint">一次确认一个步骤，代码在右侧预览，保存后再上传运行。</p>
    {path && <p className="hardware-guide-response" role="status">{path === 'test' ? '已选择联调测试。请先核对接线、接口和供电，再根据方案逐个测试；实际测试结果需要你确认。' : '好的，直接开发。告诉我你想实现什么功能，我会结合当前主控和模块来协助你。'}</p>}
  </>;
}

export function integrationPrompt(board: HardwareSummary | undefined, boardId: string, componentIds: string[], hardware: HardwareSummary[]): string {
  const label = (id: string) => hardware.find(item => item.componentId === id)?.displayName ?? '资料不可用';
  return `开始模块联调测试。\n当前主控：${board?.displayName ?? boardId}。\n已加入模块：${componentIds.map(label).join('、')}。`;
}
