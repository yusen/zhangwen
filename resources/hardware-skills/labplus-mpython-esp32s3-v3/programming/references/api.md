# 3.0 API 与最小代码

来源：原项目 `resources/hardware-skills/labplus-mpython-esp32s3-v3` 和受保护的 `code_agent/board_api_contracts.py`；官方 https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/mpython.html 。本轮官方站点403，使用原包已核对资料，未宣称重新在线核对或真机执行。

## 显示

`display.clear(color)`、`display.fill(color)`、`display.circle(x,y,r,color)`、`display.fill_circle(x,y,r,color)`、`display.rect(x,y,w,h,color)`、`display.line(x1,y1,x2,y2,color)`；`display.DispChar(str,x,y,color,auto_wrap)` 用于中文；`display.show()`刷新。

```python
from mpython import display, lcd

display.clear(lcd.BLACK)
display.circle(64, 64, 24, lcd.WHITE)
display.show()
print("MPYTHON_V3_CIRCLE_SUBMITTED")
```

原官方资料支持 `lcd.BLACK/WHITE/RED/GREEN/BLUE/YELLOW/CYAN/MAGENTA/ORANGE`。不要把颜色整数1当成单色白色约定，不使用2.0的 `oled` 对象。

## 板载对象

`button_a.is_pressed()`、`button_b.is_pressed()`；`light.read()`、`sound.read()`；`accelerometer.get_x()/get_y()/get_z()`；`gyroscope.get_x()/get_y()/get_z()`；`magnetic.get_heading()`。RGB：`rgb.fill((0,16,0)); rgb.brightness(0.2); rgb.write()`。以上为原官方资料契约，当前板卡是否导出仍需核对固件。

## 扩展库

按需查原包示例：music、urequests（关闭响应）、umqtt.simple、radio、sdcard、bluebit、parrot、ds18x20、servo。GUI的 `UI`、`MicroExcelTable`、`MicroChart` 按原例调用；官方部分表格签名疑似笔误，不能自行猜修。P19/P20与板载I2C共享，先核对地址和上拉。电机/舵机独立供电、共地和限流条件须先确认。
