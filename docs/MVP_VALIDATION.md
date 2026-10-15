# 掌问 Mu Web MVP 验证记录

2026-10-15 部署扩展：Windows一键环境准备及隔离目录真实安装/启动通过，完整硬件76包/74可见/5主控；strict构建、26API/14浏览器/13协议合计53项通过，原471源码和817资源摘要一致。部署范围及限制详见 DEPLOYMENT_VALIDATION.md、deployment-smoke.json。旧GitHub资料已有恢复标签，不改变既有设备/模型验收结论。

最新日期：2026-10-15。工作区：D:/ZW_V4，来源：D:/ZW_V1。

## 已通过

| 验证 | 结果 | 覆盖 |
|---|---|---|
| `npm run build` | 通过 | TypeScript strict、Vite 生产构建，编辑器独立资源块 |
| `npm test` | 13 passed | raw REPL 分片字节、中文代码、写前备份、上传/回读、手动运行/停止、REPL 回执失效 |
| 同组故障测试 | 包含于 13 项 | 清单变化、备份失败、暂存/最终摘要失败、取消、拔线、超时、设备文件被其他工具修改、并发互斥 |
| `npm run test:api` | 25 passed | 原硬件/媒体摘要、项目和历史版本、刷新/重启、乐观冲突、检查不执行代码、固定清单、无 Key、模拟 AI 成功/失败、旧项目隔离、首次创建保存scratch及字节/NUL边界、componentIds首次创建及非法列表边界 |
| 同组边界/生命周期测试 | 包含于 25 项 | Host/Origin/会话/跨站/请求大小、未知 API404、未暴露旧设备入口、端口占用不杀进程、数据目录单实例、进程退出后可重启 |
| `npm run test:e2e` | 14 passed | 实际 Microsoft Edge：保存/刷新/版本/草稿/检查；响应式和弹窗；双标签冲突；Mu工具；模块系列隔离；scratch保存为v1；选择浮窗、详情与已加入清单持久化；默认未命名项目、输入输出筛选、保存/新建/加载完整恢复、不自动写空项目；浅深主题刷新、缩进撤销、模块示例取消/接受、退出/返回保持草稿 |
| 页面宽度 | 375/720/1024/1440 通过 | 无横向溢出，手机硬件/AI/代码切换，reduced-motion，弹窗初始焦点/Escape |
| 视觉检查 | 通过 | 查看final-design参考及实际1440px与375px浅深截图；中性三栏、圆角方形工具，手机单栏，无外部字体依赖 |
| 生产服务健康 | 通过 | `http://127.0.0.1:3080/api/health` 返回 `ok / 0.1.0 / web-serial` |
| 浏览器设备通道前提 | 通过 | 本机 Edge secureContext=true、navigator.serial 存在、navigator.locks 存在 |
| 源码与资产保留 | 471 项一致 | V4 与源清单 SHA-256 一致；V1 来源文件也与清单一致 |
| 新源文件空白检查 | 通过 | web/src、contracts/src、mu_web 中无行末空白 |

合计 **52 项自动测试通过**。最新主控/设备文件更新完成strict构建、25项API/生命周期（75.70s）、14项浏览器（25.5s，CRLF修复后重跑）、13项协议（174ms）。真实设备独立验收另列，Fake不算真机证据。Starlette旧AnyIO别名弃用提示不影响结果。
Node/Edge 测试日志另有测试工具的 FORCE_COLOR/NO_COLOR 提示。

## 证据与可复现命令

- Playwright 截图 `test-results/mvp-desktop-mobile-respons-2d5eb-keyboard-dialog-interaction/workbench-*.png`。
- 代表性截图另保存到 `docs/mvp-workbench-1440.png` 和 `docs/mvp-workbench-375.png`。
- 复制来源和资产摘要：`legacy-source-manifest.json`。
- npm 依赖：`package-lock.json`；Python 实际环境锁：`services/local-api/requirements-web-lock.txt`。
- 自动测试未读取 V1 用户数据库、未使用真实串口/付费模型、未写系统凭据。

## Mu 原型界面改版

以下界面迭代小节保留历史证据，当时的3传感器状态已由完整硬件包导入更新；黄色圆环/连续蓝框已由最后的final-design适配取代。

