# 声明式兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "driver-required-hw-drobotics-rdk-x5",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "主控有 RDK OS 要求，但未登记 GPIO 驱动入口。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "hw_drobotics_rdk_x5"
      }
    }
  ]
}
```

## 人工检查项

- 外设 GPIO、I2C、SPI、UART、I2S 和 PWM 信号必须兼容 3.3 V，输入不得超过 3.46 V。
- 先核对 40PIN 物理针脚与 `srpi-config` 复用状态；同组复用功能不能同时生效。
- 40PIN、USB、CAN 和 DSI 的负载能力是单接口条件，多接口同时使用时必须重新核算总电流和压降。
- 相机、显示、CAN FD、PoE、Wi-Fi 和音频兼容性不能由单一机器规则表达，必须按模块规格人工核对。
