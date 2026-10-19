# DFR0486 确定性兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "dfr0486-controller-support",
      "operator": "contains-any",
      "severity": "FAIL",
      "message": "DFR0486 需要 K10 或声明兼容的 ESP32-S3 主控。",
      "params": {"field": "electrical.supportedMCUs", "candidateField": "identifiers", "subjectCategories": ["DISPLAY"], "candidateCategories": ["MCU"], "componentId": "hw_dfrobot_dfr0486"}
    },
    {
      "id": "dfr0486-supply-range",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "DFR0486 必须使用兼容电源轨；K10 方案推荐 3.3V。",
      "params": {"field": "electrical.voltage", "leftCategories": ["DISPLAY"], "rightCategories": ["MCU"], "tolerance": 0.1, "componentId": "hw_dfrobot_dfr0486"}
    },
    {
      "id": "dfr0486-logic-level",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "DFR0486 I2C 信号不得超过主控逻辑电平边界。",
      "params": {"field": "electrical.logicLevel", "leftCategories": ["DISPLAY"], "rightCategories": ["MCU"], "tolerance": 0.1, "componentId": "hw_dfrobot_dfr0486"}
    },
    {
      "id": "dfr0486-i2c-address",
      "operator": "unique",
      "severity": "FAIL",
      "message": "DFR0486 的 I2C 地址 0x3C 不得与其他器件冲突。",
      "params": {"field": "electrical.i2cAddress", "whenField": "electrical.communicationProtocol", "whenEquals": "I2C", "componentId": "hw_dfrobot_dfr0486"}
    },
    {
      "id": "dfr0486-driver-when-firmware-required",
      "operator": "required-if",
      "severity": "FAIL",
      "message": "声明固件要求时必须登记 DFR0486 驱动。",
      "params": {"requiredField": "electrical.driverName", "ifField": "electrical.firmwareRequirement", "ifPresent": true, "componentId": "hw_dfrobot_dfr0486"}
    }
  ]
}
```
