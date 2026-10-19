# 行空板 K10 确定性兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "driver-required-hw_seed_unihiker_k10",
      "operator": "required-if",
      "severity": "FAIL",
      "message": "K10 声明了固件要求时必须登记对应驱动入口。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "hw_seed_unihiker_k10"
      }
    }
  ]
}
```

## 人工复核边界

- K10 可为低功率外设提供离散 3.3 V 与 5 V 电源轨；Rule Engine 必须依据外设允许范围选择具体电源轨，不能把整板 5 V 输入直接当成唯一外设电压。
- 外设向 K10 输出高于 3.3 V 的信号时必须增加分压或电平转换。
- 舵机、电机、泵、继电器和大功率灯带必须使用驱动与独立负载电源，并与 K10 共地。
- P0/P1 可用于数字、ADC 和 PWM；其余扩展 GPIO 不默认具备 ADC/PWM 能力。
- I2C 外设必须核对地址、上拉、电平和线长。
