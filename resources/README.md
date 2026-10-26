# 硬件与结构资源

每个电子模块统一放在 `hardware-skills/<skillName>/`。原componentId、修订、电气声明、规则和来源保持，运行时继续使用原Hardware Skill与SQLite投影。

```text
hardware-skills/<skillName>/
  manifest.json                 原模块身份、核心文件和图片摘要
  SKILL.md
  references/                   电气、兼容、接线、安全、来源和机械档案
  examples/usage.md             原包案例
  examples/reviewed.md          多主控补充案例，安装时合入原案例入口
  programming/                 已有主控API与参考程序
  models/                      原机械参考模型，仅作资料
  structure/                   结构说明、明确关联的外形与图片
  assets/                      原模块产品图
structure-parts/<profileId>/     无确切电子模块对应关系的结构参考
hardware-resources.json          路径、摘要和显式身份关联
```

不是每个模块都有机械尺寸和模型；各模块的 `structure/README.md` 说明资料状态。不用占位尺寸、不凭名称并入另一型号孔位。结构专用件确认准确SKU/修订后才绑定。

用户修改继续保存在用户数据目录的原 `hardware-skills/` 和SQLite投影，发布资源保留有效用户修改。项目输出见 [项目目录](../docs/PROJECT_LAYOUT.md)。

开发者修改补充资料后运行 `python scripts/hardware_resource_index.py` 刷新摘要，再运行 `python scripts/verification/audit-hardware-resources.py` 和相关测试。刷新不认证硬件事实、不替代原核心修订校验。标准案例/供应商导入工具已接入刷新，不要重跑一次性归档脚本。
