<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_dfrobot_sen0388_urm09_trig_k10",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython） · SINGLE_WIRE",
      "summary": "掌控板2.0单线测距：默认P1=GPIO32，使用MPythonPin映射；OLED和串口显示距离及原始脉宽，B键停止，待实测。",
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
          "default": "SINGLE_WIRE",
          "options": [
            {
              "value": "SINGLE_WIRE",
              "label": "单SIG触发/回波"
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
          "signal": "SIG / S",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "仅适用SEN0388单线版本，不适用SEN0307模拟量或SEN0304 I2C版本。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "P1=GPIO32、P0=GPIO33；machine.Pin(1/0)不是板上P1/P0。SEN0388量程2–500cm，10us触发、最长35ms回波、最高25Hz。",
        "本机案例接线是保存记录；用户明确新接线优先。超时或内部上拉读1不能单独证明模块损坏；先核对逻辑P号与GPIO映射。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/sen0388/",
        "https://wiki.dfrobot.com.cn/sku_sen0388_urm09_ultrasonic_sensor_gravity_trig",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://dfimg.dfrobot.com/wiki/24709/DFR0992-EN_unihiker-k10_schematics_V1.0.pdf",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython_code.html"
      ],
      "codeTemplate": "# DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython）\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\n# SEN0388单线D：+接3.3V、-接GND；sig为板上P号，不是原始GPIO号。\nfrom mpython import MPythonPin, PinMode, oled, button_b\nfrom machine import Pin, time_pulse_us\nfrom utime import sleep_ms, sleep_us\n\nP_NUMBER = {{sig}}  # P1=GPIO32，P0=GPIO33；请匹配实际接线。\nsig = MPythonPin(P_NUMBER, PinMode.OUT).Pin\n\ndef read_pulse_us():\n    # 高电平不少于10us；随后释放单线，由传感器输出回波。\n    sig.init(Pin.OUT, pull=None)\n    sig.value(0)\n    sleep_us(2)\n    sig.value(1)\n    sleep_us(12)\n    sig.value(0)\n    sig.init(Pin.IN, pull=None)\n    try:\n        return time_pulse_us(sig, 1, 40000)  # 官方最长回波约35ms。\n    except OSError as error:\n        print(\"Pulse error =\", error)\n        return -3\n\nsleep_ms(100)\nfor _ in range(100):\n    if button_b.value() == 0:\n        break\n    pulse = read_pulse_us()\n    cm = pulse * 0.01715 if pulse > 0 else None\n    valid = cm is not None and 2 <= cm <= 500\n    # 保留原始脉宽/超时码，不能仅凭无回波或上拉读数断定模块损坏。\n    print(\"P%d pulse_us=%d distance_cm=%s\" % (P_NUMBER, pulse, \"%.1f\" % cm if valid else \"invalid\"))\n    oled.fill(0)\n    oled.DispChar(\"URM09 P%d\" % P_NUMBER, 0, 0)\n    oled.DispChar(\"距离: %.1f cm\" % cm if valid else \"无有效回波\", 0, 16)\n    oled.DispChar(\"pulse: %d us\" % pulse, 0, 32)\n    oled.DispChar(\"B键停止\", 0, 48)\n    oled.show()\n    sleep_ms(300)  # 低于最高25Hz；联调约30秒自动结束。\nsig.init(Pin.IN, pull=None)\nprint(\"URM09 test stopped\")\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython） · SINGLE_WIRE",
      "summary": "单SIG触发/回波测距，厘米输出；超时明确显示无有效回波。",
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
          "default": "SINGLE_WIRE",
          "options": [
            {
              "value": "SINGLE_WIRE",
              "label": "单SIG触发/回波"
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
          "signal": "SIG / S",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "仅适用SEN0388单线版本，不适用SEN0307模拟量或SEN0304 I2C版本。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/sen0388/",
        "https://wiki.dfrobot.com.cn/sku_sen0388_urm09_ultrasonic_sensor_gravity_trig",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://dfimg.dfrobot.com/wiki/24709/DFR0992-EN_unihiker-k10_schematics_V1.0.pdf",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython）\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import time_pulse_us\nsig = Pin({{sig}}, Pin.OUT)\ndef read_cm():\n    sig.init(Pin.OUT)\n    sig.value(0)\n    sleep_us(2)\n    sig.value(1)\n    sleep_us(12)\n    sig.value(0)\n    sig.init(Pin.IN)\n    try:\n        pulse = time_pulse_us(sig, 1, 30000)\n    except OSError:\n        return None\n    if pulse <= 0:\n        return None\n    cm = pulse * 0.017\n    return cm if 2 <= cm <= 350 else None\n\nsleep_ms(100)\nfor _ in range(30):\n    cm = read_cm()\n    print(\"No valid echo\" if cm is None else \"Distance cm: %.1f\" % cm)\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "functional",
      "title": "DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython） · SINGLE_WIRE",
      "summary": "单SIG触发/回波测距，厘米输出；超时明确显示无有效回波。",
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
          "default": "SINGLE_WIRE",
          "options": [
            {
              "value": "SINGLE_WIRE",
              "label": "单SIG触发/回波"
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
          "signal": "SIG / S",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "仅适用SEN0388单线版本，不适用SEN0307模拟量或SEN0304 I2C版本。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/sen0388/",
        "https://wiki.dfrobot.com.cn/sku_sen0388_urm09_ultrasonic_sensor_gravity_trig",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://dfimg.dfrobot.com/wiki/24709/DFR0992-EN_unihiker-k10_schematics_V1.0.pdf"
      ],
      "codeTemplate": "# DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython）\n# K10官方MicroPython / unihiker_k10\n# 功能示例，待实物测试。\nfrom unihiker_k10 import ultrasonic\nfrom utime import sleep_ms\nsensor = ultrasonic(trig={{sig}}, echo={{sig}})\nfor _ in range(30):\n    try:\n        print(\"Distance cm =\", sensor.distance())\n    except OSError as error:\n        print(\"Echo error =\", error)\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython） · SINGLE_WIRE",
      "summary": "单SIG触发/回波测距，厘米输出；超时明确显示无有效回波。",
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
          "default": "SINGLE_WIRE",
          "options": [
            {
              "value": "SINGLE_WIRE",
              "label": "单SIG触发/回波"
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
          "signal": "SIG / S",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "仅适用SEN0388单线版本，不适用SEN0307模拟量或SEN0304 I2C版本。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/sen0388/",
        "https://wiki.dfrobot.com.cn/sku_sen0388_urm09_ultrasonic_sensor_gravity_trig",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://dfimg.dfrobot.com/wiki/24709/DFR0992-EN_unihiker-k10_schematics_V1.0.pdf",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython）\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import time_pulse_us\nsig = Pin({{sig}}, Pin.OUT)\ndef read_cm():\n    sig.init(Pin.OUT)\n    sig.value(0)\n    sleep_us(2)\n    sig.value(1)\n    sleep_us(12)\n    sig.value(0)\n    sig.init(Pin.IN)\n    try:\n        pulse = time_pulse_us(sig, 1, 30000)\n    except OSError:\n        return None\n    if pulse <= 0:\n        return None\n    cm = pulse * 0.017\n    return cm if 2 <= cm <= 350 else None\n\nsleep_ms(100)\nfor _ in range(30):\n    cm = read_cm()\n    print(\"No valid echo\" if cm is None else \"Distance cm: %.1f\" % cm)\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython） · SINGLE_WIRE",
      "summary": "单SIG触发/回波测距，厘米输出；超时明确显示无有效回波。",
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
          "default": "SINGLE_WIRE",
          "options": [
            {
              "value": "SINGLE_WIRE",
              "label": "单SIG触发/回波"
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
          "signal": "SIG / S",
          "target": "{{sig}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "仅适用SEN0388单线版本，不适用SEN0307模拟量或SEN0304 I2C版本。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/sen0388/",
        "https://wiki.dfrobot.com.cn/sku_sen0388_urm09_ultrasonic_sensor_gravity_trig",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://dfimg.dfrobot.com/wiki/24709/DFR0992-EN_unihiker-k10_schematics_V1.0.pdf",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython）\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import time_pulse_us\nsig = Pin({{sig}}, Pin.OUT)\ndef read_cm():\n    sig.init(Pin.OUT)\n    sig.value(0)\n    sleep_us(2)\n    sig.value(1)\n    sleep_us(12)\n    sig.value(0)\n    sig.init(Pin.IN)\n    try:\n        pulse = time_pulse_us(sig, 1, 30000)\n    except OSError:\n        return None\n    if pulse <= 0:\n        return None\n    cm = pulse * 0.017\n    return cm if 2 <= cm <= 350 else None\n\nsleep_ms(100)\nfor _ in range(30):\n    cm = read_cm()\n    print(\"No valid echo\" if cm is None else \"Distance cm: %.1f\" % cm)\n    sleep_ms(300)\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
