---
name: design-validate
description: 对 ZW-CAD-intent 的设计执行确定性校验。用于普通盒体的干涉、壁厚、固定和开孔检查，也用于纯通用结构件项目的母版、structural_parts_v1、预览间距、逐件构建和 mesh 检查。
---

# design_validate

## 用途

执行确定性规则校验，包括硬件干涉、壳体内腔、固定结构、开孔对齐、壁厚、打印可行性和 CadQuery 静态检查。

## 何时调用

- `layout_solve` 和 `cadquery_generate` 后。
- 用户通过 GUI 或对话修改参数后。
- 独立结构件场景和组合源码生成后；该模式不要求盒体 layout。

## 输入格式

```json
{
  "enclosure": {},
  "layout_plan": {},
  "parameters": {},
  "cadquery_code": ""
}
```

独立结构件模式输入：

```json
{
  "design_mode": "structural_part_project",
  "structural_scene": {
    "schema_version": "structural_parts_v1",
    "gap_mm": 15,
    "parts": []
  },
  "hardware_profiles": [],
  "cadquery_code": ""
}
```

## 独立结构件校验

- 检查所有 profile 都属于 `common` 且 `model_type` 为 `structural_part`。
- 检查每个 `cadquery_model` 的受信任路径、AST、入口对象和禁用 API。
- 检查源码满足 `structural_parts_v1` 且每个条目保留独立对象。
- 检查预览间距不小于 15 mm、位置用途为 `preview_only`、没有伪造装配关系。
- 明确记录 controller 独立性和盒体生成已跳过；不运行盒体内腔、壳壁、上盖、底壳、安装面或开孔对齐检查。
- CadQuery 可用时逐件真实构建并导出后检查 mesh；不可用时标记 pending，不伪造通过。

## 输出格式

```json
{
  "status": "ok",
  "checks": [],
  "warnings": [],
  "validation_context": {}
}
```

## 失败状态

- `needs_input`：存在阻断性 `fail` 检查。反馈必须说明失败项、建议动作和可选按钮。

母版不可用时返回 `structural_model_template_unavailable`。任何结构件构建失败都必须阻断对应真实导出，不能用包围盒代理替代。

## 验证方式

- 单件和多件结构件场景应通过母版、schema、间距和独立对象检查。
- `enclosure_checks` 与 `electronic_function_checks` 应明确标记为 `skipped`。
- 每个独立 STL 都应有 mesh 结果；整体场景结果不能替代逐件结果。
