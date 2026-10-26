<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_dfrobot_ser0006_k10",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "DFRobot SER0006 舵机模块 · PWM",
      "summary": "单次舵机控制示例；脉宽范围需按型号核对，连续旋转型号按速度理解。",
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
          "default": "PWM",
          "options": [
            {
              "value": "PWM",
              "label": "PWM"
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
          "key": "angle",
          "label": "位置/速度指令",
          "default": "90",
          "options": [
            {
              "value": "90",
              "label": "90（中位/连续旋转停止附近）"
            },
            {
              "value": "45",
              "label": "45"
            },
            {
              "value": "135",
              "label": "135"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "舵机电源按额定值独立供电并共地，GPIO只接控制线；360°舵机脉宽表示速度/方向，不是位置角度。",
        "脉宽范围仅供空载初测，按具体舵机额定值核对；非N+示例采用保守1000～2000us。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SER0006_DF9GMS_180%C2%B0_%E5%BE%AE%E5%9E%8B%E8%88%B5%E6%9C%BA",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# DFRobot SER0006 舵机模块\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import MPythonPin, PinMode\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import PWM\nservo = PWM(MPythonPin({{sig}}, PinMode.OUT).Pin, freq=50)\npulse_us = 1000 + {{angle}} * 1000 // 180\nservo.duty(pulse_us * 1023 // 20000)\nsleep_ms(600)\nservo.deinit()\nprint(\"Servo pulse sequence complete; inspect physical motion.\")\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "DFRobot SER0006 舵机模块 · PWM",
      "summary": "单次舵机控制示例；脉宽范围需按型号核对，连续旋转型号按速度理解。",
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
          "default": "PWM",
          "options": [
            {
              "value": "PWM",
              "label": "PWM"
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
          "key": "angle",
          "label": "位置/速度指令",
          "default": "90",
          "options": [
            {
              "value": "90",
              "label": "90（中位/连续旋转停止附近）"
            },
            {
              "value": "45",
              "label": "45"
            },
            {
              "value": "135",
              "label": "135"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "舵机电源按额定值独立供电并共地，GPIO只接控制线；360°舵机脉宽表示速度/方向，不是位置角度。",
        "脉宽范围仅供空载初测，按具体舵机额定值核对；非N+示例采用保守1000～2000us。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SER0006_DF9GMS_180%C2%B0_%E5%BE%AE%E5%9E%8B%E8%88%B5%E6%9C%BA",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# DFRobot SER0006 舵机模块\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import PWM\nservo = PWM(Pin({{sig}}, Pin.OUT), freq=50)\npulse_us = 1000 + {{angle}} * 1000 // 180\nservo.duty(pulse_us * 1023 // 20000)\nsleep_ms(600)\nservo.deinit()\nprint(\"Servo pulse sequence complete; inspect physical motion.\")\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "functional",
      "title": "DFRobot SER0006 舵机模块 · PWM",
      "summary": "单次舵机控制示例；脉宽范围需按型号核对，连续旋转型号按速度理解。",
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
          "default": "PWM",
          "options": [
            {
              "value": "PWM",
              "label": "PWM"
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
          "key": "angle",
          "label": "位置/速度指令",
          "default": "90",
          "options": [
            {
              "value": "90",
              "label": "90（中位/连续旋转停止附近）"
            },
            {
              "value": "45",
              "label": "45"
            },
            {
              "value": "135",
              "label": "135"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "舵机电源按额定值独立供电并共地，GPIO只接控制线；360°舵机脉宽表示速度/方向，不是位置角度。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SER0006_DF9GMS_180%C2%B0_%E5%BE%AE%E5%9E%8B%E8%88%B5%E6%9C%BA",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# DFRobot SER0006 舵机模块\n# K10官方MicroPython / unihiker_k10\n# 功能示例，待实物测试。\nfrom unihiker_k10 import servo\nactuator = servo({{sig}})\nactuator.angle(value={{angle}})\nprint(\"Servo command submitted; inspect physical motion.\")\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "DFRobot SER0006 舵机模块 · PWM",
      "summary": "单次舵机控制示例；脉宽范围需按型号核对，连续旋转型号按速度理解。",
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
          "default": "PWM",
          "options": [
            {
              "value": "PWM",
              "label": "PWM"
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
          "key": "angle",
          "label": "位置/速度指令",
          "default": "90",
          "options": [
            {
              "value": "90",
              "label": "90（中位/连续旋转停止附近）"
            },
            {
              "value": "45",
              "label": "45"
            },
            {
              "value": "135",
              "label": "135"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "舵机电源按额定值独立供电并共地，GPIO只接控制线；360°舵机脉宽表示速度/方向，不是位置角度。",
        "脉宽范围仅供空载初测，按具体舵机额定值核对；非N+示例采用保守1000～2000us。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SER0006_DF9GMS_180%C2%B0_%E5%BE%AE%E5%9E%8B%E8%88%B5%E6%9C%BA",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# DFRobot SER0006 舵机模块\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import PWM\nservo = PWM(Pin({{sig}}, Pin.OUT), freq=50)\npulse_us = 1000 + {{angle}} * 1000 // 180\nservo.duty(pulse_us * 1023 // 20000)\nsleep_ms(600)\nservo.deinit()\nprint(\"Servo pulse sequence complete; inspect physical motion.\")\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "DFRobot SER0006 舵机模块 · PWM",
      "summary": "单次舵机控制示例；脉宽范围需按型号核对，连续旋转型号按速度理解。",
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
          "default": "PWM",
          "options": [
            {
              "value": "PWM",
              "label": "PWM"
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
          "key": "angle",
          "label": "位置/速度指令",
          "default": "90",
          "options": [
            {
              "value": "90",
              "label": "90（中位/连续旋转停止附近）"
            },
            {
              "value": "45",
              "label": "45"
            },
            {
              "value": "135",
              "label": "135"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "舵机电源按额定值独立供电并共地，GPIO只接控制线；360°舵机脉宽表示速度/方向，不是位置角度。",
        "脉宽范围仅供空载初测，按具体舵机额定值核对；非N+示例采用保守1000～2000us。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SER0006_DF9GMS_180%C2%B0_%E5%BE%AE%E5%9E%8B%E8%88%B5%E6%9C%BA",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# DFRobot SER0006 舵机模块\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import PWM\nservo = PWM(Pin({{sig}}, Pin.OUT), freq=50)\npulse_us = 1000 + {{angle}} * 1000 // 180\nservo.duty(pulse_us * 1023 // 20000)\nsleep_ms(600)\nservo.deinit()\nprint(\"Servo pulse sequence complete; inspect physical motion.\")\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
