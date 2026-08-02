---
name: hardware-bom-select
description: 从 ZW-CAD-intent 硬件库选择受约束 BOM。用于普通电子项目的功能选型，以及纯通用结构件项目中只保留 model_type 为 structural_part 的现有母版且禁止自动补主控。
---

# hardware_bom_select

## 用途

只从 `ZW-CAD-intent` 硬件库选择 BOM。不能编造硬件，库里没有的功能必须转成缺失硬件请求。

本步骤必须接收 `requirement_function_selection_analysis` / `intent_analyze` 已经拆出的功能和硬件角色。不能因为库里缺硬件，就把复杂需求降级成只做主控盒子。

## 何时调用

- `intent_analyze` 成功后。
- 用户添加、删除、替换功能或硬件时。
- `function_verify` 指出 BOM 无法覆盖需求时，最多重新尝试到工作流限制。
- `intent.design_mode` 为 `structural_part_project` 时，用于建立结构件清单，不执行电子功能选型。

## 输入格式

```json
{
  "intent": {},
  "selectedHardwareIds": ["xiao_esp32s3"],
  "customHardwareProfiles": []
}
```

独立结构件项目输出示例：

```json
{
  "status": "ok",
  "design_mode": "structural_part_project",
  "hardware_system": "common",
  "bom": [
    {
      "hardware_id": "battery_18650_holder",
      "name": "18650 电池座",
      "role": "structural_part",
      "roles": ["battery", "power"],
      "model_type": "structural_part",
      "hardware_system": "common",
      "quantity": 1,
      "why_needed": "用户选择了该通用结构件作为独立建模对象。"
    }
  ],
  "missing_hardware_requests": [],
  "warnings": []
}
```

## 独立结构件规则

- 只接受 `hardware_system: "common"` 且 `model_type: "structural_part"` 的现有 profile。
- 每个选中的 profile 首版数量固定为 1；同一 profile 不推导重复数量。
- BOM 的主角色设为 `structural_part`，但必须保留 profile 原有 `category` 和 `roles` 语义。不能把 18650 电池座的 `power` / `battery` 信息从硬件库删除。
- 不加入 controller，不运行默认 XIAO fallback，不执行品牌主控补全，也不把结构件当成 enclosure role 过滤掉。
- 不接受 custom profile、电子元器件、品牌专属硬件或不存在的 ID。混合需求应退出独立结构件模式，交回普通流程处理。
- `model_type` 是正交分类标签，不能用 `category` 替代。兼容旧数据的兜底判断只属于后端迁移逻辑，不应产生新的无标签条目。

## 输出格式

命中批量小模型模板时，BOM 由模板定义固定提供，不执行通用角色补全。模板案例的 `model_contract` 为 `template_parts_v1`，BOM 只列案例源码对应的硬件，硬件摆放和数量以模板为准；这类模板不因普通规则自动增加 XIAO、掌控板或其他主控。

```json
{
  "status": "ok",
  "bom": [
    {
      "hardware_id": "xiao_esp32s3",
      "name": "Seeed Studio XIAO ESP32S3",
      "role": "controller",
      "why_needed": "用户需要 ESP32 主控。"
    }
  ],
  "missing_hardware_requests": [],
  "warnings": []
}
```

## 失败状态

- `needs_input`：硬件库没有能覆盖某个功能的硬件。
- 失败文案必须说明“哪个功能缺少哪个硬件”，并给用户补 profile 或删减功能的选择。
- 独立结构件选择为空时返回 `structural_part_selection_required`；包含非通用结构件时返回 `invalid_structural_part_selection`。
- 结构件没有有效 `cadquery_model` 时由独立结构件流程返回 `structural_model_template_unavailable`，不得把 BOM 包围盒当成可打印模型。

## 验证方式

- 纯结构件 BOM 中不得出现 controller 或 XIAO fallback。
- 电子元器件项目仍按原规则补足主控和功能硬件。
- 普通 `structural_part` 角色不得被 `isEnclosureHardwareRole` 当作外壳角色过滤。
