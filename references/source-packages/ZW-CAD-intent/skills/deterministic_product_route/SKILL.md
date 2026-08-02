---
name: deterministic-product-route
description: ZW-CAD-intent 内置确定性产品路由说明。用于在通用 LLM 意图分析和通用 BOM/布局流程之前识别固定产品模板。
---

# deterministic_product_route

## 用途

本 skill 说明内置确定性产品的优先级。它不直接生成 CAD，不直接写坐标；实际建模由后端模板库完成。

## 触发条件

- 用户提出智能浇花、自动浇花、植物照看、植物看护、植物浇水、植物养护、自动灌溉、plant watering、plant care 等需求。
- 用户提出相册、电子相册、数码相册、数字相框、照片相框、智能相册、photo album、digital photo frame、smart photo frame 等需求。
- 未指定硬件体系时默认进入行空板版本。
- 明确指定 XIAO 或掌控板时进入对应占位分支，不回落到通用流程。

## 输出

- 行空板版本命中 `unihiker_plant_caregiver` 时，首轮调用后台模板 `unihiker_smart_watering_system_v1` 返回普通盒体流程的 `confirmation` 草案：固定 BOM、固定硬件坐标、盒体参数和 `layout_scene` 2D 预览；不返回 CadQuery 源码或真实导出。用户确认后才进入 artifact/build 阶段，生成 CadQuery、STEP/STL 和 workflow 产物。
- 行空板相册命中 `unihiker_photo_album` 时，调用后台模板 `unihiker_photo_album_v1`，返回第一阶段 artifact、固定 BOM（`unihiker_k10` + `unihiker_polymer_lipo_battery`）、design_state 和 CadQuery 代码，不进入通用流程。
- XIAO/掌控板版本暂时只返回占位响应，说明该内置模型尚未实现。

## 限制边界

## 批量小模型模板案例

以下四个模板来自 `server/template-library/batch-models/` 的只读 CadQuery 母版，并通过 `template_parts_v1` 契约接入：

- `unihiker_light_effect_cup_v1`：光效水杯；一个可打印主体，K10、聚合物锂电池和 RGB12 灯环为参考件。
- `unihiker_handheld_fan_v1`：手持小风扇；一个可打印主体，K10、电池和直流电机风扇为参考件。
- `mpython_board_enclosure_v1`：掌控板外壳；底壳和上盖两个可打印件，匹配 `mpython_board_3_0`。
- `unihiker_auto_open_lid_box_v1`：自动感应开盖智能盒子；底盒和上盖两个可打印件，K10、IO 扩展板、舵机、超声波和舵机臂为参考件。

命中这些案例时，后端跳过通用 LLM 意图、BOM 和布局推导，直接返回案例 artifact。源码先复制到当前项目 `exports/<task>/project`，后续修改只作用于项目副本；公共母版保持不变。整体场景只用于 2D/3D 关系预览，必须标记 `printable: false`，不能作为可打印零件列入 STL 清单。每个 `template_parts[].printable` 为真的条目必须各自生成 STEP/STL；参考件只能作为 `reference_only` 导出。

模板适配层必须保留源脚本的真实几何，不得使用电子板包围盒或空的 `base_part`/`lid_part` 伪造模型。缺少所需硬件 profile 或模板部件契约不完整时，返回明确 `needs_input`/构建失败，不回退普通盒体流程。

- 不允许 LLM 为内置模板临时编写 CAD 坐标或替换后台模板。
- 模板使用的硬件必须来自硬件库 profile；缺失 profile 时必须阻断并列出缺失项。
- 智能浇花草案的 BOM、安装面、旋转和硬件坐标由模板常量重新生成，客户端不能通过修改草稿替换布局；允许调整的只有盒体尺寸参数。
- 模板库独立于硬件库，不作为用户可选硬件展示。

## 验证方式

- 命中行空板植物养护系统时不调用 LLM 意图分析，但首轮仍要经过普通盒体的 2D 参数确认。
- 确认草案必须包含电池盒、继电器、SCI、K10、K10 IO 扩展板、土壤湿度传感器和直流水泵，并带 `layout_scene`。
- 确认草案不应包含 `cadquery_code` 或真实导出；确认构建后的代码必须包含模板标识、主体盒子、SCI 上盖外置、K10/扩展板右侧外置和水泵右侧电源线通道。
