<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_dfrobot_sen0206_k10",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "DFRobot SEN0206 MLX90614 非接触红外测温传感器 · I2C",
      "summary": "内置单文件MLX90614基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
          "default": "0x5a",
          "options": [
            {
              "value": "0x5a",
              "label": "0x5a"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0206_SEN0263_IR_Thermometer_Sensor-MLX90614_%E7%BA%A2%E5%A4%96%E6%B8%A9%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# DFRobot SEN0206 MLX90614 非接触红外测温传感器\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\ndef temperature(register):\n    data = i2c.readfrom_mem(ADDR, register, 3)\n    crc = 0\n    for value in bytes([ADDR << 1, register, (ADDR << 1) | 1]) + data[:2]:\n        crc ^= value\n        for _ in range(8):\n            crc = ((crc << 1) ^ 0x07) & 255 if crc & 128 else (crc << 1) & 255\n    if crc != data[2]:\n        raise RuntimeError(\"MLX90614 PEC mismatch\")\n    raw = int.from_bytes(data[:2], \"little\")\n    if raw & 0x8000:\n        raise RuntimeError(\"MLX90614 error flag\")\n    return raw * 0.02 - 273.15\ndef read():\n    print(\"Ambient C =\", temperature(0x06), \"Object C =\", temperature(0x07))\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "DFRobot SEN0206 MLX90614 非接触红外测温传感器 · I2C",
      "summary": "内置单文件MLX90614基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
          "default": "0x5a",
          "options": [
            {
              "value": "0x5a",
              "label": "0x5a"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0206_SEN0263_IR_Thermometer_Sensor-MLX90614_%E7%BA%A2%E5%A4%96%E6%B8%A9%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# DFRobot SEN0206 MLX90614 非接触红外测温传感器\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\ndef temperature(register):\n    data = i2c.readfrom_mem(ADDR, register, 3)\n    crc = 0\n    for value in bytes([ADDR << 1, register, (ADDR << 1) | 1]) + data[:2]:\n        crc ^= value\n        for _ in range(8):\n            crc = ((crc << 1) ^ 0x07) & 255 if crc & 128 else (crc << 1) & 255\n    if crc != data[2]:\n        raise RuntimeError(\"MLX90614 PEC mismatch\")\n    raw = int.from_bytes(data[:2], \"little\")\n    if raw & 0x8000:\n        raise RuntimeError(\"MLX90614 error flag\")\n    return raw * 0.02 - 273.15\ndef read():\n    print(\"Ambient C =\", temperature(0x06), \"Object C =\", temperature(0x07))\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "DFRobot SEN0206 MLX90614 非接触红外测温传感器 · I2C",
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
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "K10官方代码模式未公开通用I2C对象和原生引脚映射；本例不猜测machine.Pin端口。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0206_SEN0263_IR_Thermometer_Sensor-MLX90614_%E7%BA%A2%E5%A4%96%E6%B8%A9%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# DFRobot SEN0206 MLX90614 非接触红外测温传感器\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "DFRobot SEN0206 MLX90614 非接触红外测温传感器 · I2C",
      "summary": "内置单文件MLX90614基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
          "default": "0x5a",
          "options": [
            {
              "value": "0x5a",
              "label": "0x5a"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0206_SEN0263_IR_Thermometer_Sensor-MLX90614_%E7%BA%A2%E5%A4%96%E6%B8%A9%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# DFRobot SEN0206 MLX90614 非接触红外测温传感器\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(5), scl=Pin(6), freq=100000)\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\ndef temperature(register):\n    data = i2c.readfrom_mem(ADDR, register, 3)\n    crc = 0\n    for value in bytes([ADDR << 1, register, (ADDR << 1) | 1]) + data[:2]:\n        crc ^= value\n        for _ in range(8):\n            crc = ((crc << 1) ^ 0x07) & 255 if crc & 128 else (crc << 1) & 255\n    if crc != data[2]:\n        raise RuntimeError(\"MLX90614 PEC mismatch\")\n    raw = int.from_bytes(data[:2], \"little\")\n    if raw & 0x8000:\n        raise RuntimeError(\"MLX90614 error flag\")\n    return raw * 0.02 - 273.15\ndef read():\n    print(\"Ambient C =\", temperature(0x06), \"Object C =\", temperature(0x07))\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "DFRobot SEN0206 MLX90614 非接触红外测温传感器 · I2C",
      "summary": "内置单文件MLX90614基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
          "default": "待核对模块额定供电",
          "options": [
            {
              "value": "待核对模块额定供电",
              "label": "待核对模块额定供电"
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
          "default": "0x5a",
          "options": [
            {
              "value": "0x5a",
              "label": "0x5a"
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
        "原资料3.3V字段可能只是接入预检基线，未逐项核实额定范围；供电请看实物标识与官方产品资料。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://www.unihiker.com.cn/wiki/k10/compatibility2",
        "https://wiki.dfrobot.com.cn/_SKU_SEN0206_SEN0263_IR_Thermometer_Sensor-MLX90614_%E7%BA%A2%E5%A4%96%E6%B8%A9%E5%BA%A6%E4%BC%A0%E6%84%9F%E5%99%A8",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# DFRobot SEN0206 MLX90614 非接触红外测温传感器\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(3), scl=Pin(4), freq=100000)\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\ndef temperature(register):\n    data = i2c.readfrom_mem(ADDR, register, 3)\n    crc = 0\n    for value in bytes([ADDR << 1, register, (ADDR << 1) | 1]) + data[:2]:\n        crc ^= value\n        for _ in range(8):\n            crc = ((crc << 1) ^ 0x07) & 255 if crc & 128 else (crc << 1) & 255\n    if crc != data[2]:\n        raise RuntimeError(\"MLX90614 PEC mismatch\")\n    raw = int.from_bytes(data[:2], \"little\")\n    if raw & 0x8000:\n        raise RuntimeError(\"MLX90614 error flag\")\n    return raw * 0.02 - 273.15\ndef read():\n    print(\"Ambient C =\", temperature(0x06), \"Object C =\", temperature(0x07))\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
