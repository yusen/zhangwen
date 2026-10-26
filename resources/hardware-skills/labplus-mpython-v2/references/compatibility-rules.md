# 声明式兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "driver-required-hw_labplus_mpython_v2",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "器件有固件要求，但未登记驱动名称。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "hw_labplus_mpython_v2"
      }
    }
  ]
}
```