2026-10-13按用户 ZIP 中 MuWorkbench.tsx / mu-workbench.css 实现黄色圆环与蓝色图标工具栏、灰色底、文件标签、连续蓝框三栏、分组元件卡片、聊天气泡和暖白编辑区域。
新增浏览器测试验证 REPL 开合、字号缩放、真实主控板选择、接线资料、加载项目和帮助；代码保持不变，板型修改正确标记未保存。
375px工具栏内容776px、可视293px，内部overflow-x:auto；键盘可打开最末尾帮助。文档本身宽375px，无横向溢出。
实际生产地址3080的桌面和手机页面加载通过，无pageerror；未连接串口、未创建生产测试项目。
最新视觉证据：`docs/mu-workbench-1440.png`、`docs/mu-workbench-375.png`。历史MVP截图保留。
本次未改后端、串口协议、数据库或原资源；接线为文档入口，无电路编辑/CAD功能。

## 传感器筛选与直接对话／编辑

本次新增XIAO S3→Grove、K10→DFRobot传感器显示策略，保留原资料库；当前真实库无Grove、DFRobot有3个传感器。Grove未来录入场景使用仅测试路由中的模拟包，未写入真实库。
中间移除欢迎卡片和快捷建议，右侧直接展示CodeMirror；scratch刷新恢复、首次保存成v1通过浏览器及API测试，创建参数code复用64KiB/NUL约束。
6项浏览器回归通过。新建项目场景等待创建弹窗关闭后才继续，避免把旧项目的同名v1状态误认作新建完成；双标签冲突继续拒绝覆盖。
3080服务已重启至最新代码，桌面编辑器可见、无欢迎卡片、无pageerror，K10为3个传感器，XIAO正确空状态，375px无页面横向溢出。未在生产库新建验收项目，未连接设备或模型。
最新截图：`docs/mu-sensors-dialog-editor-1440.png` / `docs/mu-sensors-dialog-editor-375.png`。后端仅扩展CreateProject可选code，原471个复制文件和串口协议未修改。

## 已加入清单、选择浮窗与简洁详情

7项浏览器回归全部通过。新增流程实际创建隔离测试项目：选两项后取消不加入 → 再次多选 → 查看详情并返回保留勾选 → 确认后侧栏仅显示这两项 → 保存v2/刷新恢复 → 已加入项禁重复 → 查看简洁表格/注意且原档案折叠 → 移除保存v3/刷新只剩一项 → 换板仍保留并标记需核对。
375px和1440px选择/详情浮窗已截图与目视检查，页面无横向溢出；完整技术资料可展开，原安全注意默认完整显示。
最新截图：docs/mu-selected-sensors-1440.png、mu-sensor-picker-1440.png / -375.png、mu-sensor-detail-1440.png / -375.png。
本次仅App/HardwareDetails/CSS和浏览器测试变化；后端、数据库、串口协议与原471项来源不变。候选仍来自原库，Grove缺包状态保留。
实际3080生产页面验证：侧栏0项且无候选搜索框，K10选择浮窗3项，详情接线表可见、原档案默认折叠，关闭详情返回浮窗；无pageerror。未在生产项目加入器件或写设备。471项V4与V1来源哈希复核一致。

## 无项目选择修复与全量硬件资料导入

复选框/确认按钮不再依赖project存在；scratch存储board/componentIds/code，首次保存携带componentIds并验证原硬件revision。API新增边界覆盖缺失器件/重复/主控当外设/超过32项；浏览器第8项覆盖未创建项目先选两项、刷新、首次保存v1、再次刷新不丢失。

原包副本74个全部通过_load_package（0无效），导入前V4停止并完整备份.data；正式导入66新增/7保留/1初始K10更新，无冲突/缺失；最终74存储/71显示/54传感器。隔离重复演练0新增/74保留/0冲突。471个V1/V4来源文件和817个快照文件摘要复核一致，未连接V1生产库。CAD40个外形参考另归档，8个Grove条目缺编程合同，未启用为Hardware Skill。

`node scripts/verify-hardware-ui.mjs`只读验证实际3080页面：K10有54可选项、确认进入scratch、刷新保留、SEN0193搜索正确、XIAO不会显示DFRobot，pageerror为0。1440/375均无横向溢出，列表独立滚动，搜索与确认按钮保持可见；截图docs/mu-sensor-picker-54-1440.png / -375.png已经目视检查。浏览器上下文独立且项目GET被屏蔽，未写生产项目。

构建未完成时曾并行启动浏览器回归，第一次刷新遇到dist清理暂缺index.html，导致1失败/7通过；错误上下文为「前端未构建」。待生产构建完成后顺序重跑，8项全部通过（19.8s），没有重试掩盖。正式服务13943正在3080运行并健康。

导入详细证据见HARDWARE_MIGRATION.md；正式接口/摘要记录hardware-import-integrity.json，真实页面记录hardware-ui-smoke.json。

