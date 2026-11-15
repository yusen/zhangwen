# 参数

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_espressif_mosaico",
  "name": "ESP-Mosaico（Chat Coding）",
  "category": "MCU",
  "electrical": {
    "voltage": 5.0,
    "voltageMin": null,
    "voltageMax": null,
    "supplyVoltages": [
      5.0
    ],
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "WiFi",
    "i2cAddress": null,
    "supportedMCUs": [],
    "driverName": "ESP-Claw WebIM",
    "firmwareRequirement": "兼容固定局域网接口的Mosaico-Claw应用；默认掌问生成Lua、WiFi上传运行，无需板载LLM Key或MicroPython"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": [
    "USB供电",
    "3.3V逻辑",
    "任务可能驱动实物"
  ],
  "notes": "USB/IN供电与GPIO信号电平分开；外设供电、接口、CoreBoard版本按实物与官方资料确认。按下方V1.0/V1.2映射使用；结构尺寸未知不猜测，电流0为未知占位。",
  "verificationStatus": "OFFICIAL_REFERENCE_UNTESTED",
  "sourceIds": [
    "https://mosaico.espressif.com/zh/guide/",
    "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s31/esp-mosaico/index.html"
  ]
}
```

## 官方CoreBoard V1.2板内器件地址（7位）

| 器件 | 地址 | 总线/功能 |
| --- | --- | --- |
| BMI270 | 0x69 | I2C0，三轴加速度+三轴角速度 |
| BMM150 #2 / #3 | 0x11 / 0x12 | I2C0，两颗磁力计；BSP索引0/1 |
| ES8311 | 0x19 | I2C0控制，I2S音频；esp_codec_dev使用8位左移地址，不混用于7位Lua I²C |
| BQ27220 | 0x55 | I2C0电量计 |
| CST9220系列 | 0x5A | I2C0触摸 |
| 外接模块EEPROM | 左0x50 / 右0x51 | I2C1，仅实际装有EEPROM的模块存在时出现 |

### 接口引脚（CoreBoard V1.2）

左右插槽不是同一个GPIO序列；物理针脚和GPIO编号不能互换。

| 连接器Pin | 左H2 | 右H1 |
| --- | --- | --- |
| 1 / 3 / 5 / 7 / 9 / 11 | GPIO55 / 19 / 18 / 17 / 16 / 15 | GPIO49 / 52 / 54 / 37 / 40 / 38 |
| 13 / 15 | GPIO33 USJ_DN / GPIO34 USJ_DP | GPIO59 RX0 / GPIO58 TX0 |
| 17 / 19 | 5V_IN / 3.3V_OUT | 5V_IN / 3.3V_OUT |
| 20 / 18 | GND / 5V_OUT | GND / 5V_OUT |
| 16 / 14 | GPIO0 SDA1 / GPIO1 SCL1 | GPIO0 SDA1 / GPIO1 SCL1 |
| 12 / 10 / 8 / 6 / 4 / 2 | GPIO4 / 14 / 12 / 13 / 48 / 53 | GPIO5 / 39 / 10 / 11 / 47 / 46 |

右槽前5个GPIO与板载音频复用；左槽GPIO33/34与USB Serial/JTAG/摄像头资源有关。GPIO14左地址选择低、GPIO39右地址选择高；摄像头仅左，右侧模块方向旋转180°。

板内关键引脚：传感器INT2、触摸INT6、AI键7低有效、马达8高有效、BOOT61；LCD DATA3/2/0/1=9/35/36/51、CS50、TE43、RST44、CLK42；NAND CLK/D/Q/CS/HOLD/WP=20/21/22/23/24/25；音频MCLK54/BCK37/WS49/DIN52/DOUT40、PA45；GPIO60电源低有效，GPIO57开漏关机请求。

V1.0：板内I2C0=GPIO0/1，LCD RST42/CLK44、GPIO3状态LED低有效、GPIO56控制codec电源。当前BSP通过eFuse USER_DATA识别V1.0/V1.2，V1.1用V1.2映射；未编程/不支持版本返回错误，不默认猜测板型。

供电：USB-C/5V_IN或3.7V电池；GPIO为3.3V逻辑，不把5V供电接到信号脚。板载128MB NAND不是可随意格式化的空盘；项目上传继续遵循现有备份与文件清单。
