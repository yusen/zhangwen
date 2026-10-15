# 2.0 API 与最小代码

来源：原项目 `board-skills/labplus-mpython-v2`，官方 https://mpython.readthedocs.io/zh-cn/master/library/mPython/mpython.html 。本次官方站点返回403，未把抓取失败写成重新核对成功。

## OLED（128×64）

- `oled.fill(0)` 清屏；`oled.pixel(x, y, 1)`、`oled.line(x1,y1,x2,y2,1)`、`oled.rect(x,y,w,h,1)` 绘图。
- `oled.circle(x,y,r,1)` 为空心圆。`oled.show()` 提交缓冲区。
- x范围0–127，y范围0–63；半径和边界应留在屏幕范围内。

```python
from mpython import oled

oled.fill(0)
oled.circle(64, 32, 24, 1)
oled.show()
print("ZW_CIRCLE_OK")
```

这是已实测的空心圆程序。文字/字体支持随官方固件变化；需要中文优先核对 `oled.DispChar` 可用性，不把普通 `text()` 当中文字体。

## 按键、光线、声音与 RGB

官方 mPython 2.0 常用对象为 `button_a`、`button_b`、`light`、`sound`、`rgb`。先确认当前固件导出，再用 `button_a.value()`（通常低电平按下）、`light.read()`、`sound.read()`。RGB 通过 `rgb.fill((r,g,b)); rgb.write()` 更新，先用低亮度值如8。持续读取使用有退出路径的有限循环和 `time.sleep_ms()`，避免无间隔忙循环。

扩展引脚/ADC/PWM/I2C等必须再读对应硬件资料和固件API。不要拿3.0的引脚表作为2.0映射。
