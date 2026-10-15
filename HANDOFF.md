# 掌问 V4 交接

2026-10-15 部署任务（用户明确授权上传并替换旧仓库）：Windows一键安装/启动及全量硬件资源已落地。无需系统Node/Python，项目内下载SHA校验、uv创建Python3.13.7、锁定依赖、strict构建；npm run setup/web提供已有环境入口。全新安装独立验证见docs/deployment-smoke.json，74原包/817文件随源码，另加2新板，共76包/74可见/5主控/K10 68模块。新库无imports/V1路径依赖，原471文件摘要保留。仓库私有，其他电脑需仓库权限或所有者分发ZIP；Key在各机页面单独填。旧main恢复标签 backup/desktop-before-mu-web-20261015 已上传，本地完整bundle在.publish。未发布npm、未改系统凭据/仓库可见性，未触碰生产数据/设备。main替换与最终回归已完成：53项本地测试通过，初始发布a5d200d，1444文件远程树回读一致，仓库保持私有。Git传输异常改用官方Git Data API，逐blob/树摘要核对及force=false更新，Git本地main已同步。权威部署步骤docs/DEPLOYMENT.md、计划tasks/DEPLOYMENT.md。

2026-10-15最新：左上角改为主控选择，Web可见K10/XIAO S3/通用ESP32-C3/掌控2.0/掌控3.0。复用原3.0包，新增两款以原HardwareSkill加载器/写入器/SQLite投影安装，不修改原471保护文件。文件面板支持本机.py载入/导出、设备根目录列表/64KiB读取与SHA校验、历史版本。上传引导连接/保存/确认，运行支持自然返回REPL与报错反馈。strict构建、25API/14浏览器/13协议共52项通过，3080浅深×1440/375只读布局检查0异常/写入。COM522真机通过独立验收脚本运行同一serial.ts：mpython with ESP32、OLED128×64/circle可用，原main.py931bytes备份，上传177bytes、SHA一致、执行标记ZW_CIRCLE_OK、自然返回、显式读取一致、中心0/四边界点1。真实浏览器端口选择未完成，不能宣称浏览器真机闭环；用户已确认实物屏幕显示空心圆。验收项目「掌控板2.0空心圆验收」，原文件.device-backups和设备.zw-96c134f4866d482cab94dce319664f1e.bak均保留。当前服务80149。


最新任务完成：AI发送修复未命名项目禁用条件；首次显式发送先保存原项目快照再对话，刷新token/配置、保护后续草稿、显示发送/错误、失败保留输入并可重试。无Key打开设置且不创建项目。主控选择按用户截图改为原图/名称/简介大卡片、搜索、橙色选中，工作台与保存命名表单共享。真实库仍仅K10/XIAO S3两款，XIAO缺图用占位。strict构建、24项API/生命周期与13项浏览器通过；实际3080浅深×1440/375只读验证通过，0pageerror/生产写入。真实模型与设备未调用。当前服务74925，旧23004已停止。

最新任务完成：按用户提供的DeepSeek官方pricing页面核对，当前模型ID为deepseek-flash、deepseek-v4-pro。前端选项及默认/后端默认/环境与文件读取统一更新；旧chat/reasoner及v4-flash别名读取时规范为默认Flash，不修改Key或直接重写原设置文件，用户保存后持久化。构建、20项API/生命周期和11项浏览器通过，实际3080浅深×1440/375验证新选项且0生产写入。模型出处及兼容策略见docs/DEEPSEEK_MODELS.md。当前服务会话23004（旧32150已停止）。

最新任务完成：用户已提供 C:/Users/2gck 65/WorkBuddy/2026-10-13-15-30-07/outputs/final-design.html，文件完整读取、复制、渲染并适配。docs/final-design-reference.html 为原字节副本；docs/FINAL_DESIGN_ADAPTATION.md 记录布局、按钮语义与验证。此前链接登录问题已不阻塞；当前视觉以此本地参考为准。

任务：tasks/MVP.md、tasks/MU-UI.md。2026-10-13 最小 MVP 软件范围和用户 Mu 原型界面改版已完成。
来源 D:/ZW_V1；此工作区最初为空。初始复制源码与内置资源；最新已从离线副本补全硬件资料包，CAD参考另行归档。不复制V1用户数据库、凭据或未提交文件状态。
V1 原样保留。源文件 SHA-256 清单 docs/legacy-source-manifest.json。
当前权威 docs/DEVELOPMENT_MU_LOCAL_WEB.md，旧规划存为 DEVELOPMENT_MU_LOCAL_WEB_BASELINE.md。

