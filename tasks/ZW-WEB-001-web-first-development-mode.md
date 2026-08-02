# ZW-WEB-001 — 掌问 Web 优先开发模式切换与核心流程稳定化

状态：已完成

## 1. 目标

在不建立第二套 React、API、SQLite、三师领域逻辑或 Artifact 系统的前提下，把 Browser Host + FastAPI Sidecar 设为当前默认开发和流程验证入口；保留 Tauri/Rust 和全部本地能力接口，通过统一 PlatformCapabilities、Host Adapter 和 API Client 明确隔离 Web 不支持的本地能力。

## 2. 可观察验收

- `pnpm dev:web` 启动同一个 FastAPI Sidecar 与同一个 React 应用，默认访问 `http://localhost:5173`，不启动 Rust/Tauri。
- Web Host 无 Tauri Runtime 时可渲染、创建/恢复项目、对话、批量澄清、生成/确认同版本方案产物、切换专家并保持线程/草稿/SSE 隔离。
- PlatformCapabilities 集中返回 host 和文件、凭据、窗口、Shell、串口、设备、Flash、CAD 能力；业务组件不散落 `window.__TAURI__`。
- Browser/Tauri 使用同一 API Client；Base URL 默认 `http://127.0.0.1:8100`，可由非敏感 Vite 配置覆盖。
- Web 不扫描/连接串口，不上传/Flash，不执行 Shell 或本地 CAD；页面显示中文原因，不伪造成功。
- React Web 不读取或发送 Provider Key；Provider Key 只由后端环境或现有安全凭据路径提供。
- 保留 `apps/desktop/src-tauri`、Rust、FastAPI、SQLite、Windows Credential Manager、ToolRunner、设备/CAD/文件接口和全部三师领域结构。

## 3. 里程碑

### M1 — Platform and API boundary

- [x] 实现统一 PlatformCapabilities / Host Adapter 及测试覆盖。
- [x] 统一 REST/SSE Base URL、错误、超时和取消。
- [x] 增加后端环境 Key 安全读取与本地 CORS 必要来源。

### M2 — Web capability gates and entry

- [x] 隔离 Web 下设备扫描/连接/上传/Flash、Shell、本地 CAD 和前端 Key 输入。
- [x] 增加 `pnpm dev:web` 与清理可靠的 PowerShell 启动脚本。
- [x] 保持普通模式、专业模式和 UI Contract 不变量。

### M3 — Core flow and verification

- [x] 补 Web Host、能力门禁、刷新恢复和 API 共用回归测试。
- [x] 不启动 Tauri 完成 FastAPI + Vite 浏览器验收。
- [x] 更新 README、CURRENT_BASELINE、PRD、DECISIONS、HANDOFF 并运行全量验证。

## 4. Progress

- 2026-07-10：任务启动。直接从 ZW-STABILIZE-001 唯一基线实施，不重新调查、不恢复 ZW-UX-008A、不重写三师；开始 M1 平台能力层。
- 2026-07-10：M1 完成。统一 PlatformCapabilities、Host Adapter、REST/SSE API Client、30 秒超时/取消、Web Host Header、后端环境 Key 与收紧 CORS 均已有自动测试。
- 2026-07-10：M2 完成。Web 的串口、设备上传/Flash、Shell、本地 CAD 和前端 Key 均由前后端双重门禁；`pnpm dev:web` 仅启动 FastAPI + Vite，并验证 Ctrl+C 后端口清理。
- 2026-07-10：M3 浏览器验收完成。项目/消息/草稿刷新恢复，问题引导师与智能工程师线程/草稿隔离，设备页明确禁用真实操作，固定三 Tab 与中央对话保持，控制台无应用错误；开始全量验证。
- 2026-07-10：M3 与任务完成。Desktop 76 tests、local-api 151 tests、contracts/desktop 构建与类型检查、Python compileall、Cargo check、`git diff --check` 全部通过；未调用真实 Provider 或设备。

## 5. Decision Log

- 2026-07-10：Browser 和 Tauri 只是同一 React + API Client 的 Host Adapter；任何平台差异只能门禁宿主能力，不得分叉三师业务和持久化。
- 2026-07-10：Web 自动测试和验收不调用真实 Provider 或设备；设备能力只允许读取已有摘要/Mock/Dry Run 结果，不能从 Web 发起操作。
- 2026-07-10：`pnpm dev:web` 显式注入非敏感 `VITE_ZHANGWEN_HOST=web`，防止承载浏览器的外层 WebView 标记导致 Web 能力误判；未配置时仍保留原 Tauri Runtime 自动检测。

## 6. Safety

- 不删除 Tauri/Rust、本地执行接口、legacy 数据或任何用户项目数据。
- 不在前端环境、LocalStorage、IndexedDB、请求日志或 Git 中放 Provider Key。
- 不扫描、连接或操作真实串口，不运行 mpremote/esptool，不擦除 Flash 或烧录固件。
- 不暂存 `tasks/ZW-UX-003-three-expert-system.md` 的用户自有改动，不推送或强推。
