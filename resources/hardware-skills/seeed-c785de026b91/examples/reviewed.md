<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_seeed_c785de026b91",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "diagnostic",
      "title": "Grove 12 通道电容触摸键盘 (ATtiny1616) · UART",
      "summary": "仅接收原始串口字节，不含型号协议解码；先按手册选择波特率。",
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
          "default": "UART",
          "options": [
            {
              "value": "UART",
              "label": "串口 UART"
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
          "key": "rx",
          "label": "主控RX（接模块TX）",
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
          "key": "tx",
          "label": "主控TX（接模块RX）",
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
        },
        {
          "key": "baud",
          "label": "模块波特率",
          "default": "0",
          "options": [
            {
              "value": "0",
              "label": "请按模块手册选择"
            },
            {
              "value": "9600",
              "label": "9600（8N1）"
            },
            {
              "value": "19200",
              "label": "19200（8N1）"
            },
            {
              "value": "38400",
              "label": "38400（8N1）"
            },
            {
              "value": "115200",
              "label": "115200（8N1）"
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
          "signal": "模块TX",
          "target": "主控RX = {{rx}}"
        },
        {
          "signal": "模块RX",
          "target": "主控TX = {{tx}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-12-Channel-Capacitive-Touch-Keypad-ATtiny1616-/",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# Grove 12 通道电容触摸键盘 (ATtiny1616)\n# 掌控板2.0官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nfrom mpython import MPythonPin, PinMode\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nbaud = {{baud}}\nif baud == 0:\n    raise RuntimeError(\"Select the baud rate from the module's official specification first\")\nuart = UART(1, baudrate=baud, bits=8, parity=None, stop=1,\n            rx=MPythonPin({{rx}}, PinMode.IN).Pin, tx=MPythonPin({{tx}}, PinMode.OUT).Pin)\ntry:\n    for _ in range(20):\n        data = uart.read(128)\n        if data:\n            print(\"UART raw bytes =\", data)\n        sleep_ms(250)\nfinally:\n    uart.deinit()\nprint(\"Raw receive only; no command sent, no protocol decoding or measurement.\")\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "diagnostic",
      "title": "Grove 12 通道电容触摸键盘 (ATtiny1616) · UART",
      "summary": "仅接收原始串口字节，不含型号协议解码；先按手册选择波特率。",
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
          "default": "UART",
          "options": [
            {
              "value": "UART",
              "label": "串口 UART"
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
          "key": "rx",
          "label": "主控RX（接模块TX）",
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
          "key": "tx",
          "label": "主控TX（接模块RX）",
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
        },
        {
          "key": "baud",
          "label": "模块波特率",
          "default": "0",
          "options": [
            {
              "value": "0",
              "label": "请按模块手册选择"
            },
            {
              "value": "9600",
              "label": "9600（8N1）"
            },
            {
              "value": "19200",
              "label": "19200（8N1）"
            },
            {
              "value": "38400",
              "label": "38400（8N1）"
            },
            {
              "value": "115200",
              "label": "115200（8N1）"
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
          "signal": "模块TX",
          "target": "主控RX = {{rx}}"
        },
        {
          "signal": "模块RX",
          "target": "主控TX = {{tx}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-12-Channel-Capacitive-Touch-Keypad-ATtiny1616-/",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# Grove 12 通道电容触摸键盘 (ATtiny1616)\n# 掌控板3.0官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nbaud = {{baud}}\nif baud == 0:\n    raise RuntimeError(\"Select the baud rate from the module's official specification first\")\nuart = UART(1, baudrate=baud, bits=8, parity=None, stop=1,\n            rx=Pin({{rx}}, Pin.IN), tx=Pin({{tx}}, Pin.OUT))\ntry:\n    for _ in range(20):\n        data = uart.read(128)\n        if data:\n            print(\"UART raw bytes =\", data)\n        sleep_ms(250)\nfinally:\n    uart.deinit()\nprint(\"Raw receive only; no command sent, no protocol decoding or measurement.\")\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "Grove 12 通道电容触摸键盘 (ATtiny1616) · UART",
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
          "default": "UART",
          "options": [
            {
              "value": "UART",
              "label": "串口 UART"
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
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。",
        "K10官方接口未公开可用通用UART端口映射；不能将I2C扩展GPIO当串口。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-12-Channel-Capacitive-Touch-Keypad-ATtiny1616-/",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# Grove 12 通道电容触摸键盘 (ATtiny1616)\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "diagnostic",
      "title": "Grove 12 通道电容触摸键盘 (ATtiny1616) · UART",
      "summary": "仅接收原始串口字节，不含型号协议解码；先按手册选择波特率。",
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
          "default": "UART",
          "options": [
            {
              "value": "UART",
              "label": "串口 UART"
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
          "key": "rx",
          "label": "主控RX（接模块TX）",
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
          "key": "tx",
          "label": "主控TX（接模块RX）",
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
          "key": "baud",
          "label": "模块波特率",
          "default": "0",
          "options": [
            {
              "value": "0",
              "label": "请按模块手册选择"
            },
            {
              "value": "9600",
              "label": "9600（8N1）"
            },
            {
              "value": "19200",
              "label": "19200（8N1）"
            },
            {
              "value": "38400",
              "label": "38400（8N1）"
            },
            {
              "value": "115200",
              "label": "115200（8N1）"
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
          "signal": "模块TX",
          "target": "主控RX = {{rx}}"
        },
        {
          "signal": "模块RX",
          "target": "主控TX = {{tx}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-12-Channel-Capacitive-Touch-Keypad-ATtiny1616-/",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# Grove 12 通道电容触摸键盘 (ATtiny1616)\n# XIAO ESP32S3官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nbaud = {{baud}}\nif baud == 0:\n    raise RuntimeError(\"Select the baud rate from the module's official specification first\")\nuart = UART(1, baudrate=baud, bits=8, parity=None, stop=1,\n            rx=Pin({{rx}}, Pin.IN), tx=Pin({{tx}}, Pin.OUT))\ntry:\n    for _ in range(20):\n        data = uart.read(128)\n        if data:\n            print(\"UART raw bytes =\", data)\n        sleep_ms(250)\nfinally:\n    uart.deinit()\nprint(\"Raw receive only; no command sent, no protocol decoding or measurement.\")\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "diagnostic",
      "title": "Grove 12 通道电容触摸键盘 (ATtiny1616) · UART",
      "summary": "仅接收原始串口字节，不含型号协议解码；先按手册选择波特率。",
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
          "default": "UART",
          "options": [
            {
              "value": "UART",
              "label": "串口 UART"
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
          "key": "rx",
          "label": "主控RX（接模块TX）",
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
          "key": "tx",
          "label": "主控TX（接模块RX）",
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
        },
        {
          "key": "baud",
          "label": "模块波特率",
          "default": "0",
          "options": [
            {
              "value": "0",
              "label": "请按模块手册选择"
            },
            {
              "value": "9600",
              "label": "9600（8N1）"
            },
            {
              "value": "19200",
              "label": "19200（8N1）"
            },
            {
              "value": "38400",
              "label": "38400（8N1）"
            },
            {
              "value": "115200",
              "label": "115200（8N1）"
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
          "signal": "模块TX",
          "target": "主控RX = {{rx}}"
        },
        {
          "signal": "模块RX",
          "target": "主控TX = {{tx}}"
        }
      ],
      "notes": [
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-12-Channel-Capacitive-Touch-Keypad-ATtiny1616-/",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# Grove 12 通道电容触摸键盘 (ATtiny1616)\n# ESP32_GENERIC_C3官方MicroPython\n# 诊断/参考，不代表完整测量驱动。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nbaud = {{baud}}\nif baud == 0:\n    raise RuntimeError(\"Select the baud rate from the module's official specification first\")\nuart = UART(1, baudrate=baud, bits=8, parity=None, stop=1,\n            rx=Pin({{rx}}, Pin.IN), tx=Pin({{tx}}, Pin.OUT))\ntry:\n    for _ in range(20):\n        data = uart.read(128)\n        if data:\n            print(\"UART raw bytes =\", data)\n        sleep_ms(250)\nfinally:\n    uart.deinit()\nprint(\"Raw receive only; no command sent, no protocol decoding or measurement.\")\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
