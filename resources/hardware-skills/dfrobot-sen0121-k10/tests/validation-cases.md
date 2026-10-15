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

1. 对照官方资料和实物丝印核对供电、信号电平、地址/波特率、线序及峰值电流。
2. 在 K10 当前 MicroPython 固件上完成导入、初始化、最小读取/动作和连续运行测试；本批次未执行。
