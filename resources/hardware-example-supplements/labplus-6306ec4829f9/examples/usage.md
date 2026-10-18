<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_labplus_6306ec4829f9",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "盛思 心率血氧 · I2C",
      "summary": "MAX30102.measurement()后读取ir_D心率、red_D血氧；需按A键启动一次测量，不将None当成功。 接线与实物结果待测试。",
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
          "default": "I2C",
          "options": [
            {
              "value": "I2C",
              "label": "I²C"
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
          "key": "bus",
          "label": "I²C接线",
          "default": "P19 / SCL；P20 / SDA",
          "options": [
            {
              "value": "P19 / SCL；P20 / SDA",
              "label": "P19 / SCL；P20 / SDA"
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
          "signal": "SDA / SCL",
          "target": "{{bus}}"
        }
      ],
      "notes": [
        "依赖max30102、hrcalc及mpython.i2c。库算法测量约30秒且内部阻塞，期间B键不轮询；可用工作台停止中断。仅教学估计，不用于医学判断。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/max30102.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BF%83%E7%8E%87%E8%A1%80%E6%B0%A7%E6%A8%A1%E5%9D%97.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# 盛思 心率血氧\n# 官方来源核对；待实物测试。\nfrom mpython import i2c, button_b\nfrom utime import sleep_ms\ntry:\n    from max30102 import MAX30102\nexcept ImportError as error:\n    print(\"缺少此型号驱动或其依赖:\", error)\n    raise RuntimeError(\"请核对此主控固件的库版本；不能仅复制整个bluebit.py解决依赖\")\nsensor = MAX30102()\nprint(\"放好指尖，按A键开始一次约30秒的测量；B键取消等待。\")\nfrom mpython import button_a\nfor _ in range(300):\n    if button_b.value() == 0:\n        break\n    if button_a.value() == 0:\n        sensor.measurement()\n        if sensor.ir_D is None or sensor.red_D is None:\n            print(\"未取得有效心率/血氧，请检查指尖放置与环境光\")\n        else:\n            print(\"心率估计BPM:\", sensor.ir_D, \"血氧估计%:\", sensor.red_D)\n        break\n    sleep_ms(100)\nsensor.shutdown()\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "diagnostic",
      "title": "盛思 心率血氧 · I2C",
      "summary": "提供当前固件的环境/连通检查；尚未包含此型号完整的测量或控制驱动。",
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
          "default": "I2C",
          "options": [
            {
              "value": "I2C",
              "label": "I²C"
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
          "key": "bus",
          "label": "I²C接线",
          "default": "P19 / SCL；P20 / SDA",
          "options": [
            {
              "value": "P19 / SCL；P20 / SDA",
              "label": "P19 / SCL；P20 / SDA"
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
          "signal": "SDA / SCL",
          "target": "{{bus}}"
        }
      ],
      "notes": [
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/max30102.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BF%83%E7%8E%87%E8%A1%80%E6%B0%A7%E6%A8%A1%E5%9D%97.html",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# 盛思 心率血氧\n# 掌控板3.0官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nfrom mpython import i2c\nfrom utime import sleep_ms\nbefore = i2c.scan()\nprint(\"I2C addresses =\", [hex(address) for address in before])\nprint(\"Disconnect power before changing wiring; compare with board-only addresses.\")\nprint(\"Address detection is not a measurement or model identification.\")\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "盛思 心率血氧 · I2C",
      "summary": "提供当前固件的环境/连通检查；尚未包含此型号完整的测量或控制驱动。",
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
          "default": "I2C",
          "options": [
            {
              "value": "I2C",
              "label": "I²C"
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
          "key": "bus",
          "label": "I²C接线",
          "default": "K10扩展接口SDA/SCL（按实物标识）",
          "options": [
            {
              "value": "K10扩展接口SDA/SCL（按实物标识）",
              "label": "K10扩展接口SDA/SCL（按实物标识）"
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
          "signal": "SDA / SCL",
          "target": "{{bus}}"
        }
      ],
      "notes": [
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "K10官方代码模式未公开通用I2C对象和原生引脚映射；本例不猜测machine.Pin端口。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/max30102.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BF%83%E7%8E%87%E8%A1%80%E6%B0%A7%E6%A8%A1%E5%9D%97.html",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# 盛思 心率血氧\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "diagnostic",
      "title": "盛思 心率血氧 · I2C",
      "summary": "提供当前固件的环境/连通检查；尚未包含此型号完整的测量或控制驱动。",
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
          "default": "I2C",
          "options": [
            {
              "value": "I2C",
              "label": "I²C"
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
          "key": "bus",
          "label": "I²C接线",
          "default": "SDA=GPIO5 / D4；SCL=GPIO6 / D5",
          "options": [
            {
              "value": "SDA=GPIO5 / D4；SCL=GPIO6 / D5",
              "label": "SDA=GPIO5 / D4；SCL=GPIO6 / D5"
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
          "signal": "SDA / SCL",
          "target": "{{bus}}"
        }
      ],
      "notes": [
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/max30102.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BF%83%E7%8E%87%E8%A1%80%E6%B0%A7%E6%A8%A1%E5%9D%97.html",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# 盛思 心率血氧\n# XIAO ESP32S3官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(5), scl=Pin(6), freq=100000)\nbefore = i2c.scan()\nprint(\"I2C addresses =\", [hex(address) for address in before])\nprint(\"Disconnect power before changing wiring; compare with board-only addresses.\")\nprint(\"Address detection is not a measurement or model identification.\")\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "diagnostic",
      "title": "盛思 心率血氧 · I2C",
      "summary": "提供当前固件的环境/连通检查；尚未包含此型号完整的测量或控制驱动。",
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
          "default": "I2C",
          "options": [
            {
              "value": "I2C",
              "label": "I²C"
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
          "key": "bus",
          "label": "I²C接线",
          "default": "SDA=GPIO3；SCL=GPIO4",
          "options": [
            {
              "value": "SDA=GPIO3；SCL=GPIO4",
              "label": "SDA=GPIO3；SCL=GPIO4"
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
          "signal": "SDA / SCL",
          "target": "{{bus}}"
        }
      ],
      "notes": [
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/max30102.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BF%83%E7%8E%87%E8%A1%80%E6%B0%A7%E6%A8%A1%E5%9D%97.html",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# 盛思 心率血氧\n# ESP32_GENERIC_C3官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(3), scl=Pin(4), freq=100000)\nbefore = i2c.scan()\nprint(\"I2C addresses =\", [hex(address) for address in before])\nprint(\"Disconnect power before changing wiring; compare with board-only addresses.\")\nprint(\"Address detection is not a measurement or model identification.\")\n"
    }
  ],
  "i2c": {
    "defaultAddress": "0x57",
    "addresses": [
      "0x57"
    ],
    "notes": "max30102.py使用7位地址0x57，教学估计；需核对实物芯片及有效测量结果。",
    "sources": [
      "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py"
    ]
  }
}
```
<!-- /zhangwen:module-guides:v1 -->
