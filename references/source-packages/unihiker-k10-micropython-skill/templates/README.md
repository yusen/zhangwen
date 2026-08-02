# 模板说明

所有模板均针对 K10 `unihiker_k10` MicroPython 固件。

## 使用前

1. 先运行 `00_profile_probe.py`。
2. 确认导入成功。
3. 将选定模板另存为设备上的 `main.py`。
4. 根据注释修改配置。
5. 先看串口，再增加复杂功能。

## 模板状态

| 文件 | 状态 |
|---|---|
| 00_profile_probe.py | 官方模块探测 |
| 01_screen_shapes.py | 官方 API 重组 |
| 02_onboard_dashboard.py | 官方 API 重组 |
| 03_button_event_safe.py | 官方 API + FAQ 安全模式 |
| 04_rgb_status.py | 官方 API 重组 |
| 05_tf_card_list.py | 官方 API 重组 |
| 06_audio_record_play.py | 官方 API 重组 |
| 07_wifi_connect.py | 官方 API 重组 |
| 08_mqtt_probe.py | 解决官方示例缺口的探测程序 |
| 09_ble_hid.py | 官方 API 重组 |
| 10_ai_qr_scanner.py | 官方 API 重组 |
| 11_ai_motion_detect.py | 官方 API 重组 |
| 12_gpio_test.py | 官方 API 重组 |
| 13_servo_safe.py | 官方 API + 安全约束 |
| 14_camera_preview.py | 官方 API 重组 |
| 15_asr_tts.py | 官方 API + 安全回调模式 |
| 16_ai_face_recognition.py | 官方 API + 安全按键模式 |
| 17_dht_sensor.py | 官方 API 重组 |
| 18_ds18b20_sensor.py | 官方 API 重组 |
| 19_ultrasonic.py | 官方 API 重组 |
| 20_neopixel.py | 官方 API；端口需按接线验证 |
| 21_force_sensor_probe.py | 官方 API；单位需上板验证 |

“官方 API 重组”表示 API 来源明确，但本包没有连接真实 K10，仍需上板验证。
