<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_labplus_b94b67e6f02c",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "盛思 RGB LED(4灯) · NEOPIXEL",
      "summary": "低亮度点亮第一颗灯珠；数量按实际选择，不默认全亮。",
      "fields": [
        {
          "key": "firmware",
          "label": "固件环境",
          "default": "掌控板2.0官方MicroPython",
          "options": [
            {
              "value": "掌控板2.0官方MicroPython",
              "label": "掌控板2.0官方MicroPython"
            }
          ]
        },
        {
          "key": "interface",
          "label": "模块接口",
          "default": "NEOPIXEL",
          "options": [
            {
              "value": "NEOPIXEL",
              "label": "WS2812"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "3.3V",
          "options": [
            {
              "value": "3.3V",
              "label": "3.3V"
            }
          ]
        },
        {
          "key": "sig",
          "label": "信号引脚",
          "default": "0",
          "options": [
            {
              "value": "0",
              "label": "P0"
            },
            {
              "value": "1",
              "label": "P1"
            },
            {
              "value": "8",
              "label": "P8"
            },
            {
              "value": "9",
              "label": "P9"
            },
            {
              "value": "13",
              "label": "P13"
            },
            {
              "value": "14",
              "label": "P14"
            },
            {
              "value": "15",
              "label": "P15"
            },
            {
              "value": "16",
              "label": "P16"
            }
          ]
        },
        {
          "key": "count",
          "label": "灯珠数量",
          "default": "1",
          "options": [
            {
              "value": "1",
              "label": "1"
            },
            {
              "value": "3",
              "label": "3"
            },
            {
              "value": "4",
              "label": "4"
            },
            {
              "value": "7",
              "label": "7"
            },
            {
              "value": "10",
              "label": "10"
            },
            {
              "value": "24",
              "label": "24"
            }
          ]
        }
      ],
      "connections": [
        {
          "signal": "GND / G",
          "target": "主控GND（共地）"
        },
        {
          "signal": "VCC / V",
          "target": "{{supply}}"
        },
        {
          "signal": "DIN",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "灯带用符合额定值的独立电源并共地；长灯带不能由主控3V3口直接供电。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/RGB_LED(4%E7%81%AF",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# 盛思 RGB LED(4灯)\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import MPythonPin, PinMode\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom neopixel import NeoPixel\nstrip = NeoPixel(MPythonPin({{sig}}, PinMode.OUT).Pin, {{count}})\nstrip.fill((0, 0, 0))\nstrip[0] = (8, 0, 0)\nstrip.write()\nsleep_ms(1000)\nstrip.fill((0, 0, 0))\nstrip.write()\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "盛思 RGB LED(4灯) · NEOPIXEL",
      "summary": "低亮度点亮第一颗灯珠；数量按实际选择，不默认全亮。",
      "fields": [
        {
          "key": "firmware",
          "label": "固件环境",
          "default": "掌控板3.0官方MicroPython",
          "options": [
            {
              "value": "掌控板3.0官方MicroPython",
              "label": "掌控板3.0官方MicroPython"
            }
          ]
        },
        {
          "key": "interface",
          "label": "模块接口",
          "default": "NEOPIXEL",
          "options": [
            {
              "value": "NEOPIXEL",
              "label": "WS2812"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "3.3V",
          "options": [
            {
              "value": "3.3V",
              "label": "3.3V"
            }
          ]
        },
        {
          "key": "sig",
          "label": "信号引脚",
          "default": "Pin.P0",
          "options": [
            {
              "value": "Pin.P0",
              "label": "P0"
            },
            {
              "value": "Pin.P1",
              "label": "P1"
            }
          ]
        },
        {
          "key": "count",
          "label": "灯珠数量",
          "default": "1",
          "options": [
            {
              "value": "1",
              "label": "1"
            },
            {
              "value": "3",
              "label": "3"
            },
            {
              "value": "4",
              "label": "4"
            },
            {
              "value": "7",
              "label": "7"
            },
            {
              "value": "10",
              "label": "10"
            },
            {
              "value": "24",
              "label": "24"
            }
          ]
        }
      ],
      "connections": [
        {
          "signal": "GND / G",
          "target": "主控GND（共地）"
        },
        {
          "signal": "VCC / V",
          "target": "{{supply}}"
        },
        {
          "signal": "DIN",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "灯带用符合额定值的独立电源并共地；长灯带不能由主控3V3口直接供电。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/RGB_LED(4%E7%81%AF",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# 盛思 RGB LED(4灯)\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom neopixel import NeoPixel\nstrip = NeoPixel(Pin({{sig}}, Pin.OUT), {{count}})\nstrip.fill((0, 0, 0))\nstrip[0] = (8, 0, 0)\nstrip.write()\nsleep_ms(1000)\nstrip.fill((0, 0, 0))\nstrip.write()\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "functional",
      "title": "盛思 RGB LED(4灯) · NEOPIXEL",
      "summary": "低亮度点亮第一颗灯珠；数量按实际选择，不默认全亮。",
      "fields": [
        {
          "key": "firmware",
          "label": "固件环境",
          "default": "K10官方MicroPython / unihiker_k10",
          "options": [
            {
              "value": "K10官方MicroPython / unihiker_k10",
              "label": "K10官方MicroPython / unihiker_k10"
            }
          ]
        },
        {
          "key": "interface",
          "label": "模块接口",
          "default": "NEOPIXEL",
          "options": [
            {
              "value": "NEOPIXEL",
              "label": "WS2812"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "3.3V",
          "options": [
            {
              "value": "3.3V",
              "label": "3.3V"
            }
          ]
        },
        {
          "key": "sig",
          "label": "信号引脚",
          "default": "0",
          "options": [
            {
              "value": "0",
              "label": "P0（直连）"
            },
            {
              "value": "1",
              "label": "P1（直连）"
            }
          ]
        },
        {
          "key": "count",
          "label": "灯珠数量",
          "default": "1",
          "options": [
            {
              "value": "1",
              "label": "1"
            },
            {
              "value": "3",
              "label": "3"
            },
            {
              "value": "4",
              "label": "4"
            },
            {
              "value": "7",
              "label": "7"
            },
            {
              "value": "10",
              "label": "10"
            },
            {
              "value": "24",
              "label": "24"
            }
          ]
        }
      ],
      "connections": [
        {
          "signal": "GND / G",
          "target": "主控GND（共地）"
        },
        {
          "signal": "VCC / V",
          "target": "{{supply}}"
        },
        {
          "signal": "DIN",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "灯带用符合额定值的独立电源并共地；长灯带不能由主控3V3口直接供电。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/RGB_LED(4%E7%81%AF",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# 盛思 RGB LED(4灯)\n# K10官方MicroPython / unihiker_k10\n# 功能示例，待实物测试。\nfrom unihiker_k10 import neopixel\nstrip = neopixel({{sig}}, {{count}})\nstrip.brightness(1)\nstrip.write(0, 0, 0x08, 0, 0)\nprint(\"First pixel command submitted; inspect the LED.\")\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "盛思 RGB LED(4灯) · NEOPIXEL",
      "summary": "低亮度点亮第一颗灯珠；数量按实际选择，不默认全亮。",
      "fields": [
        {
          "key": "firmware",
          "label": "固件环境",
          "default": "XIAO ESP32S3官方MicroPython",
          "options": [
            {
              "value": "XIAO ESP32S3官方MicroPython",
              "label": "XIAO ESP32S3官方MicroPython"
            }
          ]
        },
        {
          "key": "interface",
          "label": "模块接口",
          "default": "NEOPIXEL",
          "options": [
            {
              "value": "NEOPIXEL",
              "label": "WS2812"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "3.3V",
          "options": [
            {
              "value": "3.3V",
              "label": "3.3V"
            }
          ]
        },
        {
          "key": "sig",
          "label": "信号引脚",
          "default": "1",
          "options": [
            {
              "value": "1",
              "label": "D0 / GPIO1"
            },
            {
              "value": "2",
              "label": "D1 / GPIO2"
            },
            {
              "value": "3",
              "label": "D2 / GPIO3"
            }
          ]
        },
        {
          "key": "count",
          "label": "灯珠数量",
          "default": "1",
          "options": [
            {
              "value": "1",
              "label": "1"
            },
            {
              "value": "3",
              "label": "3"
            },
            {
              "value": "4",
              "label": "4"
            },
            {
              "value": "7",
              "label": "7"
            },
            {
              "value": "10",
              "label": "10"
            },
            {
              "value": "24",
              "label": "24"
            }
          ]
        }
      ],
      "connections": [
        {
          "signal": "GND / G",
          "target": "主控GND（共地）"
        },
        {
          "signal": "VCC / V",
          "target": "{{supply}}"
        },
        {
          "signal": "DIN",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "灯带用符合额定值的独立电源并共地；长灯带不能由主控3V3口直接供电。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/RGB_LED(4%E7%81%AF",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# 盛思 RGB LED(4灯)\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom neopixel import NeoPixel\nstrip = NeoPixel(Pin({{sig}}, Pin.OUT), {{count}})\nstrip.fill((0, 0, 0))\nstrip[0] = (8, 0, 0)\nstrip.write()\nsleep_ms(1000)\nstrip.fill((0, 0, 0))\nstrip.write()\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "盛思 RGB LED(4灯) · NEOPIXEL",
      "summary": "低亮度点亮第一颗灯珠；数量按实际选择，不默认全亮。",
      "fields": [
        {
          "key": "firmware",
          "label": "固件环境",
          "default": "ESP32_GENERIC_C3官方MicroPython",
          "options": [
            {
              "value": "ESP32_GENERIC_C3官方MicroPython",
              "label": "ESP32_GENERIC_C3官方MicroPython"
            }
          ]
        },
        {
          "key": "interface",
          "label": "模块接口",
          "default": "NEOPIXEL",
          "options": [
            {
              "value": "NEOPIXEL",
              "label": "WS2812"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "3.3V",
          "options": [
            {
              "value": "3.3V",
              "label": "3.3V"
            }
          ]
        },
        {
          "key": "sig",
          "label": "信号引脚",
          "default": "3",
          "options": [
            {
              "value": "3",
              "label": "GPIO3"
            },
            {
              "value": "4",
              "label": "GPIO4"
            }
          ]
        },
        {
          "key": "count",
          "label": "灯珠数量",
          "default": "1",
          "options": [
            {
              "value": "1",
              "label": "1"
            },
            {
              "value": "3",
              "label": "3"
            },
            {
              "value": "4",
              "label": "4"
            },
            {
              "value": "7",
              "label": "7"
            },
            {
              "value": "10",
              "label": "10"
            },
            {
              "value": "24",
              "label": "24"
            }
          ]
        }
      ],
      "connections": [
        {
          "signal": "GND / G",
          "target": "主控GND（共地）"
        },
        {
          "signal": "VCC / V",
          "target": "{{supply}}"
        },
        {
          "signal": "DIN",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "灯带用符合额定值的独立电源并共地；长灯带不能由主控3V3口直接供电。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/RGB_LED(4%E7%81%AF",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# 盛思 RGB LED(4灯)\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom neopixel import NeoPixel\nstrip = NeoPixel(Pin({{sig}}, Pin.OUT), {{count}})\nstrip.fill((0, 0, 0))\nstrip[0] = (8, 0, 0)\nstrip.write()\nsleep_ms(1000)\nstrip.fill((0, 0, 0))\nstrip.write()\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
