# 声明式兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "voltage-hw_dfrobot_sen0388_urm09_trig_k10",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "SEN0388 的3.3-5.5V供电范围与主控供电能力没有交集。",
      "params": {
        "field": "electrical.voltage",
        "leftCategories": ["SENSOR"],
        "rightCategories": ["MCU"],
        "tolerance": 0.5,
        "componentId": "hw_dfrobot_sen0388_urm09_trig_k10"
      }
    },
    {
      "id": "logic-level-hw_dfrobot_sen0388_urm09_trig_k10",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "SEN0388 的数字信号基线与主控GPIO逻辑电平不兼容。",
      "params": {
        "field": "electrical.logicLevel",
        "leftCategories": ["SENSOR"],
        "rightCategories": ["MCU"],
        "tolerance": 0.3,
        "componentId": "hw_dfrobot_sen0388_urm09_trig_k10"
      }
    },
    {
      "id": "mcu-support-hw_dfrobot_sen0388_urm09_trig_k10",
      "operator": "contains-any",
      "severity": "FAIL",
      "message": "器件未声明支持当前主控，或主控标识不是unihiker-k10。",
      "params": {
        "field": "electrical.supportedMCUs",
        "candidateField": "identifiers",
        "subjectCategories": ["SENSOR"],
        "candidateCategories": ["MCU"],
        "componentId": "hw_dfrobot_sen0388_urm09_trig_k10"
      }
    },
    {
      "id": "driver-required-hw_dfrobot_sen0388_urm09_trig_k10",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "器件声明了K10 MicroPython固件要求，但未登记ultrasonic驱动入口。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "hw_dfrobot_sen0388_urm09_trig_k10"
      }
    }
  ]
}
```

## 人工检查项

- 确认实物 SKU 是 SEN0388，接口丝印为 `-`、`+`、`D`。
- 确认 `D` 接 K10 P0 或 P1 的直连 GPIO；本包黄金示例固定使用 P1。
- 确认代码把同一引脚同时传给 `trig` 和 `echo`，而不是使用两个独立引脚。
- 确认未生成 `read_analog()`、ADC 满量程或电压比例换算代码。
- 若传感器使用 5V 外部供电，必须另外验证 `D` 引脚进入 K10 时的逻辑电平；本包默认方案不采用该接法。

