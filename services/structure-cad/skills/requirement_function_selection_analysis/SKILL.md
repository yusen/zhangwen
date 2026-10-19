---
name: requirement-function-selection-analysis
description: ZW-CAD-intent 上层需求-功能-选型分析流程。用于复杂产品需求先拆解功能、推导硬件角色、匹配硬件库，并决定是否继续建模或向用户反馈缺失硬件。
---

# requirement_function_selection_analysis

## 用途

这是 `ZW-CAD-intent` 的上层需求-功能-选型分析 skill。它指导 agent 先理解用户要做的产品，再拆成功能，再推导每个功能需要的硬件角色，最后与硬件库匹配，决定能否继续建模。

本 skill 不直接生成 CAD、不直接决定最终布局，也不替代 `intent_analyze`、`hardware_bom_select`、`function_verify`。它是这些步骤的编排说明。

## 必须执行的分析链路

1. 读取用户原始需求和当前任务上下文。
2. 把需求拆成具体功能，例如显示、按键输入、声音提醒、土壤湿度检测、出水控制。
3. 为每个功能推导所需硬件角色，例如 `display`、`button`、`buzzer`、`soil_moisture_sensor`、`water_pump`。
4. 用硬件库匹配每个硬件角色。
5. 将结果分成：
   - 可实现功能
   - 不可实现功能
   - 已匹配硬件
   - 缺失硬件 profile
6. 如果存在不可实现功能，必须先反馈用户，不能把方案简化成只做主控盒子继续建模。

## 输入格式

```json
{
  "prompt": "做一个智能浇花系统",
  "selectedHardwareIds": [],
  "hardware_library_summary": [],
  "currentDesignState": null,
  "userAnswers": []
}
```

## 输出格式

```json
{
  "status": "needs_input",
  "product_name": "智能浇花系统",
  "functions": [
    {
      "name": "土壤湿度检测",
      "required_role": "soil_moisture_sensor",
      "library_status": "missing"
    }
  ],
  "available_functions": ["主控计算"],
  "unsupported_functions": ["土壤湿度检测", "出水控制"],
  "matched_hardware": [
    {
      "hardware_id": "xiao_esp32s3",
      "function": "主控计算"
    }
  ],
  "missing_hardware_requests": [
    {
      "role": "soil_moisture_sensor",
      "label": "土壤湿度传感器",
      "function": "土壤湿度检测"
    }
  ],
  "user_message": "当前硬件库只能覆盖主控计算，无法完成土壤湿度检测和出水控制。请补充缺失硬件 profile，或删除这些功能后继续。"
}
```

## 对用户反馈要求

如果需求无法完整覆盖，反馈必须明确说明：

- 哪些功能无法完成。
- 每个功能缺少什么硬件。
- 当前硬件库中能完成什么。
- 用户可以选择补充硬件 profile，或删除/替换无法实现的功能。

## 失败状态

- `needs_input`：缺少硬件、需求超出当前硬件库、用户需要选择删减或补充。
- `blocked`：LLM 功能验证不可用，不能继续进入 profile、布局或建模。
