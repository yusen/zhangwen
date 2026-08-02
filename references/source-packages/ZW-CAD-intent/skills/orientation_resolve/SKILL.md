---
name: orientation-resolve
description: 为 ZW-CAD-intent 普通盒体项目确定硬件安装面、交互面和旋转。独立通用结构件项目跳过本步骤，其 15 mm 并排位置只用于预览，不表示安装姿态。
---

# orientation_resolve

## 用途

确定硬件安装面、交互面和旋转覆盖，将 profile 和 intent 转成可布局的硬件姿态。

## 何时调用

- `profile_check` 通过后。
- 用户通过 GUI 或对话修改安装面、朝向、旋转时。
- `design_mode: "structural_part_project"` 时跳过本步骤，不生成 `mounting_plan` 或电子硬件安装姿态。

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

## 验证方式

- 普通盒体项目继续输出可布局姿态。
- 独立结构件项目不得把并排预览平移写成安装朝向或装配关系。
