# 兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "regulated-power-current-budget",
      "operator": "sum-lte",
      "severity": "FAIL",
      "message": "所选负载峰值电流超过 5V/3A 电源能力。",
      "params": {"field": "electrical.peakCurrent", "sumCategories": ["ACTUATOR"], "limitCategories": ["POWER"], "componentId": "hw_power_5v_3a_regulated"}
    },
    {
      "id": "regulated-power-driver-when-firmware-required",
      "operator": "required-if",
      "severity": "FAIL",
      "message": "声明固件要求时必须登记驱动。",
      "params": {"requiredField": "electrical.driverName", "ifField": "electrical.firmwareRequirement", "ifPresent": true, "componentId": "hw_power_5v_3a_regulated"}
    }
  ]
}
```

水泵 Hardware Skill 负责校验电压与峰值电流预算；本包不推断具体适配器的极性、认证或保护能力。
