# 掌问 Hardware Skill AI 编写与上线规范（v2）

本文是生成掌问 Hardware Skill 的权威编写规范，目标读者是任意大语言模型、自动化生成器和人工开发者。
只要最终目录与本文不一致，就不能声称“可被掌问直接导入”。

可复制源模板位于：

```text
services/local-api/zhangwen/hardware/hardware-skill-template/
```

## 0. 可直接交给 AI 的总指令

将下面这段指令和硬件原始资料一起交给 AI：

```text
你正在生成“掌问”的 Hardware Skill，不是在自由设计一个新的 Skill 格式。

必须遵守《掌问 Hardware Skill AI 编写与上线规范（v2）》：
1. 只生成规范白名单允许的文件，禁止增加 checksums.sha256、datasheet.pdf、src/、
   examples/*.py、任意嵌套代码文件或第二份 manifest。
2. 最终目录名、manifest.skillName、SKILL.md frontmatter.name 必须完全相同。
3. manifest.files 必须按规范顺序列出；manifest.json 本身不能放入 files。
4. 电气、规则、机械和验证 JSON 必须严格使用规范字段，不得增加自创字段。
5. 无法从资料确认的数据必须写入“不确定项”或 notes，不得猜测；不得伪造实测、官方认证、
   CadQuery 执行、实物装配或硬件测试结果。
6. 官方参数范围如果无法直接映射到单值字段，机器参数采用明确说明的保守推荐工作点，原始范围
   保留在 Markdown 正文和 notes 中。
7. 用户 Hardware Skill 的 mechanical profile 只能使用 model_kind=envelope；`mechanical.md` 的
   “自然语言描述”是 3D 预览唯一来源，AI 不得要求用户手工维护 `preview_geometry`。应用按需生成带
   描述 SHA-256 的派生缓存。cadquery.py 只能声明 REFERENCE_ONLY，不能获得文件、Shell、网络、
   串口或设备权限。
8. MicroPython 示例必须以内联代码块放在 examples/usage.md，不得新建额外 .py 文件。
9. 在计算哈希前执行敏感信息预扫描；API 文档中的 credential/password/token 只写参数名和运行时注入说明，
   不写“名称=示例值”，不保存真实密钥、Wi-Fi 密码或看似真实的占位凭据。
10. 最后计算模型 SHA、图片 SHA 和 package revision；哈希计算后不得再修改对应内容。
11. 用掌问实际仓储加载器读取整包，并确认它出现在 ACTIVE 列表；只看到目录存在不算上线成功。
12. 输出完整目录以及“AI 交付报告”，列出来源、不确定项、验证状态、所有哈希、revision 和应用可见性。

如果资料不足以形成有效包，停止并列出缺少的信息，不要生成看似完整但包含猜测的包。
```

## 1. AI 开始前必须取得的输入

| 输入 | 要求 | 缺失时处理 |
|---|---|---|
| `skillName` | 小写英文、数字、连字符组成的 slug | 根据型号生成并请求确认 |
| `componentId` | 全库唯一安全标识，例如 `hw_dfrobot_dfr0026` | 请求确认，禁止复用现有 ID |
| 名称与类别 | 类别只能是 `MCU/SENSOR/ACTUATOR/DISPLAY/POWER/STRUCTURE` | 请求确认 |
| 电气事实 | 推荐工作电压、逻辑/模拟输入基线、峰值电流、协议 | 未知值明确标注，不得猜测 |
| 集成资料 | 接线、驱动、固件/API 和初始化方法 | 缺失部分写“待板卡验证” |
| 安全边界 | 过压、过流、反接、功率、机械或环境风险 | 采用保守限制并标注依据 |
| 来源 | 官方产品页、数据手册、用户测量或参考模型标识 | 无来源不能提升验证等级 |
| 结构事实 | 包络、坐标系、安装孔、接口、开孔、避让区 | 不足时省略机械能力，不得造尺寸 |
| 模型状态 | 仅语法检查、内核执行、实物验证分别说明 | 没运行就写未运行 |
| 图片 | 本地 JPEG/PNG/WebP、来源页、署名和授权边界 | 无合法本地图片就不声明 media |

推荐验证等级：

- `MIGRATED_UNVERIFIED`：从旧库迁移，尚未人工核对。
- `USER_CONFIRMED`：用户确认过当前事实。
- `VERIFIED`：完成了明确记录的本地验证。
- `OFFICIAL_DOC_VERIFIED`：关键事实逐项核对官方资料。

机械模型的 `verificationStatus` 只能使用：

- `USER_CONFIRMED`
- `VERIFIED_REFERENCE`
- `OFFICIAL_DOC_VERIFIED`

## 2. 最终目录白名单

