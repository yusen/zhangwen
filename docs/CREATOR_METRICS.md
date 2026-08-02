# Creator V3 指标事件契约

版本：v1

日期：2026-07-31

适用任务：`ZW-CREATOR-001` M1–M8

## 1. 目的

本契约冻结 Creator V3 的成功指标、事件名称、计算口径、基线阈值和隐私边界。指标只用于回答
“作品能否从创意推进为可复现实物”，不用于证明设备身份、验证等级或替代验收证据。

关系表、Artifact、设备操作和 Creator 证据仍是工程真值；指标事件只是这些事实发生后的不可变、
去标识化投影。删除指标事件不得改变作品状态。

## 2. 写入语义

- schema 固定为 `creator-metric/v1`，共享契约使用判别字段 `metric`；
- 每个事件包含 `schemaVersion=1` 和本地生成的非敏感 `triggerId`；
- 事件 ID 由 `metric + triggerId` 确定性派生，并在产生业务事实的同一事务内追加；数据库 schema
  迁移是唯一例外：只有迁移提交且迁移前后规范 Hash 验证成功后才追加迁移事件；
- 同一幂等请求重放返回原响应，不重复记录指标；同一键换请求仍按业务边界拒绝；
- 指标消费者按事件 ID 去重，不以时间戳猜测唯一性；
- 事件只追加，不原地修改；失败尝试和恢复结果使用各自事实事件。
- 作品级事件写入 `creator_events`，但对外的 `METRIC` SSE 信封不包含 `workId`；V29→V30
  的库级迁移事件单独写入 `creator_system_metrics`，每个真实旧数据库最多一条；
- `user_version=0` 的全新数据库不是历史迁移样本，不产生 `LEGACY_MIGRATION_FINISHED`；
- `FIRST_DEPLOYMENT_FINISHED` 按作品和部署通道只记录第一次终态；设备写入失败后完成备份恢复时，
  另记录对应的 `RECOVERY_FINISHED`，不能用后续成功覆盖第一次部署结果。

## 3. 隐私边界

允许记录：

- Creator/Legacy 来源、能力类别、部署通道、受控失败分类；
- 数量、布尔结果、尝试序号、毫秒耗时和 0–1 比率；
- 包变体和来源 schema 版本。

禁止记录：

- 账户 subject、邮箱、姓名、显示名或自由文本；
- 对话、目标、方案、代码、参数值、日志或媒体内容；
- 串口、设备 ID、MAC、局域网地址、ESP-Claw 端点或凭据；
- 原始项目/作品/Artifact/修订 ID。`triggerId` 必须是专用指标触发 ID，不能复用上述标识。

## 4. 指标、事件和阈值

| 成功指标 | 事件与触发点 | 计算口径 | M8 基线阈值 |
| --- | --- | --- | --- |
| 创意到第一次可观察数字行为时间 | `WORK_CREATED`；首次通过的 `DIGITAL_BEHAVIOR_OBSERVED` | 同一作品两事件时间差的 P50/P90 | P50 ≤ 20 分钟 |
| 目标确认率 | `WORK_CREATED`、首次 `GOAL_CONFIRMED` | 有目标确认作品数 / 新建作品数 | ≥ 75% |
| 方案确认率 | 首次 `GOAL_CONFIRMED`、首次 `SOLUTION_CONFIRMED` | 有方案确认作品数 / 有目标确认作品数 | ≥ 60% |
| 仿真必需场景通过率 | 每次停止后记录 `SIMULATION_FINISHED` | 通过的必需场景数 / 执行的必需场景数 | ≥ 80% |
| 第一次真实部署成功率 | 每个作品/通道只记录首次 `FIRST_DEPLOYMENT_FINISHED` | 首次部署成功作品数 / 首次部署作品数 | ≥ 70% |
| 仿真到真机行为一致率 | 每次实物验收记录 `PHYSICAL_BEHAVIOR_FINISHED` | 一致且通过的场景数 / 同时完成仿真与真机的场景数 | ≥ 80% |
| 失败恢复成功率 | 每次受控恢复完成记录 `RECOVERY_FINISHED` | 恢复成功次数 / 启动恢复次数 | ≥ 90% |
| 新建到等级 6 完成率 | `WORK_CREATED`、首次 `WORK_ACCEPTED` | 达到等级 6 作品数 / 新建作品数 | ≥ 30% |
| 交付包证据覆盖率 | 每次成功导出记录 `DELIVERY_EXPORTED` | 当前有效证据数 / 该作品交付所需证据数 | 必须 100% |
| 第二用户复现成功率 | 每次闭环尝试记录 `REPRODUCTION_FINISHED` | 成功复现数 / 有效复现尝试数 | ≥ 80% |
| 历史迁移成功与零丢失率 | 每个迁移事务记录 `LEGACY_MIGRATION_FINISHED` | 成功迁移库数 / 尝试库数；迁移前后规范 Hash 一致库数 / 成功库数 | 成功 100%，数据丢失 0 |

