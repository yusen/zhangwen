# 兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [{
    "id": "core-c3-driver",
    "operator": "required-if",
    "severity": "WARNING",
    "message": "本板须核对已安装的 MicroPython 固件与 UART0 REPL，不能运行出厂 Lua 固件上的 Python。",
    "params": {"requiredField": "electrical.driverName", "ifField": "electrical.firmwareRequirement", "ifPresent": true, "componentId": "hw_luatos_esp32c3_core"}
  }]
}
```

模块可加入项目不等于接线、驱动或功能已验证；本板没有新增模块实测认证。电源容量与瞬态负载未知。
