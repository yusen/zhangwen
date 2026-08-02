---
name: box-feasibility-check
description: 为 ZW-CAD-intent 普通盒体项目计算外壳尺寸并检查安装面容量。独立通用结构件项目无盒体，必须跳过本步骤并保持 enclosure_parameters 为 null。
---

# box_feasibility_check

## 用途

计算盒体尺寸，检查当前安装面容量是否能容纳硬件和交互开孔。

## 何时调用

- `orientation_resolve` 成功后。
- 用户调整盒体尺寸、边距、硬件间距或安装面后。
- `design_mode: "structural_part_project"` 时跳过本步骤，不创建默认盒体或为满足旧契约伪造 enclosure。

## 输入格式

```json
{
  "oriented_hardware_specs": [],
  "parameters": {},
  "user_constraints": {}
}
```

## 输出格式

```json
{
  "status": "ok",
  "enclosure": {},
  "capacity": {}
}
```

## 失败状态

- `needs_input`：盒体尺寸受用户约束，无法自动增大到可用尺寸。

## 验证方式

- 普通盒体项目继续检查面容量和自动增大策略。
- 独立结构件项目的 `enclosure_parameters` 应为 `null`，不得出现底壳、上盖或盒体容量结果。