推荐的统一包如下。标记“可选”的文件没有使用时，必须从磁盘和 `manifest.files` 同时移除。

```text
<skillName>/
├── manifest.json                              必需；不能列入 manifest.files
├── README.md                                  可选，推荐
├── CHANGELOG.md                               可选
├── SKILL.md                                   必需
├── assets/                                    可选；只放 manifest.media 声明的图片
│   ├── cover.webp
│   └── <gallery-name>.png
├── references/
│   ├── specifications.md                      必需
│   ├── compatibility-rules.md                 必需
│   ├── mechanical.md                          与 models/cadquery.py 成对可选
│   ├── integration.md                         必需
│   ├── safety.md                              必需
│   └── sources.md                             必需
├── models/
│   └── cadquery.py                            与 mechanical.md 成对可选
├── examples/
│   └── usage.md                               必需；代码以内联 fenced block 保存
└── tests/
    └── validation-cases.md                    必需
```

最终包禁止出现：

- `manifest.template.json`（必须重命名为 `manifest.json`）；
- `checksums.sha256`；
- PDF、Word、Excel、压缩包或原始网页；
- `examples/*.py`、`src/`、`docs/` 或其他自定义目录；
- `__pycache__`、`.pyc`、日志、构建产物和隐藏文件；
- 未在 `manifest.media` 中声明的图片；
- 符号链接。

实际文件集合必须严格等于：

```text
manifest.json + manifest.files + manifest.media[*].path
```

多一个或少一个文件，整个包都会被隔离。

## 3. 全局边界

- 所有文本使用 UTF-8 和 LF 换行；禁止 NUL 字符。
- 单个文本文件不超过 80,000 bytes；全部声明文本不超过 300,000 bytes。
- 最多 6 张图片；单张不超过 2 MiB；全部图片不超过 8 MiB。
- Markdown 本地链接只能指向本规范白名单中的文件。
- 禁止写入主机绝对路径、真实串口标识、API Key、Token、Wi-Fi 密码或个人隐私数据。
- 不得用 Hardware Skill 文本授予文件、Shell、网络、串口、上传、擦除 Flash 或固件烧录权限。
- 事实写在 Markdown；SQLite 组件与机械档案只是应用生成的投影，不能成为第二真源。

### 3.1 敏感信息扫描与 API 文档占位值

应用会扫描所有声明文本，而不只扫描代码块。出现以下名称并紧跟 `:` 或 `=` 和具体非空值时，整包会被
隔离：`api key`、`access token`、`secret`、`password`、`wifi password/passphrase`。`sk-...` 和
`Bearer ...` 形态也会被拒绝。

为了兼容仍在运行的旧版 Sidecar，AI 应使用以下稳定写法：

```markdown
构造函数接受 `user` 和 `password` 两个可选凭据参数；凭据必须在运行时从安全配置注入，禁止写回 Skill。
```

不要在 Hardware Skill 中写：

```text
password=<某个值>
api_key=<某个值>
WIFI_PASSWORD=<某个值>
```

即使右侧只是 `None`、`null` 或示例字符串，也不应依赖某个版本的扫描器是否把它识别为安全占位值。
如果必须记录官方函数签名，可省略凭据默认值，并在签名下单独列出凭据参数名和运行时注入边界。

### 3.2 “目录存在”与“应用可见”不是同一状态

一个 Hardware Skill 只有同时满足下列条件才会出现在硬件库：

1. 目录名、`manifest.skillName`、`SKILL.md` 的 `name` 完全一致。
2. `manifest.status` 为 `ACTIVE`。
3. 文件集合、机器 JSON、模型 SHA、媒体 SHA 和 package revision 全部有效。
4. `componentId` 在活动目录中唯一。
5. 所有文本通过路径、串口、凭据和隐私边界扫描。
6. 使用应用实际的 `HardwareSkillRepository.get_skill()` 能加载，并且 `list_active_components()` 能列出。

列表读取会隔离单个无效包，以保证其他硬件仍可使用。因此“其他硬件正常显示，但新目录没有显示”通常意味着
新包被逐包隔离；必须直接加载目标 `skillName` 查看第一条校验错误，不能只检查 SQLite 或反复复制目录。

## 4. `manifest.json` 精确模板

`files` 的顺序固定为下面白名单顺序，未使用的可选文件只能跳过，不能改变剩余顺序。

