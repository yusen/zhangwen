# orientation_resolve

## 用途

确定硬件安装面、交互面和旋转覆盖，将 profile 和 intent 转成可布局的硬件姿态。

## 何时调用

- `profile_check` 通过后。
- 用户通过 GUI 或对话修改安装面、朝向、旋转时。

## 输入格式

```json
{
  "mounting_intents": [],
  "hardware_profiles": [],
  "hardwareFaceOverrides": {},
  "hardwareRotationOverrides": {}
}
```

## 输出格式

```json
{
  "status": "ok",
  "mounting_plan": [],
  "oriented_hardware_specs": []
}
```

## 失败状态

本步骤应尽量给出确定性结果；无法解析时应返回 `needs_input`，要求用户指定硬件和目标安装面。