最新增补：用户要求网页设置API，工具栏「API 设置」及掌问AI标题旁均可打开。AiSettingsDialog.tsx提供密码框、模型选择、取消/保存/清除，失败在弹窗内显示；关闭后不保留输入。后端GET/POST /api/settings/ai返回状态/模型，Key原子保存在.data/mu-settings.json（明文），不回显或写入项目/浏览器草稿；网页设置优先于环境默认值，清除不会重新启用环境Key。配置保存不代表真实连接验收。

## 已完成

- React Mu 三栏 / 手机标签：真实硬件资料、项目、CodeMirror、AI、终端。当前为 final-design 的标题栏、40px圆角方形图标、中性三栏和浅深主题；软件蓝/硬件橙/运行金，取代此前ZIP黄色圆环/蓝框。
- final-design.css 在 style.css/mu.css 后加载；主题保存于 mu-theme，CodeMirror高亮/光标/弹窗共用主题变量。主控入口移至左栏，保留真实连接状态，未连接不显示成功。
- 「载入模块」从原HardwareDetail的examples提取Python示例，先预览，再明确替换main.py草稿；无示例如实提示。「格式化」仅整理四空格缩进且可撤销；「退出」在设备断开且无进行中操作时收起工作区，「返回工作台」恢复草稿，不关闭服务。AI Ctrl/Cmd+Enter沿用真实配置和项目限制。
- 主控板/加载/文件版本/REPL/接线资料/80–160%编辑字号/帮助均为真实入口；终端按需展开。接线展示库资料，尚无电路编辑器。
- 最新：按主控系列筛选输入/输出模块，XIAO S3→Grove、K10→DFRobot；74个原Hardware Skill包全部保留，71包可见，K10模块网格68项（54输入/14输出），Grove编程包为0。原政策隐藏3个控制器。显示策略读取原记录，不是兼容验证；已有隐藏元件保留并提示。
- 中间直接对话，无欢迎卡片/板型上下文/快捷建议；右侧直接编辑器，无项目可写scratch，刷新恢复，首次保存作为v1。CreateProject新增可选code并保留64KiB/NUL校验；初始化载入时编辑器只读。
- 最新：左侧「已加入的模块」大图标卡片，桌面单列、手机双列，按输入/输出分组，只读原componentIds；「添加模块」四列/手机两列浮窗承载候选库，按全部/输入/输出筛选与搜索。确认才修改草稿，取消无变化；分类切换/详情返回保持勾选，已加入项禁重复，换板不删旧选项。
- ModuleCard.tsx媒体来自原硬件包，缺图/加载失败使用类别SVG。moduleDirection依据原category：SENSOR输入，ACTUATOR/DISPLAY输出，不通过名字猜测电气方向。完整68项网格用max-content行与230px最小卡片高度，避免弹窗挤压。
- 工作台默认未命名项目，可直接编辑/加模块/检查/接线；首次保存命名成v1，当前项目名直接显示。新建清空代码/组件沿用主控，未保存先确认；加载更新清单，成功打开才关闭。启动仅恢复明确mu-active-project，避免随机打开列表第一个；新建/刷新不自动写DB空项目。
- HardwareDetails.tsx：默认简述/参数卡片/接线表/全部使用注意，版本/规范/原始档案折叠。复用原资料，无生成接线、无HTML执行；从候选详情返回仍保留勾选。
- 修复无项目无法选传感器：scratch保存board/components/code，刷新恢复，CreateProject携带componentIds并经原库校验保存v1。选择最多32项；54项候选内部滚动，搜索/确认保持可见。
- 硬件离线导入已完成：imports/v1-hardware-snapshot-20261013-093547，817文件/74有效包；原加载器和写入器投影，隔离演练后停服务并备份V4，再导入66包/保留7包/更新初始K10。幂等重跑0新增/74保留/0冲突。详见docs/HARDWARE_MIGRATION.md；旧V1数据库未连接。
- FastAPI 同源静态服务，精确 Host/Origin、内存写请求标识、跨站/大请求拒绝、API404。
- 单目录单实例、预先绑定端口、无桌面依赖，npm start / start-web.bat，构建和运行分离。
- 原 Project/Conversation/Artifact/HardwareSkill 复用，新 mu_workspaces 扩展；版本不可变、双标签与旧草稿冲突拒绝。
- Python 静态语法 + 原电气规则；可选网页API设置/环境默认Key的固定DeepSeek接口，无配置真实显示，建议需接受。
- 浏览器 Web Serial classic raw REPL、设备身份、128-byte 块、写前 IndexedDB 备份、暂存/最终摘要、保留设备备份、取消/已知失败恢复、超时/拔线 attention。
- 运行命令单独提交，运行前核对 main.py；停止等待 REPL；任意 REPL 作废旧上传回执。

