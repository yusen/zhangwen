# conversation_route

## 用途

判断用户最新输入在当前任务中属于哪一种动作，并把它路由到对应工具链。本 skill 只做对话调度，不生成 CAD，不直接决定最终坐标或模型代码。

## 何时调用

- `/api/agent/prepare` 收到用户输入时优先调用。
- 用户点击“确认分析”、输入“确认/继续”、提出修改需求、修改已生成方案、或要求“给选定硬件做盒子”时调用。
- 前端按钮可以显式传入 `routeAction`，但后端仍应记录 route 结果。

## 输入格式

```json
{
  "prompt": "用户最新输入或原始需求",
  "latestUserMessage": "用户最新消息",
  "conversationContext": {
    "workflowStage": "requirement_analysis|confirming|review|idle",
    "hasRequirementAnalysis": true,
    "hasDraft": false,
    "hasArtifact": false,
    "taskId": "ZW-PRODUCT-20260623-120000"
  },
  "selectedHardwareIds": ["xiao_esp32s3"],
  "currentDesignState": {},
  "routeAction": ""
}
```

## 输出格式

```json
{
  "route_action": "revise_requirement",
  "confidence": 0.88,
  "reason": "需求分析阶段收到非确认类修改消息",
  "source": "deterministic_conversation_route"
}
```

## 支持的 route_action

- `new_requirement`：新需求或普通首次需求分析。
- `confirm_requirement_analysis`：确认需求分析，进入 BOM/profile/布局预审。
- `revise_requirement`：需求分析阶段修改功能、硬件或约束。
- `revise_artifact`：已有 artifact 后修改方案并在当前任务内重算。
- `selected_hardware_enclosure`：用户已选硬件，要求直接为选定硬件做盒子。
- `provide_custom_profile`：用户准备补充临时硬件 profile。
- `change_mounting_face`：用户要求修改硬件安装面。
- `build_confirmed`：用户确认 2D 草案，进入最终建模。

## 限制边界

- 不输出 CadQuery、Python、OpenSCAD 或最终 CAD 坐标。
- 不凭空补硬件；是否能选硬件仍由 `hardware_bom_select` 决定。
- 无法判断时回退为 `new_requirement` 或当前阶段最保守动作，并记录低置信度原因。

## 验证方式

- 对“确认/继续/可以”应路由为 `confirm_requirement_analysis` 或 `build_confirmed`。
- 对“把超声波改成人体传感器”应路由为 `revise_requirement` 或 `revise_artifact`。
- 对“给选定硬件做一个盒子”且存在已选硬件时，应路由为 `selected_hardware_enclosure`。
