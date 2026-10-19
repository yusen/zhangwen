---
name: k10
description: 行空板 K10 的统一硬件事实包，包含电气参数、结构档案、CadQuery 参考模型、MicroPython 集成边界和验证规则。
---

# 行空板 K10

行空板 K10（DFRobot DFR0992）是基于 ESP32-S3 N16R8 的 AI/IoT 教学开发板。本 Skill 是
掌问中 K10 器件事实的单一来源；硬件目录、组合校验、三师上下文和结构机械档案都从本包
当前 revision 派生。

## 快速事实

- 主控：ESP32-S3 N16R8，16 MB Flash、8 MB PSRAM。
- 显示与视觉：2.8 英寸 240×320 彩屏、GC2145 摄像头。
- 板载感知：AHT20 温湿度、LTR303ALS 环境光、SC7A20H 三轴加速度。
- 外部接口：USB Type-C、PH2.0 电池、P0/P1、PH2.0 I2C、TF 卡和金手指。
- 软件入口：K10 MicroPython 固件中的 `unihiker_k10`、`k10_base`、`ai`、`asr`。

## 渐进加载

- [结构化电气参数](references/specifications.md)
- [确定性兼容规则](references/compatibility-rules.md)
- [结构描述与机械档案](references/mechanical.md)
- [集成说明](references/integration.md)
- [安全边界](references/safety.md)
- [资料来源](references/sources.md)
- [CadQuery 参考模型](models/cadquery.py)
- [使用示例](examples/usage.md)
- [验证用例](tests/validation-cases.md)

本 Skill 只提供声明式事实、参考源码和规则，不授予文件、Shell、串口、网络或设备执行权限。