```json
{
  "schema": "zhangwen.hardware-skill-manifest/v1",
  "schemaVersion": 1,
  "skillName": "<skill-name>",
  "componentId": "<unique-component-id>",
  "displayName": "<硬件显示名称>",
  "description": "<一句话用途和边界>",
  "status": "ACTIVE",
  "sourceKind": "MANUAL",
  "files": [
    "README.md",
    "CHANGELOG.md",
    "SKILL.md",
    "references/specifications.md",
    "references/compatibility-rules.md",
    "references/mechanical.md",
    "references/integration.md",
    "references/safety.md",
    "references/sources.md",
    "models/cadquery.py",
    "examples/usage.md",
    "tests/validation-cases.md"
  ],
  "media": [
    {
      "path": "assets/cover.webp",
      "role": "cover",
      "alt": "<名称、视角和可见特征>",
      "contentType": "image/webp",
      "sha256": "<图片原始字节的64位小写SHA-256>",
      "sourceUrl": "https://<图片来源页>",
      "attribution": "<权利人或来源方>",
      "license": "<授权说明或公开再分发限制>"
    }
  ],
  "revision": "<24位小写内容revision>",
  "createdAt": "<ISO-8601时间>",
  "updatedAt": "<ISO-8601时间>"
}
```

规则：

- 不使用 `CHANGELOG.md` 时，同时删除磁盘文件和 `files` 中该行。
- 没有结构能力时，同时删除 `references/mechanical.md` 和 `models/cadquery.py` 两行及磁盘文件。
- 没有图片时使用 `"media": []`，不要创建空图片文件。
- `role` 只能是 `cover` 或 `gallery`；最多一张 `cover`。
- `contentType` 只能是 `image/jpeg`、`image/png`、`image/webp`。
- `sourceKind` 可用 `MANUAL/UPLOAD/DIALOGUE/MIGRATED/BUNDLED`；用户或 AI 离线编写使用 `MANUAL`。
- `revision` 最后计算，不能手写随机值。

## 5. `SKILL.md` 精确模板

frontmatter 只能有 `name` 和 `description`，不能增加第三个字段。

```markdown
---
name: <skill-name>
description: <硬件用途、关键接口和使用边界>
---

# <硬件显示名称>

本 Skill 为 <型号> 提供电气、兼容、集成、结构和安全事实。

## 核心边界

- <最重要的供电或接口边界>
- <最重要的安全边界>
- <未验证事实和使用限制>

## 渐进加载

- [结构化电气参数](references/specifications.md)
- [兼容规则](references/compatibility-rules.md)
- [结构与机械档案](references/mechanical.md)
- [集成说明](references/integration.md)
- [安全边界](references/safety.md)
- [资料来源](references/sources.md)
- [使用示例](examples/usage.md)
- [验证用例](tests/validation-cases.md)
- [CadQuery 参考模型](models/cadquery.py)
```

如果没有机械能力，必须同时移除最后一条模型链接和机械档案链接。

## 6. `references/specifications.md` 精确模板

该文件必须且只能包含一个 `zhangwen:hardware-spec:v1` fenced JSON。JSON 不允许增加字段。

````markdown
# 结构化电气参数

## 工程摘要

