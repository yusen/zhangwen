<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_seeed_f226fa37b837",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "Grove - ADC用于称重传感器 (HX711) · HX711",
      "summary": "HX711双线原始计数，通道A/增益128；含就绪超时，不换算重量。",
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
          "default": "HX711",
          "options": [
            {
              "value": "HX711",
              "label": "HX711双线"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
          "key": "sig2",
          "label": "第二信号引脚",
          "default": "1",
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
          "signal": "DOUT",
          "target": "{{sig}}"
        },
        {
          "signal": "PD_SCK",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "按称重桥铭牌接E+/E-/A+/A-；需空秤去皮和已知砝码校准后才能换算重量，示例只读有符号24位原始计数。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/grove_adc_for_load_cell_hx711/",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# Grove - ADC用于称重传感器 (HX711)\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import MPythonPin, PinMode\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import disable_irq, enable_irq\nfrom utime import ticks_ms, ticks_diff\ndata = MPythonPin({{sig}}, PinMode.IN).Pin\nclock = MPythonPin({{sig2}}, PinMode.OUT).Pin\nclock.value(0)\n\ndef read_raw():\n    start = ticks_ms()\n    while data.value():\n        if ticks_diff(ticks_ms(), start) > 1500:\n            return None\n        sleep_ms(1)\n    value = 0\n    # Keep clock-high pulses below the HX711 power-down threshold.\n    state = disable_irq()\n    try:\n        for _ in range(24):\n            clock.value(1)\n            sleep_us(1)\n            value = (value << 1) | data.value()\n            clock.value(0)\n            sleep_us(1)\n        # 25 pulses selects channel A, gain 128 for the NEXT conversion.\n        clock.value(1)\n        sleep_us(1)\n        clock.value(0)\n    finally:\n        enable_irq(state)\n    return value - 0x1000000 if value & 0x800000 else value\n\nread_raw()  # Discard the first conversion after power-up / gain change.\nfor _ in range(20):\n    raw = read_raw()\n    print(\"HX711 timeout\" if raw is None else \"HX711 raw = %s\" % raw)\n    sleep_ms(100)\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "Grove - ADC用于称重传感器 (HX711) · HX711",
      "summary": "HX711双线原始计数，通道A/增益128；含就绪超时，不换算重量。",
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
          "default": "HX711",
          "options": [
            {
              "value": "HX711",
              "label": "HX711双线"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
          "key": "sig2",
          "label": "第二信号引脚",
          "default": "Pin.P1",
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
          "signal": "DOUT",
          "target": "{{sig}}"
        },
        {
          "signal": "PD_SCK",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "按称重桥铭牌接E+/E-/A+/A-；需空秤去皮和已知砝码校准后才能换算重量，示例只读有符号24位原始计数。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/grove_adc_for_load_cell_hx711/",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# Grove - ADC用于称重传感器 (HX711)\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import disable_irq, enable_irq\nfrom utime import ticks_ms, ticks_diff\ndata = Pin({{sig}}, Pin.IN)\nclock = Pin({{sig2}}, Pin.OUT)\nclock.value(0)\n\ndef read_raw():\n    start = ticks_ms()\n    while data.value():\n        if ticks_diff(ticks_ms(), start) > 1500:\n            return None\n        sleep_ms(1)\n    value = 0\n    # Keep clock-high pulses below the HX711 power-down threshold.\n    state = disable_irq()\n    try:\n        for _ in range(24):\n            clock.value(1)\n            sleep_us(1)\n            value = (value << 1) | data.value()\n            clock.value(0)\n            sleep_us(1)\n        # 25 pulses selects channel A, gain 128 for the NEXT conversion.\n        clock.value(1)\n        sleep_us(1)\n        clock.value(0)\n    finally:\n        enable_irq(state)\n    return value - 0x1000000 if value & 0x800000 else value\n\nread_raw()  # Discard the first conversion after power-up / gain change.\nfor _ in range(20):\n    raw = read_raw()\n    print(\"HX711 timeout\" if raw is None else \"HX711 raw = %s\" % raw)\n    sleep_ms(100)\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "Grove - ADC用于称重传感器 (HX711) · HX711",
      "summary": "K10未公开可用原生GPIO，不能套用HX711位操作；仅提供环境诊断。",
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
          "default": "HX711",
          "options": [
            {
              "value": "HX711",
              "label": "HX711双线"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
          "key": "sig2",
          "label": "第二信号引脚",
          "default": "1",
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
          "signal": "DOUT",
          "target": "{{sig}}"
        },
        {
          "signal": "PD_SCK",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "按称重桥铭牌接E+/E-/A+/A-；需空秤去皮和已知砝码校准后才能换算重量，示例只读有符号24位原始计数。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/grove_adc_for_load_cell_hx711/",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# Grove - ADC用于称重传感器 (HX711)\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "Grove - ADC用于称重传感器 (HX711) · HX711",
      "summary": "HX711双线原始计数，通道A/增益128；含就绪超时，不换算重量。",
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
          "default": "HX711",
          "options": [
            {
              "value": "HX711",
              "label": "HX711双线"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
          "key": "sig2",
          "label": "第二信号引脚",
          "default": "2",
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
          "signal": "DOUT",
          "target": "{{sig}}"
        },
        {
          "signal": "PD_SCK",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "按称重桥铭牌接E+/E-/A+/A-；需空秤去皮和已知砝码校准后才能换算重量，示例只读有符号24位原始计数。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/grove_adc_for_load_cell_hx711/",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# Grove - ADC用于称重传感器 (HX711)\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import disable_irq, enable_irq\nfrom utime import ticks_ms, ticks_diff\ndata = Pin({{sig}}, Pin.IN)\nclock = Pin({{sig2}}, Pin.OUT)\nclock.value(0)\n\ndef read_raw():\n    start = ticks_ms()\n    while data.value():\n        if ticks_diff(ticks_ms(), start) > 1500:\n            return None\n        sleep_ms(1)\n    value = 0\n    # Keep clock-high pulses below the HX711 power-down threshold.\n    state = disable_irq()\n    try:\n        for _ in range(24):\n            clock.value(1)\n            sleep_us(1)\n            value = (value << 1) | data.value()\n            clock.value(0)\n            sleep_us(1)\n        # 25 pulses selects channel A, gain 128 for the NEXT conversion.\n        clock.value(1)\n        sleep_us(1)\n        clock.value(0)\n    finally:\n        enable_irq(state)\n    return value - 0x1000000 if value & 0x800000 else value\n\nread_raw()  # Discard the first conversion after power-up / gain change.\nfor _ in range(20):\n    raw = read_raw()\n    print(\"HX711 timeout\" if raw is None else \"HX711 raw = %s\" % raw)\n    sleep_ms(100)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "Grove - ADC用于称重传感器 (HX711) · HX711",
      "summary": "HX711双线原始计数，通道A/增益128；含就绪超时，不换算重量。",
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
          "default": "HX711",
          "options": [
            {
              "value": "HX711",
              "label": "HX711双线"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
          "key": "sig2",
          "label": "第二信号引脚",
          "default": "4",
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
          "signal": "DOUT",
          "target": "{{sig}}"
        },
        {
          "signal": "PD_SCK",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "按称重桥铭牌接E+/E-/A+/A-；需空秤去皮和已知砝码校准后才能换算重量，示例只读有符号24位原始计数。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/grove_adc_for_load_cell_hx711/",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# Grove - ADC用于称重传感器 (HX711)\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import disable_irq, enable_irq\nfrom utime import ticks_ms, ticks_diff\ndata = Pin({{sig}}, Pin.IN)\nclock = Pin({{sig2}}, Pin.OUT)\nclock.value(0)\n\ndef read_raw():\n    start = ticks_ms()\n    while data.value():\n        if ticks_diff(ticks_ms(), start) > 1500:\n            return None\n        sleep_ms(1)\n    value = 0\n    # Keep clock-high pulses below the HX711 power-down threshold.\n    state = disable_irq()\n    try:\n        for _ in range(24):\n            clock.value(1)\n            sleep_us(1)\n            value = (value << 1) | data.value()\n            clock.value(0)\n            sleep_us(1)\n        # 25 pulses selects channel A, gain 128 for the NEXT conversion.\n        clock.value(1)\n        sleep_us(1)\n        clock.value(0)\n    finally:\n        enable_irq(state)\n    return value - 0x1000000 if value & 0x800000 else value\n\nread_raw()  # Discard the first conversion after power-up / gain change.\nfor _ in range(20):\n    raw = read_raw()\n    print(\"HX711 timeout\" if raw is None else \"HX711 raw = %s\" % raw)\n    sleep_ms(100)\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
