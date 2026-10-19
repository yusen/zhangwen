# 声明式兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "driver-required-hw-see-xiao-esp32s3",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "主控有固件要求，但未登记 MicroPython 驱动入口。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "hw_seeed_xiao_esp32s3"
      }
    }
  ]
}
```

## 人工检查项

- 外设供电必须匹配 3.3 V 或条件成立时的 5 V/VBUS 轨；所有 GPIO 信号必须与 3.3 V 逻辑兼容。
- I2C 地址、上拉电阻、SPI 模式、UART 电平和带宽取决于所接外设，需在组合方案中核对。
- 峰值电流未知，不能仅凭机器字段完成电源预算；必须按外设和无线工作模式人工核算。
- 使用 BAT 输入或 5V 引脚反向供电前，核对极性、充电路径和官方二极管要求。