## 大图标输入／输出模块与直接项目流程

原category映射输入SENSOR、输出ACTUATOR/DISPLAY；K1068项可选（54输入/14输出），显示74包中的71包政策不变。ModuleCard大图标/媒体失败回退，已加入模块输入输出分组，分类切换保持pending多选。桌面四列、手机两列，全量68项时网格行不压缩，仅网格内部滚动，搜索/分类/确认保留在视口。

最新9项浏览器测试通过；新增第9项验证已有其他本机项目时新浏览器仍进入未命名项目且不POST、输入/输出数量/隔离、跨分类选择两项、图标宽82px、草稿刷新、命名保存v1、点击新建清空、加载恢复代码与两种模块、刷新保持明确当前项目、手机无横向溢出。其余8项已适配首次保存命名流程，旧并发冲突与键盘/资料回归继续通过。

实际3080只读`node scripts/verify-hardware-ui.mjs`通过：68项分类为54/14，多选原库4模块/刷新恢复/搜索/系列隔离，pageerror=0。1440/375卡片高度253.28/237.28px，网格滚动且搜索/确认可见，无横向溢出。全量网格检查发现auto行被有限容器挤成空行，已通过max-content行与230px最小卡片高度修复，重新构建/真实冒烟/9项浏览器回归通过。第一次冒烟脚本使用错误DFR0523名称也已按原真实库更正为实际模块，不修改库资料。

证据：docs/module-ui-smoke.json；docs/mu-module-picker-1440.png / -375.png、mu-module-project-1440.png / -375.png已目视检查。实际脚本不写生产项目或设备；保存加载场景在隔离e2e数据目录验证。后端、设备协议及原471来源未改。生产服务13943继续运行，直接服务最新构建。

## final-design最新布局与交互

用户本地参考文件已完整复制为docs/final-design-reference.html，SHA-256为0b8f120dfff907aaf0af4d0fb49d3fef1c90b991814172e96ba7ce2ad32687ff，复制摘要一致。原参考浅深截图final-design-reference-light.png / -dark.png已查看。实现标题栏、40px图标/9px圆角/22px glyph/2.6描边、软件蓝/硬件橙/运行金、中性三栏与浅深主题，编辑器和弹窗共用主题变量。

`npm run build`通过strict TypeScript与Vite构建；`npm run test:e2e`10项通过（20.3s）。第10项新增主题切换/刷新、深色弹窗焦点/Escape、原DFR0029加入、两空格缩进整理为四空格及Ctrl+Z原文恢复、原Python示例预览取消不变/明确替换、退出确认/返回后草稿与模块保持。示例来自原包，不是模型生成。原9项项目/冲突/分类/资料等回归继续通过。

`node scripts/verify-final-design.mjs`对实际3080进行独立Edge只读冒烟，项目GET在隔离浏览器中屏蔽，不写生产项目/设备/模型。浅深主题×1440/1024/720/375八种布局均无document横向溢出，编辑器可见，图标40px/圆角9px；每种布局均检查完整68项网格内部滚动、卡片≥230px、搜索/确认可见、帮助弹窗键盘/Escape。原DFR0033输入与SER0006输出加入浏览器scratch；刷新主题/草稿恢复，pageErrors=[]，productionWrites=false。结果docs/final-design-ui-smoke.json。

目视截图：docs/final-workbench-light-1440.png、final-workbench-dark-1440.png、final-workbench-light-375.png、final-workbench-dark-375.png；选择浮窗同组final-picker-light/dark-1440/375.png。截图代码和选择仅为隔离浏览器草稿，不代表真机运行。

docs/final-design-integrity.json确认471项原保护文件与V1/V4来源一致，无行末空白，3080健康ok/0.1.0/web-serial。本次后端/设备协议/原资源未改。当前生产服务会话61814，旧13943已结束。

明确范围：仅main.py；格式化仅可撤销缩进整理；退出收起工作区，不关闭浏览器或服务；载入模块仅预览后显式替换草稿，不自动保存或上传；无真实设备与真实模型验收。

## 网页 API 设置（此前）

新增工具栏和AI标题旁设置入口；填写DeepSeek Key、选择deepseek-chat/reasoner，保存立即生效并持久到本机mu-settings.json（明文）。留空保持原Key、取消无变化、清除显式停用。GET仅返回状态/模型；POST使用原Host/Origin/会话校验，校验错误不回显输入，保存失败不改变当前设置或原文件。已开始对话固定当前Key/模型。

