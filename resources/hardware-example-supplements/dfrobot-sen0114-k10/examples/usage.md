<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_dfrobot_sen0114_k10",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "DFRobot SEN0114 土壤湿度传感器 · ADC",
      "summary": "读取一路ADC原始量；未做物理单位转换或校准。",
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
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0114_Moisture_Sensor%E5%9C%9F%E5%A3%A4%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# DFRobot SEN0114 土壤湿度传感器\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import MPythonPin, PinMode\nfrom utime import sleep_ms\nadc0 = MPythonPin({{sig}}, PinMode.ANALOG)\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read_analog())\n    sleep_ms(250)\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "DFRobot SEN0114 土壤湿度传感器 · ADC",
      "summary": "读取一路ADC原始量；未做物理单位转换或校准。",
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
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0114_Moisture_Sensor%E5%9C%9F%E5%A3%A4%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# DFRobot SEN0114 土壤湿度传感器\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, ADC\nfrom utime import sleep_ms\nadc0 = ADC(Pin({{sig}}))\nadc0.atten(ADC.ATTN_11DB)\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read())\n    sleep_ms(250)\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "functional",
      "title": "DFRobot SEN0114 土壤湿度传感器 · ADC",
      "summary": "读取一路ADC原始量；未做物理单位转换或校准。",
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
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0114_Moisture_Sensor%E5%9C%9F%E5%A3%A4%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# DFRobot SEN0114 土壤湿度传感器\n# K10官方MicroPython / unihiker_k10\n# 功能示例，待实物测试。\nfrom unihiker_k10 import pin\nfrom utime import sleep_ms\nadc0 = pin({{sig}})\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read_analog())\n    sleep_ms(250)\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "DFRobot SEN0114 土壤湿度传感器 · ADC",
      "summary": "读取一路ADC原始量；未做物理单位转换或校准。",
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
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0114_Moisture_Sensor%E5%9C%9F%E5%A3%A4%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# DFRobot SEN0114 土壤湿度传感器\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, ADC\nfrom utime import sleep_ms\nadc0 = ADC(Pin({{sig}}))\nadc0.atten(ADC.ATTN_11DB)\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read())\n    sleep_ms(250)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "DFRobot SEN0114 土壤湿度传感器 · ADC",
      "summary": "读取一路ADC原始量；未做物理单位转换或校准。",
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
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0114_Moisture_Sensor%E5%9C%9F%E5%A3%A4%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# DFRobot SEN0114 土壤湿度传感器\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, ADC\nfrom utime import sleep_ms\nadc0 = ADC(Pin({{sig}}))\nadc0.atten(ADC.ATTN_11DB)\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read())\n    sleep_ms(250)\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
