# 双板项目实物仿真与部署人工验收清单

以下真实设备项目全部标记为 `hardware`。本轮自动实现不得执行真实部署、烧录、复位或参数写入。

## 自动测试隔离

- `services/local-api/pyproject.toml` 默认使用 `-m "not hardware"`，普通本地与 CI 测试不会收集
  真实硬件用例；
- `hardware` 用例即使被显式选择，也必须同时设置
  `ZHANGWEN_RUN_HARDWARE_TESTS=1` 和
  `ZHANGWEN_HARDWARE_TEST_CONFIRMATION=I_UNDERSTAND_REAL_HARDWARE`；
- PowerShell 显式入口为：

  ```powershell
  $env:ZHANGWEN_RUN_HARDWARE_TESTS = "1"
  $env:ZHANGWEN_HARDWARE_TEST_CONFIRMATION = "I_UNDERSTAND_REAL_HARDWARE"
  .venv\Scripts\python.exe -m pytest services/local-api/tests/hardware -o addopts="" -m hardware
  ```

- 这两个门禁只允许进入 M8 人工验收，不授权 Flash 擦除、固件烧录、凭据变更或执行器动作；
  这些操作仍需各自的风险确认与恢复方案；
- 当前 `tests/hardware` 只有安全跳过的 M8 占位入口。真实 K10/XIAO、USB、ESP-Claw 和执行器
  操作留到 M8，由在场操作者按本清单逐项执行。

## 立项与场景

- [ ] 分别建立 K10、XIAO 项目，选择至少一个外接传感器和执行器并确认立项。
- [ ] 立项确认后无需再次选板；项目实物仿真自动显示正确主控、外设和已确认/待确认接线。
- [ ] 修改并确认 BOM/IO Map 后生成新 scene revision；旧运行仍显示原场景快照。
- [ ] 第三种 MCU、多主控、无主控和未确认立项均阻止仿真与部署。
- [ ] 界面中旧 K10 别名不形成第二块板。

## 两种代码部署通道

- [ ] 设备页同级显示“USB 串口 / ESP-Claw”，两者都使用当前已接受 CodeRun。
- [ ] MicroPython CodeRun 只允许 USB；ESP-Claw Lua CodeRun 只允许 ESP-Claw，错配在写入前阻止。
- [ ] USB 路径继续完成安全接管、备份、写入、读回、启动和结果记录，不发生硬件复位或 Flash 擦除。
- [ ] ESP-Claw 端点只有在专业模式手动填写双地址、完成三重确认、精确板型和能力握手后可选；
      首版不宣称 mDNS 自动发现或设备级认证。
- [ ] ESP-Claw 完成版本化脚本写入、SHA-256 读回、异步 Lua 执行和 job 结果确认。
- [ ] 取消、超时、断网、读回不符和运行失败均收敛为明确结果；不得跨通道误重试。
- [ ] 同一项目经同一设备的 IP/`.local` 别名重新配对时仍替换同一 managed job；未知 job 状态、
      孤儿操作或退出清理未确认时显示人工急停，不虚报已取消或已停止。
- [ ] ESP-Claw 部署期间没有 `esptool`、`INSTALL_APPLICATION` 或整片擦除调用。

## 运行时初始化与恢复

- [ ] 运行时安装只在专业维护区显示，并明确区别于当前代码部署。
- [ ] 记录应用版本和 SHA-256，不记录真实串口 ID、Wi-Fi 密码、令牌或端点地址。
- [ ] 精确板型、Flash/PSRAM、分区范围和受保护数据门禁通过。
- [ ] 逐段备份、写入、回读校验；取消/故障后恢复，NVS/用户数据保持。

## K10 场景与调试

- [ ] LCD、A/B/RST/BOOT、摄像头、温湿度、环境光、加速度、麦克风、扬声器、RGB、TF 卡和扩展口按项目事实显示。
- [ ] 项目外接传感器输入会改变功能模型/兼容仿真镜像行为。
- [ ] 执行器解锁、范围、刷新率、停止、断线看门狗和重连安全值通过。

## XIAO Sense 场景与调试

- [ ] OV2640、PDM 波形/WAV、虚拟 FAT32 SD、USB 串口与项目扩展引脚正确显示。
- [ ] SD 启用时 GPIO21 LED 在 UI、协议和运行时三处锁定。
- [ ] 参数 staging、提交、读回和失败恢复通过。

## UI 与收尾

- [ ] 390/720/1280 宽度无页面级横向溢出。
- [ ] 在 Creator 四阶段间往返后，对话消息、草稿、附件、引用和滚动位置保持。
- [ ] 顶部作品状态、0–6 等级和唯一下一步保持可见；四阶段可查看，动作按证据受控。
- [ ] 工程 Hash、raw job/status 与运行时安装按当前任务就地逐层展开，不恢复旧全局普通/专业模式。
- [ ] 将 scene revision、板型、CodeRun runtime、通道和结果写入独立验收记录；不得提交凭据或真实设备标识。
