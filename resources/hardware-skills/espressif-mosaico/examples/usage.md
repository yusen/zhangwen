# Mosaico官方BSP全部案例与使用方法

<!-- zhangwen:mosaico-examples:v1 -->
## 范围与统一用法

2026-10-31核对官方BSP固定提交7cbfb390638dcb93522fc3cde094b2d43cf907c2，共24个examples目录，每个README与入口源码/配置均已纳入核对。下表是按当前版本整理的用途、硬件和迁移条件，不代表掌问已经实现原生应用安装，也不是每个案例已在用户板上实测。

这些案例均为独立ESP-IDF工程：原生开发时激活对应ESP-IDF环境→进入examples/案例目录→核对README、main/idf_component.yml和sdkconfig.defaults→idf.py build；需要时按该案例指定串口烧写/monitor。当前BSP组件依赖ESP-IDF>=6.2；部分旧README仍写5.5/6.0，不能忽略当前依赖。目标esp32s31，preview标记按所用IDF版本要求。**这些是原生参考说明；当前掌问Lua模式不执行这些构建、刷写、分区或驱动安装步骤。**

当前Lua路径仍是掌问生成→用户接受保存→WiFi上传运行，先根据integration.md提供的已核对Lua接口实现可支持的局部逻辑。未确认驱动的扩展模块只解释案例和缺项，不直接假造Lua模块名。以下固定链接可回到对应完整上游案例。

### AI按键与状态LED · button_led_test

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/button_led_test)
- 用法与现象：按下/松开/单击/连击/长按；按住AI键亮LED。
- 硬件前提：板载AI键；V1.2无旧GPIO3状态LED。
- 当前Lua适配：Lua button可参考事件逻辑；不得在V1.2切换GPIO3。README中的agent_feedback/collect_serial.py不在当前树，不指导执行这些缺失文件。

### 麦克风到扬声器回环 · audio_loopback

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/audio_loopback)
- 用法与现象：ES8311默认PCM采集并回放，原生增益30dB/音量50。
- 硬件前提：板载音频。
- 当前Lua适配：Lua audio可做有时限回环；依据info格式，低音量起步，防声反馈。

### 触摸显示与LVGL基准 · hmi_demo

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/hmi_demo)
- 用法与现象：480×480 CO5300，bsp_display_start与LVGL锁。
- 硬件前提：板载屏幕/触摸。
- 当前Lua适配：Lua用display或lvgl；原生LVGL benchmark不是可直接粘贴Lua。

### BMI270摇晃/倾斜/翻转 · imu_gesture

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/imu_gesture)
- 用法与现象：40ms采样，80ms启动等待，600ms冷却；幅度突变/XY倾斜/Z翻转。
- 硬件前提：板载BMI270，无外接传感器。
- 当前Lua适配：Lua imu原始计数须确认量程或先做相对基线；不能直接照抄以g为单位的1.6/0.75/-0.70阈值；原生可选马达80ms反馈，V1.2跳过LED。

### 低功耗与定时唤醒 · low_power_wakeup

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/low_power_wakeup)
- 用法与现象：准备LCD/NAND休眠，关电源轨，再进入深睡；默认定时10秒。
- 硬件前提：主板。
- 当前Lua适配：原生固件模板，当前WiFi运行流程不自动做；BOOT61非RTC IO，不能EXT1唤醒。

### NVS产品设置 · device_settings

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/device_settings)
- 用法与现象：schema版本迁移、类型校验、默认值、保存/修复；只重置本应用namespace。
- 硬件前提：主板。
- 当前Lua适配：原生NVS案例；Lua存储能力按storage文档，不能擦设备凭据或全库。

### 摄像头实时预览 · camera_lcd_preview

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/camera_lcd_preview)
- 用法与现象：自动发现/claim，UYVY经PPA裁剪转RGB565显示；超时恢复。
- 硬件前提：左槽Camera，OV3640/SC101IOT；UART调试。
- 当前Lua适配：Lua用camera+image+display，先枚举path和格式，及时释放帧；不可用右槽。