## 验证与运行位置

- npm run build：strict typecheck 与生产构建通过。
- 最新npm run test:api：24 passed（76.44s）、npm run test:e2e：13 passed（32.1s），新增API设置的持久/留空/取消/清除/重启/失败原子性/密钥脱敏与会话边界，既有流程继续通过。npm test协议10项沿用未改模块前次记录。
- Edge 375/720/1024/1440 无横向溢出；弹窗焦点/Escape、reduced-motion、草稿刷新及版本冲突通过。
- 471 个复制文件与清单以及 V1 原来源摘要一致；原 V1 未修改。
- docs/MVP_VALIDATION.md记录范围；最新截图docs/final-workbench-light-1440.png / dark-1440.png / light-375.png / dark-375.png以及final-picker同组截图；前次mu-*保留作历史。
- 当前3080生产页面桌面/手机加载通过，无页面运行异常；375px工具栏内部滚动，末尾帮助入口可达，页面无横向溢出。
- 当前已启动 `npm start -- --no-open`，工具会话74925（旧23004已停止），http://127.0.0.1:3080，数据 .data；本机 Edge 的安全上下文、serial、locks 已验证。
- node scripts/verify-api-settings.mjs：真实3080设置弹窗浅深×1440/375检查密码框为空/聚焦、Escape、无文档溢出及0pageerror，无生产写入。证据docs/api-settings-ui-smoke.json及api-settings-light/dark-1440/375.png。
- node scripts/verify-final-design.mjs：实际3080浅深主题×375/720/1024/1440八种布局通过；无文档溢出，编辑器可见，图标40px/圆角9px，68项选择网格卡片≥230px且搜索/确认可见，弹窗焦点/Escape、主题与草稿刷新通过。docs/final-design-ui-smoke.json记录0pageerror/无生产写入；final-design-integrity.json记录参考副本一致、471项V1/V4来源一致和健康状态。
- node scripts/verify-hardware-ui.mjs：实际3080只读冒烟通过，68项（54输入/14输出），分类多选4项、scratch确认/刷新、搜索与系列隔离；1440/375网格可滚动，卡片高度253/237px且搜索/确认可见，无pageerror/页面溢出。记录docs/module-ui-smoke.json，截图docs/mu-module-picker-1440.png / -375.png、mu-module-project-1440.png / -375.png。
- 后续 `npm start` / 双击 start-web.bat；Ctrl+C 停止启动窗口。若同目录已有服务运行，启动器拒绝第二个实例。

## 限制与精确下一步

最小软件闭环完成，不代表完整 M1–M6 或真实硬件完成。main.py 上限64 KiB，classic raw REPL，无固件烧录/多文件。
掌控板2.0 COM522已通过独立共享协议上传/执行/缓冲区验证，用户已确认实物显示空心圆；浏览器原生串口选择待验。未访问真实模型/Key，未迁移V1用户DB/库存/旧项目，未公开发布。硬件包文件迁移已经完成；CAD40项外形参考（含8个Grove）已归档，缺少电气/MicroPython合同，未启用为编程包。
只有原包资料可见不代表所有固件已通过：先逐板核验 K10/XIAO 的实际 raw REPL / SHA-256 / 上传 / 运行 / 中断。
需要保留设备上一版时导出浏览器备份；断线核对日志中的随机 .tmp/.bak 路径，勿盲目清空文件。
旧数据迁移只使用停止服务后的完整备份副本；不要把新服务直接指向 V1 生产库。
若继续实施，先读本文件、tasks/MVP.md 与 tasks/MU-UI.md；保留已有源码/内置资产和 V1，按用户需求扩展，不自动跑 Flash/LAN/发布。

最新编辑器修复：CRLF显示同步不触发用户编辑回调，载入项目不再误报未保存；strict构建/14项浏览器重跑通过。当前运行服务80149，实物圆已由用户确认。
