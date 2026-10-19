# 行空板 K10 统一 Hardware Skill

本目录是掌问内置 K10 器件事实的源包。电气目录、规则、结构机械档案、专家上下文和
CadQuery 参考模型均属于同一 revision。

更新时必须同时检查：

1. `references/specifications.md` 的电气事实；
2. `references/mechanical.md` 的自然描述和机器可读机械档案；
3. `models/cadquery.py` 及其 SHA-256；
4. `references/sources.md` 的来源与验证状态；
5. `tests/validation-cases.md` 的本地门禁。

`models/cadquery.py` 是可审计参考源码，不是普通编辑保存后的任意执行入口。

