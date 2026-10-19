# 本地验证用例

```zhangwen:hardware-validation:v1
{
  "schema": "zhangwen.hardware-validation/v1",
  "cases": [
    {
      "id": "canonical-self-smoke",
      "components": ["$self"],
      "expectedOverall": ["PASS", "WARNING", "FAIL"]
    }
  ]
}
```

## 人工验收

1. 在基础版 XIAO ESP32S3 上确认目标 `ESP32_GENERIC_S3` 固件可启动，并检查 `machine.freq()`、GPIO、ADC、PWM、UART、I2C、SPI、Timer 和 WLAN 的实际可用性。
2. 用万用表和受限流电源核对 3V3 输出、USB 5 V、BAT 极性以及外部 5V 引脚输入的二极管方向；未执行前不得声称电气实测通过。
3. 验证 USER_LED 是否确为 GPIO21及其有效电平，确认官方 MicroPython 页面的 GPIO6 示例不被误用。
4. 在无线 active 和所有外设峰值负载下记录输入电压、峰值电流、复位和温升；最大峰值电流当前未知。
5. 使用掌问实际 `HardwareSkillRepository.get_skill()` 加载本包，并确认 `list_active_components()` 返回同一 componentId 与 revision；当前未执行。
6. 若需要外壳或安装设计，先取得官方 CAD 或实物测量的高度、原点、孔位、接口与禁布区，再单独增加成对的机械档案与参考模型。