阈值用于 M8 样板和后续小规模试用的预警，不是单个作品的验证门禁。样本不足 20 个作品或 5 次真实
部署时只报告样本与区间，不宣称达到平台成熟度。

## 5. 严格事件载荷

所有事件共用：

```text
schemaVersion: 1
metric: 判别事件名
triggerId: 专用、不可反推业务标识的本地触发 ID
```

各事件只允许以下附加字段：

- `WORK_CREATED`：`origin = CREATOR | LEGACY`；
- `GOAL_CONFIRMED`：`revision`；
- `SOLUTION_CONFIRMED`：`revision`、`capabilityClass = SENSING | RESPONSE |
  VISION_AUDIO | MIXED`；
- `DIGITAL_BEHAVIOR_OBSERVED`：`elapsedMs`；
- `SIMULATION_FINISHED`：`passed`、`requiredScenarioCount`、`passedRequiredScenarioCount`、
  `failureCategory = PARAMETER | LOGIC | IO | CAPABILITY | UNKNOWN | NONE`；
- `FIRST_DEPLOYMENT_FINISHED`：`passed`、`channel = USB_SERIAL | ESP_CLAW`、`recoveryRequired`；
- `PHYSICAL_BEHAVIOR_FINISHED`：`passedScenarioCount`、`comparedScenarioCount`、
  `simulationConsistent`；
- `RECOVERY_FINISHED`：`action = USB_UPLOAD | ESP_CLAW_UPLOAD | PARAMETER_SYNC |
  SIMULATION`、`passed`；
- `WORK_ACCEPTED`：`elapsedMs`；
- `DELIVERY_EXPORTED`：`variant = SHARE | REPRODUCIBLE | TEMPLATE`、
  `requiredEvidenceCount`、`currentEvidenceCount`、`coverageRatio`；
- `REPRODUCTION_FINISHED`：`passed`；
- `LEGACY_MIGRATION_FINISHED`：`fromSchemaVersion`、`migratedRowCount`、`zeroDataLoss`、
  `passed`。

额外字段必须被 TypeScript 判别联合和 Pydantic `extra="forbid"` 拒绝。

## 6. 验收

自动测试必须证明：

1. 同一幂等请求只产生一个指标事件；
2. 同一触发 ID 换事件内容不能覆盖历史；
3. 未通过的业务动作不产生成功事件；
4. payload 额外字段、自由文本、设备标识和账户字段被拒绝；
5. 非迁移业务的事件写入失败时业务事务不提交；
6. V29→V30 先规范化受支持的旧形态，再对 V29 历史表做规范 Hash；只有全部 V30 repair、
   外键检查和迁移前后 Hash 校验成功后才记录，重复打开不重复写迁移事件；
7. 新建数据库不计入旧库迁移，两个历史项目仍只产生一条数据库级迁移事件；
8. 对外指标信封和载荷均不泄露作品 ID、设备 ID、端点、账户或自由文本。

真实漏斗、真实部署和真人复现的样本采集属于 M8；事件契约、埋点和测试属于 M1–M7 软件范围。
