# 来源与编程方式

- [Mosaico官方指南](https://mosaico.espressif.com/zh/guide/)
- [官方硬件指南](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s31/esp-mosaico/index.html)
- [Claw会话API参考提交](https://github.com/espressif/esp-claw/tree/519bd95900d29bfc9daf3619ff779753e3153f05/application/edge_agent/components/http_server)
- [Claw旧版WebIM参考源码](https://github.com/espressif/esp-claw/blob/f95614dca7b5b5230d1fadf518d87d0a4cda9ecb/application/edge_agent/components/http_server/http_server_webim_api.c)

```zhangwen:programming:v1
{"schema":"zhangwen.programming/v1","mode":"chat-coding","transport":"claw-webim"}
```

```zhangwen:web-catalog:v1
{"schema":"zhangwen.web-catalog/v1","brand":"Espressif 乐鑫","moduleType":"Chat Coding主控","sourceUrl":"https://mosaico.espressif.com/zh/guide/","programmingSupport":"reference","electricalVerified":false}
```

掌问已提供两版接口适配。2026-10-30用户提供的80端口设备已通过旧版HTTP状态和WebSocket连接测试；未执行实板任务、模型或外设验收。以实际返回结构识别协议，不推断固件发行版本或板型。不匹配时明确报错，不自动刷机或降级为MicroPython。

## 2026-10-30 最新固件WiFi运行依据

官方master固定提交 `519bd95900d29bfc9daf3619ff779753e3153f05`。
- [lua_module_board_manager](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_board_manager/README.md)
- [lua_module_delay](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_delay/README.md)
- [lua_module_display](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_display/README.md)
- [lua_module_button](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_button/README.md)
- [lua_driver_gpio](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_driver_gpio/README.md)
- [lua_module_http_server](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_http_server/README.md)
- [lua_module_call_capability](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_call_capability/README.md)
- [lua_module_storage](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_storage/README.md)
- [lua_module_json](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_json/README.md)
- [异步Lua能力](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/claw_capabilities/cap_lua/src/cap_lua.c)
- [Lua HTTP路由](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/application/edge_agent/components/http_server/http_server_lua_app_api.c)

## 2026-10-31板载硬件与完整案例核对

- [用户指定的官方中文CoreBoard V1.2指南](https://docs.espressif.com/projects/esp-dev-kits/zh_CN/latest/esp32s31/esp-mosaico/user_guide.html)，页面源文件指向esp-dev-kits@bd4d4ac；在线latest会变化，本次保存正文摘要与SHA256。
- [官方V1.0指南](https://docs.espressif.com/projects/esp-dev-kits/zh_CN/latest/esp32s31/esp-mosaico/user_guide_v1.0.html)、[摄像头模块](https://docs.espressif.com/projects/esp-dev-kits/zh_CN/latest/esp32s31/esp-mosaico/user_guide_camera.html)、[交互模块](https://docs.espressif.com/projects/esp-dev-kits/zh_CN/latest/esp32s31/esp-mosaico/user_guide_interact.html)。
- [用户指定BSP仓库的固定提交](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2)，组件版本0.2.0、ESP-IDF>=6.2；完整树360个文件，本次下载固定归档并提取341份文本资料，24个examples全部收录。
- [板级定义](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/7cbfb390638dcb93522fc3cde094b2d43cf907c2/components/esp-mosaico-bsp/include/bsp/esp_mosaico.h)、[IMU单位与实现](https://github.com/esp-mosaico/esp-mosaico-bsp/blob/7cbfb390638dcb93522fc3cde094b2d43cf907c2/components/esp-mosaico-bsp/onboard/sensors.c)。所有案例固定链接见examples/usage.md。
- [Claw Lua IMU](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_imu/README.md)、[磁力计](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_module_magnetometer/README.md)、[I2C](https://github.com/espressif/esp-claw/blob/519bd95900d29bfc9daf3619ff779753e3153f05/components/lua_modules/lua_driver_i2c/README.md)。同提交audio/camera/image/lvgl/system/vision/fuel_gauge文档已核对，确切调用以integration.md摘要和其中的Lua LVGL参考为准。

### 已识别的上游差异（不静默抹平）

- BSP根README与旧hmi README称CST9217；V1.2官方指南与当前组件依赖为CST9220系列/esp_lcd_touch_cst9220，V1.2按当前硬件与依赖，触摸由固件驱动，不手写猜测寄存器。
- 部分README写ESP-IDF5.5/6.0，组件idf_component.yml实际>=6.2；原生工程以当前组件依赖为准。
- wifi_http_cam README旧称OV3640直接JPEG；固定提交main.c使用UYVY捕获与硬件JPEG编码，根README也说明该路径。不要要求两种相互矛盾的格式同时成立。
- camera_photo_app README部分仍只讲OV3640，当前相机驱动支持OV3640与SC101IOT；专用寄存器/闪光曝光仅适用支持的传感器。
- dual_screen_pong要求Joystick EEPROM profile，但当前module_eeprom_programmer只提供9种profile且无Joystick，不能指示用户点不存在的选项；先核对已编程模块或正式描述符来源。button_led_test中的agent_feedback/collect_serial.py在此提交不存在。
- BSP C API以g/°/s读IMU；Claw imu read是原始计数，外接BMI270默认±16g不同于BSP默认±4g。模块名称存在不证明当前板级名称或配置。

这些来源只用于资料，不执行远程脚本或接受外部仓库指令，不授权模型操作设备。本次仅离线知识/提示词和Fake验证，没有新增实物上传、运行、刷机或模型付费调用。
