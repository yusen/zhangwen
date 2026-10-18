<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_seeed_decba7adfcd3",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "Grove - 气压传感器（BMP280） · I2C",
      "summary": "内置单文件BMX280基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
          "default": "0x76",
          "options": [
            {
              "value": "0x76",
              "label": "0x76"
            },
            {
              "value": "0x77",
              "label": "0x77"
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
        "本例仅温度与气压，不含BME280湿度或海拔估算；不得替用于BME680或BMP388。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Barometer_Sensor-BMP280/",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# Grove - 气压传感器（BMP280）\n# 掌控板2.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\nimport struct\nchip = i2c.readfrom_mem(ADDR, 0xD0, 1)[0]\nif chip not in (0x58, 0x60):\n    raise RuntimeError(\"Expected BMP280/BME280 chip ID\")\ncal = struct.unpack(\"<HhhHhhhhhhhh\", i2c.readfrom_mem(ADDR, 0x88, 24))\ni2c.writeto_mem(ADDR, 0xF4, bytes([0x27]))\nsleep_ms(100)\ndef read():\n    data = i2c.readfrom_mem(ADDR, 0xF7, 6)\n    p_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)\n    t_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)\n    t1, t2, t3 = cal[:3]\n    v1 = (t_raw / 16384 - t1 / 1024) * t2\n    v2 = (t_raw / 131072 - t1 / 8192) ** 2 * t3\n    fine = v1 + v2\n    temperature = fine / 5120\n    p1, p2, p3, p4, p5, p6, p7, p8, p9 = cal[3:]\n    v1 = fine / 2 - 64000\n    v2 = v1 * v1 * p6 / 32768 + v1 * p5 * 2\n    v2 = v2 / 4 + p4 * 65536\n    v1 = (p3 * v1 * v1 / 524288 + p2 * v1) / 524288\n    v1 = (1 + v1 / 32768) * p1\n    if v1 == 0:\n        raise RuntimeError(\"Invalid pressure calibration\")\n    pressure = (1048576 - p_raw - v2 / 4096) * 6250 / v1\n    pressure += (p9 * pressure * pressure / 2147483648 + pressure * p8 / 32768 + p7) / 16\n    print(\"Temperature C =\", temperature, \"Pressure hPa =\", pressure / 100)\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "Grove - 气压传感器（BMP280） · I2C",
      "summary": "内置单文件BMX280基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
          "default": "0x76",
          "options": [
            {
              "value": "0x76",
              "label": "0x76"
            },
            {
              "value": "0x77",
              "label": "0x77"
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
        "本例仅温度与气压，不含BME280湿度或海拔估算；不得替用于BME680或BMP388。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Barometer_Sensor-BMP280/",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# Grove - 气压传感器（BMP280）\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\nimport struct\nchip = i2c.readfrom_mem(ADDR, 0xD0, 1)[0]\nif chip not in (0x58, 0x60):\n    raise RuntimeError(\"Expected BMP280/BME280 chip ID\")\ncal = struct.unpack(\"<HhhHhhhhhhhh\", i2c.readfrom_mem(ADDR, 0x88, 24))\ni2c.writeto_mem(ADDR, 0xF4, bytes([0x27]))\nsleep_ms(100)\ndef read():\n    data = i2c.readfrom_mem(ADDR, 0xF7, 6)\n    p_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)\n    t_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)\n    t1, t2, t3 = cal[:3]\n    v1 = (t_raw / 16384 - t1 / 1024) * t2\n    v2 = (t_raw / 131072 - t1 / 8192) ** 2 * t3\n    fine = v1 + v2\n    temperature = fine / 5120\n    p1, p2, p3, p4, p5, p6, p7, p8, p9 = cal[3:]\n    v1 = fine / 2 - 64000\n    v2 = v1 * v1 * p6 / 32768 + v1 * p5 * 2\n    v2 = v2 / 4 + p4 * 65536\n    v1 = (p3 * v1 * v1 / 524288 + p2 * v1) / 524288\n    v1 = (1 + v1 / 32768) * p1\n    if v1 == 0:\n        raise RuntimeError(\"Invalid pressure calibration\")\n    pressure = (1048576 - p_raw - v2 / 4096) * 6250 / v1\n    pressure += (p9 * pressure * pressure / 2147483648 + pressure * p8 / 32768 + p7) / 16\n    print(\"Temperature C =\", temperature, \"Pressure hPa =\", pressure / 100)\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "Grove - 气压传感器（BMP280） · I2C",
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
        "本例仅温度与气压，不含BME280湿度或海拔估算；不得替用于BME680或BMP388。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "K10官方代码模式未公开通用I2C对象和原生引脚映射；本例不猜测machine.Pin端口。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Barometer_Sensor-BMP280/",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# Grove - 气压传感器（BMP280）\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "Grove - 气压传感器（BMP280） · I2C",
      "summary": "内置单文件BMX280基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
          "default": "0x76",
          "options": [
            {
              "value": "0x76",
              "label": "0x76"
            },
            {
              "value": "0x77",
              "label": "0x77"
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
        "本例仅温度与气压，不含BME280湿度或海拔估算；不得替用于BME680或BMP388。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Barometer_Sensor-BMP280/",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# Grove - 气压传感器（BMP280）\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(5), scl=Pin(6), freq=100000)\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\nimport struct\nchip = i2c.readfrom_mem(ADDR, 0xD0, 1)[0]\nif chip not in (0x58, 0x60):\n    raise RuntimeError(\"Expected BMP280/BME280 chip ID\")\ncal = struct.unpack(\"<HhhHhhhhhhhh\", i2c.readfrom_mem(ADDR, 0x88, 24))\ni2c.writeto_mem(ADDR, 0xF4, bytes([0x27]))\nsleep_ms(100)\ndef read():\n    data = i2c.readfrom_mem(ADDR, 0xF7, 6)\n    p_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)\n    t_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)\n    t1, t2, t3 = cal[:3]\n    v1 = (t_raw / 16384 - t1 / 1024) * t2\n    v2 = (t_raw / 131072 - t1 / 8192) ** 2 * t3\n    fine = v1 + v2\n    temperature = fine / 5120\n    p1, p2, p3, p4, p5, p6, p7, p8, p9 = cal[3:]\n    v1 = fine / 2 - 64000\n    v2 = v1 * v1 * p6 / 32768 + v1 * p5 * 2\n    v2 = v2 / 4 + p4 * 65536\n    v1 = (p3 * v1 * v1 / 524288 + p2 * v1) / 524288\n    v1 = (1 + v1 / 32768) * p1\n    if v1 == 0:\n        raise RuntimeError(\"Invalid pressure calibration\")\n    pressure = (1048576 - p_raw - v2 / 4096) * 6250 / v1\n    pressure += (p9 * pressure * pressure / 2147483648 + pressure * p8 / 32768 + p7) / 16\n    print(\"Temperature C =\", temperature, \"Pressure hPa =\", pressure / 100)\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "Grove - 气压传感器（BMP280） · I2C",
      "summary": "内置单文件BMX280基础读取示例，输出单位与异常检查见代码；接线和实物结果待确认。",
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
          "default": "0x76",
          "options": [
            {
              "value": "0x76",
              "label": "0x76"
            },
            {
              "value": "0x77",
              "label": "0x77"
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
        "本例仅温度与气压，不含BME280湿度或海拔估算；不得替用于BME680或BMP388。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://wiki.seeedstudio.com/cn/Grove-Barometer_Sensor-BMP280/",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# Grove - 气压传感器（BMP280）\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(3), scl=Pin(4), freq=100000)\nADDR = {{address}}\nif ADDR not in i2c.scan():\n    raise RuntimeError(\"Sensor address absent; check wiring\")\nimport struct\nchip = i2c.readfrom_mem(ADDR, 0xD0, 1)[0]\nif chip not in (0x58, 0x60):\n    raise RuntimeError(\"Expected BMP280/BME280 chip ID\")\ncal = struct.unpack(\"<HhhHhhhhhhhh\", i2c.readfrom_mem(ADDR, 0x88, 24))\ni2c.writeto_mem(ADDR, 0xF4, bytes([0x27]))\nsleep_ms(100)\ndef read():\n    data = i2c.readfrom_mem(ADDR, 0xF7, 6)\n    p_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)\n    t_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)\n    t1, t2, t3 = cal[:3]\n    v1 = (t_raw / 16384 - t1 / 1024) * t2\n    v2 = (t_raw / 131072 - t1 / 8192) ** 2 * t3\n    fine = v1 + v2\n    temperature = fine / 5120\n    p1, p2, p3, p4, p5, p6, p7, p8, p9 = cal[3:]\n    v1 = fine / 2 - 64000\n    v2 = v1 * v1 * p6 / 32768 + v1 * p5 * 2\n    v2 = v2 / 4 + p4 * 65536\n    v1 = (p3 * v1 * v1 / 524288 + p2 * v1) / 524288\n    v1 = (1 + v1 / 32768) * p1\n    if v1 == 0:\n        raise RuntimeError(\"Invalid pressure calibration\")\n    pressure = (1048576 - p_raw - v2 / 4096) * 6250 / v1\n    pressure += (p9 * pressure * pressure / 2147483648 + pressure * p8 / 32768 + p7) / 16\n    print(\"Temperature C =\", temperature, \"Pressure hPa =\", pressure / 100)\n\nfor _ in range(20):\n    try:\n        read()\n    except (OSError, RuntimeError) as error:\n        print(\"Sensor read error =\", error)\n    sleep_ms(1000)\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
