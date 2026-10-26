# 兼容性边界

旧版格式要求范围算子，未知参数仅作保守警告；Web 检查将此包排除数值比较，并单独提示未核实。不得将0占位当电气事实。

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "nplus-2ad6a9f375bf-driver",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "MicroPython 驱动与固件尚未核实。",
      "params": {
        "componentId": "hw_nplus_2ad6a9f375bf",
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true
      }
    },
    {
      "id": "nplus-2ad6a9f375bf-supply",
      "operator": "range-overlap",
      "severity": "WARNING",
      "message": "电气参数未知，须核对官方资料。",
      "params": {
        "componentId": "hw_nplus_2ad6a9f375bf",
        "field": "electrical.voltage",
        "leftCategories": [
          "ACTUATOR"
        ],
        "rightCategories": [
          "MCU"
        ],
        "tolerance": 0
      }
    },
    {
      "id": "nplus-2ad6a9f375bf-logic",
      "operator": "range-overlap",
      "severity": "WARNING",
      "message": "电气参数未知，须核对官方资料。",
      "params": {
        "componentId": "hw_nplus_2ad6a9f375bf",
        "field": "electrical.logicLevel",
        "leftCategories": [
          "ACTUATOR"
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
