# V1 硬件资料包补全记录

日期：2026-10-13。用户反馈传感器不能加入、数量少。本次补全原项目已安装的Hardware Skill文件包，并修复无项目选择路径。V1保留原样，没有连接或复制其生产SQLite数据库。

## 原因与结果

此前只随源码安装8个内置包，漏掉V1 hardware-skills目录中后来安装的资料。选择浮窗又把无项目状态当作不可编辑，禁用复选框和加入按钮。现在允许先选入scratch、刷新恢复，首次保存将主控、代码和componentIds一起写入项目v1。

| 项目 | 结果 |
|---|---|
| 原安装目录离线快照 | 817文件，74个有效Hardware Skill包 |
| 导入新增 | 66包 |
| 相同revision保留 | 7包 |
| 初始K10资料更新 | 1包，仅允许目标仍等于新V4基线时替换 |
| 最终存储 | 74包，无缺失componentId |
| 原目录显示政策 | 71包可见，3个控制器保留但隐藏 |
| SENSOR | 54个，全部DFRobot，K10浮窗可选 |
| 幂等重复演练 | 0新增、74保留、0冲突、0替换 |

3个隐藏控制器是hw_drobotics_rdk_x5、hw_labplus_mpython_esp32s3_v3、hw_seeed_xiao_esp32s3，由原库_supported_controller_component策略决定，不是丢失包。显示筛选不代表真机/固件兼容通过。

## 副本、校验、备份与导入

1. 从D:/ZW_V1/services/local-api/.data/hardware-skills复制文件树到imports/v1-hardware-snapshot-20261013-093547，之后只对V4快照校验与导入。
2. 通过原HardwareSkillRepository._load_package验证全部包的白名单、规范、revision及媒体摘要，74有效、0无效。
3. 在.test-data/hardware-import-rehearsal演练。K10差异来自原库较完整的机械预览资料；只有目标revision仍等于全新V4安装器生成的初始K10时才允许更新。
4. 停止V4服务，完整备份.data到.backups/v4-before-hardware-import-20261013-094350，再导入正式V4目录。
5. 使用原_write_package及sync_projection，不建平行硬件数组或另一个事实库。同revision跳过，其他冲突报告且保留目标。脚本持有与服务相同的数据目录锁，拒绝向运行中的目录导入。
6. 重启3080，验证真实接口71包/54传感器，隔离浏览器中验证scratch选择/刷新、搜索/系列筛选、1440/375长列表交互；不写生产项目、设备或模型。

演练重复执行：

```powershell
.venv/Scripts/python.exe scripts/import-hardware-snapshot.py `
  --snapshot imports/v1-hardware-snapshot-20261013-093547 `
  --target .test-data/hardware-import-rehearsal `
  --report docs/hardware-import-idempotence.json `
  --replace-pristine-k10
```

正式数据如需恢复，先停止V4，再将当前完整.data另行备份，使用上述导入前备份恢复整个数据目录。不要仅恢复数据库或仅恢复硬件文件；不要让V4指向V1生产库。imports/.backups被.gitignore排除，须在本机独立保留。

## Grove 与 CAD 参考的边界

本次74个有效Hardware Skill中没有Grove编程包。原CAD source-package另有hardware-library.json，40个机械外形参考，其中8个Grove条目（OLED、Button、Dual Button、Passive Buzzer、SHT4x、BME280、PIR、Ultrasonic Ranger）。原JSON已复制到imports/v1-cad-reference-snapshot，摘要及清单另行记录。

这些条目没有完整电气/MicroPython合同，不能直接代替Hardware Skill，也不都属于SENSOR类别。XIAO S3因此继续显示Grove资料缺包状态；后续补录必须有实际接口、供电/电平、接线与MicroPython示例，使用原资料包校验流程。

## 证据

- hardware-import-snapshot.json：817个快照文件SHA-256/字节数。
- hardware-import-package-audit.json、hardware-import-validation.json：包清单与原验证器结果。
- hardware-import-rehearsal.json、hardware-import-idempotence.json：演练与幂等重跑。
- hardware-import-target-backup.json、hardware-import-applied.json：正式备份路径和导入结果。
- hardware-import-integrity.json：817快照文件与471个V1/V4保留来源摘要一致，真实接口数量与健康状态。
- legacy-cad-reference-audit.json：CAD参考归档及Grove条目。
- hardware-ui-smoke.json、mu-sensor-picker-54-1440.png / -375.png：真实页面只读验证与截图。

本次硬件包文件迁移完成。旧项目、课堂、库存与历史Work数据库尚未迁移；真实设备与模型验收仍单列。
