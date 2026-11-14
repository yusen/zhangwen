import type { ControllerCheck } from '../../../packages/contracts/src/channels';

export const MICROBIT_BOARD = 'hw_bbc_microbit';
export function selfTestPrograms(boardId: string): { id: string; label: string; code: string }[] {
  const basic = [
    { id: 'runtime', label: 'MicroPython 运行环境', code: 'import sys\nprint("ZW_CHECK|" + sys.implementation[0] + "|" + sys.platform)' },
    { id: 'memory', label: '可用内存', code: 'import gc\nprint("ZW_CHECK|" + str(gc.mem_free()))' },
    { id: 'filesystem', label: '文件系统读取', code: 'import os\nprint("ZW_CHECK|" + str(len(os.listdir())))' },
  ];
  const module = boardId === MICROBIT_BOARD ? 'microbit' : boardId.includes('mpython') ? 'mpython' : boardId === 'hw_seed_unihiker_k10' ? 'unihiker_k10' : 'machine';
  basic.push({ id: 'board-api', label: '主控编程接口', code: `import ${module}\nprint("ZW_CHECK|${module}")` });
  if (boardId === MICROBIT_BOARD) basic.push({ id: 'onboard', label: '板载按钮、温度与加速度读取', code: 'from microbit import button_a, button_b, temperature, accelerometer\nprint("ZW_CHECK|" + str(button_a.is_pressed()) + "|" + str(button_b.is_pressed()) + "|" + str(temperature()) + "|" + str(accelerometer.get_values()))' });
  return basic;
}
export function parseSelfTestResult(id: string, label: string, output: string): ControllerCheck {
  const lines = output.trim().split(/\r?\n/);
  const line = lines.find(value => value.startsWith('ZW_CHECK|'));
  if (!line) return { id, label, status: 'failed', detail: '自检程序未返回有效标记。' };
  const detail = line.slice(9);
  if ((id === 'runtime' && !detail.startsWith('micropython|')) || (id === 'memory' && (!/^\d+$/.test(detail) || Number(detail) <= 0)) || (id === 'filesystem' && !/^\d+$/.test(detail))) return { id, label, status: 'failed', detail };
  return { id, label, status: 'passed', detail };
}