- 官方工作范围：<原始范围和单位>。
- 推荐接入基线：<为什么机器参数选择下面的单值>。
- 未知项：<明确列出>。

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "<unique-component-id>",
  "name": "<硬件显示名称>",
  "category": "SENSOR",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": 3.0,
    "voltageMax": 5.0,
    "supplyVoltages": [],
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "ANALOG",
    "i2cAddress": null,
    "supportedMCUs": ["unihiker-k10"],
    "driverName": "machine.ADC",
    "firmwareRequirement": "MicroPython with machine.ADC support"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": [],
  "notes": "<原始范围、推荐基线、未知参数和使用限制>",
  "verificationStatus": "USER_CONFIRMED",
  "sourceIds": ["<source-id>"]
}
```
````

允许字段只有：

| 层级 | 字段 |
|---|---|
| 根 | `schema/componentId/name/category/electrical/stock/price/ageRecommendation/safetyTags/notes/verificationStatus/sourceIds` |
| electrical | `voltage/voltageMin/voltageMax/supplyVoltages/logicLevel/peakCurrent/communicationProtocol/i2cAddress/supportedMCUs/driverName/firmwareRequirement` |

禁止在 JSON 中增加 `signal`、`connector`、`measurement`、`currency`、
`stockStatus` 或 `mechanicalSummary`。这些信息应写在 fenced JSON 外的 Markdown 和 `notes`。

字段处理规则：

- `voltage`：推荐或标称工作点，必须位于 `voltageMin/voltageMax` 内。
- `voltageMin/voltageMax`：器件可接受的连续供电范围；只有单一工作点时两者都等于 `voltage`。不得把未经来源确认的绝对最大值当作正常工作范围。
- `supplyVoltages`：该器件对其他外设实际暴露的离散电源轨，仅 MCU/POWER 等供电来源填写，例如 `[3.3, 5.0]`；普通传感器填 `[]`。它不是连续范围，不能写成任意中间电压。
- `logicLevel`：数字信号写逻辑电平；模拟器件写推荐接入时 ADC 需要承受的信号基线。
- `peakCurrent`：未知但 Schema 要求时填 `0.0`，必须在 `notes` 明确“0 表示未知，不表示零电流”。
- `communicationProtocol`：使用稳定短标识，如 `GPIO/I2C/SPI/UART/ANALOG/PWM`。
- `supportedMCUs`：只写有依据的平台标识；无依据使用空数组。
- `driverName/firmwareRequirement`：未知使用 `null`，不要编造包名。

## 7. `references/compatibility-rules.md` 精确模板

该文件必须且只能包含一个 `zhangwen:hardware-rules:v1` fenced JSON。对普通传感器，推荐从下列
四条规则开始：

````markdown
# 声明式兼容规则

```zhangwen:hardware-rules:v1
{
  "schema": "zhangwen.hardware-rules/v1",
  "rules": [
    {
      "id": "voltage-<component-id>",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "允许工作电压范围与主控外设电源轨不匹配。",
      "params": {
        "field": "electrical.voltage",
        "leftCategories": ["SENSOR"],
        "rightCategories": ["MCU"],
        "tolerance": 0.5,
        "componentId": "<component-id>"
      }
    },
    {
      "id": "logic-level-<component-id>",
      "operator": "range-overlap",
      "severity": "FAIL",
      "message": "信号电平与主控不兼容。",
      "params": {
        "field": "electrical.logicLevel",
        "leftCategories": ["SENSOR"],
        "rightCategories": ["MCU"],
        "tolerance": 0.3,
        "componentId": "<component-id>"
      }
    },
    {
      "id": "mcu-support-<component-id>",
      "operator": "contains-any",
      "severity": "FAIL",
      "message": "器件未声明支持当前主控。",
      "params": {
        "field": "electrical.supportedMCUs",
        "candidateField": "identifiers",
        "subjectCategories": ["SENSOR"],
        "candidateCategories": ["MCU"],
        "componentId": "<component-id>"
      }
    },
    {
      "id": "driver-required-<component-id>",
      "operator": "required-if",
      "severity": "WARNING",
      "message": "器件有固件要求，但未登记驱动入口。",
      "params": {
        "requiredField": "electrical.driverName",
        "ifField": "electrical.firmwareRequirement",
        "ifPresent": true,
        "componentId": "<component-id>"
      }
    }
  ]
}
```
````

规则引擎只允许以下算子和字段组合：

| operator | 核心字段 | 用途 |
|---|---|---|
| `range-overlap` | `electrical.voltage` 或 `electrical.logicLevel` | 电压规则从主控 `supplyVoltages` 中选择落入器件 `voltageMin/voltageMax` 且最接近 `voltage` 的电源轨；电平规则仍独立比较信号基线 |
| `sum-lte` | `electrical.peakCurrent` | POWER 类电流预算 |
| `unique` | `electrical.i2cAddress` | 非空 I2C 地址冲突 |
| `contains-any` | `electrical.supportedMCUs` 对 `identifiers` | 主控支持列表 |
| `required-if` | `electrical.driverName` 对 `electrical.firmwareRequirement` | 驱动登记完整性 |

其余算子的精确参数模板：

```json
{
  "i2cUnique": {
    "id": "i2c-address-<component-id>",
    "operator": "unique",
    "severity": "FAIL",
    "message": "I2C 地址被多个组件占用。",
    "params": {
      "field": "electrical.i2cAddress",
      "whenField": "electrical.communicationProtocol",
      "whenEquals": "I2C",
      "componentId": "<component-id>"
    }
  },
  "powerBudget": {
    "id": "current-budget-<component-id>",
    "operator": "sum-lte",
    "severity": "FAIL",
    "message": "供电电流不足，存在掉电或过热风险。",
    "params": {
      "field": "electrical.peakCurrent",
      "sumCategories": ["MCU", "SENSOR", "ACTUATOR", "DISPLAY"],
      "limitCategories": ["POWER"]
    }
  }
}
```

上面的 `i2cUnique` 和 `powerBudget` 只是文档分组名，真正写入 `rules` 数组时只放各自内部的规则对象，
不能把这两个分组名写进机器 JSON。

按类别选择规则：

| 类别 | 必需规则 |
|---|---|
| `SENSOR/ACTUATOR/DISPLAY` | voltage、logic-level、required-if；supportedMCUs 非空时加 contains-any；非空 I2C 地址再加 unique |
| `MCU` | required-if；不要为自身生成传感器对主控的 range-overlap |
| `POWER` | sum-lte、required-if |
| `STRUCTURE` | required-if；其他结构限制写机械档案和人工检查 |

覆盖要求：

- 所有包至少有一条 `required-if`。
- 除 `MCU/POWER/STRUCTURE` 外，必须同时有 voltage 和 logicLevel 的 `range-overlap`。
- `supportedMCUs` 非空且类别不是 MCU 时，必须有 `contains-any`。
- I2C 且 `i2cAddress` 非空时，必须有 `unique`。
- POWER 类必须有 `sum-lte`。

禁止使用 `ifGreaterThanField`、`fixture`、任意 `integration.*`、`board.*`、`mechanical.*` 路径或表达式。
无法表达的复杂规则写成 JSON 块外的“人工检查项”，不能伪装成可执行规则。

## 8. `references/mechanical.md` 精确模板

机械能力是可选的，但 `mechanical.md` 与 `models/cadquery.py` 必须同时存在或同时不存在。
用户创建的普通器件只能使用 `model_kind: "envelope"`。

### 8.1 3D 预览资料与精度等级

应用中的“查看 3D 预览”不执行 `models/cadquery.py`。点击按钮后，Sidecar 只截取当前
`references/mechanical.md` 的“## 自然语言描述”章节，计算规范化 SHA-256，并把该文本交给结构化模型。
模型只能返回受控基本体；本地 Schema 通过后，结果作为带 `source_sha256` 的派生缓存回写同一 Skill。
缓存与描述哈希一致时直接打开；描述改变、缓存缺失或缓存过期时重新生成。用户和编写 AI 只维护自然
描述，不需要预先生成图片、项目 CAD 产物或第二份几何真值。

| 目标精度 | 必需资料 | 预览能力 |
|---|---|---|
| 基础包络 | `dimensions`、`coordinate_system`、`model_kind=envelope` | 显示器件长宽高和方向 |
| 可用于结构设计 | 再提供 `mounting`、孔中心/直径、`openings`、`keepouts` 和间隙 | 显示安装孔、壳体开口及线缆/感应禁布区 |
| 外观辨识 | 自然描述中逐项给出 PCB、探头、连接器等实体的形状、尺寸和坐标 | 应用按需编译后分别显示，而非一个总包络盒 |
| 制造级复现 | 来源明确且经过审核的 STEP/STL/GLB 或平台受信参数模型 | 可与制造 CAD 对照；当前普通 Skill 导入尚不直接消费这些二进制模型 |

AI 必须优先索取：整体长/宽/高和测量基准；原点及 XYZ 正方向；安装面与安装方式；孔中心坐标、
孔径和紧固件；每个接口/传感窗口的形状、尺寸、中心、所在面和装配间隙；线缆弯折、光学视场、
运动件及其他禁布区的中心和三轴尺寸。缺失项写“待实物验证”，不得由产品图片猜入 JSON。
自然语言中已经给出且来源可信的尺寸会原样编译为声明式实体；自然语言没有给出的尺寸不得补猜。

````markdown
# 结构描述与机械档案

## 自然语言描述

记录尺寸基准、原点、方向、安装孔、接口、开孔、活动空间、线缆和禁布区。
不确定尺寸写“待实物验证”，不得填入机器 JSON。

保存前把包络、安装、孔位、开口和禁布区等工程事实转换到下面的机器 JSON。3D 外观实体只需要写在
上面的自然描述；首次点击预览时应用自动生成缓存，描述变化后自动失效。若没有有效机器 JSON，应用
仍必须拒绝机械档案；这不代表可以从描述猜测缺失的工程尺寸。

## 机器可读机械档案

```zhangwen:hardware-mechanical:v1
{
  "schema": "zhangwen.hardware-mechanical/v1",
  "profile": {
    "profile_id": "<lowercase_profile_id>",
    "display_name": "<硬件显示名称>",
    "category": "sensor",
    "roles": ["sensor"],
    "dimensions": {
      "length_x": 30.0,
      "width_y": 20.0,
      "height_z": 8.0
    },
    "coordinate_system": {
      "origin": "envelope_center",
      "x_axis": "length",
      "y_axis": "width",
      "positive_z": "height"
    },
    "mounting": {
      "mode": "envelope_only",
      "preferred_surface": "external",
      "strategy": "none",
      "clearance": 0.8,
      "mating_hardware_face": null,
      "allowed_enclosure_surfaces": [],
      "holes": []
    },
    "model_kind": "envelope",
    "keepouts": [],
    "openings": []
  },
  "model": {
    "path": "models/cadquery.py",
    "sha256": "<规范化模型源码的64位小写SHA-256>",
    "verificationStatus": "USER_CONFIRMED",
    "executionPolicy": "REFERENCE_ONLY"
  }
}
```
````

禁止项：

- `profile` 内禁止提供 `revision` 和 `source`，这两个字段由应用生成。
- 普通用户包禁止使用 `unihiker_k10` 等注册模型身份。
- `model` 只允许 `path/sha256/verificationStatus/executionPolicy`。
- 禁止把 `componentId/units/envelope/connector/sensorBody/sourceConflict` 直接放在机械 JSON 根部；
  这些信息应转换为 `profile` 字段或写在 Markdown 正文。

机械枚举和范围：

| 字段 | 允许值/范围 |
|---|---|
| `profile_id/category/roles` 标识 | 小写字母开头，后续小写字母、数字、下划线或连字符；`profile_id` 最长 64 字符 |
| `dimensions.*` | 大于 0 且不超过 800 mm |
| `coordinate_system.origin` | `envelope_center` 或 `pcb_center` |
| `coordinate_system.x_axis/y_axis` | 固定为 `length/width` |
| `coordinate_system.positive_z` | `height` 或 `component_side` |
| `mounting.mode` | `envelope_only/external_independent_module/base_floor/lid_inner/lid_outer/front_inner/back_inner/left_inner/right_inner/inner_surface` |
| `mounting.preferred_surface` | `base_floor/lid_inner/lid_outer/front_inner/back_inner/left_inner/right_inner/external` |
| `mounting.strategy` | `none/hole_fastened/edge_retainer` |
| `mating_hardware_face` | `+X/-X/+Y/-Y/+Z/-Z` 或 `null` |
| `mounting.clearance` | 0–10 mm |
| 安装孔直径 | 1–20 mm；`hole_fastened` 至少需要一个孔 |
| `openings[*].kind` | `circle` 或 `rectangle` |
| opening `preferred_face` | `top/bottom/left/right/front/back` |
| 应用派生的 `preview_geometry` | 用户/编写 AI 不填写；应用生成 1–32 个受控基本体并写入当前自然描述的 `source_sha256` |
| 派生 primitive | 只允许 `box/rounded_box/cylinder`、`add/cut` 和 `0/90/180/270` 度；禁止代码、路径、URL、网格或自由曲面 |

当 `allowed_enclosure_surfaces` 非空时，必须包含 `preferred_surface`。`edge_retainer` 只允许
`base_floor` 模式和表面。roles、安装孔 ID、开孔 ID 必须各自唯一。

常用机械字段形状：

```json
{
  "mounting": {
    "mode": "external_independent_module",
    "preferred_surface": "external",
    "strategy": "hole_fastened",
    "clearance": 0.8,
    "mating_hardware_face": null,
    "allowed_enclosure_surfaces": ["external"],
    "holes": [
      {
        "hole_id": "h1",
        "center": {"x": -10.0, "y": 5.0},
        "diameter": 3.0,
        "fastener": "M3"
      }
    ]
  },
  "keepouts": [
    {
      "keepout_id": "cable_zone",
      "center": {"x": 20.0, "y": 0.0, "z": 4.0},
      "size": {"length_x": 10.0, "width_y": 8.0, "height_z": 8.0}
    }
  ],
  "openings": [
    {
      "kind": "circle",
      "opening_id": "sensor_view",
      "center": {"x": 0.0, "y": 0.0},
      "center_z": 2.0,
      "diameter": 5.0,
      "preferred_face": "front",
      "clearance": 0.8
    }
  ]
}
```

## 9. `models/cadquery.py` 模板

该文件是可审计参考源码，不是应用自动执行入口。禁止文件读写、网络、Shell、串口、设备控制、动态执行
和凭据访问。推荐提供纯 `build_model()`：

```python
from __future__ import annotations

