# 声明式兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "driver-required-hw_labplus_mpython_esp32s3_v3",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "主控声明了固件要求，但未登记驱动入口。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "hw_labplus_mpython_esp32s3_v3"
      }
    }
  ]
}
```

## 人工检查项

- 外接模块必须兼容 3.3V 逻辑；5V 供电模块的信号端仍须单独检查或电平转换。
- P19/P20 与板载 I2C 设备共享，增加设备前扫描地址并确认总线上拉电压和总电容。
- 外接电机、舵机、灯带、继电器和扬声器应独立核算峰值电流，不得只依据 1000mA 标称负载值。
