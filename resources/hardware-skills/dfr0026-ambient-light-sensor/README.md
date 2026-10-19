# dfr0026-ambient-light-sensor

DFRobot DFR0026 模拟环境光线传感器的掌问 Hardware Skill 文件包，版本 1.0.0。

## 目录

```text
dfr0026-ambient-light-sensor/
├─ manifest.json
├─ SKILL.md
├─ assets/cover.webp
├─ models/cadquery.py
├─ references/
│  ├─ specifications.md
│  ├─ mechanical.md
│  ├─ compatibility-rules.md
│  ├─ integration.md
│  ├─ safety.md
│  └─ sources.md
├─ examples/usage.md
├─ tests/validation-cases.md
└─ CHANGELOG.md
```

## 安装

将整个 `dfr0026-ambient-light-sensor` 目录放入：

```text
hardware-skills/dfr0026-ambient-light-sensor/
```

目录名、`manifest.json` 的 `skillName` 与 `SKILL.md` 的 `name` 已保持一致。

## 验证状态

- 官方电气资料：已核对。
- MicroPython 示例：已完成 CPython 语法静态检查；未执行真实板卡验证。
- CadQuery 模型：已完成语法与参数一致性检查；当前环境没有 CadQuery，未执行几何内核。
- 机械尺寸：存在官方20 × 30 mm与用户模型30 × 22 mm冲突，紧配或制造前必须实物复核。

原始独立 MicroPython 示例和旧校验清单保存在数据目录的
`hardware-skill-import-backups` 中；应用允许的示例已合并到 `examples/usage.md`。
