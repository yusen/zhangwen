# 结构化电气参数

## 工程摘要

- 官方工作范围：以 DFRobot Wiki/官方产品页为准；本批次不把未逐项核对的范围提升为机器事实。
- 推荐接入基线：3.3 V 供电、3.3 V 逻辑，以便与 K10 项目做保守的第一轮兼容预检。
- 未知项：峰值电流、批次差异、具体端口映射和当前 K10 固件 API 完整签名。

> SKU 更正：K10 兼容页写作 DFR0063；DFRobot 官方 Wiki 显示 DFR0063 实为 LCD1602，电量计正确 SKU 为 DFR0563。

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_dfrobot_dfr0563_k10",
  "name": "DFRobot DFR0563 Gravity 3.7V 锂电池电量计",
  "category": "SENSOR",
  "electrical": {
    "voltage": 3.3,
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "I2C",
    "i2cAddress": "0x36",
    "supportedMCUs": [
      "unihiker-k10"
    ],
    "driverName": null,
    "firmwareRequirement": "行空板 K10 官方 MicroPython 固件；此 SKU 仅在 Mind+ 官方兼容清单中，unihiker_k10 代码模式页面未公开专用 API"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": [
    "VERIFY_WIRING"
  ],
  "notes": "机器字段 voltage=3.3 V、logicLevel=3.3 V 是 K10 接入预检基线，不替代模块官方范围。peakCurrent=0.0 表示未知，不表示零电流。K10 兼容页写作 DFR0063；DFRobot 官方 Wiki 显示 DFR0063 实为 LCD1602，电量计正确 SKU 为 DFR0563。 K10 Python 驱动仅采用 unihiker_k10 官方代码模式文档；未公开的 SKU API 保持为空。",
  "verificationStatus": "MIGRATED_UNVERIFIED",
  "sourceIds": [
    "vendor-board:k10-compatibility",
    "vendor-product:dfr0563",
    "official:k10-unihiker-k10"
  ]
}
```
