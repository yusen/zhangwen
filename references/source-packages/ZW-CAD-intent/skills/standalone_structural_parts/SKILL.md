---
name: standalone-structural-parts
description: 生成不依赖主控、不包含盒体的 ZW-CAD-intent 通用结构件项目。用于用户只选择 common 中 model_type 为 structural_part 的条目，或明确点名机器狗身体、大腿、小腿、18650 电池座等现有通用结构件且未要求外壳时；负责母版校验、并排预览、项目源码副本、逐件 STEP/STL 导出和失败阻断。
---

# standalone_structural_parts

## 用途

从通用件库的现有 CadQuery 母版建立纯结构件项目。该流程面向“用户手头已有电子元器件，只需要一个或若干结构件”的场景，不要求主控，不生成带盖长方体盒子，也不推导电子装配关系。

## 触发条件

满足以下任一条件，并且用户没有要求盒子、盒体、外壳、壳体、保护壳或机箱时触发：

- 所有已选条目都属于 `hardware_system: "common"`，且 `model_type: "structural_part"`。
- 用户在自然语言中明确点名一个或多个通用结构件。
- 调用方显式传入 `route_action: "standalone_structural_parts"` 或 `design_mode: "structural_part_project"`。

存在盒体词时普通盒体流程优先。结构件与电子元器件混选时不触发；显式路由但没有识别到具体结构件时返回选择阻断。

## 输入格式

```json
{
  "prompt": "做一个机器狗大腿和小腿",
  "latestUserMessage": "做一个机器狗大腿和小腿",
  "selectedHardwareIds": ["quadruped_dog_thigh", "quadruped_dog_shin"],
  "routeAction": "standalone_structural_parts",
  "designMode": "structural_part_project",
  "taskId": "ZW-PRODUCT-20260717-120000",
  "currentDesignState": null
}
```

## 输出格式

确认阶段返回 `status: "confirmation"`；用户确认构建后返回 `status: "artifact"`。核心字段如下：

```json
{
  "status": "artifact",
  "design_mode": "structural_part_project",
  "schema_version": "structural_parts_v1",
  "source": "deterministic_structural_parts",
  "bom": [],
  "design_state": {
    "hardware_system": "common",
    "enclosure_parameters": null,
    "structural_parts": [],
    "printable_parts": [],
    "project_source_hash": "SHA-256"
  },
  "structural_scene": {
    "schema_version": "structural_parts_v1",
    "gap_mm": 15,
    "arrangement": "x_axis_side_by_side_preview",
    "assembly_relationship": "none_inferred",
    "parts": []
  },
  "exports": [],
  "checks": [],
  "warnings": []
}
```

## 执行流程

1. 解析已选 ID 和已知别名，得到去重后的结构件 profile 列表。
2. 确认每个 profile 都属于 `common` 且 `model_type` 为 `structural_part`。
3. 读取 `cadquery_model` 指向的可信母版，执行路径、Python AST、入口对象和禁用 API 静态检查。
4. 每个 profile 取一件，沿 X 轴按 15 mm 间距并排；保存 `placement_purpose: "preview_only"`，不推断机械连接。
5. 生成 `structural_parts_v1` CadQuery 项目源码。每个条目保留独立对象，整体场景只用于预览。
6. 首次构建时把组合源码写入 `exports/<task>/project/structural-parts.cq.py`，建立 `project.json`、源码哈希、模型索引、项目记忆和修订目录。
7. 由受控 CadQuery 构建器导出整体预览 STEP/STL、每个结构件的独立 STEP/STL、结构件 manifest 和 mesh 检查。

## 项目副本与修改

- 公共硬件库和 `server/data/hardware-models/` 母版始终只读。首次项目源码由可信母版复制、组合后，后续修改只作用于当前 `project/structural-parts.cq.py`。
- 自然语言修改继续复用 `model_edit`：计划必须绑定当前源码 SHA-256，先暂存并构建；改变实体、孔槽、壁厚、圆角、倒角或结构关系的修改必须确认后提交。
- 提交、撤销和失败恢复必须生成项目修订并保持 artifact、预览与源码一致。不得用修改后的项目副本反向覆盖公共母版。
- 受管项目按最近活动时间保留三份；正在执行的项目临时受保护。旧项目首次纳入保留策略时，按项目存储的审计与确认规则处理。

## 导出边界

- `cadquery_structural_scene_step` 和 `cadquery_structural_scene_stl` 是并排整体预览，必须设置 `printable: false`、`scene_only: true`，不得出现在可打印零件清单中。
- 每个结构件分别输出 `cadquery_structural_<id>_step` 和 `cadquery_structural_<id>_stl`，并设置 `printable_part_id`。
- `printable_parts` 每个条目数量固定为 1。首版不支持同一 profile 的重复数量，也不推导真实装配关系。
- 本流程只使用现有通用件母版，不从零生成任意自然语言结构，不接受 custom profile。

## 失败状态

- `structural_part_selection_required`：没有识别到具体结构件。
- `invalid_structural_part_selection`：包含电子元器件、品牌专属硬件、不存在的 ID 或非结构件条目。
- `structural_model_template_unavailable`：母版缺失、路径越界、源码不安全、入口对象无效或静态检查失败。必须阻断，不能退回包围盒代理。
- CadQuery/OCP 缺失时保留项目源码，并把真实 STEP/STL 标记为 pending；不得把调试预览冒充真实模型。

## 验证方式

- 单选、多选、自然语言点名都应生成 `design_mode: "structural_part_project"`，BOM 中没有 controller 或 XIAO fallback。
- 包含“盒子/外壳”的相同请求应退出本流程。
- 检查 `enclosure_parameters` 为 `null`，电子功能验证为 `skipped_structural_part_project`。
- 检查每个母版通过静态验证，组合源码满足 `structural_parts_v1`，每个条目都能真实构建并独立导出 STEP/STL。
- 检查整体预览间距为 15 mm 且不可打印；逐件 STL 分别通过 mesh 校验。
- 修改项目副本后，公共母版哈希保持不变；确认、撤销和失败恢复继续遵守项目修订契约。
