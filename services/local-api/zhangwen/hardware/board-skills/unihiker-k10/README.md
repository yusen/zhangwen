# 行空板 K10 MicroPython Skill 文档包

这是一个面向智能体的 **行空板 K10（UNIHIKER K10 / DFR0992）MicroPython 工程 Skill**。

它基于行空板官网的 `micropython_unihiker_k10` 代码模式资料整理，目标是让智能体：

- 正确识别 K10，而不是 M10；
- 使用 `unihiker_k10`、`k10_base`、`ai`、`asr` 等 K10 固件内置接口；
- 优先复用经过整理的最小模板；
- 不编造 API；
- 避免在回调或子线程中进行高内存屏幕刷新；
- 输出代码、接线、部署、验收和排错步骤。

## 包结构

```text
unihiker-k10-micropython-skill/
├── SKILL.md
├── README.md
├── CHANGELOG.md
├── NOTICE.md
├── manifest.json
├── references/
│   ├── 00-sources-and-scope.md
│   ├── 01-platform-and-firmware.md
│   ├── 02-deployment.md
│   ├── 03-screen-api.md
│   ├── 04-onboard-api.md
│   ├── 05-storage-audio-api.md
│   ├── 06-connectivity-api.md
│   ├── 07-ai-api.md
│   ├── 08-external-hardware-api.md
│   ├── 09-safety-and-troubleshooting.md
│   └── 10-verification-matrix.md
├── templates/
│   ├── 00_profile_probe.py
│   ├── 01_screen_shapes.py
│   ├── 02_onboard_dashboard.py
│   ├── 03_button_event_safe.py
│   ├── 04_rgb_status.py
│   ├── 05_tf_card_list.py
│   ├── 06_audio_record_play.py
│   ├── 07_wifi_connect.py
│   ├── 08_mqtt_probe.py
│   ├── 09_ble_hid.py
│   ├── 10_ai_qr_scanner.py
│   ├── 11_ai_motion_detect.py
│   ├── 12_gpio_test.py
│   ├── 13_servo_safe.py
│   ├── 14_camera_preview.py
│   ├── 15_asr_tts.py
│   ├── 16_ai_face_recognition.py
│   ├── 17_dht_sensor.py
│   ├── 18_ds18b20_sensor.py
│   ├── 19_ultrasonic.py
│   ├── 20_neopixel.py
│   ├── 21_force_sensor_probe.py
│   └── README.md
├── examples/
│   ├── environment_monitor/
│   ├── button_rgb/
│   └── qr_scanner/
└── tests/
    ├── syntax_check.py
    └── agent_acceptance_tests.md
```

## 使用方式

1. 将整个目录安装或复制到支持 `SKILL.md` 的智能体 Skill 目录。
2. 保持 `SKILL.md`、`references/` 和 `templates/` 的相对路径不变。
3. 智能体接到 K10 MicroPython 任务时，先读取 `SKILL.md`。
4. 根据功能加载相应的 `references/*.md`。
5. 优先基于 `templates/*.py` 生成项目。
6. 在真实 K10 上完成固件和 API 验证后，更新验证矩阵。

## 验证声明

- 本包中的 API 名称来自官方 K10 文档。
- 所有 Python 文件已做 CPython 语法编译检查。
- 由于当前环境没有连接真实 K10，本包未进行上板运行验证。
- 官方文档中的 MQTT 示例缺少 `WiFi` 和 `MqttClient` 对象实例化过程，包内将其标记为“需要上板探测”，不作为无条件可信模板。
- 官方页面说明该 MicroPython 固件仍处于测试阶段，使用时应记录固件版本。
