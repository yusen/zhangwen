<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_labplus_f2d23891735d",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "盛思 颜色传感器 · I2C",
      "summary": "官方Color协议的单文件RGB读取；未就绪显式报错，不伪报黑色。 接线与实物结果待测试。",
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
        "Color：0x0A写[1]启动，100ms后写[2]读状态3，再写[3]读6字节；按R/G/B重排并归一至0–255，非照度或颜色名称。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "库缺失不能证明接线错误；不自动安装或刷固件。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E9%A2%9C%E8%89%B2%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/bluebit.html"
      ],
      "codeTemplate": "# 盛思 颜色传感器\n# 官方来源核对；待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\nfrom mpython import button_b\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n\nclass Color(object):\n    \"\"\"\n    颜色模块控制类\n\n    :param i2c: I2C实例对象,默认i2c=i2c.\n    \"\"\"\n\n    def __init__(self, i2c=i2c):\n        self.i2c = i2c\n\n    def getRGB(self):\n        \"\"\"\n        获取RGB值\n\n        :return: 返回RGB三元组,(r,g,b)\n        \"\"\"\n        color = [0, 0, 0]\n        self.i2c.writeto(0x0a, bytearray([1]))\n        sleep_ms(100)\n        self.i2c.writeto(0x0a, bytearray([2]))\n        state = self.i2c.readfrom(0x0a, 1)\n        if state[0] == 3:\n            self.i2c.writeto(0x0a, bytearray([3]))\n            c = self.i2c.readfrom(0x0a, 6)\n            color[0] = c[5] * 256 + c[4]  # color R\n            color[1] = c[1] * 256 + c[0]  # color G\n            color[2] = c[3] * 256 + c[2]  # color B\n            maxColor = max(color[0], color[1], color[2])\n            if maxColor > 255:\n                color[0] = color[0] * 255 // maxColor\n                color[1] = color[1] * 255 // maxColor\n                color[2] = color[2] * 255 // maxColor\n        else:\n            raise OSError(\"颜色转换未就绪\")\n        return color\n\n\nsensor = Color(i2c)\nfor _ in range(40):\n    if button_b.value() == 0:\n        break\n    try:\n        print(\"RGB:\", sensor.getRGB())\n    except OSError as error:\n        print(\"测量失败:\", error)\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "盛思 颜色传感器 · I2C",
      "summary": "官方Color协议的单文件RGB读取；未就绪显式报错，不伪报黑色。 接线与实物结果待测试。",
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
        "Color：0x0A写[1]启动，100ms后写[2]读状态3，再写[3]读6字节；按R/G/B重排并归一至0–255，非照度或颜色名称。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E9%A2%9C%E8%89%B2%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# 盛思 颜色传感器\n# 官方来源核对；待实物测试。\nfrom mpython import i2c\nfrom utime import sleep_ms\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n\nclass Color(object):\n    \"\"\"\n    颜色模块控制类\n\n    :param i2c: I2C实例对象,默认i2c=i2c.\n    \"\"\"\n\n    def __init__(self, i2c=i2c):\n        self.i2c = i2c\n\n    def getRGB(self):\n        \"\"\"\n        获取RGB值\n\n        :return: 返回RGB三元组,(r,g,b)\n        \"\"\"\n        color = [0, 0, 0]\n        self.i2c.writeto(0x0a, bytearray([1]))\n        sleep_ms(100)\n        self.i2c.writeto(0x0a, bytearray([2]))\n        state = self.i2c.readfrom(0x0a, 1)\n        if state[0] == 3:\n            self.i2c.writeto(0x0a, bytearray([3]))\n            c = self.i2c.readfrom(0x0a, 6)\n            color[0] = c[5] * 256 + c[4]  # color R\n            color[1] = c[1] * 256 + c[0]  # color G\n            color[2] = c[3] * 256 + c[2]  # color B\n            maxColor = max(color[0], color[1], color[2])\n            if maxColor > 255:\n                color[0] = color[0] * 255 // maxColor\n                color[1] = color[1] * 255 // maxColor\n                color[2] = color[2] * 255 // maxColor\n        else:\n            raise OSError(\"颜色转换未就绪\")\n        return color\n\n\nsensor = Color(i2c)\nfor _ in range(40):\n    try:\n        print(\"RGB:\", sensor.getRGB())\n    except OSError as error:\n        print(\"测量失败:\", error)\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "diagnostic",
      "title": "盛思 颜色传感器 · I2C",
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
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E9%A2%9C%E8%89%B2%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# 盛思 颜色传感器\n# K10官方MicroPython / unihiker_k10\n# 诊断/参考，不代表完整测量驱动。\nimport sys\nprint(\"Runtime =\", sys.implementation)\nprint(\"Machine =\", getattr(sys.implementation, \"_machine\", \"unknown\"))\nprint(\"Module-specific driver is not included for this firmware yet.\")\nprint(\"Use the source link and confirm module version, supply and protocol first.\")\nimport unihiker_k10\nprint(\"Available K10 APIs =\", dir(unihiker_k10))\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "盛思 颜色传感器 · I2C",
      "summary": "官方Color协议的单文件RGB读取；未就绪显式报错，不伪报黑色。 接线与实物结果待测试。",
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
        "Color：0x0A写[1]启动，100ms后写[2]读状态3，再写[3]读6字节；按R/G/B重排并归一至0–255，非照度或颜色名称。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E9%A2%9C%E8%89%B2%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# 盛思 颜色传感器\n# 官方来源核对；待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(5), scl=Pin(6), freq=100000)\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n\nclass Color(object):\n    \"\"\"\n    颜色模块控制类\n\n    :param i2c: I2C实例对象,默认i2c=i2c.\n    \"\"\"\n\n    def __init__(self, i2c=i2c):\n        self.i2c = i2c\n\n    def getRGB(self):\n        \"\"\"\n        获取RGB值\n\n        :return: 返回RGB三元组,(r,g,b)\n        \"\"\"\n        color = [0, 0, 0]\n        self.i2c.writeto(0x0a, bytearray([1]))\n        sleep_ms(100)\n        self.i2c.writeto(0x0a, bytearray([2]))\n        state = self.i2c.readfrom(0x0a, 1)\n        if state[0] == 3:\n            self.i2c.writeto(0x0a, bytearray([3]))\n            c = self.i2c.readfrom(0x0a, 6)\n            color[0] = c[5] * 256 + c[4]  # color R\n            color[1] = c[1] * 256 + c[0]  # color G\n            color[2] = c[3] * 256 + c[2]  # color B\n            maxColor = max(color[0], color[1], color[2])\n            if maxColor > 255:\n                color[0] = color[0] * 255 // maxColor\n                color[1] = color[1] * 255 // maxColor\n                color[2] = color[2] * 255 // maxColor\n        else:\n            raise OSError(\"颜色转换未就绪\")\n        return color\n\n\nsensor = Color(i2c)\nfor _ in range(40):\n    try:\n        print(\"RGB:\", sensor.getRGB())\n    except OSError as error:\n        print(\"测量失败:\", error)\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "盛思 颜色传感器 · I2C",
      "summary": "官方Color协议的单文件RGB读取；未就绪显式报错，不伪报黑色。 接线与实物结果待测试。",
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
        "Color：0x0A写[1]启动，100ms后写[2]读状态3，再写[3]读6字节；按R/G/B重排并归一至0–255，非照度或颜色名称。",
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "先记录主控空载I2C地址，再断电接入单个模块比较；扫描不能证明型号或测量成功。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E9%A2%9C%E8%89%B2%E4%BC%A0%E6%84%9F%E5%99%A8.html",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# 盛思 颜色传感器\n# 官方来源核对；待实物测试。\nfrom machine import Pin, SoftI2C\nfrom utime import sleep_ms\ni2c = SoftI2C(sda=Pin(3), scl=Pin(4), freq=100000)\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n\nclass Color(object):\n    \"\"\"\n    颜色模块控制类\n\n    :param i2c: I2C实例对象,默认i2c=i2c.\n    \"\"\"\n\n    def __init__(self, i2c=i2c):\n        self.i2c = i2c\n\n    def getRGB(self):\n        \"\"\"\n        获取RGB值\n\n        :return: 返回RGB三元组,(r,g,b)\n        \"\"\"\n        color = [0, 0, 0]\n        self.i2c.writeto(0x0a, bytearray([1]))\n        sleep_ms(100)\n        self.i2c.writeto(0x0a, bytearray([2]))\n        state = self.i2c.readfrom(0x0a, 1)\n        if state[0] == 3:\n            self.i2c.writeto(0x0a, bytearray([3]))\n            c = self.i2c.readfrom(0x0a, 6)\n            color[0] = c[5] * 256 + c[4]  # color R\n            color[1] = c[1] * 256 + c[0]  # color G\n            color[2] = c[3] * 256 + c[2]  # color B\n            maxColor = max(color[0], color[1], color[2])\n            if maxColor > 255:\n                color[0] = color[0] * 255 // maxColor\n                color[1] = color[1] * 255 // maxColor\n                color[2] = color[2] * 255 // maxColor\n        else:\n            raise OSError(\"颜色转换未就绪\")\n        return color\n\n\nsensor = Color(i2c)\nfor _ in range(40):\n    try:\n        print(\"RGB:\", sensor.getRGB())\n    except OSError as error:\n        print(\"测量失败:\", error)\n    sleep_ms(300)\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
