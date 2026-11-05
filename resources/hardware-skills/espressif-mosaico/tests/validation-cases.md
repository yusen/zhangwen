# 验收

```zhangwen:hardware-validation:v1
{"schema":"zhangwen.hardware-validation/v1","cases":[{"id":"canonical-self-smoke","components":["$self"],"expectedOverall":["PASS","WARNING","FAIL"]}]}
```

- 主控选择显示Chat Coding；不进入MicroPython连接/刷写/上传main.py。
- Fake WebIM验证连接、任务、回执、回复、重启、占用和超时未知；同任务ID不重发。
- 旧版Fake与真实本地Mock WebSocket验证chat_id过滤、回复持久化、重复与异常seq、断线不重连、丢回执不重发和拒绝重定向。
- 原Project/Artifact保存任务与证据，文件夹恢复不恢复活动设备连接。
- 2026-10-30实际用户设备完成HTTP状态及WebSocket连接测试，未发送执行任务；版本/芯片/屏幕、模型可用性和动作观察仍须单列验收。

- 集成工具以Fake验证配置修订/密钥保留清除、扫码采用、文件备份回读与恢复、附件授权、日志与重启；真实设备本轮只读重试超时，未进行管理写入或实物功能验收。

## 2026-10-31知识覆盖回归

- 提问板载IMU：应回答BMI270六轴、0x69，无需外接，不要求先加传感器模块。
- 板内/板外I²C按V1.0/V1.2区分，V1.2不得把GPIO3当LED；外接模块不得当作板载。
- Lua使用imu.new对象与read/close，明确raw计数、注册名条件；不得将BSP的g阈值直接用于Lua raw值。
- 两颗BMM150地址0x11/0x12，磁场µT与校准、非姿态角；不编造两个注册名。
- 完整24案例必须到达实际Lua模型请求，含imu_gesture、磁吸、Pong、USB、语音和EEPROM的限制；不能因6000字符主控摘要丢失案例。
- 已安装旧v2 Skill从同componentId发布包补充只读章节；保留用户包、代码、设置与校验边界，不因更新覆盖用户资料。
- 模型请求没有tools或设备/命令权限；上述案例均不是实板验收记录。
