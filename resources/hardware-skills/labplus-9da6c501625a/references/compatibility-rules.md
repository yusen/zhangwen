# 兼容性边界

旧版格式要求范围算子，未知参数仅作保守警告；Web 检查将此包排除数值比较，并单独提示未核实。不得将0占位当电气事实。

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "labplus-9da6c501625a-driver",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "MicroPython 驱动与固件尚未核实。",
      "params": {
        "componentId": "hw_labplus_9da6c501625a",
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true
      }
    },
    {
      "id": "labplus-9da6c501625a-supply",
      "operator": "range-overlap",
      "severity": "WARNING",
      "message": "电气参数未知，须核对官方资料。",
      "params": {
        "componentId": "hw_labplus_9da6c501625a",
        "field": "electrical.voltage",
        "leftCategories": [
          "DISPLAY"
        ],
        "rightCategories": [
          "MCU"
        ],
        "tolerance": 0
      }
    },
    {
      "id": "labplus-9da6c501625a-logic",
      "operator": "range-overlap",
      "severity": "WARNING",
      "message": "电气参数未知，须核对官方资料。",
      "params": {
        "componentId": "hw_labplus_9da6c501625a",
        "field": "electrical.logicLevel",
        "leftCategories": [
          "DISPLAY"
        ],
        "rightCategories": [
          "MCU"
        ],
        "tolerance": 0
      }
    }
  ]
}
```
