# ZW-CAD-intent 来源快照策略

该目录是用户在 2026-07-26 指定的 CAD 行为基线。`SOURCE_SNAPSHOT.json` 记录来源统计和组合哈希，`CHECKSUMS.sha256` 记录每个原始文件的 SHA-256。新增的掌问适配器和 golden 测试放在 `services/cad-intent-worker/`，不改写这里的原始业务文件。

生产融合只采用这些行为：对话路由、需求/功能/硬件分析、确定性模板、独立结构件、profile/方向/布局/验证、CadQuery 源码修订、源哈希补丁、AST 门禁、刻字和 STEP/STL/mesh 导出。

以下内容仅供审计，不能成为掌问第二套真值：`public/` 独立 UI、`server/project-store.js`、`server/model-sources.js`、`server/data/hardware-library.json` 和独立 HTTP 服务。

快照明确排除依赖目录、本机模型配置、密钥、缓存、结果目录和运行产物。禁止把本机绝对来源路径写入 Artifact、Release 或公开导出。
