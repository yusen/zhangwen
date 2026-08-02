# 声明式兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "voltage-<唯一硬件ID>",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "允许工作电压范围与主控外设电源轨不匹配。",
      "params": {
        "field": "electrical.voltage",
        "leftCategories": ["SENSOR"],
        "rightCategories": ["MCU"],
        "tolerance": 0.5,
        "componentId": "<唯一硬件ID>"
      }
    },
    {
      "id": "logic-level-<唯一硬件ID>",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "逻辑电平与主控不兼容。",
      "params": {
        "field": "electrical.logicLevel",
        "leftCategories": ["SENSOR"],
        "rightCategories": ["MCU"],
        "tolerance": 0.3,
        "componentId": "<唯一硬件ID>"
      }
    },
    {
      "id": "mcu-support-<唯一硬件ID>",
      "operator": "contains-any",
      "severity": "FAIL",
      "message": "器件未声明支持当前主控。",
      "params": {
        "field": "electrical.supportedMCUs",
        "candidateField": "identifiers",
        "subjectCategories": ["SENSOR"],
        "candidateCategories": ["MCU"],
        "componentId": "<唯一硬件ID>"
      }
    },
    {
      "id": "driver-required-<唯一硬件ID>",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "器件有固件要求，但未登记驱动名称。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "<唯一硬件ID>"
      }
    }
  ]
}
```

若填写非空 I2C 地址，还必须增加 `unique` 地址规则。器件类别不是 SENSOR 时同步替换规则中的类别。
