---
id: xiao-esp32s3-sense
name: Seeed Studio XIAO ESP32S3 Sense
aliases: XIAO ESP32S3 Sense, XIAO Sense, seeedstudio/xiao_esp32s3_sense
platform: ESP32-S3 8MB Flash 8MB OPI PSRAM
language: micropython
---

# Seeed Studio XIAO ESP32S3 Sense BoardProfile

## 规范身份与运行时

- 规范板型 ID：`seeedstudio/xiao_esp32s3_sense`；不能以通用 `esp32s3` 代替。
- 主控：ESP32-S3，8 MB Flash、8 MB OPI PSRAM。
- 日常 MicroPython 更新优先使用 USB Serial/JTAG 文件上传；普通代码修改不得擦除整片 Flash 或重刷固件。
- ESP-Claw/ESP-IDF 只接受与该精确板型和容量匹配的预构建应用包，不在用户电脑上安装 ESP-IDF 编译工具链。

## 板载资源

- Sense 扩展板提供 OV2640 摄像头。
- 板载数字麦克风使用 PDM 音频输入。
- microSD 使用 SPI 总线，可作为受控 FAT32 夹具或真机存储。
- USB Serial/JTAG 用于串口日志、上传和受控调试通道。

## 引脚与冲突规则

- microSD 片选与用户 LED 复用 GPIO21。启用 SD 时，GPIO21 不得再作为可用 LED 或普通输出展示。
- 摄像头、PDM 麦克风、SPI microSD 和扩展引脚可能共享外设控制器或引脚；生成接线或代码前必须按当前启用组合检查冲突。
- GPIO 逻辑按 3.3 V 处理；电机、泵、加热器、舵机和高亮灯带必须使用合适驱动与独立供电，不能由 GPIO 直接供电。

## 图形调试边界

- 摄像头仿真只接受图片或视频夹具，麦克风只接受波形或 WAV，microSD 使用虚拟 FAT32 镜像。
- 这些夹具只提供功能输入，不代表真实模拟信号、电气精度或实时物理环境。
- 真机原始传感器值只读；只允许写入档案声明的校准、阈值、采样率和安全执行器通道。

## 生成代码前检查

1. 确认选择的是带 Sense 扩展板的 XIAO ESP32S3 Sense，而不是其他 XIAO 或通用 ESP32-S3。
2. 确认 8 MB Flash、8 MB OPI PSRAM 和目标固件分区表一致。
3. 使用 SD 时锁定 GPIO21 LED，并在代码、连线图和调试面板中保持一致。
4. Wi-Fi 密码、令牌和服务凭据只经内存通道发送，不进入代码、参数版本、日志或项目文件。
5. 未声明 `zwdbg/1` 的固件只能提供串口启动检查，不能显示虚假的图形化调参能力。

## 来源

- ESP-Claw 板级配置：`application/edge_agent/boards/seeedstudio/xiao_esp32s3_sense`。
- Seeed Studio XIAO ESP32S3 Sense 官方硬件资料与原理图。

本档案只固化已核对的板型、存储、板载外设与 GPIO21 冲突。具体固件版本和引脚映射仍需与应用包 manifest 一致。
