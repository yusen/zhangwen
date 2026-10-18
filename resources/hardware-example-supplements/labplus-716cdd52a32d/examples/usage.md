<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_labplus_716cdd52a32d",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "盛思 温湿度传感器（I2C） · I2C",
      "summary": "内置单文件SHT20基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
        },
        {
          "key": "address",
          "label": "I²C地址",
          "default": "0x40",
          "options": [
            {
              "value": "0x40",
              "label": "0x40"
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
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E6%B8%A9%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# 盛思 温湿度传感器（I2C）\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\ndef sample(command, delay):\n    i2c.writeto(ADDR, bytes([command]))\n    sleep_ms(delay)\n    data = i2c.readfrom(ADDR, 3)\n    # SHT2x uses the same polynomial but initial CRC=0x00.\n    crc = 0\n    for value in data[:2]:\n        crc ^= value\n        for _ in range(8):\n            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF\n    if crc != data[2]:\n        raise RuntimeError(\"SHT20 CRC mismatch\")\n    return int.from_bytes(data[:2], \"big\") & 0xFFFC\ndef read():\n    t = -46.85 + 175.72 * sample(0xF3, 100) / 65536\n    h = -6 + 125 * sample(0xF5, 40) / 65536\n    print(\"Temperature C =\", t, \"Humidity %:\", max(0, min(100, h)))\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "盛思 温湿度传感器（I2C） · I2C",
      "summary": "内置单文件SHT20基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
        },
        {
          "key": "address",
          "label": "I²C地址",
          "default": "0x40",
          "options": [
            {
              "value": "0x40",
              "label": "0x40"
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
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E6%B8%A9%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# 盛思 温湿度传感器（I2C）\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\ndef sample(command, delay):\n    i2c.writeto(ADDR, bytes([command]))\n    sleep_ms(delay)\n    data = i2c.readfrom(ADDR, 3)\n    # SHT2x uses the same polynomial but initial CRC=0x00.\n    crc = 0\n    for value in data[:2]:\n        crc ^= value\n        for _ in range(8):\n            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF\n    if crc != data[2]:\n        raise RuntimeError(\"SHT20 CRC mismatch\")\n    return int.from_bytes(data[:2], \"big\") & 0xFFFC\ndef read():\n    t = -46.85 + 175.72 * sample(0xF3, 100) / 65536\n    h = -6 + 125 * sample(0xF5, 40) / 65536\n    print(\"Temperature C =\", t, \"Humidity %:\", max(0, min(100, h)))\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "盛思 温湿度传感器（I2C） · I2C",
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
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "K10官方代码模式未公开通用I2C对象和原生引脚映射；本例不猜测machine.Pin端口。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E6%B8%A9%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# 盛思 温湿度传感器（I2C）\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "盛思 温湿度传感器（I2C） · I2C",
      "summary": "内置单文件SHT20基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
        },
        {
          "key": "address",
          "label": "I²C地址",
          "default": "0x40",
          "options": [
            {
              "value": "0x40",
              "label": "0x40"
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
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E6%B8%A9%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# 盛思 温湿度传感器（I2C）\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(5), scl=Pin(6), freq=100000)\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\ndef sample(command, delay):\n    i2c.writeto(ADDR, bytes([command]))\n    sleep_ms(delay)\n    data = i2c.readfrom(ADDR, 3)\n    # SHT2x uses the same polynomial but initial CRC=0x00.\n    crc = 0\n    for value in data[:2]:\n        crc ^= value\n        for _ in range(8):\n            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF\n    if crc != data[2]:\n        raise RuntimeError(\"SHT20 CRC mismatch\")\n    return int.from_bytes(data[:2], \"big\") & 0xFFFC\ndef read():\n    t = -46.85 + 175.72 * sample(0xF3, 100) / 65536\n    h = -6 + 125 * sample(0xF5, 40) / 65536\n    print(\"Temperature C =\", t, \"Humidity %:\", max(0, min(100, h)))\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "盛思 温湿度传感器（I2C） · I2C",
      "summary": "内置单文件SHT20基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
        },
        {
          "key": "address",
          "label": "I²C地址",
          "default": "0x40",
          "options": [
            {
              "value": "0x40",
              "label": "0x40"
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
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E6%B8%A9%E6%B9%BF%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# 盛思 温湿度传感器（I2C）\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(3), scl=Pin(4), freq=100000)\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\ndef sample(command, delay):\n    i2c.writeto(ADDR, bytes([command]))\n    sleep_ms(delay)\n    data = i2c.readfrom(ADDR, 3)\n    # SHT2x uses the same polynomial but initial CRC=0x00.\n    crc = 0\n    for value in data[:2]:\n        crc ^= value\n        for _ in range(8):\n            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF\n    if crc != data[2]:\n        raise RuntimeError(\"SHT20 CRC mismatch\")\n    return int.from_bytes(data[:2], \"big\") & 0xFFFC\ndef read():\n    t = -46.85 + 175.72 * sample(0xF3, 100) / 65536\n    h = -6 + 125 * sample(0xF5, 40) / 65536\n    print(\"Temperature C =\", t, \"Humidity %:\", max(0, min(100, h)))\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
