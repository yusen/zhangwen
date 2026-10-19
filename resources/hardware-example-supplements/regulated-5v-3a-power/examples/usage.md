<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_power_5v_3a_regulated",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "reference",
      "title": "外接稳压 5V/3A 电源 · POWER",
      "summary": "电源接线参考，无软件驱动。",
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
          "default": "POWER",
          "options": [
            {
              "value": "POWER",
              "label": "电源"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "电源模块没有MicroPython驱动；按额定值给负载供电，不把5V电源输出接入GPIO或3V3。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/dfr0523/",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# 外接稳压 5V/3A 电源\n# 掌控板2.0官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "reference",
      "title": "外接稳压 5V/3A 电源 · POWER",
      "summary": "电源接线参考，无软件驱动。",
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
          "default": "POWER",
          "options": [
            {
              "value": "POWER",
              "label": "电源"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "电源模块没有MicroPython驱动；按额定值给负载供电，不把5V电源输出接入GPIO或3V3。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/dfr0523/",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# 外接稳压 5V/3A 电源\n# 掌控板3.0官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "reference",
      "title": "外接稳压 5V/3A 电源 · POWER",
      "summary": "电源接线参考，无软件驱动。",
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
          "default": "POWER",
          "options": [
            {
              "value": "POWER",
              "label": "电源"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "电源模块没有MicroPython驱动；按额定值给负载供电，不把5V电源输出接入GPIO或3V3。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/dfr0523/",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# 外接稳压 5V/3A 电源\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "reference",
      "title": "外接稳压 5V/3A 电源 · POWER",
      "summary": "电源接线参考，无软件驱动。",
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
          "default": "POWER",
          "options": [
            {
              "value": "POWER",
              "label": "电源"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "电源模块没有MicroPython驱动；按额定值给负载供电，不把5V电源输出接入GPIO或3V3。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/dfr0523/",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# 外接稳压 5V/3A 电源\n# XIAO ESP32S3官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "reference",
      "title": "外接稳压 5V/3A 电源 · POWER",
      "summary": "电源接线参考，无软件驱动。",
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
          "default": "POWER",
          "options": [
            {
              "value": "POWER",
              "label": "电源"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "电源模块没有MicroPython驱动；按额定值给负载供电，不把5V电源输出接入GPIO或3V3。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://wiki.dfrobot.com/dfr0523/",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# 外接稳压 5V/3A 电源\n# ESP32_GENERIC_C3官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
