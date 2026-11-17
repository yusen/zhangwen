import { Dialog } from './Dialog';

export function MicrobitPreparation({ onClose }: { onClose: () => void }) {
  return <Dialog title="micro:bit 固件准备" onClose={onClose}>
    <ol>
      <li>首次使用先备份旧程序，再用官方 Python 编辑器为实际 V1/V2 主控准备 MicroPython。已经能在掌问连接并通过自检时，可继续使用现有固件。</li>
      <li>关闭其他编辑器的串口连接，回到掌问选择 micro:bit 串口，执行“主控自检”。</li>
      <li>核对代码，采用并保存后点击“上传并运行”，查看终端和板上现象。</li>
    </ol>
    <a href="https://python.microbit.org/v/3" target="_blank" rel="noreferrer">打开官方 micro:bit Python 编辑器</a>
    <details><summary>能看到 MICROBIT 盘，串口列表却没有设备</summary>
      <p>MICROBIT 盘和串口是两个接口。Windows 中可在设备管理器查看“端口”；若 mbed Serial Port 报错 39，需先修复该设备的串口驱动，可核对并选择兼容的 Windows 自带“USB 串行设备”驱动，再返回掌问连接。</p>
    </details>
    <p className="muted">掌问上传 main.py，上传前备份并完整回读；写入中断后须重连核对，不自动重发。固件和 HEX 由你在官方编辑器中准备。</p>
  </Dialog>;
}
