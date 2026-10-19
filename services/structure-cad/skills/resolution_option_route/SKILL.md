# resolution_option_route

## 用途

把用户对当前阻断选项的按钮点击或自然语言回复，转换成明确的 `resolution_options` 选择。

## 触发条件

- 后端收到 `/api/agent/prepare` 请求，并且请求体包含 `activeResolutionOptions`、`lastNeedsInput.resolution_options` 或 `currentRequirementAnalysis.resolution_options`。
- 前端传入 `resolutionOptionId`，表示用户点击了某个处理按钮。
- 用户直接输入类似“忽略缺失继续”“我来补 profile”“放大盒子”“把蜂鸣器移到底壳”等文字。

## 输入

- `latestUserMessage`：用户最新输入。
- `resolutionOptionId`：按钮明确传入的选项 id，可选。
- `activeResolutionOptions`：当前可选处理方案。
- `lastNeedsInput` / `currentRequirementAnalysis`：当前阻断或需求分析上下文。

## 输出

```json
{
  "status": "matched | ambiguous | no_match",
  "option_id": "ignore_missing_hardware_continue",
  "action": "ignore_missing_hardware_continue",
  "confidence": 0.92,
  "reason": "用户要求忽略缺失硬件并用剩余硬件继续"
}
```

## 边界

- 只负责判断用户选择了哪个处理方案。
- 不直接生成 CAD。
- 不直接决定硬件坐标、开孔坐标或装配变换。
- 如果用户文本太模糊，必须返回 `ambiguous`，由前端继续要求用户明确选择。

## 验证方式

- 点击“忽略缺失功能继续”应返回 `ignore_missing_hardware_continue`。
- 输入“先忽略缺失硬件，用剩下的继续”应匹配同一选项。
- 输入“我来补参数/profile”应匹配 `provide_custom_hardware_profile`。
- 输入“随便吧”应返回 `ambiguous`，并保留原始选项。
