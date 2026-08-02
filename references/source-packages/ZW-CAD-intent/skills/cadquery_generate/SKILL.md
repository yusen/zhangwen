---
name: cadquery-generate
description: 由 ZW-CAD-intent 后端确定性生成 CadQuery 源码。用于普通带盖盒体，也用于把通过校验的通用结构件母版组合成 structural_parts_v1 多对象项目源码。
---

# cadquery_generate

## 用途

由后端确定性程序生成 CadQuery 建模代码。LLM 不直接写 CadQuery 代码。

## 何时调用

- `layout_solve` 后。
- 影响结构、开孔、固定方式、盒体参数的步骤被重跑后。
- 独立结构件 profile 和可信母版通过校验后；该模式跳过 `layout_solve`，直接根据结构件场景生成多对象源码。

## 输入格式

```json
{
  "enclosure": {},
  "layout_plan": {},
  "bom": [],
  "hardware_profiles": [],
  "parameters": {}
}
```

独立结构件模式输入至少包含：

```json
{
  "design_mode": "structural_part_project",
  "structural_scene": {
    "schema_version": "structural_parts_v1",
    "gap_mm": 15,
    "parts": []
  },
  "hardware_profiles": []
}
```

## 输出格式

```json
{
  "status": "ok",
  "cadquery_code": "string",
  "cad_parameters": {}
}
```

独立结构件源码必须定义 `STRUCTURAL_PARTS_SCHEMA_VERSION = "structural_parts_v1"` 和非空 `structural_parts` 列表。每个条目包含稳定 `id`、名称、独立 CadQuery `object`、`placement_mm` 和 `size_mm`。预览位移只在 `show_object` 场景中应用，独立可打印对象保持自身坐标。

## 限制边界

批量小模型模板使用 `template_parts_v1`，不重新推导盒体参数：适配器只声明源脚本已经存在的 `template_parts`、`template_reference_parts` 和 `template_scene`。整体场景是预览关系，单个可打印对象必须保留自身坐标并可独立导出；不得为了复用普通盒体契约添加空底壳或上盖。

- 普通盒体源码继续由盒体参数和确定性布局生成。
- 独立结构件源码只组合已通过校验的 `common` 结构母版，不读取 custom profile，不从自然语言临时写任意几何。
- 多结构件沿 X 轴按 15 mm 间距并排，只表示预览，不写入装配关系。
- 不能生成 base、lid、hardware 代理来冒充结构件产物。

## 失败状态

如果无法生成安全代码，应返回 `needs_input` 或 validation fail，不能把用户输入当成代码执行。

结构件缺少有效母版时返回 `structural_model_template_unavailable`，不得退回包围盒代理。

## 验证方式

- 对普通盒体运行原有源码静态契约。
- 对结构件项目检查 `structural_parts_v1`、非空对象列表、稳定 ID、独立对象和只用于预览的位移。
- 检查组合源码没有越界文件访问、动态执行或未受信任导入。
