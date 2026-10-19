# 本地验证用例

```zhangwen:hardware-validation:v1
{
  "schema": "zhangwen.hardware-validation/v1",
  "cases": [
    {
      "id": "canonical-self-smoke",
      "components": ["$self"],
      "expectedOverall": ["PASS", "WARNING"]
    }
  ]
}
```

## 自动/静态验收

1. `componentId` 为 `hw_dfrobot_sen0388_urm09_trig_k10`，且在硬件库中唯一。
2. 正向接线和代码方案不得采用 SEN0307 的 `read_analog`、ADC 换算或 `communicationProtocol: ANALOG`；型号对比和禁止项中的文字说明允许保留。
3. 示例必须能通过 Python 语法检查，并使用 `ultrasonic(trig=1, echo=1)`。
4. manifest revision、机械模型 SHA 和声明文件集合必须一致。
5. 应用组件投影中能查询到 SEN0388，且不产生旧 SEN0307 活跃项。

## 实物验收

1. 断电核对 P1 的 3.3V/GND/Signal 后再上电。
2. 用平整挡板在 30cm、50cm、100cm 处各采集至少 20 次，记录均值、极差和异常值。
3. 连续采样间隔先使用 100ms；再测试接近 40ms 时是否稳定。
4. 在装入外壳后重复测距，确认双探头无遮挡且没有明显多径反射。
5. 用卡尺或 DFRobot 正式尺寸图复核 PCB、探头、接线座和安装孔；参考孔径 3mm、孔中心距相邻边 2.4mm 不得直接视为 SEN0388 官方尺寸。
6. 记录 K10 固件、MindPlus/K10 扩展和实物 SKU 后，才能把代码状态提升为实机验证。
