---
name: profile-check
description: 检查 ZW-CAD-intent 普通电子项目 BOM 的尺寸、坐标、固定、开孔、避让和参考模型字段。独立通用结构件项目不调用本通用检查，而由 standalone_structural_parts 校验可信 CadQuery 母版。
---

# profile_check

## 用途

检查 BOM 中硬件 profile 是否包含尺寸、坐标系、固定方式、开孔、避让和参考模型信息。

## 何时调用

- `function_verify` 通过后。
- 用户补充或替换硬件 profile 后。
- `design_mode: "structural_part_project"` 时跳过本步骤；不得要求结构件补齐盒体安装面或电子开孔字段。

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

独立结构件缺少有效 `cadquery_model` 时由专用流程返回 `structural_model_template_unavailable`，不能退回包围盒代理。

## 验证方式

- 普通电子项目保持原有 profile 完整性检查。
- 独立结构件项目不得因缺少盒体安装字段而在此阻断，且必须在专用流程中完成母版静态校验。
