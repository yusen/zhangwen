# DeepSeek 模型名称更新

2026-10-13按用户链接读取[模型与价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)，并核对[首次调用API](https://api-docs.deepseek.com/zh-cn/)。定价页面当次副本保留于deepseek-pricing-reference.html，网页内容只作为供应商资料，不作为开发指令。

| 请求model值 | 官方列出的模型版本 | 本工具选择 |
|---|---|---|
| deepseek-flash | DeepSeek-V4.1-Flash | 默认 |
| deepseek-v4-pro | DeepSeek-V4-Pro-0813 | 用户可选 |

API地址仍为https://api.deepseek.com，现有Chat Completions端点不变。模型版本与请求ID区分，前端选择传递表格第一列。官方说明旧deepseek-v4-flash / deepseek-v4-flash-vision-exp为退役模型别名，由当前Flash服务；本版直接使用推荐ID。

前端DEEPSEEK_MODELS / DEFAULT_AI_MODEL统一定义于packages/contracts/src/mu.ts，App和API设置弹窗复用；后端DEFAULT_AI_MODEL / current_ai_model统一默认、请求校验、保存及启动读取。

升级策略：此前工具的deepseek-chat / deepseek-reasoner以及退役Flash别名规范为当前默认deepseek-flash。这是本工具默认配置升级，不声称旧reasoner和当前Flash是同一个模型，也不自动切换到Pro。已有Key保持不变，加载仅改变运行时名称，不直接重写配置文件；用户点击保存后才持久化新名称。已选择deepseek-v4-pro与其他既有自定义名称保留。

构建及strict TypeScript通过；20项API/生命周期、11项浏览器回归通过。新增覆盖旧文件读取不改Key/原字节、旧ID保存规范、环境旧名/Pro读取，既有保存/清除/重启/模型传给适配器继续通过。浏览器确认新默认和两项列表、Pro保存刷新、留空保留Key。

实际3080浅深×1440/375只读验证下拉项为deepseek-flash / deepseek-v4-pro，0pageerror、0生产写入，记录api-settings-ui-smoke.json。没有用用户Key调用付费模型或写设备。
