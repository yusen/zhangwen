# 掌问 Hardware Skill 可复制模板

这是“最小统一包”模板：包含电气、兼容、结构、CadQuery 参考模型、集成、安全、来源、示例和验证用例。
面向 AI 的完整权威规范位于仓库 `docs/HARDWARE_SKILL_AI_AUTHORING_GUIDE.md`。生成新硬件包前必须完整阅读该文档，不能从其他 Skill 格式推断字段。

## 最终文件白名单

复制后允许保留的文件只有：

```text
<skill-name>/
├── manifest.json
├── README.md
├── SKILL.md
├── references/
│   ├── specifications.md
│   ├── compatibility-rules.md
│   ├── mechanical.md
│   ├── integration.md
│   ├── safety.md
│   └── sources.md
├── models/cadquery.py
├── examples/usage.md
└── tests/validation-cases.md
```

`CHANGELOG.md` 和 `assets/<image>` 可以按权威规范选配；没有使用时不能创建。最终包禁止出现
`manifest.template.json`、`checksums.sha256`、PDF、额外 `.py` 示例、`src/`、`docs/`、缓存或其他自定义文件。

## AI 编写步骤

1. 复制本目录到临时工作区。
2. 把 `manifest.template.json` 重命名为 `manifest.json`，最终目录中不能同时保留两个 manifest。
3. 选择全库唯一的 `componentId` 和安全小写 slug；目录名、`manifest.skillName`、`SKILL.md name` 必须相同。
4. 从来源资料提取事实。不能确认的参数写入 Markdown“不确定项”，不得猜测或伪造测试状态。
5. 严格替换模板 JSON 的占位值，不得增加自创字段。
6. 官方电压等范围无法映射到单值时，机器字段写有理由的保守推荐工作点，完整范围保留在正文和 notes。
7. MicroPython 示例以内联 fenced code 写入 `examples/usage.md`，不得创建额外代码文件。
8. 修改 `models/cadquery.py` 后，按 UTF-8/LF 规范化内容计算 SHA-256，更新 `mechanical.md`。
9. 如需图片，先加入合法本地 JPEG/PNG/WebP，再按权威规范增加 `manifest.media`，填写原始字节 SHA、来源、署名和授权边界。
10. 所有内容完成后最后计算 manifest revision；此后改动任意声明文件或 media 元数据都必须重算。
11. 对全部文本执行凭据预扫描；网络凭据只列参数名和“运行时安全注入”说明，不写
    `password/token/key/secret` 的赋值示例。
12. 把包放入 `<data_dir>/hardware-skills/<skill-name>/`，使用应用实际仓储加载器执行目标 `get_skill()`，
    并确认 `list_active_components()` 能列出；只看到目录存在不能声称导入完成。

## 单一事实源映射

- `specifications.md`：硬件目录、电气参数和组合规则输入。
- `compatibility-rules.md`：只保存当前规则引擎白名单可执行的规则；复杂判断写成人工检查项。
- `mechanical.md`：自然描述和严格机器机械档案。
- `cadquery.py`：与机械档案 SHA 绑定的 `REFERENCE_ONLY` 参考源码，不因普通保存执行。
- `integration.md`：接线、固件、初始化和板卡差异。
- `safety.md`：电气、结构和操作安全边界。
- `sources.md`：每项事实、图片和模型的证据来源。
- `usage.md`：仅保存内联示例与上板前检查。
- `validation-cases.md`：严格三字段机器 case 和人工验收列表。

SQLite 中的硬件组件和机械档案只是应用生成的投影。Board Skill 只能提供板级 MicroPython API 与部署模板，不能复制本包的电气或结构事实。

## 必须拒绝的生成结果

- manifest 把自身列入 `files`，或 files 顺序与权威白名单不同；
- 磁盘上存在任何未声明文件；
- 电气 JSON 增加白名单外的 `signal/connector/measurement` 等扩展字段，或把连续工作范围误填为离散 `supplyVoltages`；
- 机械 JSON 不使用 `profile + model` 形状；
- 规则使用 `integration.*`、`board.*`、动态表达式或未支持算子；
- validation case 增加 `fixture`，或使用字符串组件别名；
- 把 Python 语法通过写成 CadQuery 内核或实物装配通过；
- 模型、图片或 package revision 哈希不匹配；
- 包含绝对路径、真实串口、密钥、密码或隐私数据。
- API 文档把凭据参数写成 `password/token/key/secret = 示例值`，导致包被敏感信息扫描隔离。

## 图片对象模板

默认 `manifest.template.json` 使用 `"media": []`，因此不要求图片。如需封面，改为：

```json
"media": [
  {
    "path": "assets/cover.webp",
    "role": "cover",
    "alt": "<名称、视角和关键可见特征>",
    "contentType": "image/webp",
    "sha256": "<图片原始字节的64位小写SHA-256>",
    "sourceUrl": "https://<图片来源页>",
    "attribution": "<权利人或来源方>",
    "license": "<授权说明或公开再分发限制>"
  }
]
```

图片只负责展示，不得成为电气、结构、兼容或安全事实的替代来源。
