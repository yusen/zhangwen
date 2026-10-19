# 掌控板 3.0（ESP32-S3）Hardware Skill

本目录是面向掌问的掌控板 3.0 Hardware Skill，整理官方电气参数、板载硬件、引脚映射、完整 mPython 类库（10 个模块、159 个显式 API 入口）、结构包络、安全边界和验证用例。

## 导入

将完整目录 `labplus-mpython-esp32s3-v3` 导入掌问；不要增加、删除或单独移动目录内文件。

## 验证状态

- 电气、主要硬件、引脚、尺寸和 mPython 类库 10 个官方子页面已逐项纳入。
- 电气机器块已采用新版 `voltageMin`、`voltageMax`、`supplyVoltages` 字段；机械自然语言描述是 3D 预览唯一来源，包内没有手工派生缓存。
- CadQuery 仅通过 Python 语法检查，未执行 CadQuery 内核、未导出模型、未进行实物装配。
- 机械能力仅为官方外形尺寸形成的包络模型；安装孔纵向坐标、接口开孔和器件避让区未机器化。
