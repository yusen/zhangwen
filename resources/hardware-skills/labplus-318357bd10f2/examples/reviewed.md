<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_labplus_318357bd10f2",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "盛思 超声波传感器 · I2C",
      "summary": "2026-10-18用户控制实现经官方bluebit交叉核对；单文件测距，不依赖bluebit。 接线与实物结果待测试。",
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
        "案例为有限次采样；含button_b轮询的案例可按B停止，其他案例可用工作台停止。接线选项中的P号不是原始GPIO号。",
        "Ultrasonic：0x0B写[1]→等待2ms→读2字节；小端/10为厘米，超过200截为200；200不能证明真实距离恰为200cm。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "这是I2C乐动超声波，不能套用Grove单线或K10 SEN0388驱动。",
        "用户提供的控制流程：7位地址0x0B写入[1]，等待2ms，读取2字节；小端整数/10换算厘米，超过200返回200。不能仅readfrom(address, 1)。",
        "原bluebit.Ultrasonic()调用同样可保留；此单文件实现用于明确协议并避免依赖缺库，不表示平台已完成实物验证。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E8%B6%85%E5%A3%B0%E6%B3%A2.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/bluebit.html"
      ],
      "codeTemplate": "# 盛思 超声波传感器\n# 官方来源核对；待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\nfrom mpython import button_b\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n\nclass Ultrasonic(object):\n    \"\"\"\n    超声波模块控制类\n\n    :param i2c: I2C实例对象,默认i2c=i2c.\n    \"\"\"\n\n    def __init__(self, i2c=i2c):\n        self.i2c = i2c\n\n    def distance(self):\n        \"\"\"\n        获取超声波测距\n\n        :return: 返回测距,单位cm\n        \"\"\"\n        self.i2c.writeto(0x0b, bytearray([1]))\n        sleep_ms(2)\n        temp = self.i2c.readfrom(0x0b, 2)\n        distanceCM = (temp[0] + temp[1] * 256) / 10\n        if(distanceCM>200):\n            distanceCM=200\n        return distanceCM\n\nsensor = Ultrasonic(i2c)\nfor _ in range(40):\n    if button_b.value() == 0:\n        break\n    try:\n        print(sensor.distance(), \"cm（200为库上限）\")\n    except OSError as error:\n        print(\"测量失败:\", error)\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "盛思 超声波传感器 · I2C",
      "summary": "2026-10-18用户控制实现经官方bluebit交叉核对；单文件测距，不依赖bluebit。 接线与实物结果待测试。",
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
        "Ultrasonic：0x0B写[1]→等待2ms→读2字节；小端/10为厘米，超过200截为200；200不能证明真实距离恰为200cm。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "这是I2C乐动超声波，不能套用Grove单线或K10 SEN0388驱动。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E8%B6%85%E5%A3%B0%E6%B3%A2.html",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# 盛思 超声波传感器\n# 官方来源核对；待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n\nclass Ultrasonic(object):\n    \"\"\"\n    超声波模块控制类\n\n    :param i2c: I2C实例对象,默认i2c=i2c.\n    \"\"\"\n\n    def __init__(self, i2c=i2c):\n        self.i2c = i2c\n\n    def distance(self):\n        \"\"\"\n        获取超声波测距\n\n        :return: 返回测距,单位cm\n        \"\"\"\n        self.i2c.writeto(0x0b, bytearray([1]))\n        sleep_ms(2)\n        temp = self.i2c.readfrom(0x0b, 2)\n        distanceCM = (temp[0] + temp[1] * 256) / 10\n        if(distanceCM>200):\n            distanceCM=200\n        return distanceCM\n\nsensor = Ultrasonic(i2c)\nfor _ in range(40):\n    try:\n        print(sensor.distance(), \"cm（200为库上限）\")\n    except OSError as error:\n        print(\"测量失败:\", error)\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "盛思 超声波传感器 · I2C",
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
        "这是I2C乐动超声波，不能套用Grove单线或K10 SEN0388驱动。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "K10官方代码模式未公开通用I2C对象和原生引脚映射；本例不猜测machine.Pin端口。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E8%B6%85%E5%A3%B0%E6%B3%A2.html",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# 盛思 超声波传感器\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "盛思 超声波传感器 · I2C",
      "summary": "2026-10-18用户控制实现经官方bluebit交叉核对；单文件测距，不依赖bluebit。 接线与实物结果待测试。",
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
        "Ultrasonic：0x0B写[1]→等待2ms→读2字节；小端/10为厘米，超过200截为200；200不能证明真实距离恰为200cm。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "这是I2C乐动超声波，不能套用Grove单线或K10 SEN0388驱动。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E8%B6%85%E5%A3%B0%E6%B3%A2.html",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# 盛思 超声波传感器\n# 官方来源核对；待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(5), scl=Pin(6), freq=100000)\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n\nclass Ultrasonic(object):\n    \"\"\"\n    超声波模块控制类\n\n    :param i2c: I2C实例对象,默认i2c=i2c.\n    \"\"\"\n\n    def __init__(self, i2c=i2c):\n        self.i2c = i2c\n\n    def distance(self):\n        \"\"\"\n        获取超声波测距\n\n        :return: 返回测距,单位cm\n        \"\"\"\n        self.i2c.writeto(0x0b, bytearray([1]))\n        sleep_ms(2)\n        temp = self.i2c.readfrom(0x0b, 2)\n        distanceCM = (temp[0] + temp[1] * 256) / 10\n        if(distanceCM>200):\n            distanceCM=200\n        return distanceCM\n\nsensor = Ultrasonic(i2c)\nfor _ in range(40):\n    try:\n        print(sensor.distance(), \"cm（200为库上限）\")\n    except OSError as error:\n        print(\"测量失败:\", error)\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "盛思 超声波传感器 · I2C",
      "summary": "2026-10-18用户控制实现经官方bluebit交叉核对；单文件测距，不依赖bluebit。 接线与实物结果待测试。",
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
        "Ultrasonic：0x0B写[1]→等待2ms→读2字节；小端/10为厘米，超过200截为200；200不能证明真实距离恰为200cm。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "这是I2C乐动超声波，不能套用Grove单线或K10 SEN0388驱动。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E8%B6%85%E5%A3%B0%E6%B3%A2.html",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# 盛思 超声波传感器\n# 官方来源核对；待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(3), scl=Pin(4), freq=100000)\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n\nclass Ultrasonic(object):\n    \"\"\"\n    超声波模块控制类\n\n    :param i2c: I2C实例对象,默认i2c=i2c.\n    \"\"\"\n\n    def __init__(self, i2c=i2c):\n        self.i2c = i2c\n\n    def distance(self):\n        \"\"\"\n        获取超声波测距\n\n        :return: 返回测距,单位cm\n        \"\"\"\n        self.i2c.writeto(0x0b, bytearray([1]))\n        sleep_ms(2)\n        temp = self.i2c.readfrom(0x0b, 2)\n        distanceCM = (temp[0] + temp[1] * 256) / 10\n        if(distanceCM>200):\n            distanceCM=200\n        return distanceCM\n\nsensor = Ultrasonic(i2c)\nfor _ in range(40):\n    try:\n        print(sensor.distance(), \"cm（200为库上限）\")\n    except OSError as error:\n        print(\"测量失败:\", error)\n    sleep_ms(300)\n"
    }
  ],
  "i2c": {
    "defaultAddress": "0x0b",
    "addresses": [
      "0x0b"
    ],
    "notes": "用户于2026-10-18提供的盛思Ultrasonic控制实现：向7位设备地址0x0B写入[1]，等待2ms，读取2字节；(低字节+高字节*256)/10为厘米，超过200返回200。不可只读1字节，不是Grove单线或SEN0388脉宽协议。此为用户资料，尚未由平台实物核验；官方链接供交叉核对。 2026-10-18已对照用户指定官方bluebit.py固定版本交叉核对，协议一致；仍未实物验收。",
    "sources": [
      "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
      "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/bluebit.html"
    ]
  }
}
```
<!-- /zhangwen:module-guides:v1 -->
