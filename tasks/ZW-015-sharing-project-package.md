# ZW-015 Sharing and Project Package

## Purpose / Big Picture

ZW-015 建立项目分享和项目包闭环。MVP 需要能从本地项目生成可审计 ZIP 包，包含 manifest、项目摘要、选中的产物预览和隐私扫描报告；也需要能导入项目包并防护路径穿越、敏感信息和导入冲突。导出导入均由 Python Sidecar 执行，前端只调用受控 API。

## Scope

- Project Package shared contracts 与 Python Pydantic models。
- SQLite v13 `package_exports`。
- ZIP export/import API、manifest、隐私扫描、路径穿越防护和导入冲突处理。
- `PACKAGE` Artifact 同步。
- 左侧项目区提供导出/导入入口，中央主对话保持常驻。

## Non-goals

- 公开发布、云端分享、安装器、代码签名或自动更新。
- 导出系统凭据、真实设备标识、临时日志或构建缓存。
- 真实文件系统项目工作区打包。
- ZW-016 MVP 硬化以外的新增阶段。

## Interfaces and Data Contracts

- `ProjectPackageStatus`: `READY | EXPORTED | IMPORTED | BLOCKED | FAILED`
- `ProjectPackageItemKind`: `PROJECT | ARTIFACT | MANIFEST | PRIVACY_REPORT`
- `ProjectPackageArtifactSelection`: `includeDocuments/includeCode/includeCad/includeLessons/includeDeviceLogs`
- `ProjectPackageManifest`: package schema version, package/project IDs, source project metadata, selected artifacts, privacy report and timestamps.
- `ProjectPackagePrivacyReport`: `ok/checks`.
- `ExportProjectPackageRequest`: artifact selection and optional display title.
- `ImportProjectPackageRequest`: base64 ZIP payload and conflict strategy.

## Milestones

### M1 Contracts, Schema and API

新增 contracts、Python models、SQLite v13 migration、package repository 和 Sidecar routes。

### M2 Export/Import Safety

实现 ZIP manifest、artifact 选择、敏感扫描、路径穿越防护、导入冲突处理和 `PACKAGE` Artifact。

### M3 Desktop UI

在左侧项目区增加导出当前项目包和导入项目包入口，保持中央主对话常驻。

### M4 Validation and Stage Close

运行全量回归节点验证；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts, Schema and API
- [x] M2 Export/Import Safety
- [x] M3 Desktop UI
- [x] M4 Validation and Stage Close

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | 导出内容 | 导出 manifest、项目摘要和选中 Artifact 预览，不导出原始 DB | 降低隐私和兼容风险，保留可审计交付物 |
| A-02 | 导入策略 | 默认 `CREATE_COPY`，冲突时生成新项目 ID | 不覆盖本地项目，保证可逆 |
| A-03 | ZIP 路径 | 仅允许固定相对路径前缀 | 防护路径穿越和绝对路径泄露 |
| A-04 | 隐私扫描 | 导出前由 Sidecar 扫描并阻断可疑凭据、串口和绝对路径 | 防止敏感本地信息进入包、日志、测试快照或 Git |
| A-05 | 项目包产物 | 导出和导入同步 `PACKAGE` Artifact | 复用右侧产物系统，不替换中央主对话 |

## Validation

- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw015_project_packages.py -q --rootdir services/local-api`：6 passed。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`：93 passed。
- `pnpm --filter @zhangwen/desktop test`：47 passed。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop build`：通过，产物位于 `apps/desktop/dist`。
- Python `compileall` for `project_packages`、`projects`、`main.py`：通过。
- ZW-015 变更范围敏感信息扫描：未发现真实 API Key、Authorization、Bearer token 或真实串口标识；仅有 ZW-015 隐私拦截测试用 `apiKey: hidden-value` 和 ZW-002 既有假 Key 测试夹具。

## Handoff

ZW-015 自动验收已通过，待阶段提交 `feat: complete ZW-015 sharing and project package` 和标签 `zw-015-complete`。提交时不要包含 `.codex/config.toml` 的本地配置改动。