`npm run build`通过；`npm run test:api`19项通过（38.26s），新增重启持久/模型变更保留Key/显式清除/密钥不回显/拒绝跨站与失效会话/非法边界/失败原子性；模拟模型适配断言实际传入配置Key/模型。原来源471项保护检查继续通过。

`npm run test:e2e`11项通过（17.5s），新增取消不变、保存/刷新保留、Key框不回填、模型变化留空保留旧Key、无浏览器storage密钥、手机布局、清除与Escape。测试仅使用占位Key，未调用真实DeepSeek或写设备。

`node scripts/verify-api-settings.mjs`实际3080只读通过，浅深×1440/375设置浮窗无文档溢出，密码框为空且聚焦，Escape关闭，0pageerror、0生产写入；docs/api-settings-ui-smoke.json及api-settings-light/dark-1440/375.png为证据，截图已目视检查。当前服务32150，旧61814已停止；未向生产配置写入测试Key。

保存成功仅表示本机配置已保存，真实网络/用户Key/模型调用仍待实际对话验证。

## 官方模型名称更新（此前）

按用户官方pricing链接与首次API调用页核对为deepseek-flash / deepseek-v4-pro，前端列表/默认及后端默认统一更新。旧chat/reasoner与退役Flash别名规范为Flash默认，已配置Key保留，读取旧文件不重写；Pro需明确选择。这是本工具升级策略，不是旧reasoner与Flash等价声明，详见DEEPSEEK_MODELS.md。

strict构建通过，API/生命周期20项（57.70s）、浏览器11项（29.2s）通过；新增旧文件Key/原字节保留、四种旧名称POST规范、环境旧默认和Pro读取。浏览器确认两项最新ID与Flash默认，Pro选择/保存/刷新/保持旧Key/清除继续通过。API适配器合同断言传入新Pro名称。原471项来源保护检查继续通过。

实际3080重新执行verify-api-settings.mjs，浅深×1440/375下拉项均为deepseek-flash / deepseek-v4-pro，0pageerror、0生产写入，证据api-settings-ui-smoke.json及同组截图已更新。当前服务23004，旧32150已停止；未直接修改用户密钥文件，未使用真实模型/串口。

## AI发送与主控大图选择（最新）

定位AI已配置但按钮被未命名project条件禁用，现首次发送显式保存原项目快照成v1后提交chat；bootstrap刷新会话和配置，无Key先打开设置且不创建项目。首次项目保存不覆盖等待期间后续编辑；防重入、失败保留问题/新输入，重试复用同一项目。pending消息与内联错误可见，不把提交视为模型成功。

主控按用户截图改为大图/名称/原简介卡片、橙色选中/aria-pressed、搜索、帮助，工作台和首次保存表单共享；表单往返保留名称，取消不改当前板型。实际原库仍仅K10和XIAO S3，K10原图/XIAO无图占位，不添加假主控。手机双列、桌面网格行同高；检查发现手机标题栏被固定flex-basis挤压、工具栏拦截主题按钮点击，已改为auto并重新通过真实点击检查。

strict构建通过；API/生命周期24项通过（76.44s），新增当前两款模型HTTP MockTransport合同、非思考请求/最终回答、Key与限流错误提示且不回显原体。浏览器13项通过（32.1s），新增首次发送真实隔离项目创建一次、期间代码/新问题不被覆盖、失败/快捷键重试、代码建议不自动执行、未配置打开设置；主控浅深×1440/375搜索/图片/当前选择/键盘切换、模块DFRobot联动、保存表单往返/取消保留名称与主控。

中途回归因旧测试仍使用selectOption访问已替换的主控选择按钮而失败，已调整为真实卡片流程后重跑，最终13项全通过。后端/浏览器测试只用Fake模型或占位Key，不调用用户Key/真实设备。原471项来源保护测试继续通过。

实际3080运行verify-board-chat-ui.mjs只读验证：未命名项目填问题后sendEnabledBeforeSave=true；浅深×1440/375均两款卡片、K10图片完成解码、搜索聚焦/过滤、无横向溢出；换板保留代码并显示DFRobot模块，pageErrors=[]、productionWrites=0。证据board-chat-ui-smoke.json及board-picker-light/dark-1440/375.png已目视检查。当前服务74925，旧23004已停止。

真实DeepSeek调用成功与真实硬件行为仍未验收。

## 未执行，不能声称通过

