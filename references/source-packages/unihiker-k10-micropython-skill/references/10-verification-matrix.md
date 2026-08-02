# API 验证矩阵

| 功能 | 导入/API | 文档级别 | 初版状态 | 备注 |
|---|---|---:|---|---|
| 屏幕图形 | `unihiker_k10.screen` | D | 语法检查 | 官方代码明确 |
| 摄像头预览 | `k10_base.Camera` | D | 语法检查 | 需实际摄像头测试 |
| A/B 按键 | `button` | D | 语法检查 | 回调建议设标志 |
| 温湿度 | `temp_humi` | D | 语法检查 | 板载 AHT20 |
| 环境光 | `light` | D | 语法检查 | 板载 LTR303ALS |
| 加速度 | `acce` | D | 语法检查 | 板载 SC7A20H |
| RGB | `rgb` | D | 语法检查 | 亮度 0～9 |
| TF 卡 | `k10_base.TF_card` | D | 语法检查 | 路径 `/sd` |
| 录音播放 | `mic`/`speaker` | D | 语法检查 | 文件格式需实测 |
| Wi-Fi | `k10_base.WiFi` | D | 语法检查 | 类实例化明确 |
| MQTT | `k10_base.MqttClient` | B | 需探测 | 官方页面缺实例化 |
| 蓝牙 HID | `hid`/`keycode` | D | 语法检查 | 主机配对需实测 |
| ASR/TTS | `asr` | D | 语法检查 | 命令词和语言需实测 |
| 移动检测 | `ai.move_detect` | D | 语法检查 | 资源释放 |
| 二维码 | `ai.code_scanner` | D | 语法检查 | `code_data` |
| 猫脸 | `ai.cat_detect` | D | 语法检查 | 嵌套字段防御读取 |
| 人脸识别 | `ai.face_recognize_start` | D | 语法检查 | 注册/识别流程 |
| 舵机 | `servo` | D | 语法检查 | 供电需评估 |
| 灯带 | `neopixel` | C | 语法检查 | 官方端口注释不一致 |
| DHT | `dht` | D | 语法检查 | 自动识别 11/22 |
| DS18B20 | `ds18b20` | D | 语法检查 | 单总线接线需实测 |
| 超声波 | `ultrasonic` | D | 语法检查 | SEN0388 单线模式 |
| KIT0176 | `force` | B | 语法检查 | 页面单位表述冲突 |
| GPIO | `pin` | D | 语法检查 | P0/P1 能力更完整 |

## 上板验证记录模板

```text
日期：
开发板批次：
固件文件：
固件版本：
模板文件：
测试结果：
串口输出：
修改内容：
验证人：
```
