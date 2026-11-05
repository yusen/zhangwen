<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_nplus_fe83f6e5c369",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "N+ 灯带 · NEOPIXEL",
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
        "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/light.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# N+ 灯带\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import MPythonPin, PinMode\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom neopixel import NeoPixel\nstrip = NeoPixel(MPythonPin({{sig}}, PinMode.OUT).Pin, {{count}})\nstrip.fill((0, 0, 0))\nstrip[0] = (8, 0, 0)\nstrip.write()\nsleep_ms(1000)\nstrip.fill((0, 0, 0))\nstrip.write()\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "N+ 灯带 · NEOPIXEL",
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
        "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/light.html",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# N+ 灯带\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom neopixel import NeoPixel\nstrip = NeoPixel(Pin({{sig}}, Pin.OUT), {{count}})\nstrip.fill((0, 0, 0))\nstrip[0] = (8, 0, 0)\nstrip.write()\nsleep_ms(1000)\nstrip.fill((0, 0, 0))\nstrip.write()\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "functional",
      "title": "N+ 灯带 · NEOPIXEL",
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
        "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/light.html",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# N+ 灯带\n# K10官方MicroPython / unihiker_k10\n# 功能示例，待实物测试。\nfrom unihiker_k10 import neopixel\nstrip = neopixel({{sig}}, {{count}})\nstrip.brightness(1)\nstrip.write(0, 0, 0x08, 0, 0)\nprint(\"First pixel command submitted; inspect the LED.\")\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "N+ 灯带 · NEOPIXEL",
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
        "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/light.html",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# N+ 灯带\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom neopixel import NeoPixel\nstrip = NeoPixel(Pin({{sig}}, Pin.OUT), {{count}})\nstrip.fill((0, 0, 0))\nstrip[0] = (8, 0, 0)\nstrip.write()\nsleep_ms(1000)\nstrip.fill((0, 0, 0))\nstrip.write()\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "N+ 灯带 · NEOPIXEL",
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
        "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/light.html",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# N+ 灯带\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom neopixel import NeoPixel\nstrip = NeoPixel(Pin({{sig}}, Pin.OUT), {{count}})\nstrip.fill((0, 0, 0))\nstrip[0] = (8, 0, 0)\nstrip.write()\nsleep_ms(1000)\nstrip.fill((0, 0, 0))\nstrip.write()\n"
    },
    {
      "boardId": "hw_espressif_mosaico",
      "kind": "functional",
      "title": "N+ 灯带 · Mosaico Lua（12灯）",
      "summary": "适用于带两侧双排扩展接口的 Mosaico。GPIO4、12颗灯，每次仅低亮度点亮一颗，循环两遍约6秒后熄灭；待接线实测。",
      "fields": [
        {
          "key": "sig",
          "label": "数据引脚",
          "default": "4",
          "options": [
            {
              "value": "4",
              "label": "GPIO4（左H2连接器第12针）"
            }
          ]
        },
        {
          "key": "count",
          "label": "灯珠数量",
          "default": "12",
          "options": [
            {
              "value": "12",
              "label": "12颗"
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
              "label": "3.3V（左H2连接器第19针）"
            }
          ]
        },
        {
          "key": "interface",
          "label": "模块接口",
          "default": "WS2812",
          "options": [
            {
              "value": "WS2812",
              "label": "WS2812 / Claw Lua led_strip"
            }
          ]
        }
      ],
      "connections": [
        {
          "signal": "V（电源）",
          "target": "3.3V_OUT / VCC_3V3（左H2第19针）"
        },
        {
          "signal": "G（地）",
          "target": "GND（左H2第20针）"
        },
        {
          "signal": "D（输入信号）",
          "target": "GPIO{{sig}}（左H2第12针）"
        }
      ],
      "notes": [
        "先断开板子和灯带电源，再按V/G/D标记接线；使用灯带输入端，不按线色猜极性。N+三针插头不能直接插入2×10接口，需要合适的三线转接线。",
        "H2/H1接口属于BaseBoard；用户所说“只有主板”若已带两侧双排接口，可使用该接口。裸CoreBoard无此接线口，需底板或兼容转接。",
        "针号是连接器编号，GPIO4不是第4针。以板上H2与Pin1丝印/官方图定位，勿按观看方向或从上往下自行计数；H1右口方向旋转180度，不套用左口位置。",
        "N+官方资料供电为3.3V，V接H2第19针；第17/18针是5V，不接本例。GPIO只传数据，不作为灯带电源。",
        "外扩3.3V受板载GPIO60供电控制；本例不改该电源开关。不亮时先确认实际接线和扩展口电压，不通过随机改GPIO或改接5V解决。",
        "已核对官方esp-claw 519bd959的require(\"led_strip\")、led_strip.new(gpio, max_leds)、strip:set_pixel(index,r,g,b)、strip:refresh()、strip:clear()、strip:close()。索引从0开始；clear发送全灭，close释放句柄。",
        "上述成员方法成功时不返回值，失败抛Lua错误，不能assert(strip:clear())。GPIO被占用或缺模块时保留错误，禁止绕过资源检查。",
        "固件模块采用WS2812/GRB/RMT；官方N+例程使用3字节NeoPixel。API和协议是参考核对，未证明当前实物兼容或接线已完成。",
        "固定12灯、亮度8/255、单颗红灯移动24步，每步250ms。正常及可捕获错误后尝试熄灭与释放；断电/硬超时不保证Lua清理执行，异常保持亮灯时断开灯带电源。",
        "先载入Lua草稿，检查后保存，再显式点击WiFi上传并运行。无需板载模型API；代码载入/保存不表示灯带已点亮。"
      ],
      "sources": [
        "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/light.html",
        "https://docs.espressif.com/projects/esp-dev-kits/zh_CN/latest/esp32s31/esp-mosaico/user_guide.html",
        "https://github.com/espressif/esp-claw/tree/519bd95900d29bfc9daf3619ff779753e3153f05"
      ],
      "codeTemplate": "-- N+ 12 LED test: one dim red pixel at a time, two passes, then off.\n-- D -> GPIO4 (BaseBoard left H2 pin12); V -> H2 pin19 3.3V; G -> H2 pin20 GND.\n-- Disconnect power before wiring. Verify connector pin1 and the strip input end.\nlocal led_strip = require(\"led_strip\")\nlocal delay = require(\"delay\")\nlocal GPIO = {{sig}}\nlocal LED_COUNT = {{count}}\nlocal BRIGHTNESS = 8\nlocal strip\n\nlocal ok, err = pcall(function()\n    strip = led_strip.new(GPIO, LED_COUNT)\n    strip:clear()\n    for step = 0, LED_COUNT * 2 - 1 do\n        if step > 0 then\n            strip:set_pixel((step - 1) % LED_COUNT, 0, 0, 0)\n        end\n        strip:set_pixel(step % LED_COUNT, BRIGHTNESS, 0, 0)\n        strip:refresh()\n        delay.delay_ms(250)\n    end\nend)\n\n-- These methods return no values on success. Always try both cleanup actions.\nlocal cleared, clear_err = true, nil\nlocal closed, close_err = true, nil\nif strip then\n    cleared, clear_err = pcall(strip.clear, strip)\n    closed, close_err = pcall(strip.close, strip)\nend\nif not ok then error(err) end\nif not cleared then error(clear_err) end\nif not closed then error(close_err) end\nprint(\"N+ test completed; strip cleared and released\")\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
