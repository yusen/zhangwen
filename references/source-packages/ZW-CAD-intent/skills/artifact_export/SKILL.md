---
name: artifact-export
description: 把 ZW-CAD-intent 的设计状态、项目源码、workflow 记录和导出清单写入当前任务目录。用于普通盒体，也用于保存 structural_parts_v1 项目的结构件场景、可打印零件和项目源码副本。
---

# artifact_export

## 用途

写入当前任务目录，生成 2D/调试预览资产、metadata、`artifact.json`、`design-state.json`、`checks.json` 和 8 个 workflow 产物。

## 何时调用

- 所有预建模校验通过后。
- 普通盒体确认草案阶段只生成内存中的 2D `layout_scene`，不调用本 skill 写入 CadQuery 源码或 STL/STEP 导出；用户确认后才进入 artifact 导出。
- 同一任务重生成时，复用当前 `ZW-PRODUCT-*` 目录并覆盖受管产物。
- 独立结构件参数确认后，保存结构件 artifact 和 `project/structural-parts.cq.py`。

## 输入格式

```json
{
  "prepared": {},
  "taskId": "ZW-PRODUCT-20260623-120000"
}
```

批量小模型案例的 artifact 还必须携带：

- `design_mode: "template_case"`、`model_contract: "template_parts_v1"` 和 `template_id`；
- `template_source`（文件名、源文件 SHA-256 和期望哈希）；
- `printable_parts`（只列真实可打印部件，并通过 `source_export_id` 关联独立 STL）；
- `preview_assets[].scene_kind: "template_case"`（整体关系预览，可包含参考件，但整体场景不可打印）。

首轮模板 artifact 先将原始案例源码复制到当前项目 `project` 目录。后续编辑、暂存、确认和撤销只能更新该副本；公共 `server/template-library/batch-models` 母版保持不变。水杯、风扇等单主体案例不能为了兼容普通导出而制造空上盖或重复主体。

独立结构件 artifact 必须包含：

- `design_mode: "structural_part_project"` 和 `schema_version: "structural_parts_v1"`。
- `structural_scene.parts`：按 15 mm 间距并排的预览场景。
- `printable_parts`：每个结构件一个可打印条目，不包含整体预览。
- `function_verification_report.verification_status: "skipped_structural_part_project"`。
- `project_source_hash`、项目 manifest、修订号和模型索引。
- 整体预览的 pending 导出项和每个结构件的独立 STEP/STL pending 导出项。

首次建立项目时必须把可信母版组合源码复制到当前项目目录。后续重生成、模型修改和撤销只更新项目副本及其修订，公共母版保持只读。

受管项目按最近活动时间保留三份；正在执行的项目临时保护。旧项目首次启用清理策略时必须遵守存储层的审计和确认要求。

## 输出格式

```json
{
  "status": "artifact",
  "design_state": {},
  "exports": [],
  "checks": []
}
```

## 失败状态

导出文件写入失败不应阻断主体 artifact，但必须写入 warning 和 failed export entry。

项目源码副本、`project.json` 或 artifact 核心元数据写入失败属于项目建立失败，不能报告为可编辑项目成功。

## 验证方式

- 检查结构件 artifact 没有 enclosure、base、lid 或 controller 数据。
- 检查整体预览导出不可打印，`printable_parts` 与逐件 STEP/STL 导出一一对应。
- 检查项目源码位于当前任务的 `project/` 下，公共母版内容和哈希未改变。
