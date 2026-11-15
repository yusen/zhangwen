import type { HardwareSummary, HardwareVerificationRecord } from '../../../packages/contracts/src/platform';
export const verificationDimensions: Record<HardwareVerificationRecord['dimension'], string> = {
  identity: '型号身份', electrical: '供电与信号电平', wiring: '接线与通信', driver: '驱动与固件', function: '功能实测', mechanical: '机械尺寸',
};
export const verificationLabels = { unverified: '未核实', documented: '资料已核对', pending: '待实测', passed: '用户报告实测通过', failed: '测试异常' };
export function verificationSummary(item: HardwareSummary, boardId?: string): { text: string; tone: string } {
  const rows = (item.verificationRecords ?? []).filter(row => row.boardId === boardId);
  if (!boardId) return { text: '请选择主控查看核实状态', tone: 'unverified' };
  if (rows.some(row => row.stale && row.state !== 'unverified')) return { text: '当前主控 · 需复核', tone: 'pending' };
  if (rows.some(row => row.state === 'failed')) return { text: '当前主控 · 测试异常', tone: 'failed' };
  if (rows.some(row => row.dimension === 'function' && row.state === 'passed')) return { text: '当前主控 · 用户报告功能通过', tone: 'passed' };
  if (rows.some(row => row.state === 'documented')) return { text: '当前主控 · 资料已核对', tone: 'documented' };
  if (rows.some(row => row.state === 'pending')) return { text: '当前主控 · 待实测', tone: 'pending' };
  return { text: item.verifiedBoardIds?.includes(boardId) ? '旧版标记 · 条件待补充' : '当前主控 · 未核实', tone: 'unverified' };
}
