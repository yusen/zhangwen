# 参考输入目录

此目录存放掌问实现和验证过程中使用的参考输入，不是应用运行时数据目录。

## `source-packages/`

受 Git 跟踪、可审计和可恢复的原始参考包。目前包含：

- `unihiker-k10-micropython-skill/`：用户提供的行空板 K10 MicroPython Skill 原始包。运行时只读副本位于 `services/local-api/zhangwen/hardware/board-skills/unihiker-k10/`。

修改这里的内容必须同步检查运行时副本、manifest 和哈希；不能把它与 `.agents/`、`.qoder/` 或 `ai/skills/` 的工具发现目录随意合并。

## `local/`

仅本机使用且整体被 `.gitignore` 忽略的外部工程和资料。当前目录包括：

- `ZW-CAD-intent/`：CAD 语义、几何和测试 oracle；产品不执行其中的服务、模型或任意 Python 入口。
- `openclaw-robot-dog-soul-k12(1)/`：外部硬件参考工程。
- `复杂结构件建模的人机交互资料/`：K10 电子相册固定结构模板的来源资料。

`local/` 可能包含外部工程自己的依赖、日志或本机配置。它不参与掌问构建，不得批量加入 Git，也不得在普通整理中删除。

## 保护边界

- 用户项目和应用数据位于 `.data/`，不属于参考输入。
- 生成结果位于 `outputs/`，不属于参考输入。
- 可再生依赖与构建缓存由 `scripts-dev/clean-generated.ps1` 的显式允许列表管理。
- 新增参考资料时，优先判断它应当可审计跟踪还是仅本机保留，再放入对应分层；不要重新散落到仓库根目录。
