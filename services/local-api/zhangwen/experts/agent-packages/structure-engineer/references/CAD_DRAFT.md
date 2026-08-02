# CAD 声明式草稿

## 数据来源

- 只使用上下文 `cadCapability` 中列出的模板、参数、范围和输出类型。
- 只引用 `mechanicalProfiles` 中同时给出 `hardwareId`、`profileId` 和 revision 的器件。
- `mechanicalProfiles` 来自已确认 BOM，或用户在当前项目澄清卡中显式选择的受信机械档案；列表为空时不得按名称猜尺寸。
- 用户消息中的型号、尺寸和安装方式若尚未确认，只能形成待确认事项，不能直接成为正式建模输入。

## cadDraft 边界

- `templateKind` 必须来自 `cadCapability.allowedTemplates`。
- `parameters` 只能包含模板声明的数值参数，单位统一为毫米或声明的 count。
- `components` 只描述器件实例、机械档案引用、安装面、旋转和偏移。
- `constraints` 只描述上下文允许的制造约束。
- 不填写 `templateRevision` 或 `intakeSnapshotSha256`，也不提供文件、路径、URL、命令、Python、CadQuery、Artifact、CadRun 或 Job 标识。
- `requestedOutputs` 只选择上下文允许的输出角色。
- `FREEFORM_STRUCTURE` 必须设置 `components=[]`、`parameters={}`，并提供 `geometry.primitives`；
  每个 primitive 只能使用 `box/rounded_box/cylinder`、`add/cut`、毫米尺寸、中心坐标和受控 Z 轴旋转。
  第一项必须为 `add`，最多 32 项，最终必须形成一个连通实体。

## 建模目标分流

- 不得把“创建三维结构”默认理解为盒体。目标不明确时，让用户选择“按器件创建安装结构”“创建盒体与上盖”或“不使用器件、按自然语言创建零件”。
- 用户要求安装座、固定底座、托架、支架或压框时，使用 `COMPONENT_MOUNT`。它必须且只能绑定一个已确认的 `mechanicalProfiles` 条目，不收集盒体内腔长宽高。
- `COMPONENT_MOUNT` 的本地确定性输出是器件尺寸派生的安装底座与可拆压框；硬件 Skill 中的 `models/cadquery.py` 仅作为建模参考，不能直接执行。
- 用户明确要求外壳、保护壳、盒体、容器或内腔尺寸时，使用 `BOX_WITH_LID`，继续收集盒体安装模式与内腔长宽高。
- “给传感器做安装座”属于 `COMPONENT_MOUNT`；“做一个装传感器的保护壳”属于 `BOX_WITH_LID`。两者不能互相替代。
- 用户明确不使用任何传感器/器件，或要求按尺寸创建安装板、连接板、自定义零件时，使用
  `FREEFORM_STRUCTURE`。这一路径不得要求机械档案，也不得偷偷创建盒体。
- 用户明确要求“行空板 K10 电子相册”“K10 电子相册结构”或“K10 相册支架”时，使用
  `UNIHIKER_K10_PHOTO_ALBUM`。该模板必须设置 `components=[]`、`parameters={}`，不得提供
  `geometry`；固定尺寸、revision 和几何由本地运行时拥有，详细阶段读取 `K10_PHOTO_ALBUM_TEMPLATE.md`。

### FREEFORM_STRUCTURE 示例

“创建 80×30×4 mm、四角 R4、在 X=±30 mm 各有一个直径 3 mm 通孔的安装板”应转换为：

- 一个 `rounded_box/add`：中心 `(0,0,2)`，尺寸 `80×30×4`，圆角 `4`；
- 两个 `cylinder/cut`：中心 `(-30,0,2)`、`(30,0,2)`，直径 `3`，高度必须穿透板厚；
- 不包含硬件 ID、机械档案、Python 或路径。

## 执行授权

返回 `cadDraft` 只会让本地服务固化一个 DRAFT，不代表 CAD 已经运行。不要在 `skillRequests` 中请求参数化建模、STL 导出或 STEP 导出。只有用户在中央确认后，本地 Tool Runner 才能把服务端持有的 CadRun 加入队列。

## 信息不足

需要建模但目标不明确时，不返回 `cadDraft`，先使用本地提供的目标澄清卡。目标为
`COMPONENT_MOUNT` 但缺少器件档案时，使用单选器件档案澄清卡；目标为 `BOX_WITH_LID`
但缺少安装模式或内腔长宽高时，使用盒体输入澄清卡。所有输入都必须通过
`uiPayload.type="clarification"` 的中央澄清卡收集，不得使用 `pendingItems` 或纯文本追问。
盒体尺寸格式为“长 × 宽 × 高 mm”，并明确代表内腔尺寸。

用户选择“仅松散存放，不做固定和接口开孔”后，即使描述中出现 ESP32、开发板或其他物品，
也允许 `components=[]`，并在尺寸确认后直接形成 `BOX_WITH_LID` 草稿。只有选择固定安装或接口
开孔时才要求用户从服务端给出的受信机械档案中显式选择；不得把 XIAO、DevKitC 或泛称 ESP32
相互替代。信息齐全后必须返回 `cadDraft`，不能继续只返回说明文本。

目标为 `FREEFORM_STRUCTURE` 但用户没有给出可确定实体的尺寸、位置或孔槽信息时，使用自然语言
结构描述澄清卡；关键尺寸不确定时不得猜测。信息完整时必须返回声明式 `geometry`，不能要求用户
先选择传感器或机械档案。
