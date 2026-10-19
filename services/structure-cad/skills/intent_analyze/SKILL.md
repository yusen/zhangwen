# intent_analyze

## 用途

把用户自然语言、已选硬件和当前任务状态整理成结构化 `intent`。本步骤只理解需求，不生成 CAD 坐标或代码。

复杂产品需求必须先遵守 `requirement_function_selection_analysis`：先拆功能，再推导硬件角色，再进入结构化 intent。

## 何时调用

- 新任务第一次发送需求时。
- 用户在对话中修改产品功能、使用场景、硬件需求或尺寸约束时。
- 后续步骤发现需求不清晰，需要回到意图层重新解释时。

## 输入格式

```json
{
  "prompt": "用户原始或追加需求",
  "selectedHardwareIds": ["xiao_esp32s3"],
  "currentDesignState": null,
  "userAnswers": []
}
```

## 输出格式

```json
{
  "status": "ok",
  "intent": {
    "product_name": "开发板外壳",
    "functions": ["主控保护", "USB-C 外露"],
    "required_hardware_roles": [],
    "mounting_intents": [],
    "user_constraints": {}
  }
}
```

## 复杂需求要求

对“智能浇花系统”这类需求，不能只输出主控保护。必须识别土壤湿度检测、出水控制、驱动控制、供电等功能，并为硬件库缺失项生成 `unsupported_in_library: true` 的 required hardware role。

## 失败状态

- `needs_input`：需求为空、形状超出带盖长方体盒子范围，或用户要求直接生成 CAD 代码。
