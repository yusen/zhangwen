# ZW-CAD-005 — mechanical.md 自然描述生成预览

状态：实现完成且自动验收通过；真人桌面抽检待用户（2026-07-17）

## 1. 目标

任意 `hardware-skills/<skill-name>/references/mechanical.md` 的“自然语言描述”是器件 3D 预览的唯一
源数据。用户更新自然描述后，不需要手工同步第二份几何；应用在打开预览时校验派生缓存，缺失或过期
则调用结构化模型重新生成受控几何，并把新缓存与描述哈希回写到该 Hardware Skill。

## 2. 安全与产品边界

- 云端只读取当前 mechanical.md 的自然描述，不读取主机路径、参考 Python、Shell、串口或凭据。
- 输出仍只允许最多 32 个 `box/rounded_box/cylinder` 和顺序 `add/cut`；本地 Pydantic 边界最终裁决。
- `preview_geometry` 是带 `source_sha256` 的可重建缓存，不是用户真值；哈希与当前描述不一致时禁止使用。
- 生成成功后通过 Hardware Skill 的 revision CAS 和原子投影更新回写，不能直接修改 SQLite 真值。
- 缺少云端配置或模型连续无效时显示明确错误，不使用旧缓存冒充当前描述。
- 预览继续使用既有浮窗，中央对话不卸载，右侧一级 Tab 固定为“工作 / 产物 / 设备”。

## 3. 计划

1. 增加自然描述提取、规范化 SHA-256 和 fenced JSON 安全回写函数。
2. 增加 Provider-backed 受控几何编译服务及一次结构修复重试。
3. 增加机械预览生成 API：命中同描述缓存则直接返回，否则编译、更新 Skill revision 并返回新档案。
4. 桌面预览按钮先显示“生成中”，成功后打开浮窗并刷新机械档案列表。
5. 增加缓存命中、描述变更、非法输出、CAS、UI 单实例与三 Tab 回归。

## 4. 验收标准

- 任意有效 `<xxx>/references/mechanical.md` 只修改自然描述后，下一次预览不会使用旧描述生成的几何。
- 首次没有 `preview_geometry` 时可从自然描述生成；生成结果写入 `source_sha256` 并产生新 Skill revision。
- DFR0026 当前缓存与其自然描述哈希一致，可直接打开且不需要重复云端调用。
- 模型缺配置、输出非法、Skill revision 竞争或目录无自然描述时失败关闭并给出中文提示。
- 中央 `CenterChat`、草稿、附件、引用和右侧“工作 / 产物 / 设备”不受影响。

## 5. Decision Log

- 2026-07-17：自然描述是唯一真值；声明式几何保留为带来源哈希的派生缓存，以兼顾可审计、即时打开和
  不执行任意代码。
- 2026-07-17：不在普通 GET 列表接口隐式调用付费模型；用户点击“查看 3D 预览”是明确的生成动作。

## 6. 实现结果

- `hardware/mechanical_preview.py` 只提取唯一 `## 自然语言描述` 章节，规范化换行后计算 SHA-256；
  Provider 只能返回受控 `DeclarativeGeometry`，本地边界拒绝代码、路径、URL、未知字段和超限几何。
- `POST /api/hardware/mechanical-profiles/{profileId}/preview` 接受当前精确 revision。缓存哈希匹配时不初始化
  Provider 或凭据；缓存缺失、旧版无哈希或描述变化时生成并通过 Hardware Skill revision CAS 原子回写。
- 旧机械快照在新增 `preview_geometry/source_sha256` 默认字段后仍按 schema v1 原哈希读取；旧缓存只可读取，
  因无描述哈希会在下一次显式预览时失效重建。
- 桌面按钮先显示按 `mechanical.md` 生成状态，成功后以响应中的新档案打开既有浮窗，失败不打开旧模型。
- DFR0026 当前活动 revision 为 `2f2456787cf3db4a91767a80`，描述哈希为
  `2409c80cd73dac4e1519c572083da9e0fe0678a59d3bf606255ab0cea20b9e1b`；真实数据请求返回
  `DESCRIPTION_CACHE`，在 Provider/凭据工厂被设置为“调用即失败”时仍成功。

## 7. 验证记录

- CAD、结构工程师、Hardware Skill、统一硬件库与机械预览后端：`221 passed`。
- 机械档案 UI、右侧栏与项目隔离：`51 passed`。
- `pnpm typecheck`：Contracts build/typecheck 与 Desktop strict typecheck 通过。
- `pnpm build:desktop`：production build 通过；只有既存 Vite chunk-size 提示。
- 定向 `git diff --check` 通过；只有仓库既有 LF→CRLF 提示。

## 8. 剩余验收

- 重启当前非热更新 Sidecar/桌面应用，在专业模式打开 DFR0026 预览，真人确认圆角 PCB、接线口、
  感光圆柱、两孔与 keepout 的视觉位置。
- 修改一处自然描述并保存后再次预览，确认出现生成状态、Skill revision 更新且显示新几何。
- 本轮未调用真实付费 Provider、未执行参考 Python，也未进行串口、Flash、固件或公开发布操作。
