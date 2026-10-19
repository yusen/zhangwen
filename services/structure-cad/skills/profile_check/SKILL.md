# profile_check

## 用途

检查 BOM 中硬件 profile 是否包含尺寸、坐标系、固定方式、开孔、避让和参考模型信息。

## 何时调用

- `function_verify` 通过后。
- 用户补充或替换硬件 profile 后。

## 输入格式

```json
{
  "bom": [],
  "customHardwareProfiles": []
}
```

## 输出格式

```json
{
  "status": "ok",
  "hardware_profiles": [],
  "profile_validation_report": {
    "status": "pass",
    "checked_count": 1,
    "profiles": []
  },
  "warnings": []
}
```

## 失败状态

- `needs_input`：缺少必要 profile 字段，必须要求用户补充或换用库内完整硬件。