import cadquery as cq


LENGTH_X = 30.0
WIDTH_Y = 20.0
HEIGHT_Z = 8.0


def build_model():
    return cq.Workplane("XY").box(
        LENGTH_X,
        WIDTH_Y,
        HEIGHT_Z,
        centered=(True, True, False),
    )


if __name__ == "__main__" and "show_object" in globals():
    show_object(build_model(), name="hardware_reference")
```

允许宣称的状态必须与实际证据一致：

- 只通过 `ast.parse`：只能称“Python 语法通过”。
- 真正加载 CadQuery 并构建有效实体：可以记录“内核执行通过”。
- 导出 STEP/STL：只说明导出通过，不能等同实物验证。
- 卡尺和装配测试：必须记录设备、日期、方法和结果后才可称实物验证。

## 10. 其余 Markdown 文件模板

### `references/integration.md`

至少包含：引脚/线色表、推荐供电、上电前检查、固件/API、初始化步骤、故障排查、板卡差异。不能把
未经目标 Board Skill 确认的 GPIO/ADC 通道写成通用事实。

### `references/safety.md`

至少包含：禁止操作、电气上限、接线顺序、过压/过流/反接措施、环境和机械风险、未确认事项。

### `references/sources.md`

使用表格逐项记录来源：

```markdown
| sourceId | 类型 | URL/标识 | 支持的事实 | 核对状态 |
|---|---|---|---|---|
| vendor-product:model | 官方产品页 | https://... | 供电、接口 | 已核对 |
| user-model:model-date | 用户模型 | 用户提供 | 包络、孔位 | 待实物复核 |
```

不能把搜索摘要、AI 推断或无法定位的网页当作官方证据。

### `examples/usage.md`

所有代码只能作为 Markdown fenced code 内联保存。必须说明目标固件、板卡差异、未实测状态和安全接线。
禁止再创建 `examples/*.py`。

### `README.md`

只写包用途、目录、安装、验证状态和已知限制。不要在 README 复制第二份机器参数 JSON。

### `CHANGELOG.md`

可选。只记录 revision 之间的事实变化和验证提升，不记录凭据、真实串口或个人路径。

## 11. `tests/validation-cases.md` 精确模板

机器块每个 case 只能有 `id/components/expectedOverall` 三个字段。

````markdown
# 本地验证用例

```zhangwen:hardware-validation:v1
{
  "schema": "zhangwen.hardware-validation/v1",
  "cases": [
    {
      "id": "canonical-self-smoke",
      "components": ["$self"],
      "expectedOverall": ["PASS", "WARNING", "FAIL"]
    }
  ]
}
```

## 人工验收

1. <真实硬件、电气或结构检查>
2. <尚未执行的验证>
````

约束：

- 每个 case 必须且只能包含一次 `"$self"`。
- 其他组件必须写成完整的 `HardwareSkillSpecification` JSON 对象，不能使用字符串别名。
- 禁止添加 `fixture`、`expectedMessage` 或其他字段。
- 没有完整组合器件对象时，只保留 self smoke；复杂场景写在“人工验收”中。

## 12. 哈希与 revision

### 12.1 CadQuery 模型 SHA

先把 `models/cadquery.py` 的 CRLF/CR 统一为 LF，再对 UTF-8 字节计算 SHA-256。把 64 位小写结果写入
`mechanical.md` 的 `model.sha256`。

```python
from hashlib import sha256
from pathlib import Path

text = Path("models/cadquery.py").read_text(encoding="utf-8")
text = text.replace("\r\n", "\n").replace("\r", "\n")
print(sha256(text.encode("utf-8")).hexdigest())
```

### 12.2 图片 SHA

图片对原始二进制字节计算 SHA-256，不做文本规范化：

```python
from hashlib import sha256
from pathlib import Path

print(sha256(Path("assets/cover.webp").read_bytes()).hexdigest())
```

### 12.3 Package revision

revision 覆盖所有声明文本的“路径 + NUL + 规范化内容 + NUL”，再覆盖按路径排序的 media 元数据。
图片本体通过 `media.sha256` 间接绑定。最终取 SHA-256 前 24 位小写十六进制。

在最终目录中运行以下独立脚本；它同时检查 `files` 顺序并回写 `manifest.json`：

```python
from hashlib import sha256
import json
from pathlib import Path
import sys

ALLOWED = (
    "README.md",
    "CHANGELOG.md",
    "SKILL.md",
    "references/specifications.md",
    "references/compatibility-rules.md",
    "references/mechanical.md",
    "references/integration.md",
    "references/safety.md",
    "references/sources.md",
    "models/cadquery.py",
    "examples/usage.md",
    "tests/validation-cases.md",
)

root = Path(sys.argv[1]).resolve()
manifest_path = root / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
declared = manifest["files"]
expected = [path for path in ALLOWED if path in set(declared)]
if declared != expected or len(declared) != len(set(declared)):
    raise SystemExit("manifest.files is duplicated, unknown, or out of order")

digest = sha256()
for relative in ALLOWED:
    if relative not in declared:
        continue
    text = (root / relative).read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    digest.update(relative.encode("utf-8"))
    digest.update(b"\0")
    digest.update(text.encode("utf-8"))
    digest.update(b"\0")

for item in sorted(manifest.get("media", []), key=lambda value: value["path"]):
    digest.update(b"media\0")
    digest.update(
        json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    digest.update(b"\0")

manifest["revision"] = digest.hexdigest()[:24]
manifest_path.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
    newline="\n",
)
print(manifest["revision"])
```

计算顺序必须是：完成文本 → 计算模型 SHA → 更新 mechanical.md → 计算图片 SHA → 更新 manifest.media
→ 最后计算 revision。revision 生成后再改任何声明文本或媒体元数据，都必须重算。

不要复制旧 `revision` 或在修改单个 Markdown 后继续使用原值。应用会隔离指纹不一致的包：公共列表继续加载其他有效器件，但该包不能被打开、编辑、选入项目或进入三师上下文。修复时应运行上面的完整脚本并再次执行整包导入校验，不要只手填一个看似合法的 24 位值。

## 13. AI 交付报告格式

AI 在生成目录后必须输出以下报告，不能只说“已完成”：

```text
skillName: <...>
componentId: <...>
category: <...>
sourceKind: MANUAL
declaredFiles: <按 manifest 顺序逐项列出>
mediaFiles: <逐项列出或 none>
electricalBaseline: <机器单值及其选择理由>
officialRangesPreservedInProse: <yes/no>
mechanicalProfile: <profile_id 或 none>
modelVerification: <语法/内核/导出/实物分别说明>
modelSha256: <值或 none>
mediaSha256: <值或 none>
packageRevision: <24位值>
unknowns: <所有未知项>
manualChecks: <上线前仍需执行的项目>
claimsNotMade: <未执行的真实硬件/CAD/授权验证>
```

## 14. 最终检查清单

AI 和人工必须逐项确认：

- [ ] 目录名、`manifest.skillName`、`SKILL.md name` 完全一致。
- [ ] `componentId` 在目标硬件库中唯一。
- [ ] 实际文件严格等于 manifest、声明文本和 media 图片的并集。
- [ ] `manifest.files` 没有 manifest、checksum、PDF 或额外代码文件，且顺序正确。
- [ ] 四个机器 fenced block 各自只出现一次，JSON 没有扩展字段。
- [ ] 所有必需规则覆盖满足当前类别和协议。
- [ ] 机械描述与模型成对存在或成对省略。
- [ ] 普通器件使用 `model_kind=envelope`，模型为 `REFERENCE_ONLY`。
- [ ] 自然语言中逐项写明每个需要显示的 PCB、连接器、探头或主体的形状、尺寸、中心和基准；没有手工伪造派生缓存。
- [ ] 模型 SHA 使用规范化文本计算；图片 SHA 使用原始字节计算。
- [ ] revision 最后计算且为 24 位小写十六进制。
- [ ] Markdown 链接没有指向白名单外路径。
- [ ] 没有绝对路径、真实串口、密钥、密码或隐私数据。
- [ ] API 文档没有把 `password/token/key/secret` 写成“名称=示例值”；凭据参数只说明运行时注入。
- [ ] 所有未知、冲突、未运行和未实测项目都明确写出。
- [ ] 没有把语法通过写成 CadQuery 内核通过，没有把模型导出写成实物验证。
- [ ] 导入后应用中能同时看到 ACTIVE 组件和同 revision 的机械档案关联。
- [ ] 使用应用真实仓储加载器对目标 skill 执行 `get_skill()` 成功，并在 `list_active_components()` 中命中。

## 15. 常见失败与修正

| 失败 | 为什么被隔离 | 正确做法 |
|---|---|---|
| `manifest.files` 包含 `manifest.json` | manifest 不是内容文件 | 从 files 移除 |
| 增加 `checksums.sha256` | 不在白名单 | 删除；使用规定的模型/media/revision 哈希字段 |
| 增加 `examples/demo.py` | 示例目录只允许 `usage.md` | 把代码合并为 Markdown fenced block |
| 把外设 3–5V 工作范围写成 MCU `supplyVoltages: [3,4,5]` | 连续允许范围与离散供电轨语义混淆 | 外设写 `voltageMin=3/voltageMax=5`；MCU 只写真实暴露的离散轨，如 `[3.3,5.0]` |
| 机械 JSON 自创 `envelope/connector` 根字段 | 不符合 `profile + model` 结构 | 转换为 dimensions/mounting/keepouts/openings |
| model 使用 `executionMode` | 字段名错误 | 使用 `executionPolicy: REFERENCE_ONLY` |
| validation case 增加 `fixture` | case 只允许三个字段 | 移到人工验收 |
| 规则引用 `integration.*` | 规则字段不在白名单 | 降级为 Markdown 人工检查项 |
| revision 随机填写或修改内容后沿用旧值 | 内容指纹不匹配，该包被隔离 | 用第 12.3 节完整算法重算并重新校验整包 |
| 图片只写 URL | 应用只展示本地校验图片 | 保存合法本地图片并填写 SHA/来源/授权 |
| API 文档写 `password=None` 或类似默认参数 | 旧版凭据扫描会把参数默认值误判为已保存密码，整包被隔离 | 函数签名省略凭据默认值；在正文只列凭据参数名并说明运行时安全注入 |
| 目录存在但硬件库不显示 | ACTIVE、revision、媒体、敏感信息或 componentId 任一校验失败，列表会逐包隔离 | 直接用实际仓储 `get_skill(skillName)` 获取首个错误；修复后重算 revision，再验证 ACTIVE 列表和应用投影 |