1. 真实 K10 / XIAO / 其他具体板型与固件的 raw REPL、文件备份/上传/回读、运行/停止及物理行为。
2. 真实 DeepSeek 请求、实际用户 Key 和网络；当前只验证真实适配入口与模拟响应合同。
3. V1 用户数据库、库存、旧项目和历史课堂 Work 的离线副本迁移；硬件资料包文件导入已完成，V1 保留原样。
4. 干净电脑从零安装、macOS/Linux、Safari/Firefox 或手机 USB；本版支持目标为桌面 Chrome/Edge。
5. 固件烧录、多文件、LAN/公网、多账号、CAD/仿真 UI、公开分发与完整 M1–M6。

## 真机最小验收

在 Chrome/Edge 打开本机页面；使用匹配板型与已安装 MicroPython 的设备：
先保留一个独立 user-test.txt 并记录摘要 → 核对 main.py 旧内容 → 连接/确认上传 → 查看两个阶段 SHA-256 → 显式运行 → 串口输出/实际观察 → 停止并获得提示符 → 验证 user-test.txt 未变 → 导出旧 main.py 备份。
拔线/取消验收使用非敏感样例，记录具体 OS、浏览器、板型、固件、project/revision 和恢复路径。真实设备写入由用户在页面确认，本次未代操作。


## 2026-10-15 五款主控、文件面板与实际COM522（最新）

软件：左上角主控选择；Web硬件策略新增3.0可见，并使用原加载器/写入器安装通用C3和掌控2.0目录包。无改动原控制器白名单或471保护文件，原库/SQLite投影继续作为事实来源。主控3.0复用原media，缺图占位。保存、检查、上传清单、运行和观察分开。

设备文件：根目录256项/单文件64KiB，只读分块与SHA验证；本机UTF-8.py导入、草稿确认替换/导出、历史版本。无任意写/删除/递归。上传从未连接/未命名/有更改引导到串口选择、保存与冻结清单，取消不写设备。ujson/uhashlib兼容；正常程序与Traceback自然结束恢复REPL状态。

测试：25API新增五款板真实库投影/项目清单覆盖，原471来源检查继续通过；13协议新增只读目录/分块/摘要/路径/大小边界/回执保留、自然结束/错误分片；14浏览器新增Fake serial完整按钮流程、首次上传命名、文件导入/回读、新版本上传。最后ujson兼容修订已重建和重跑协议，通过。

node scripts/verify-board-chat-ui.mjs：实际3080浅深×1440/375主控五卡片/两张原图解码、文件面板无横向溢出/焦点/Escape，未连接只读按钮禁用；0pageerror/生产写入。截图board-picker-*、device-files-*已目视检查。V4安装前完整备份.backups/20261015-before-board-device-update。

真实设备：COM522为CH9102；Browser原生串口选择未完成，两次等待结束，未写设备。随后通过**独立验收COM传输**使用产品相同serial.ts/MicroPythonDevice进行硬件验收（无backend设备接口；pyserial仅.test-data测试依赖）。它不证明浏览器权限/真机闭环。设备报告mpython with ESP32，OLED128×64/circle能力探测通过。

原main.py为931 bytes，写前保存本机.device-backups/.zw-96c134f4866d482cab94dce319664f1e.bak.py；设备同名.bak保留。通过原项目/检查/清单API保存「掌控板2.0空心圆验收」prj_cf1773f5ee964bf699ebf2dafe06b81c，上传177 bytes，SHA-256为75c78a167a54a6ce682c97fc9f0cd5a15fc332e150d0c8177432677a7152a800。暂存与最终校验、运行前校验通过；运行输出ZW_CIRCLE_OK: center=(64,32), radius=24, outline，返回REPL；文件读取一致。OLED中心像素0，四个半径24边界像素1，其余原设备文件元数据保持不变。**用户于2026-10-15确认「已显示空心圆」**；此项来自用户实物观察，区别于独立脚本缓冲区验证。

证据docs/device-acceptance/real-com522.json、backup-metadata.json、circle-project.png；示例examples/mpython-v2-circle/main.py。脚本accept-real-mpython.mjs可审查，重复运行会另备份当前程序，不应无目的重复写板卡。未调用真实模型，无Flash，无删除设备根目录；当前服务80149，旧74925/28677已结束。

最终追加：Windows CRLF载入导致CodeMirror隐式onChange把已保存代码规范化并误标未保存，已用外部赋值Annotation区分显示同步与用户编辑。导入/原API保存保持原字节，显示LF不生成修改；历史载入显式作废旧检查。strict构建和14项浏览器全量重跑通过（25.5s），新闭环测试使用CRLF文件并验证上传后已保存v1。实际circle-project只读截图也验证已保存v1；源码无行末空白。
