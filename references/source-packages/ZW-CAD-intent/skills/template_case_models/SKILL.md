---
name: template-case-models
description: 处理来自批量小模型的确定性 CadQuery 案例模板，区分可打印部件、硬件参考件和整体预览场景。
---

# 模板案例模型

## 适用范围

仅用于 `server/template-library/batch-models/` 中已经通过静态安全检查的案例。当前包括光效水杯、手持小风扇、掌控板外壳和行空板自动感应开盖智能盒子。模板源码是公共只读母版，项目建立后必须复制到当前任务的 `exports/<task>/project`。

## 契约

模板适配后的 CQ-editor 源码必须声明：

```python
TEMPLATE_PARTS_SCHEMA_VERSION = "template_parts_v1"
template_parts = [{"id": "...", "object": result, "printable": True}]
template_reference_parts = []
template_scene = result
```

`template_parts` 中 `printable: true` 的对象分别导出 STEP/STL；`template_reference_parts` 只用于硬件或装配关系检查；`template_scene` 只用于整体预览，必须标记为不可打印。不能用 `base_part`、`lid_part` 或电子板包围盒代理替代缺失的案例部件。

## 路由和验证

- 案例名称带有明确限定词时，在通用 LLM 意图分析前命中对应 `template_id`。
- 固定 BOM 必须逐项来自硬件库 profile；缺 profile 时明确阻断。
- 源文件 SHA-256 必须与导入记录一致，项目副本可修改但公共母版不变。
- 建模前执行 Python AST/静态安全预检；构建后仅对可打印模板部件执行 mesh 校验。
- 整体场景和参考件不进入 STL 打印清单，也不生成普通盒体的底壳/上盖/硬件伪导出。

## 输出

artifact 应包含 `design_mode: "template_case"`、`model_contract: "template_parts_v1"`、`template_source`、`printable_parts` 和 `scene_kind: "template_case"` 的 2D `layout_scene`。模板部件单项预览、整体关系预览和项目源码下载都必须可追溯到同一个任务目录。