### 触摸相机与相册 · camera_photo_app

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/camera_photo_app)
- 用法与现象：快门、照片浏览/滑动、镜像、可选闪光、GPIO7长按开关；NAND照片，USB MSC默认关闭。
- 硬件前提：左槽Camera；USB导出需要专门分区/TinyUSB配置。
- 当前Lua适配：Lua可参考拍照/图像流程；完整相册/USB磁盘是原生应用，不覆盖当前固件/NAND。照片删除不自动回收原始页；README部分只描述旧OV3640，当前驱动支持两传感器并限制专用寄存器。

### WiFi图传 · wifi_http_cam

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/wifi_http_cam)
- 用法与现象：原生SoftAP mosaico-cam，192.168.4.1的/、/jpg、/stream。
- 硬件前提：左槽Camera；UART调试。
- 当前Lua适配：这是独立固件的开放SoftAP，不是当前Claw局域网运行接口。README称OV3640直出JPEG已落后，当前源码UYVY用硬件JPEG编码。Lua须依实际camera/HTTP模块，不改当前WiFi配置。

### 人脸/COCO模型切换 · ai_model_gallery

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/ai_model_gallery)
- 用法与现象：AI键轮换face/coco/idle；一次仅构建一个模型，PPA转换BGR888。
- 硬件前提：左槽Camera、PSRAM及对应原生模型组件。
- 当前Lua适配：Lua视觉用已编译的具体模块与已存在模型；不可臆造human_face_detect Lua对象。

### MP3播放 · gmf_audio_player

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/gmf_audio_player)
- 用法与现象：ESP-GMF解码内置alarm.mp3，BSP PCM输出。
- 硬件前提：板载ES8311及喇叭。
- 当前Lua适配：Lua可用audio.player播放实际存在的媒体；不假设alarm.mp3已在Claw存储中。

### 中文离线TTS · voice_tts

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/voice_tts)
- 用法与现象：ESP-SR Xiaole voice_data专用分区，启动播固定词组。
- 硬件前提：板载喇叭、语音数据分区。
- 当前Lua适配：完整ESP-SR是原生依赖；audio模块不代表已有任意中文TTS Lua接口，不要求配置板载模型来代替。

### 离线唤醒与命令识别 · voice_wake_cmd

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/voice_wake_cmd)
- 用法与现象：WakeNet9+MultiNet7中文命令+Xiaole反馈，默认Hi乐鑫。
- 硬件前提：板载麦克风/喇叭，约6MB model+3.8MB voice_data分区。
- 当前Lua适配：专用原生应用；不能在普通Lua里编造唤醒引擎或改分区。

### Windows USB副屏 · usb_extend_screen

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/usb_extend_screen)
- 用法与现象：480×480默认RGB565，选配最多5触点HID与UAC音频。
- 硬件前提：HS OTG、Windows10/11官方IDD；UART调试。
- 当前Lua适配：专用TinyUSB固件占用OTG并默认关BSP CDC，非当前WiFi Lua功能；不自动安装驱动。

### 多功能交互板 · interaction_board_demo

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/interaction_board_demo)
- 用法与现象：左右触摸/GPIO键、PIR、环境光、6颗WS2812，点击IR SEND发NEC 0x00/0x10。
- 硬件前提：额外Interaction模块，任一槽位。
- 当前Lua适配：不是主板自带PIR/灯/光敏。Lua若缺板级驱动须按对应库/实际映射逐项适配，不能把检测到EEPROM当成功。

### VL53L0X距离仪表 · tof_distance

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/tof_distance)
- 用法与现象：有效距离mm与信号/环境MCPS，100ms间隔；无效值清屏，移除释放再发现。
- 硬件前提：额外ToF，描述符type0x10，I²C0x29；共享总线只接1块。
- 当前Lua适配：原生驱动案例；未核实Claw对应ToF Lua模块，不造tof.read。无效range status不等于已拔出。

### MLX90640热成像 · thermal_camera

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/thermal_camera)
- 用法与现象：32×24、伪彩/中值/双线性、中心/最高/最低温；400kHz、16Hz子页约8Hz整帧。
- 硬件前提：额外Thermal，type0x12，I²C0x33；同地址只接1块。
- 当前Lua适配：原生组件，默认发射率0.95需按材料调整；Lua无已核实热像API。不把官方局部现场验收当用户本板温度精度认证。

