# 资料来源

| sourceId | 类型 | URL/标识 | 支持的事实 | 核对状态 |
|---|---|---|---|---|
| drobotics:rdk-x5-spec-v1.1 | 官方产品规格书 | https://archive.d-robotics.cc/downloads/hardware/rdk_x5/d_robotics_rdk_x5_zh_v1_1.pdf | CPU/BPU/GPU、内存、存储、接口、无线、5V/5A、温度、85×56×20mm、孔径 | 已核对，2026-07-18 |
| drobotics:rdk-x5-hardware | 官方 RDK DOC | https://developer.d-robotics.cc/rdk_doc/Quick_start/hardware_introduction/rdk_x5/ | 接口布局、供电、调试串口、相机/TF 禁止热插拔、网络、负载能力 | 已核对，2026-07-18 |
| drobotics:rdk-x5-40pin | 官方 RDK DOC | https://developer.d-robotics.cc/rdk_x_doc/Basic_Application/01_40pin_user_sample/40pin_define | 3.3V/3.46V、保守输出电流、物理针脚图、复用关系 | 已核对，2026-07-18 |
| drobotics:rdk-x5-gpio | 官方 RDK DOC | https://developer.d-robotics.cc/rdk_x_doc/Basic_Application/01_40pin_user_sample/gpio | Hobot.GPIO、编号模式与基础 GPIO API | 已核对，2026-07-18 |
| drobotics:rdk-x5-pwm | 官方 RDK DOC | https://developer.d-robotics.cc/rdk_x_doc/Basic_Application/01_40pin_user_sample/pwm | 8 路硬件 PWM、针脚、频率与启用边界 | 已核对，2026-07-18 |
| drobotics:rdk-x5-download | 官方下载汇总 | https://developer.d-robotics.cc/rdk_doc/Quick_start/download/ | RDK OS 版本基线、官方规格书和 2D/3D 资料入口 | 已核对，2026-07-18 |
| drobotics:rdk-doc-license | 官方 GitHub | https://github.com/D-Robotics/rdk_doc/blob/main/LICENSE | rdk_doc 仓库 Apache License 2.0 | 已核对，2026-07-18 |

## 证据边界

- 媒体来自官方 `rdk_doc` Markdown 引用的图片资源，并按仓库 Apache-2.0 许可证记录署名。
- 产品规格书是外形、计算、电气与温度参数的主依据；RDK DOC 用于接口和软件操作边界。
- 不把搜索摘要、经销商页面、论坛评论或 AI 推断作为官方参数来源。
- 当官方页面对 40PIN 电源负载给出不同值时，本包保留冲突并采用较低值作为安全上限。
