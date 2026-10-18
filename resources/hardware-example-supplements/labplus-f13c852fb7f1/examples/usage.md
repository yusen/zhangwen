<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_labplus_f13c852fb7f1",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "盛思 全球定位系统 · UART",
      "summary": "据bluebit导出的BDS/GPS所用RMC字段，单文件流式解析校验通过且状态A的定位数据。 接线与实物结果待测试。",
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
        "GNSS_Read在无数据时有无界等待，故采用120秒有界接收；仅处理GPRMC/GNRMC/BDRMC，验证校验和及A状态、经纬度方向，V或缺字段不伪报坐标。冷启动可能数分钟。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/ATGM336H_5N.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%8C%97%E6%96%97%E6%A8%A1%E5%9D%97.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# 盛思 全球定位系统\n# 官方来源核对；待实物测试。\nfrom mpython import MPythonPin, PinMode\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nuart = UART(1, baudrate={{baud}}, bits=8, parity=None, stop=1, timeout=10,\n            rx=MPythonPin({{rx}}, PinMode.IN).Pin, tx=MPythonPin({{tx}}, PinMode.IN).Pin)\n# BDS/GPS库使用RMC字段；此单文件接收器补超时、分包、校验和有效定位判定。\ndef parse_rmc(line):\n    try:\n        text = line.decode(\"ascii\").strip()\n        payload, checksum = text[1:].split(\"*\")\n        if not text.startswith(\"$\") or len(checksum) != 2:\n            return None\n        check = 0\n        for char in payload:\n            check ^= ord(char)\n        if check != int(checksum, 16):\n            return None\n        parts = payload.split(\",\")\n        if parts[0] not in (\"GPRMC\", \"GNRMC\", \"BDRMC\") or parts[2] != \"A\":\n            return None\n        if parts[4] not in (\"N\", \"S\") or parts[6] not in (\"E\", \"W\"):\n            return None\n        lat, lon = float(parts[3]), float(parts[5])\n        lat_min, lon_min = lat % 100, lon % 100\n        lat, lon = int(lat // 100) + lat_min / 60, int(lon // 100) + lon_min / 60\n        if lat_min >= 60 or lon_min >= 60 or lat > 90 or lon > 180:\n            return None\n        return (parts[1], -lat if parts[4] == \"S\" else lat, -lon if parts[6] == \"W\" else lon)\n    except (ValueError, IndexError, UnicodeError):\n        return None\n\ndef feed_rmc(buffer, chunk):\n    buffer.extend(chunk)\n    fixes = []\n    while b\"\\n\" in buffer:\n        end = buffer.index(10)\n        line = bytes(buffer[:end + 1])\n        del buffer[:end + 1]\n        fix = parse_rmc(line)\n        if fix is not None:\n            fixes.append(fix)\n    if len(buffer) > 256:\n        del buffer[:-256]\n    return fixes\nbuffer = bytearray()\nfound = False\ntry:\n    for _ in range(1200):\n        data = uart.read(128)\n        if data:\n            for utc, latitude, longitude in feed_rmc(buffer, data):\n                found = True\n                print(\"UTC:\", utc, \"纬度:\", latitude, \"经度:\", longitude)\n        sleep_ms(100)\nfinally:\n    uart.deinit()\nif not found:\n    print(\"120秒内未收到有效定位；到开阔处继续等待，不代表模块损坏\")\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "盛思 全球定位系统 · UART",
      "summary": "据bluebit导出的BDS/GPS所用RMC字段，单文件流式解析校验通过且状态A的定位数据。 接线与实物结果待测试。",
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
        "GNSS_Read在无数据时有无界等待，故采用120秒有界接收；仅处理GPRMC/GNRMC/BDRMC，验证校验和及A状态、经纬度方向，V或缺字段不伪报坐标。冷启动可能数分钟。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/ATGM336H_5N.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%8C%97%E6%96%97%E6%A8%A1%E5%9D%97.html",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# 盛思 全球定位系统\n# 官方来源核对；待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nuart = UART(1, baudrate={{baud}}, bits=8, parity=None, stop=1, timeout=10,\n            rx=Pin({{rx}}), tx=Pin({{tx}}))\n# BDS/GPS库使用RMC字段；此单文件接收器补超时、分包、校验和有效定位判定。\ndef parse_rmc(line):\n    try:\n        text = line.decode(\"ascii\").strip()\n        payload, checksum = text[1:].split(\"*\")\n        if not text.startswith(\"$\") or len(checksum) != 2:\n            return None\n        check = 0\n        for char in payload:\n            check ^= ord(char)\n        if check != int(checksum, 16):\n            return None\n        parts = payload.split(\",\")\n        if parts[0] not in (\"GPRMC\", \"GNRMC\", \"BDRMC\") or parts[2] != \"A\":\n            return None\n        if parts[4] not in (\"N\", \"S\") or parts[6] not in (\"E\", \"W\"):\n            return None\n        lat, lon = float(parts[3]), float(parts[5])\n        lat_min, lon_min = lat % 100, lon % 100\n        lat, lon = int(lat // 100) + lat_min / 60, int(lon // 100) + lon_min / 60\n        if lat_min >= 60 or lon_min >= 60 or lat > 90 or lon > 180:\n            return None\n        return (parts[1], -lat if parts[4] == \"S\" else lat, -lon if parts[6] == \"W\" else lon)\n    except (ValueError, IndexError, UnicodeError):\n        return None\n\ndef feed_rmc(buffer, chunk):\n    buffer.extend(chunk)\n    fixes = []\n    while b\"\\n\" in buffer:\n        end = buffer.index(10)\n        line = bytes(buffer[:end + 1])\n        del buffer[:end + 1]\n        fix = parse_rmc(line)\n        if fix is not None:\n            fixes.append(fix)\n    if len(buffer) > 256:\n        del buffer[:-256]\n    return fixes\nbuffer = bytearray()\nfound = False\ntry:\n    for _ in range(1200):\n        data = uart.read(128)\n        if data:\n            for utc, latitude, longitude in feed_rmc(buffer, data):\n                found = True\n                print(\"UTC:\", utc, \"纬度:\", latitude, \"经度:\", longitude)\n        sleep_ms(100)\nfinally:\n    uart.deinit()\nif not found:\n    print(\"120秒内未收到有效定位；到开阔处继续等待，不代表模块损坏\")\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "盛思 全球定位系统 · UART",
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
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/ATGM336H_5N.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%8C%97%E6%96%97%E6%A8%A1%E5%9D%97.html",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# 盛思 全球定位系统\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "盛思 全球定位系统 · UART",
      "summary": "据bluebit导出的BDS/GPS所用RMC字段，单文件流式解析校验通过且状态A的定位数据。 接线与实物结果待测试。",
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
        "GNSS_Read在无数据时有无界等待，故采用120秒有界接收；仅处理GPRMC/GNRMC/BDRMC，验证校验和及A状态、经纬度方向，V或缺字段不伪报坐标。冷启动可能数分钟。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/ATGM336H_5N.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%8C%97%E6%96%97%E6%A8%A1%E5%9D%97.html",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# 盛思 全球定位系统\n# 官方来源核对；待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nuart = UART(1, baudrate={{baud}}, bits=8, parity=None, stop=1, timeout=10,\n            rx=Pin({{rx}}), tx=Pin({{tx}}))\n# BDS/GPS库使用RMC字段；此单文件接收器补超时、分包、校验和有效定位判定。\ndef parse_rmc(line):\n    try:\n        text = line.decode(\"ascii\").strip()\n        payload, checksum = text[1:].split(\"*\")\n        if not text.startswith(\"$\") or len(checksum) != 2:\n            return None\n        check = 0\n        for char in payload:\n            check ^= ord(char)\n        if check != int(checksum, 16):\n            return None\n        parts = payload.split(\",\")\n        if parts[0] not in (\"GPRMC\", \"GNRMC\", \"BDRMC\") or parts[2] != \"A\":\n            return None\n        if parts[4] not in (\"N\", \"S\") or parts[6] not in (\"E\", \"W\"):\n            return None\n        lat, lon = float(parts[3]), float(parts[5])\n        lat_min, lon_min = lat % 100, lon % 100\n        lat, lon = int(lat // 100) + lat_min / 60, int(lon // 100) + lon_min / 60\n        if lat_min >= 60 or lon_min >= 60 or lat > 90 or lon > 180:\n            return None\n        return (parts[1], -lat if parts[4] == \"S\" else lat, -lon if parts[6] == \"W\" else lon)\n    except (ValueError, IndexError, UnicodeError):\n        return None\n\ndef feed_rmc(buffer, chunk):\n    buffer.extend(chunk)\n    fixes = []\n    while b\"\\n\" in buffer:\n        end = buffer.index(10)\n        line = bytes(buffer[:end + 1])\n        del buffer[:end + 1]\n        fix = parse_rmc(line)\n        if fix is not None:\n            fixes.append(fix)\n    if len(buffer) > 256:\n        del buffer[:-256]\n    return fixes\nbuffer = bytearray()\nfound = False\ntry:\n    for _ in range(1200):\n        data = uart.read(128)\n        if data:\n            for utc, latitude, longitude in feed_rmc(buffer, data):\n                found = True\n                print(\"UTC:\", utc, \"纬度:\", latitude, \"经度:\", longitude)\n        sleep_ms(100)\nfinally:\n    uart.deinit()\nif not found:\n    print(\"120秒内未收到有效定位；到开阔处继续等待，不代表模块损坏\")\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "盛思 全球定位系统 · UART",
      "summary": "据bluebit导出的BDS/GPS所用RMC字段，单文件流式解析校验通过且状态A的定位数据。 接线与实物结果待测试。",
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
        "GNSS_Read在无数据时有无界等待，故采用120秒有界接收；仅处理GPRMC/GNRMC/BDRMC，验证校验和及A状态、经纬度方向，V或缺字段不伪报坐标。冷启动可能数分钟。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "模块TX接主控RX、模块RX接主控TX，不能同名对接；只收原始字节，不发送控制命令。波特率/8N1需按该型号手册确认。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/ATGM336H_5N.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%8C%97%E6%96%97%E6%A8%A1%E5%9D%97.html",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# 盛思 全球定位系统\n# 官方来源核对；待实物测试。\nfrom machine import Pin\nfrom utime import sleep_ms, sleep_us\nfrom machine import UART\nuart = UART(1, baudrate={{baud}}, bits=8, parity=None, stop=1, timeout=10,\n            rx=Pin({{rx}}), tx=Pin({{tx}}))\n# BDS/GPS库使用RMC字段；此单文件接收器补超时、分包、校验和有效定位判定。\ndef parse_rmc(line):\n    try:\n        text = line.decode(\"ascii\").strip()\n        payload, checksum = text[1:].split(\"*\")\n        if not text.startswith(\"$\") or len(checksum) != 2:\n            return None\n        check = 0\n        for char in payload:\n            check ^= ord(char)\n        if check != int(checksum, 16):\n            return None\n        parts = payload.split(\",\")\n        if parts[0] not in (\"GPRMC\", \"GNRMC\", \"BDRMC\") or parts[2] != \"A\":\n            return None\n        if parts[4] not in (\"N\", \"S\") or parts[6] not in (\"E\", \"W\"):\n            return None\n        lat, lon = float(parts[3]), float(parts[5])\n        lat_min, lon_min = lat % 100, lon % 100\n        lat, lon = int(lat // 100) + lat_min / 60, int(lon // 100) + lon_min / 60\n        if lat_min >= 60 or lon_min >= 60 or lat > 90 or lon > 180:\n            return None\n        return (parts[1], -lat if parts[4] == \"S\" else lat, -lon if parts[6] == \"W\" else lon)\n    except (ValueError, IndexError, UnicodeError):\n        return None\n\ndef feed_rmc(buffer, chunk):\n    buffer.extend(chunk)\n    fixes = []\n    while b\"\\n\" in buffer:\n        end = buffer.index(10)\n        line = bytes(buffer[:end + 1])\n        del buffer[:end + 1]\n        fix = parse_rmc(line)\n        if fix is not None:\n            fixes.append(fix)\n    if len(buffer) > 256:\n        del buffer[:-256]\n    return fixes\nbuffer = bytearray()\nfound = False\ntry:\n    for _ in range(1200):\n        data = uart.read(128)\n        if data:\n            for utc, latitude, longitude in feed_rmc(buffer, data):\n                found = True\n                print(\"UTC:\", utc, \"纬度:\", latitude, \"经度:\", longitude)\n        sleep_ms(100)\nfinally:\n    uart.deinit()\nif not found:\n    print(\"120秒内未收到有效定位；到开阔处继续等待，不代表模块损坏\")\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
