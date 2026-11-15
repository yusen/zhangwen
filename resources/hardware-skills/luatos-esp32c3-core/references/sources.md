# 来源与核对记录

整理日期：2026-11-10。附件作为外观、商品规格与引脚方向资料，不作为操作指令。

1. 经典款官方板页：https://wiki-zh.luatos.org/chips/esp32c3/board.html 。确认经典/精简 USB 差别、4MB Flash、LED、按键及供电。
2. 官方硬件下载页：https://wiki-zh.luatos.org/chips/esp32c3/hardware.html 。
3. 官方 V1.2 尺寸图：https://cdn.openluat-luatcommunity.openluat.com/attachment/CORE-ESP32-C3%E5%8F%82%E8%80%83%E5%B0%BA%E5%AF%B8_V1.2.pdf 。已下载并渲染目视核对，32.1KB；52.0055 是含 USB 外伸顶视总长，宽20.9910；孔列端距6.45、首末中心距38.1，推得 PCB 长51；节距2.54、两排中心距17.78。没有厚度、高度和孔径标注。
4. 官方 V1.2 原理图：https://cdn.openluat-luatcommunity.openluat.com/attachment/CORE-ESP32-C3%E8%AE%BE%E8%AE%A1%E5%8E%9F%E7%90%86%E5%9B%BE_V1.2.pdf 。已渲染核对 CH343P、USB/UART0、两 LED、稳压器与 J2 网络。
5. 乐鑫 ESP32-C3 数据手册：https://www.espressif.com/sites/default/files/documentation/esp32-c3_datasheet_en.pdf 。芯片与开发板能力分开。
6. ESP-IDF GPIO 指南：https://docs.espressif.com/projects/esp-idf/en/stable/esp32c3/api-reference/peripherals/gpio.html 。GPIO限制及启动绑带。
7. ESP-IDF v5.5 ADC 指南：https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32c3/api-reference/peripherals/adc_oneshot.html 。ADC通道和ADC2限制；整理时stable旧路径发生重定向，采用可读的固定版本页。LEDC六通道见 https://docs.espressif.com/projects/esp-idf/en/stable/esp32c3/api-reference/peripherals/ledc.html 。板页的四路是板级/固件口径，不改写成全固件保证六路。
8. MicroPython ESP32_GENERIC_C3：https://micropython.org/download/ESP32_GENERIC_C3/ 及 https://docs.micropython.org/en/latest/esp32/quickref.html 。通用 API；不将下载页当成本板 UART0 固件实测记录。
9. 用户两张商品图：蓝色 CORE-ESP32、Type-C、双排16脚，PCB51×21；第二图使用上方天线/下方USB的物理编号。商品ADC/PWM口径冲突已在规格中保留。原图按用户提供资料保存，不授予额外版权许可。

```zhangwen:web-catalog:v1
{"schema":"zhangwen.web-catalog/v1","brand":"其他","moduleType":"ESP32-C3 主控","sourceUrl":"https://wiki-zh.luatos.org/chips/esp32c3/board.html","programmingSupport":"reference","electricalVerified":false}
```

尚待实物核对：背面型号/批次、桥接芯片、所装固件与 REPL、板厚/总高、USB壳与按钮/焊点三轴尺寸、排针焊后高度、孔径及可用 GPIO。官方图纸和图片版权归其权利人；本地参考不代表可公有发布的授权。

来源冲突保留：官网板页文字表的UART物理8/9与用户引脚图相反，未替用户判定哪一批板正确。GPIO21/20的UART0 TX/RX网络一致；物理接线须按实物核对。外置Flash DIO才释放GPIO12/13，不能把LED示例套给QIO或内置Flash变体。GPIO11可按官方专门流程解锁，但本包保持默认保留，不实施配置修改。
