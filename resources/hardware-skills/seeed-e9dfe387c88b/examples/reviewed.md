<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_seeed_e9dfe387c88b",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "reference",
      "title": "Grove - 三轴数字加速度计 · UNKNOWN",
      "summary": "型号、接口或来源有待核对项；仅提供环境检查，不猜测测量驱动与端口。",
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
          "default": "UNKNOWN",
          "options": [
            {
              "value": "UNKNOWN",
              "label": "接口待核对"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对型号与额定供电",
          "options": [
            {
              "value": "待核对型号与额定供电",
              "label": "待核对型号与额定供电"
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
        "原目录“三轴数字加速度计”的来源实际指向MQ2气体页，型号与来源不符，禁止据此套用接线或驱动。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Gas_Sensor-MQ2/",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# Grove - 三轴数字加速度计\n# 掌控板2.0官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "reference",
      "title": "Grove - 三轴数字加速度计 · UNKNOWN",
      "summary": "型号、接口或来源有待核对项；仅提供环境检查，不猜测测量驱动与端口。",
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
          "default": "UNKNOWN",
          "options": [
            {
              "value": "UNKNOWN",
              "label": "接口待核对"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对型号与额定供电",
          "options": [
            {
              "value": "待核对型号与额定供电",
              "label": "待核对型号与额定供电"
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
        "原目录“三轴数字加速度计”的来源实际指向MQ2气体页，型号与来源不符，禁止据此套用接线或驱动。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Gas_Sensor-MQ2/",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# Grove - 三轴数字加速度计\n# 掌控板3.0官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "reference",
      "title": "Grove - 三轴数字加速度计 · UNKNOWN",
      "summary": "型号、接口或来源有待核对项；仅提供环境检查，不猜测测量驱动与端口。",
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
          "default": "UNKNOWN",
          "options": [
            {
              "value": "UNKNOWN",
              "label": "接口待核对"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对型号与额定供电",
          "options": [
            {
              "value": "待核对型号与额定供电",
              "label": "待核对型号与额定供电"
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
        "原目录“三轴数字加速度计”的来源实际指向MQ2气体页，型号与来源不符，禁止据此套用接线或驱动。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Gas_Sensor-MQ2/",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# Grove - 三轴数字加速度计\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "reference",
      "title": "Grove - 三轴数字加速度计 · UNKNOWN",
      "summary": "型号、接口或来源有待核对项；仅提供环境检查，不猜测测量驱动与端口。",
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
          "default": "UNKNOWN",
          "options": [
            {
              "value": "UNKNOWN",
              "label": "接口待核对"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对型号与额定供电",
          "options": [
            {
              "value": "待核对型号与额定供电",
              "label": "待核对型号与额定供电"
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
        "原目录“三轴数字加速度计”的来源实际指向MQ2气体页，型号与来源不符，禁止据此套用接线或驱动。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Gas_Sensor-MQ2/",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# Grove - 三轴数字加速度计\n# XIAO ESP32S3官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "reference",
      "title": "Grove - 三轴数字加速度计 · UNKNOWN",
      "summary": "型号、接口或来源有待核对项；仅提供环境检查，不猜测测量驱动与端口。",
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
          "default": "UNKNOWN",
          "options": [
            {
              "value": "UNKNOWN",
              "label": "接口待核对"
            }
          ]
        },
        {
          "key": "supply",
          "label": "模块供电",
          "default": "待核对型号与额定供电",
          "options": [
            {
              "value": "待核对型号与额定供电",
              "label": "待核对型号与额定供电"
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
        "原目录“三轴数字加速度计”的来源实际指向MQ2气体页，型号与来源不符，禁止据此套用接线或驱动。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Gas_Sensor-MQ2/",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# Grove - 三轴数字加速度计\n# ESP32_GENERIC_C3官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
