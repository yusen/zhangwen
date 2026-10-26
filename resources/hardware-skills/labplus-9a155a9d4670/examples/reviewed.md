<!-- zhangwen:module-guides:v1 -->
```json
{
  "schema": "zhangwen.module-guides/v1",
  "componentId": "hw_labplus_9a155a9d4670",
  "guides": [
    {
      "boardId": "hw_labplus_mpython_v2",
      "kind": "functional",
      "title": "盛思 循迹传感器（模拟） · ADC",
      "summary": "官方LineFollow双路模拟循迹，保留原始量和各路阈值判定。 接线与实物结果待测试。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
          "key": "sig",
          "label": "信号引脚",
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
              "value": "2",
              "label": "P2"
            }
          ]
        },
        {
          "key": "sig2",
          "label": "第二信号引脚",
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
              "value": "2",
              "label": "P2"
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
          "signal": "AO / S",
          "target": "{{sig}}"
        },
        {
          "signal": "第二路信号",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "案例为有限次采样；含button_b轮询的案例可按B停止，其他案例可用工作台停止。接线选项中的P号不是原始GPIO号。",
        "LineFollow用于双路模拟版；num=1/2，阈值≤2000为库默认，先在黑/白底分别测量再校准；不能替用于数字版。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BE%AA%E8%BF%B9%E4%BC%A0%E6%84%9F%E5%99%A8%EF%BC%88%E6%A8%A1%E6%8B%9F%EF%BC%89.html",
        "https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html"
      ],
      "codeTemplate": "# 盛思 循迹传感器（模拟）\n# 官方来源核对；待实物测试。\nfrom mpython import i2c, button_b\nfrom utime import sleep_ms\nfrom mpython import MPythonPin, PinMode\n# The MIT License (MIT)\n\n# Copyright (c) 2018, Tangliufeng. LabPlus\n\n# Permission is hereby granted, free of charge, to any person obtaining a copy\n# of this software and associated documentation files (the \"Software\"), to deal\n# in the Software without restriction, including without limitation the rights\n# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n# copies of the Software, and to permit persons to whom the Software is\n# furnished to do so, subject to the following conditions:\n\n# The above copyright notice and this permission notice shall be included in\n# all copies or substantial portions of the Software.\n\n# THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\n# THE SOFTWARE.\n\nclass LineFollow(object):\n    def __init__(self,num1,num2):\n        if(isinstance(num1, int) and isinstance(num2, int)):\n            self.pin1 = MPythonPin(num1, PinMode.ANALOG)\n            self.pin2 = MPythonPin(num2, PinMode.ANALOG)\n            self.threshold = [2000, 2000]\n        else:\n            raise ValueError('参数错误')\n\n    def detect(self,num):\n        '''是否探测到，num 1/2 return int 0/1'''\n        if(isinstance(num, int)):\n            tmp = self.get_raw_val()[num-1]\n            if(tmp<=self.threshold[num-1]):\n                return 1\n            else:\n                return 0\n\n    def get_raw_val(self):\n        ''' list [0,0]  0-4095 '''\n        try:\n            tmp = [max(min(self.pin1.read_analog(), 4095), 0),max(min(self.pin2.read_analog(), 4095), 0)]\n            return tmp\n        except Exception as error:\n            print(error)\n            return [-1,-1]\n       \n    def set_threshold(self, threshold):\n        '''设置阈值'''\n        if(isinstance(threshold, list)):\n            if(len(threshold) == 2):\n                self.threshold = threshold\n            else:\n                raise ValueError('参数错误')\n        else:\n            raise ValueError('参数错误')\n\nsensor = LineFollow({{sig}}, {{sig2}})\nsensor.set_threshold([2000, 2000])\nfor _ in range(40):\n    if button_b.value() == 0:\n        break\n    print(\"两路ADC:\", sensor.get_raw_val(), \"判定:\", sensor.detect(1), sensor.detect(2))\n    sleep_ms(300)\n"
    },
    {
      "boardId": "hw_labplus_mpython_esp32s3_v3",
      "kind": "functional",
      "title": "盛思 循迹传感器（模拟） · ADC",
      "summary": "读取两路ADC原始量；未做物理单位转换或校准。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
          "key": "sig",
          "label": "信号引脚",
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
          "key": "sig2",
          "label": "第二信号引脚",
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
          "signal": "AO / S",
          "target": "{{sig}}"
        },
        {
          "signal": "第二路信号",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BE%AA%E8%BF%B9%E4%BC%A0%E6%84%9F%E5%99%A8%EF%BC%88%E6%A8%A1%E6%8B%9F%EF%BC%89.html",
        "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/micropython/machine/machine.Pin.html"
      ],
      "codeTemplate": "# 盛思 循迹传感器（模拟）\n# 掌控板3.0官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, ADC\nfrom utime import sleep_ms\nadc0 = ADC(Pin({{sig}}))\nadc0.atten(ADC.ATTN_11DB)\nadc1 = ADC(Pin({{sig2}}))\nadc1.atten(ADC.ATTN_11DB)\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read(), adc1.read())\n    sleep_ms(250)\n"
    },
    {
      "boardId": "hw_seed_unihiker_k10",
      "kind": "functional",
      "title": "盛思 循迹传感器（模拟） · ADC",
      "summary": "读取两路ADC原始量；未做物理单位转换或校准。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
          "key": "sig",
          "label": "信号引脚",
          "default": "0",
          "options": [
            {
              "value": "0",
              "label": "P0（直连）"
            },
            {
              "value": "1",
              "label": "P1（直连）"
            }
          ]
        },
        {
          "key": "sig2",
          "label": "第二信号引脚",
          "default": "1",
          "options": [
            {
              "value": "0",
              "label": "P0（直连）"
            },
            {
              "value": "1",
              "label": "P1（直连）"
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
          "signal": "AO / S",
          "target": "{{sig}}"
        },
        {
          "signal": "第二路信号",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BE%AA%E8%BF%B9%E4%BC%A0%E6%84%9F%E5%99%A8%EF%BC%88%E6%A8%A1%E6%8B%9F%EF%BC%89.html",
        "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10"
      ],
      "codeTemplate": "# 盛思 循迹传感器（模拟）\n# K10官方MicroPython / unihiker_k10\n# 功能示例，待实物测试。\nfrom unihiker_k10 import pin\nfrom utime import sleep_ms\nadc0 = pin({{sig}})\nadc1 = pin({{sig2}})\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read_analog(), adc1.read_analog())\n    sleep_ms(250)\n"
    },
    {
      "boardId": "hw_seeed_xiao_esp32s3_sense",
      "kind": "functional",
      "title": "盛思 循迹传感器（模拟） · ADC",
      "summary": "读取两路ADC原始量；未做物理单位转换或校准。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
          "key": "sig",
          "label": "信号引脚",
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
          "key": "sig2",
          "label": "第二信号引脚",
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
          "signal": "AO / S",
          "target": "{{sig}}"
        },
        {
          "signal": "第二路信号",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "XIAO：D0=GPIO1，D1=GPIO2，D2=GPIO3，D4/SDA=GPIO5，D5/SCL=GPIO6；D号不等于GPIO号。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BE%AA%E8%BF%B9%E4%BC%A0%E6%84%9F%E5%99%A8%EF%BC%88%E6%A8%A1%E6%8B%9F%EF%BC%89.html",
        "https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/"
      ],
      "codeTemplate": "# 盛思 循迹传感器（模拟）\n# XIAO ESP32S3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, ADC\nfrom utime import sleep_ms\nadc0 = ADC(Pin({{sig}}))\nadc0.atten(ADC.ATTN_11DB)\nadc1 = ADC(Pin({{sig2}}))\nadc1.atten(ADC.ATTN_11DB)\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read(), adc1.read())\n    sleep_ms(250)\n"
    },
    {
      "boardId": "hw_esp32_generic_c3",
      "kind": "functional",
      "title": "盛思 循迹传感器（模拟） · ADC",
      "summary": "读取两路ADC原始量；未做物理单位转换或校准。",
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
          "default": "ADC",
          "options": [
            {
              "value": "ADC",
              "label": "模拟量"
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
          "key": "sig",
          "label": "信号引脚",
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
          "key": "sig2",
          "label": "第二信号引脚",
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
          "signal": "AO / S",
          "target": "{{sig}}"
        },
        {
          "signal": "第二路信号",
          "target": "{{sig2}}"
        }
      ],
      "notes": [
        "bluebit依赖mpython与多个外部库；不能把掌控板2.0库直接认作此主控已适配。当前板独立单文件案例可按所列接口使用。",
        "已对照用户提供的bluebit.py固定版本核对；资料/功能案例不等于实物验收，也不会自动标记主控已核实。",
        "默认接线只是建议；先断电接线，模块与主控共地。保存、语法检查及串口回读均不代表实际测量通过。",
        "示例只显示ADC原始量，不直接标为℃、分贝、ppm、湿度百分比或重量；物理单位需此型号的转换公式和校准。",
        "只把已确认不超过3.3V的信号接入主控；模块5V供电不表示信号可直连。",
        "通用C3没有统一D/P别名；确认GPIO3/4实际引出且未被板载功能占用。"
      ],
      "sources": [
        "https://github.com/labplus-cn/mpython/blob/80bbda23f3ae28e8edbff7c47dc5990a108eba30/port/modules/bluebit.py",
        "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BE%AA%E8%BF%B9%E4%BC%A0%E6%84%9F%E5%99%A8%EF%BC%88%E6%A8%A1%E6%8B%9F%EF%BC%89.html",
        "https://docs.micropython.org/en/latest/esp32/quickref.html"
      ],
      "codeTemplate": "# 盛思 循迹传感器（模拟）\n# ESP32_GENERIC_C3官方MicroPython\n# 功能示例，待实物测试。\nfrom machine import Pin, ADC\nfrom utime import sleep_ms\nadc0 = ADC(Pin({{sig}}))\nadc0.atten(ADC.ATTN_11DB)\nadc1 = ADC(Pin({{sig2}}))\nadc1.atten(ADC.ATTN_11DB)\nfor _ in range(40):\n    print(\"ADC raw =\", adc0.read(), adc1.read())\n    sleep_ms(250)\n"
    }
  ]
}
```
<!-- /zhangwen:module-guides:v1 -->
