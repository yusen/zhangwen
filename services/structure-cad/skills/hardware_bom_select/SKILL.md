# hardware_bom_select

## 用途

只从 `ZW-CAD-intent` 硬件库选择 BOM。不能编造硬件，库里没有的功能必须转成缺失硬件请求。

本步骤必须接收 `requirement_function_selection_analysis` / `intent_analyze` 已经拆出的功能和硬件角色。不能因为库里缺硬件，就把复杂需求降级成只做主控盒子。

## 何时调用

- `intent_analyze` 成功后。
- 用户添加、删除、替换功能或硬件时。
- `function_verify` 指出 BOM 无法覆盖需求时，最多重新尝试到工作流限制。

## 输入格式

```json
{
  "intent": {},
  "selectedHardwareIds": ["xiao_esp32s3"],
  "customHardwareProfiles": []
}
```

## 输出格式

```json
{
  "status": "ok",
  "bom": [
    {
      "hardware_id": "xiao_esp32s3",
      "name": "Seeed Studio XIAO ESP32S3",
      "role": "controller",
      "why_needed": "用户需要 ESP32 主控。"
    }
  ],
  "missing_hardware_requests": [],
  "warnings": []
}
```

## 失败状态

- `needs_input`：硬件库没有能覆盖某个功能的硬件。
- 失败文案必须说明“哪个功能缺少哪个硬件”，并给用户补 profile 或删减功能的选择。