### 4路继电器触摸控制 · relay_control

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/relay_control)
- 用法与现象：点卡片翻转通道，ALL OFF；上电/重连全关，拔出清理。
- 硬件前提：额外Relay，描述符type0x13；任一槽位。
- 当前Lua适配：原生mosaico_relay；显示的是GPIO命令状态，不是触点反馈。Lua先确认真实模块和映射，不能自动接通负载。

### 8×8 RGB矩阵 · matrix_rgb_led

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/matrix_rgb_led)
- 用法与现象：plasma/spiral/ripples/meteor/fire/balls/scan/twinkle，各约8秒，LCD同步预览。
- 硬件前提：额外Matrix，type0x11；左GPIO48/右47，任一槽位、一次1块。
- 当前Lua适配：WS2812，索引x*8+y，右槽旋转180°；原生驱动claim。Lua led_strip需另核实签名和占用，不能以主板自带矩阵回答。

### 左右模块监视 · module_slot_scan

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/module_slot_scan)
- 用法与现象：左右半屏，空槽占位；左Camera预览、Interaction控制、其他模块只显示名称。
- 硬件前提：按需要插入外接模块；UART调试。
- 当前Lua适配：识别不等于具备驱动，三个缺失probe后判拔出；当前管理器可在claim时继续探测。无通用Lua module_mgr API依据。

### EEPROM制造/配置工具 · module_eeprom_programmer

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/module_eeprom_programmer)
- 用法与现象：一次接1块、屏幕选类型、Start Write后写入并回读。
- 硬件前提：AT24C02模块；标准0x50优先后0x51。
- 当前Lua适配：会修改模块识别信息，是独立原生配置工具，不能作为普通探测程序自动执行。当前9个profile无Joystick；其他README要求Joystick profile与工具现状不一致，应先核对正式描述符来源。

### 多板ESP-NOW聊天 · espnow_chat

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/espnow_chat)
- 用法与现象：AI键广播短消息，周期HELLO，显示来源与RSSI。
- 硬件前提：2台或以上Mosaico。
- 当前Lua适配：无磁吸依赖，独立原生ESP-NOW应用；当前Claw未核实对应Lua绑定，不把普通WiFi连接等同ESP-NOW可用。

### 磁吸边缘/拓扑/能量接力 · magnetic_interaction_demo

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/magnetic_interaction_demo)
- 用法与现象：双BMM150识别TOP/RIGHT/BOTTOM/LEFT；ESP-NOW握手与网格路由。
- 硬件前提：2台以上同型板，非铁磁桌面；先分开放稳校准，逐条接缝等待PAIRED。
- 当前Lua适配：固定通道/网络ID/同版本；不输出未经校准的磁场角/距离/置信度。支持16节点是数据结构容量，九板RF/视觉连续性仍待实板验证；不冒充本次验收。

### 双屏Pong · dual_screen_pong

- [官方案例](https://github.com/esp-mosaico/esp-mosaico-bsp/tree/7cbfb390638dcb93522fc3cde094b2d43cf907c2/examples/dual_screen_pong)
- 用法与现象：两台组成960×480，ESP-NOW同步；每板摇杆控制，1确认/发球、2暂停、3重启、4表情。
- 硬件前提：2台Mosaico+2个Joystick模块，原生双轴摇杆驱动。
- 当前Lua适配：先全量程摇杆校准；磁吸仅选配无缝布局，失败仍可无线玩；两板按钮1确认配对。当前EEPROM工具无Joystick profile须核对，不编造Lua多人游戏绑定。

## 建议先做的三个板载测试

1. IMU原始采样：无需加模块，使用integration.md的5秒参考，先看静置/移动轴变化；注册名报错时只核对固件设备名称。
2. 方向控制小球：在有效原始采样的基础上使用板载屏幕，先设死区、平滑、边界和明确运行时限；不以未核实量程输出精确角度。
3. 双磁力计变化：核实两个固件注册名并分别采样，先比较无磁铁/接近时数据，再讨论校准或磁吸边缘。两颗磁力计不是两套IMU。

以上均为待接受的参考/设计，不自动保存、上传、运行、修改路由或配置设备。
