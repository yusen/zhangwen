# SEN0193 确定性兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "sen0193-k10-supply-range",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "SEN0193 必须使用兼容电源轨；K10 方案固定推荐 3.3V。",
      "params": {"field": "electrical.voltage", "leftCategories": ["SENSOR"], "rightCategories": ["MCU"], "tolerance": 0.1, "componentId": "hw_dfrobot_sen0193"}
    },
    {
      "id": "sen0193-k10-support",
      "operator": "contains-any",
      "severity": "FAIL",
      "message": "SEN0193 当前受信闭环需要 K10 或声明兼容的 ESP32-S3 主控。",
      "params": {"field": "electrical.supportedMCUs", "candidateField": "identifiers", "subjectCategories": ["SENSOR"], "candidateCategories": ["MCU"], "componentId": "hw_dfrobot_sen0193"}
    },
    {
      "id": "sen0193-k10-adc-level",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "SEN0193 模拟输出不得超过主控 ADC 逻辑电平边界。",
      "params": {"field": "electrical.logicLevel", "leftCategories": ["SENSOR"], "rightCategories": ["MCU"], "tolerance": 0.3, "componentId": "hw_dfrobot_sen0193"}
    },
    {
      "id": "sen0193-driver-when-firmware-required",
      "operator": "required-if",
      "severity": "FAIL",
      "message": "声明固件要求时必须登记 SEN0193 驱动。",
      "params": {"requiredField": "electrical.driverName", "ifField": "electrical.firmwareRequirement", "ifPresent": true, "componentId": "hw_dfrobot_sen0193"}
    }
  ]
}
```
