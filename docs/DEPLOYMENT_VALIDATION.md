# 一键部署与仓库替换验证

## 最新：启动前检测与复用

2026-10-15按用户反馈修订。`npm run test:setup` 5项通过：无回执仍复用、回执不能掩盖缺包、版本不符触发修复、适用平台原生包缺失触发修复、CLI入口缺失触发修复。

通过Windows PowerShell5.1实际运行启动器验证：全新源码目录复用系统Node24.14.0/npm11.9/Python3.14.3，运行时下载0次；Python依赖保持项目内.venv隔离。重复启动跳过安装/构建；删除安装回执仍跳过依赖安装；隔离环境移除colorama及@lezer/highlight后检测并修复，之后再次跳过安装/构建。保留版本元数据但删除pydantic_core模块文件时，也能检测导入失败并修复。另移除系统PATH中的Node/Python路径，仍复用项目Node24.14/Python3.13.7且不下载依赖。复用后的实际HTTP页面和健康检查通过。strict构建通过，原471文件与817资源摘要一致。记录environment-detection-smoke.json；本次无真实设备/模型或生产数据写入。

日期：2026-10-15。范围：以当前 Mu Web 替换旧桌面仓库工作树，保持私有仓库和旧 Git 历史。

## 已验证

- `npm run build`：TypeScript strict 与 Vite 生产构建通过。
- `npm test`：13 项 Fake 串口协议测试通过。
- `npm run test:api`：26 项通过（277.57s），包含全新 76 包初始化、74 包 Web 显示、五款主控、用户包保留、817 资源摘要及原 471 文件摘要；保存/版本/会话边界/模型模拟测试沿用。
- `npm run test:e2e`：14 项通过（59.1s），候选库测试更新为完整 68 模块/54 输入/14 输出。Python 3.14 的 Windows asyncio 在浏览器关闭连接时输出过连接重置日志，未导致测试失败；新安装运行环境使用 3.13.7。
- 从 Git index 导出隔离源码目录，不复制 `.venv`、`node_modules`、`imports` 或 `.data`。实际运行 Windows 引导脚本，下载并校验 Node 24.14.0 / uv 0.8.22，准备 Python 3.13.7、pip/npm 锁定依赖和生产页面，全部成功。
- 通过真正的 `start-web.bat --no-open --port 3084` 再次启动，跳过安装与构建，HTTP 页面和健康检查通过；数据只在隔离目录。
- 全新库初始项目数 0、AI 未配置；硬件 76 包 / Web 可见 74 包 / 主控 5 / 输入 54 / 输出 14。保存、读取、静态检查、上传清单 SHA-256 一致；没有连接硬件或调用模型。记录：`deployment-smoke.json`。
- 在下载的 Python 3.13.7 环境补跑原文件与完整资源/保留测试：2 passed（12.09s）。
- 发布跟踪路径检查无 `.data`、Key 设置、SQLite、依赖、imports、运行环境、设备备份或本机真机验收原始元数据。常见 API Key / GitHub token / 私钥模式扫描无命中，不输出凭据内容。

## 旧资料恢复

旧 main：`7e0b34e160cae274983018d9916f31ab0e92fc70`。

已上传标签：`backup/desktop-before-mu-web-20261015`，保留该旧提交和完整历史。本地另有验证通过的 `.publish/desktop-before-mu-web-20261015.bundle`。新版通过正常后继提交更新 main，不强推、不重写旧历史。

## 远程回读

初始主分支替换提交：`a5d200dff106e4e18cf994a85c11ef7e2f257823`，父提交为旧main。根树：`3a66048d9a30c0f4ea6185d6bc3b3a5289fe8477`。Git传输多次重置/超时，改用官方Git Data API上传：98个新二进制blob以及所有子树/根树SHA与本地逐一相等，随后普通提交以`force=false`更新main。回读1444文件的路径/模式/blob SHA与本地完全一致，含817个随包硬件资源；旧apps/desktop与Cargo入口已从当前树移除，README一键启动说明已远程确认。仓库仍为私有。

GitHub Actions `Verify Mu Web` 已触发，首次回读时正在运行，不能当作远程CI已通过。Windows本地53项及隔离安装为已完成证据。上传过程的凭据由现有Git Credential Manager在内存中取得，不写入脚本/报告/项目设置，不修改系统凭据。

## 限制

这是在本机隔离目录模拟新电脑的实际安装，尚未在第二台物理电脑或 macOS/Linux 实机运行。Windows 标准用户目录、首次联网、桌面 Chrome/Edge 是推荐路径；代理/企业限制和板卡串口驱动由目标电脑环境决定。没有发布 npm 包，不提供虚构的 npx 安装命令。新增 GitHub Actions 工作流用于后续推送回归，其远程运行结果与上述本地验证分别记录。

设备/真实模型验收范围不因仓库上传而扩大，见原 MVP 验证记录。
