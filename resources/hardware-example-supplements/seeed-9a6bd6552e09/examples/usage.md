<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_seeed_9a6bd6552e09",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "Grove - 三轴模拟加速度计 · ADC",
      "summary": "读取三路ADC原始量；未做物理单位转换或校准。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
              "value": "2",
              "label": "P2"
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
              "value": "2",
              "label": "P2"
            }
          ]
        },
        {
          "key": "sig3",
          "label": "第三信号引脚",
          "default": "2",
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
              "value": "2",
              "label": "P2"
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
          "signal": "AO / S",
          "target": "{{sig}}"
        },
        {
          "signal": "第三路信号",
          "target": "{{sig3}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-3-Axis_Analog_Accelerometer/",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# Grove - 三轴模拟加速度计\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import MPythonPin, PinMode\nfrom utime import sleep_ms\nadc0 = MPythonPin({{sig}}, PinMode.ANALOG)\nadc1 = MPythonPin({{sig2}}, PinMode.ANALOG)\nadc2 = MPythonPin({{sig3}}, PinMode.ANALOG)\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read_analog(), adc1.read_analog(), adc2.read_analog())\n    sleep_ms(250)\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "reference",
      "title": "Grove - 三轴模拟加速度计 · ADC",
      "summary": "此模块需要三路ADC；当前已核对的可选引脚不足三路，需要确认额外ADC引脚或另配ADC扩展。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-3-Axis_Analog_Accelerometer/",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# Grove - 三轴模拟加速度计\n# 掌控板3.0官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "reference",
      "title": "Grove - 三轴模拟加速度计 · ADC",
      "summary": "此模块需要三路ADC；当前已核对的可选引脚不足三路，需要确认额外ADC引脚或另配ADC扩展。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-3-Axis_Analog_Accelerometer/",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# Grove - 三轴模拟加速度计\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "Grove - 三轴模拟加速度计 · ADC",
      "summary": "读取三路ADC原始量；未做物理单位转换或校准。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
        },
        {
          "key": "sig3",
          "label": "第三信号引脚",
          "default": "3",
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
          "signal": "AO / S",
          "target": "{{sig}}"
        },
        {
          "signal": "第三路信号",
          "target": "{{sig3}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-3-Axis_Analog_Accelerometer/",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# Grove - 三轴模拟加速度计\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, ADC\nfrom utime import sleep_ms\nadc0 = ADC(Pin({{sig}}))\nadc0.atten(ADC.ATTN_11DB)\nadc1 = ADC(Pin({{sig2}}))\nadc1.atten(ADC.ATTN_11DB)\nadc2 = ADC(Pin({{sig3}}))\nadc2.atten(ADC.ATTN_11DB)\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read(), adc1.read(), adc2.read())\n    sleep_ms(250)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "reference",
      "title": "Grove - 三轴模拟加速度计 · ADC",
      "summary": "此模块需要三路ADC；当前已核对的可选引脚不足三路，需要确认额外ADC引脚或另配ADC扩展。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-3-Axis_Analog_Accelerometer/",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# Grove - 三轴模拟加速度计\n# ESP32_GENERIC_C3官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
