# DFR0029 确定性兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "dfr0029-controller-support",
      "operator": "contains-any",
      "severity": "FAIL",
      "message": "DFR0029 需要 K10 或声明兼容的 ESP32-S3 主控。",
      "params": {"field": "electrical.supportedMCUs", "candidateField": "identifiers", "subjectCategories": ["SENSOR"], "candidateCategories": ["MCU"], "componentId": "hw_dfrobot_dfr0029_button"}
    },
    {
      "id": "dfr0029-supply-range",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "DFR0029 必须使用兼容电源轨；K10 方案固定 3.3V。",
      "params": {"field": "electrical.voltage", "leftCategories": ["SENSOR"], "rightCategories": ["MCU"], "tolerance": 0.1, "componentId": "hw_dfrobot_dfr0029_button"}
    },
    {
      "id": "dfr0029-logic-level",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "DFR0029 数字信号不得超过主控逻辑电平边界。",
      "params": {"field": "electrical.logicLevel", "leftCategories": ["SENSOR"], "rightCategories": ["MCU"], "tolerance": 0.1, "componentId": "hw_dfrobot_dfr0029_button"}
    },
    {
      "id": "dfr0029-driver-when-firmware-required",
      "operator": "required-if",
      "severity": "FAIL",
      "message": "声明固件要求时必须登记 DFR0029 驱动。",
      "params": {"requiredField": "electrical.driverName", "ifField": "electrical.firmwareRequirement", "ifPresent": true, "componentId": "hw_dfrobot_dfr0029_button"}
    }
  ]
}
```
