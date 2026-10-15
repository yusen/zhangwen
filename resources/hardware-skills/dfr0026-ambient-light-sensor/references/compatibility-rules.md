# DFR0026 声明式兼容规则

## 机器可读规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "voltage-hw_dfrobot_dfr0026",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "DFR0026 的允许供电范围与主控外设电源轨不匹配。",
      "params": {
        "field": "electrical.voltage",
        "leftCategories": ["SENSOR"],
        "rightCategories": ["MCU"],
        "tolerance": 0.5,
        "componentId": "hw_dfrobot_dfr0026"
      }
    },
    {
      "id": "logic-level-hw_dfrobot_dfr0026",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "DFR0026 模拟输出电平与主控 ADC 输入范围不兼容。",
      "params": {
        "field": "electrical.logicLevel",
        "leftCategories": ["SENSOR"],
        "rightCategories": ["MCU"],
        "tolerance": 0.3,
        "componentId": "hw_dfrobot_dfr0026"
      }
    },
    {
      "id": "mcu-support-hw_dfrobot_dfr0026",
      "operator": "contains-any",
      "severity": "FAIL",
      "message": "目标主控未声明为 DFR0026 支持的 ADC 平台。",
      "params": {
        "field": "electrical.supportedMCUs",
        "candidateField": "identifiers",
        "subjectCategories": ["SENSOR"],
        "candidateCategories": ["MCU"],
        "componentId": "hw_dfrobot_dfr0026"
      }
    },
    {
      "id": "driver-required-hw_dfrobot_dfr0026",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "当前固件需要 ADC API，但未登记对应驱动入口。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "hw_dfrobot_dfr0026"
      }
    }
  ]
}
```

## 仍需人工确认的工程边界

| 场景 | 结果 | 处理 |
|---|---|---|
| K10 3.3 V 外设电源轨供电并接入 3.3 V ADC | 推荐 | Rule Engine 选择 3.3 V 轨；共地后连接，并确认端口确实支持 ADC |
| 5 V 供电并直接接入 3.3 V-only ADC | 禁止直接采用 | 降低供电或增加分压、缓冲和过压保护 |
| 输出接入纯数字引脚 | 不可用 | 改接 ADC 引脚 |
| ADC 值未经标定 | 只能表示相对亮度 | 不得直接标记为 lux |
| 制作紧配外壳或治具 | 待确认 | 用卡尺复核 20 mm 与 22 mm 的尺寸冲突 |
