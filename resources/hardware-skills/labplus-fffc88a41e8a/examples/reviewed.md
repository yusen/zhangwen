<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_labplus_fffc88a41e8a",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "盛思 细微颗粒物PM2.5(新版，模块+探头) · UART",
      "summary": "据PM25_DC的A5四字节帧读取新版串口模块，分包/噪声/校验与2秒总超时，K=0.4需标定。 接线与实物结果待测试。",
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
          "default": "9600",
          "options": [
            {
              "value": "9600",
              "label": "9600"
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
        "仅适用于新版9600串口模块及PM25_DC协议，非旧裸探头、模拟pm25.PM25或其他PMS帧；无有效帧不报告0浓度。上游PM25_DC在持续错误数据时可能无限等待，本例增加总超时。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/PM2.5%EF%BC%88%E5%90%AB%E6%A8%A1%E5%9D%97%EF%BC%89.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# 盛思 细微颗粒物PM2.5(新版，模块+探头)\n# 官方来源核对；待实物测试。\nfrom mpython import MPythonPin, PinMode\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nuart = UART(1, baudrate={{baud}}, bits=8, parity=None, stop=1, timeout=10,\n            rx=MPythonPin({{rx}}, PinMode.IN).Pin, tx=MPythonPin({{tx}}, PinMode.IN).Pin)\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n# 据bluebit.PM25_DC：A5+两字节7位数据+校验；K=0.4仅为库默认标定系数。\nfrom utime import ticks_ms, ticks_diff\ndef read_pm25(uart, timeout_ms=2000):\n    started = ticks_ms()\n    packet = bytearray()\n    while ticks_diff(ticks_ms(), started) < timeout_ms:\n        chunk = uart.read(32)\n        if chunk:\n            packet.extend(chunk)\n            while len(packet) >= 4:\n                if packet[0] != 0xA5:\n                    del packet[0]\n                    continue\n                high, low, check = packet[1], packet[2], packet[3]\n                # 保留上游的异或校验表达式，不将PMS5003等其他帧格式混入。\n                if ((0xA5 + high + low) ^ 0x80) == check:\n                    del packet[:4]\n                    return 0.4 * ((high << 7) | (low & 0x7F))\n                del packet[0]\n        sleep_ms(5)\n    return None\nprint(\"等待模块上电稳定10秒\")\nsleep_ms(10000)\ntry:\n    for _ in range(10):\n        value = read_pm25(uart)\n        print(\"无有效帧/校验失败\" if value is None else \"PM2.5估计 ug/m3: %.1f\" % value)\n        sleep_ms(1000)\nfinally:\n    uart.deinit()\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "盛思 细微颗粒物PM2.5(新版，模块+探头) · UART",
      "summary": "据PM25_DC的A5四字节帧读取新版串口模块，分包/噪声/校验与2秒总超时，K=0.4需标定。 接线与实物结果待测试。",
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
          "default": "9600",
          "options": [
            {
              "value": "9600",
              "label": "9600"
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
        "仅适用于新版9600串口模块及PM25_DC协议，非旧裸探头、模拟pm25.PM25或其他PMS帧；无有效帧不报告0浓度。上游PM25_DC在持续错误数据时可能无限等待，本例增加总超时。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/PM2.5%EF%BC%88%E5%90%AB%E6%A8%A1%E5%9D%97%EF%BC%89.html",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# 盛思 细微颗粒物PM2.5(新版，模块+探头)\n# 官方来源核对；待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nuart = UART(1, baudrate={{baud}}, bits=8, parity=None, stop=1, timeout=10,\n            rx=Pin({{rx}}), tx=Pin({{tx}}))\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n# 据bluebit.PM25_DC：A5+两字节7位数据+校验；K=0.4仅为库默认标定系数。\nfrom utime import ticks_ms, ticks_diff\ndef read_pm25(uart, timeout_ms=2000):\n    started = ticks_ms()\n    packet = bytearray()\n    while ticks_diff(ticks_ms(), started) < timeout_ms:\n        chunk = uart.read(32)\n        if chunk:\n            packet.extend(chunk)\n            while len(packet) >= 4:\n                if packet[0] != 0xA5:\n                    del packet[0]\n                    continue\n                high, low, check = packet[1], packet[2], packet[3]\n                # 保留上游的异或校验表达式，不将PMS5003等其他帧格式混入。\n                if ((0xA5 + high + low) ^ 0x80) == check:\n                    del packet[:4]\n                    return 0.4 * ((high << 7) | (low & 0x7F))\n                del packet[0]\n        sleep_ms(5)\n    return None\nprint(\"等待模块上电稳定10秒\")\nsleep_ms(10000)\ntry:\n    for _ in range(10):\n        value = read_pm25(uart)\n        print(\"无有效帧/校验失败\" if value is None else \"PM2.5估计 ug/m3: %.1f\" % value)\n        sleep_ms(1000)\nfinally:\n    uart.deinit()\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "盛思 细微颗粒物PM2.5(新版，模块+探头) · UART",
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
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。",
        "K10官方接口未公开可用通用UART端口映射；不能将I2C扩展GPIO当串口。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/PM2.5%EF%BC%88%E5%90%AB%E6%A8%A1%E5%9D%97%EF%BC%89.html",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# 盛思 细微颗粒物PM2.5(新版，模块+探头)\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "盛思 细微颗粒物PM2.5(新版，模块+探头) · UART",
      "summary": "据PM25_DC的A5四字节帧读取新版串口模块，分包/噪声/校验与2秒总超时，K=0.4需标定。 接线与实物结果待测试。",
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
          "default": "9600",
          "options": [
            {
              "value": "9600",
              "label": "9600"
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
        "仅适用于新版9600串口模块及PM25_DC协议，非旧裸探头、模拟pm25.PM25或其他PMS帧；无有效帧不报告0浓度。上游PM25_DC在持续错误数据时可能无限等待，本例增加总超时。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/PM2.5%EF%BC%88%E5%90%AB%E6%A8%A1%E5%9D%97%EF%BC%89.html",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# 盛思 细微颗粒物PM2.5(新版，模块+探头)\n# 官方来源核对；待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nuart = UART(1, baudrate={{baud}}, bits=8, parity=None, stop=1, timeout=10,\n            rx=Pin({{rx}}), tx=Pin({{tx}}))\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n# 据bluebit.PM25_DC：A5+两字节7位数据+校验；K=0.4仅为库默认标定系数。\nfrom utime import ticks_ms, ticks_diff\ndef read_pm25(uart, timeout_ms=2000):\n    started = ticks_ms()\n    packet = bytearray()\n    while ticks_diff(ticks_ms(), started) < timeout_ms:\n        chunk = uart.read(32)\n        if chunk:\n            packet.extend(chunk)\n            while len(packet) >= 4:\n                if packet[0] != 0xA5:\n                    del packet[0]\n                    continue\n                high, low, check = packet[1], packet[2], packet[3]\n                # 保留上游的异或校验表达式，不将PMS5003等其他帧格式混入。\n                if ((0xA5 + high + low) ^ 0x80) == check:\n                    del packet[:4]\n                    return 0.4 * ((high << 7) | (low & 0x7F))\n                del packet[0]\n        sleep_ms(5)\n    return None\nprint(\"等待模块上电稳定10秒\")\nsleep_ms(10000)\ntry:\n    for _ in range(10):\n        value = read_pm25(uart)\n        print(\"无有效帧/校验失败\" if value is None else \"PM2.5估计 ug/m3: %.1f\" % value)\n        sleep_ms(1000)\nfinally:\n    uart.deinit()\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "盛思 细微颗粒物PM2.5(新版，模块+探头) · UART",
      "summary": "据PM25_DC的A5四字节帧读取新版串口模块，分包/噪声/校验与2秒总超时，K=0.4需标定。 接线与实物结果待测试。",
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
          "default": "9600",
          "options": [
            {
              "value": "9600",
              "label": "9600"
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
        "仅适用于新版9600串口模块及PM25_DC协议，非旧裸探头、模拟pm25.PM25或其他PMS帧；无有效帧不报告0浓度。上游PM25_DC在持续错误数据时可能无限等待，本例增加总超时。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/PM2.5%EF%BC%88%E5%90%AB%E6%A8%A1%E5%9D%97%EF%BC%89.html",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# 盛思 细微颗粒物PM2.5(新版，模块+探头)\n# 官方来源核对；待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nuart = UART(1, baudrate={{baud}}, bits=8, parity=None, stop=1, timeout=10,\n            rx=Pin({{rx}}), tx=Pin({{tx}}))\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n# 据bluebit.PM25_DC：A5+两字节7位数据+校验；K=0.4仅为库默认标定系数。\nfrom utime import ticks_ms, ticks_diff\ndef read_pm25(uart, timeout_ms=2000):\n    started = ticks_ms()\n    packet = bytearray()\n    while ticks_diff(ticks_ms(), started) < timeout_ms:\n        chunk = uart.read(32)\n        if chunk:\n            packet.extend(chunk)\n            while len(packet) >= 4:\n                if packet[0] != 0xA5:\n                    del packet[0]\n                    continue\n                high, low, check = packet[1], packet[2], packet[3]\n                # 保留上游的异或校验表达式，不将PMS5003等其他帧格式混入。\n                if ((0xA5 + high + low) ^ 0x80) == check:\n                    del packet[:4]\n                    return 0.4 * ((high << 7) | (low & 0x7F))\n                del packet[0]\n        sleep_ms(5)\n    return None\nprint(\"等待模块上电稳定10秒\")\nsleep_ms(10000)\ntry:\n    for _ in range(10):\n        value = read_pm25(uart)\n        print(\"无有效帧/校验失败\" if value is None else \"PM2.5估计 ug/m3: %.1f\" % value)\n        sleep_ms(1000)\nfinally:\n    uart.deinit()\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
