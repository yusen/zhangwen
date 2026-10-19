# 资料来源

| sourceId | 类型 | URL/标识 | 支持的事实 | 核对状态 |
|---|---|---|---|---|
| `vendor-product:dfrobot-sen0388` | DFRobot 官方英文 Wiki | https://wiki.dfrobot.com/sen0388/ | SKU、3.3–5.5V、<20mA、2–500cm、1cm、1%、25Hz、40±2kHz、47×22mm、单线 `D` 接口 | 已核对，2026-07-17 |
| `vendor-product:dfrobot-sen0388-cn` | DFRobot 官方中文 Wiki | https://wiki.dfrobot.com.cn/sku_sen0388_urm09_ultrasonic_sensor_gravity_trig | `-`/`+`/`D` 引脚、10μs 触发、同引脚输入输出、最长约 35000μs 回波 | 已核对，2026-07-17 |
| `vendor-board:unihiker-k10-micropython` | 行空板官方文档 | https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10 | `ultrasonic(trig=0, echo=0)` API；同一引脚示例明确对应 SEN0388 | 已核对，2026-07-17 |
| `vendor-board:unihiker-k10-schematic` | DFRobot 官方原理图 | https://dfimg.dfrobot.com/wiki/24709/DFR0992-EN_unihiker-k10_schematics_V1.0.pdf | K10 P0/P1 的 3V3/GND 与直连 GPIO 网络 | 已核对，2026-07-16 |
| `user-code:mindplus-sen0388-2026-07-17` | 用户提供 MindPlus 导出代码 | 对话中的 `ultrasonic(trig=1, echo=1)` + K10 屏幕程序 | P1 单线 API 和屏幕显示用法 | 已保存并通过语法检查，待实机验证 |
| `user-model:urm09-2026-07-16` | 用户提供结构文本和 CadQuery 代码 | `超声波测距传感器.txt` | 双探头、接线座和安装孔参考包络 | 仅作为 SEN0388 参考模型；开壳前必须实物复核 |

## 来源边界

- 官方页面足以确认 SEN0388 的电气、测量和单线接口事实。
- K10 官方页面把同引脚 `ultrasonic` 示例明确指向 SEN0388，因此该 API 是本包默认黄金路径。
- 用户结构模型不等同于 DFRobot 官方尺寸图。官方只明确给出 47×22mm 外形，其他机械细节保持 `REFERENCE_ONLY`。

