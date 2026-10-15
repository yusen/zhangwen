# 本地验证用例

```zhangwen:hardware-validation:v1
{
  "schema": "zhangwen.hardware-validation/v1",
  "cases": [
    {
      "id": "canonical-self-smoke",
      "components": [
        "$self"
      ],
      "expectedOverall": [
        "PASS",
        "WARNING",
        "FAIL"
      ]
    }
  ]
}
```

## 人工验收

1. 使用万用表确认 USB 供电时 3V3 金手指电压，并确认 GPIO 只承受 3.3V 逻辑。
2. 在当前官方固件验证 `from mpython import *`、LCD、光线、六轴、按键和低亮度 RGB 最小示例。
3. 扫描 P19/P20 I2C 总线，记录板载地址，再接入外设验证地址和上拉不冲突。
4. 用卡尺复核 51.8×47.39×7.65mm 包络；孔位和外壳开孔仍待实物建模。
