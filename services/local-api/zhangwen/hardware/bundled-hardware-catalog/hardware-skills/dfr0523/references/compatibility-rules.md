# DFR0523 确定性兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "dfr0523-independent-power-voltage",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "DFR0523 只能由 5–6V 的独立负载电源供电。",
      "params": {"field": "electrical.voltage", "leftCategories": ["ACTUATOR"], "rightCategories": ["POWER"], "tolerance": 0.0, "componentId": "hw_dfrobot_dfr0523"}
    },
    {
      "id": "dfr0523-independent-power-current",
      "operator": "sum-lte",
      "severity": "FAIL",
      "message": "DFR0523 峰值 2.5A，必须选择至少 5V/3A 的独立稳压电源；不得由 K10 或 GPIO 供电。",
      "params": {"field": "electrical.peakCurrent", "sumCategories": ["ACTUATOR"], "limitCategories": ["POWER"]}
    },
    {
      "id": "dfr0523-k10-support",
      "operator": "contains-any",
      "severity": "FAIL",
      "message": "DFR0523 当前受信闭环需要 K10 或声明兼容的 ESP32-S3 主控。",
      "params": {"field": "electrical.supportedMCUs", "candidateField": "identifiers", "subjectCategories": ["ACTUATOR"], "candidateCategories": ["MCU"], "componentId": "hw_dfrobot_dfr0523"}
    },
    {
      "id": "dfr0523-k10-pwm-level",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "DFR0523 控制信号必须兼容 K10 的 3.3V PWM 逻辑。",
      "params": {"field": "electrical.logicLevel", "leftCategories": ["ACTUATOR"], "rightCategories": ["MCU"], "tolerance": 0.0, "componentId": "hw_dfrobot_dfr0523"}
    },
    {
      "id": "dfr0523-driver-when-firmware-required",
      "operator": "required-if",
      "severity": "FAIL",
      "message": "声明固件要求时必须登记 DFR0523 驱动。",
      "params": {"requiredField": "electrical.driverName", "ifField": "electrical.firmwareRequirement", "ifPresent": true, "componentId": "hw_dfrobot_dfr0523"}
    }
  ]
}
```
