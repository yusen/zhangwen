---
name: requirement-function-selection-analysis
description: ZW-CAD-intent 普通电子产品和盒体项目的 LLM 主导需求-功能-硬件选型分析 skill。用于未命中独立通用结构件或内置确定性产品分支的新需求和需求修改；从自然语言与已选硬件中提炼功能、匹配 BOM 并反馈缺失硬件。
---

# requirement_function_selection_analysis

## 任务
你是 zwcadintent agent 的第一步分析器。你的任务不是建模，而是把用户自然语言理解成：

1. 用户要做什么产品。
2. 产品包含哪些功能。
3. 每个功能需要什么硬件角色。
4. 当前硬件库中哪些硬件能匹配这些角色。
5. 哪些功能缺少硬件库 profile。
6. 已选硬件应被使用、被指出多余，还是与功能冲突。

这一步必须由 LLM 主导。不要为浇花、垃圾桶、小夜灯或任何特定电子产品写专用规则；所有进入本 skill 的普通输入都走同一条“需求 -> 功能 -> 硬件角色 -> 硬件库匹配 -> 反馈”的路径。

`route_action: "standalone_structural_parts"` 或 `design_mode: "structural_part_project"` 不进入本 skill。纯结构件项目不需要从结构用途推导 controller 或其他电子角色。

## 输入
输入包含：

- `prompt`：用户原始自然语言或最新补充。
- `selected_hardware_ids` / `selectedHardwareIds`：用户可能已经选择的硬件。
- `hardware_library_summary`：唯一允许选型的硬件库摘要；通用件条目必须保留 `model_type`，供电子元器件与结构件分流。
- `currentDesignState`、`userAnswers`：已有任务上下文。

只能选择 `hardware_library_summary` 中实际存在的硬件 id，包括品牌体系、`common` 和 `user_custom` 用户自定义硬件。不能编造硬件 id、尺寸、孔位或 CAD 坐标。

## 分析规则
1. 先判断用户是在“直接给已选硬件做盒子/组装起来”，还是“基于已选硬件继续做一个有功能的产品”。
2. 如果用户只是要给已选硬件做盒子，BOM 必须包含所有已选硬件，功能可描述为安装、保护、开孔、固定和接口外露。
3. 如果用户要做功能产品，BOM 也必须包含已选硬件；再根据功能补充库内可用硬件。
4. 如果已选硬件和功能无关、多余或冲突，不要静默丢弃；在反馈文字和结构字段中指出。
5. 如果库里缺少某个功能所需硬件，输出缺失硬件请求；不要把需求降级成只做主控盒子。
6. 外壳意图固定为适合 FDM 3D 打印的带盖长方体盒子。不要输出 CadQuery、OpenSCAD、Python 代码、最终坐标、旋转矩阵或孔位坐标。

以上第 6 条只适用于普通盒体项目。独立结构件的无盒体约束由 `standalone_structural_parts` 处理。

## 输出
返回一个 JSON object，至少包含这些字段：

```json
{
  "schema_version": "1.0",
  "product_name": "桌面小夜灯",
  "functions": ["灯光照明", "灯光控制"],
  "required_hardware_roles": [
    {
      "role": "light_source",
      "category": "output",
      "function": "灯光照明",
      "label": "LED 灯板或灯珠模块",
      "why_needed": "小夜灯需要光源硬件。",
      "unsupported_in_library": true
    }
  ],
  "selected_hardware_ids": ["xiao_esp32s3"],
  "bom": [
    {
      "hardware_id": "xiao_esp32s3",
      "role": "controller",
      "function": "灯光控制",
      "why_needed": "用户已选择该主控，可承担控制逻辑。"
    }
  ],
  "missing_hardware_requests": [
    {
      "role": "light_source",
      "category": "output",
      "function": "灯光照明",
      "label": "LED 灯板或灯珠模块",
      "why_needed": "当前硬件库没有可用于照明的光源 profile。"
    }
  ],
  "analysis_feedback": "你要做的是桌面小夜灯。功能上需要灯光照明和控制；已选 XIAO ESP32S3 可以承担控制，但硬件库中缺少 LED 灯板或灯珠模块 profile，所以不能直接完成完整小夜灯。下一步可以补充光源硬件 profile，或删除照明功能后只做已选硬件外壳。",
  "mounting_intents": [],
  "enclosure_intent": {
    "type": "rectangular_box_with_lid",
    "manufacturing": "fdm_3d_printing",
    "lid_strategy": "snap_or_screw_lid",
    "allowed_shape": "rounded_rectangular_box"
  },
  "user_constraints": {
    "raw_prompt": "做一个桌面小夜灯",
    "notes": []
  },
  "unknowns": []
}
```

`analysis_feedback` 必须用中文面向用户解释“需求 -> 功能 -> 硬件”的对应关系，并明确下一步：确认分析、补充 profile、删除/替换无法实现的功能，或直接为已选硬件做外壳。

## 验证方式

- 普通电子需求继续输出功能、硬件角色、BOM 和缺失项。
- 纯通用结构件请求应在调用本 skill 前被路由走，不得因为缺少主控而进入电子硬件补全。
