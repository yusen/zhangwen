# ZW-005 硬件库与兼容规则引擎

## Purpose / Big Picture

实现 PRD §9.9 硬件库与推荐规则（FR-HW-001 ~ FR-HW-006）。用户可在左侧栏管理主控、传感器、执行器等硬件组件，方案生成时通过确定性规则引擎校验电气兼容性，确保不兼容组合不会进入推荐方案。

## Scope

- 硬件组件 CRUD（新增、编辑、归档、搜索）
- 用户库存管理
- 硬件兼容规则引擎（电压、电平、电流、I2C 地址、总线、固件校验）
- 规则引擎与方案生成集成
- 左侧栏硬件库 UI

## Non-goals

- PCB 布线或电路仿真
- 硬件商城/在线采购
- 硬件图片上传/3D 预览
- 立项书生成（ZW-006+）

## Repository Orientation

| 模块 | 现状 | ZW-005 动作 |
|------|------|------------|
| `packages/contracts` | 无硬件类型 | 新增枚举 + 接口 |
| `services/local-api/zhangwen/hardware/` | 不存在 | 全新模块 |
| `services/local-api/zhangwen/projects/migrations.py` | v2 | v3 迁移 |
| `apps/desktop/src/components/layout/LeftSidebar.tsx` | 硬件库占位符 | 替换为实际组件 |

## Interfaces and Data Contracts

### 新增枚举（enums.ts）

- `HardwareCategory`：MCU / SENSOR / ACTUATOR / DISPLAY / POWER / STRUCTURE
- `HardwareComponentStatus`：ACTIVE / ARCHIVED
- `ValidationSeverity`：PASS / WARNING / FAIL

### 新增接口（api.ts）

- `HardwareElectricalProps`：voltage、logicLevel、peakCurrent、communicationProtocol、i2cAddress、supportedMCUs、driverName、firmwareRequirement
- `HardwareComponent`：id、name、category、status、electrical、stock、price、ageRecommendation、safetyTags、notes、createdAt、updatedAt
- `CreateComponentRequest` / `UpdateComponentRequest`
- `ComponentListResponse` / `ComponentListQuery`
- `ValidationCheck`：dimension、severity、message、details
- `ValidationResult`：checks、overall、message
- `ValidateCombinationRequest` / `ValidateCombinationResponse`

### Sidecar REST API

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | /api/hardware | 列表（支持 category/search 过滤） |
| GET | /api/hardware/{id} | 获取单个组件 |
| POST | /api/hardware | 创建组件 |
| PUT | /api/hardware/{id} | 更新组件 |
| DELETE | /api/hardware/{id} | 归档组件 |
| POST | /api/hardware/validate | 校验组件组合兼容性 |

### SQLite v3 新增表

- `hardware_components`：id, name, category, status, electrical_json, stock, price, age_recommendation, safety_tags_json, notes, created_at, updated_at

## Milestones

### M1: Contracts 硬件类型
新增枚举、接口类型到 contracts 包，build + typecheck 通过。

### M2: Sidecar 硬件 CRUD
新增 hardware 模块：models、repository、router；migrations v3；main.py 注册路由。

### M3: 规则引擎核心
新增 rule_engine.py：确定性校验（电压、电平、电流、I2C、总线、固件）。

### M4: 前端硬件库 UI
HardwareLibrary + HardwareForm 组件；LeftSidebar 集成；hardwareApi 调用层。

### M5: 方案生成集成
generate_solution() 中插入规则校验调用。

## Progress

- [x] M1 Contracts（已完成，build/typecheck 通过）
- [x] M2 Sidecar CRUD（已完成，SQLite v3 迁移和 CRUD 测试通过）
- [x] M3 规则引擎（已完成，覆盖电压、电平、电流、I2C、总线、MCU 支持和固件风险）
- [x] M4 前端 UI（已完成，左侧硬件库 UI 集成，中央 MainConversation 常驻）
- [x] M5 方案生成集成（已完成，`componentIds` 失败时先返回 `HARDWARE_VALIDATION_FAILED`，不读取 LLM Key、不调用 DeepSeek）

## Decision Log

| 编号 | 决策 | 方案选择 | 理由 |
|------|------|---------|------|
| A-01 | 硬件数据存储位置 | 方案一：SQLite 全局表（同库） | MVP 简化，与项目共享连接池 |
| A-02 | 规则引擎校验时机 | 方案一：generate_solution 前同步执行 | 遵循 PRD FR-HW-005，失败组合不得进入方案 |
| A-03 | 硬件初始数据 | 方案一：内置 ESP32 最小集 | 开箱即用，可立即验证端到端 |
| B-01 | 硬件搜索方式 | 前端本地过滤 | 数据量小，无需后端全文搜索 |
| B-02 | 硬件表单布局 | 右侧浮窗或侧滑面板 | 遵守中央区域不可变约束 |
| B-03 | 规则引擎校验粒度 | MVP 6 个维度 | 不含热设计/EMI 等高级维度 |
| C-01 | Project schemaVersion | 返回 `ProjectPersistenceVersion.V3` | 与 SQLite `user_version = 3` 保持一致 |

## Validation

### 自动测试
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw005_rule_engine.py services/local-api/tests/test_zw005_hardware_crud.py services/local-api/tests/test_zw004_clarification_solution.py services/local-api/tests/test_project_repository.py -v --rootdir services/local-api`：36 passed，1 个 Starlette/httpx deprecation warning；pytest atexit 清理 Windows 临时目录时出现 `PermissionError`，不影响测试结果。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests -v --rootdir services/local-api`：53 passed，1 个 Starlette/httpx deprecation warning；同样存在 pytest 临时目录 atexit 清理权限警告。
- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test`：6 files / 36 tests passed。
- `pnpm --filter @zhangwen/desktop build`：通过，生成 `apps/desktop/dist`。
- `.\.venv\Scripts\python.exe scripts/check_ai_assets.py`：通过。

### 手工验收
- 左侧栏硬件库可新增/编辑/搜索组件
- 方案生成时自动校验硬件兼容性
- 校验失败时显示具体错误

## Surprises & Discoveries

- Windows 环境下 pytest 用例通过后，pytest 的 numbered temp symlink 清理可能触发 `PermissionError: [WinError 5]`；该错误发生在 atexit cleanup，不影响测试断言结果。
- ZW-005 将 SQLite `user_version` 推到 3 后，需要同步扩展 `ProjectPersistenceVersion` 并让项目 workspace 返回 `schemaVersion: 3`，否则 API 契约会落后于数据库迁移。

## Outcomes & Retrospective

- ZW-005 软件实现完成：硬件库、内置 ESP32 MVP seed、确定性规则引擎、硬件校验 API、方案生成前阻断、左侧硬件库 UI 和自动测试均已落地。
- 未执行真实硬件验收；该项留到 ZW-012 设备阶段和最终手工验收。

## Handoff

- 下一步：提交 ZW-005 阶段，创建 `zw-005-complete` 标签，并将 `CURRENT_TASK.md` 切换到 ZW-006。
