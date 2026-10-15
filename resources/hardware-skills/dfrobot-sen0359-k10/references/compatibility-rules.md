# 声明式兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "voltage-hw_dfrobot_sen0359_k10",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "工作电压与主控不匹配。",
      "params": {
        "field": "electrical.voltage",
        "leftCategories": [
          "SENSOR"
        ],
        "rightCategories": [
          "MCU"
        ],
        "tolerance": 0.5,
        "componentId": "hw_dfrobot_sen0359_k10"
      }
    },
    {
      "id": "logic-level-hw_dfrobot_sen0359_k10",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "信号电平与主控不兼容。",
      "params": {
        "field": "electrical.logicLevel",
        "leftCategories": [
          "SENSOR"
        ],
        "rightCategories": [
          "MCU"
        ],
        "tolerance": 0.3,
        "componentId": "hw_dfrobot_sen0359_k10"
      }
    },
    {
      "id": "mcu-support-hw_dfrobot_sen0359_k10",
      "operator": "contains-any",
      "severity": "FAIL",
      "message": "器件未声明支持当前主控。",
      "params": {
        "field": "electrical.supportedMCUs",
        "candidateField": "identifiers",
        "subjectCategories": [
          "SENSOR"
        ],
        "candidateCategories": [
          "MCU"
        ],
        "componentId": "hw_dfrobot_sen0359_k10"
      }
    },
    {
      "id": "driver-required-hw_dfrobot_sen0359_k10",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "器件有固件要求，但未登记驱动入口。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "hw_dfrobot_sen0359_k10"
      }
    }
  ]
}
```

## 人工检查项

- 对照模块丝印和官方 Wiki 复核 VCC、GND、信号方向及接口电平。
- 规则只覆盖声明字段，不能代替负载电流、上拉电压、模拟满量程和大功率供电检查。
