# 板载传感器、按键和 RGB API

验证级别：D。

## A/B 按键

```python
from unihiker_k10 import button

button_a = button(button.a)
button_b = button(button.b)
```

状态：

```python
button_a.status()
button_b.status()
```

事件：

```python
button_a.event_pressed = callback
button_a.event_released = callback
```

建议事件函数只设置标志位。

## 温湿度

```python
from unihiker_k10 import temp_humi

temperature_c = temp_humi.read_temp()
temperature_f = temp_humi.read_temp_f()
humidity = temp_humi.read_humi()
```

## 环境光

```python
from unihiker_k10 import light

lux = light.read()
```

官方硬件页面说明板载器件为 LTR303ALS，检测范围 0～64k Lux。

## 三轴加速度

```python
from unihiker_k10 import acce

x_value = acce.read_x()
y_value = acce.read_y()
z_value = acce.read_z()
```

## 板载 RGB

```python
from unihiker_k10 import rgb
```

按 24 位颜色：

```python
rgb.write(num=0, color=0x0000FF)
rgb.write(color=0xFF00FF)
```

按 RGB 分量：

```python
rgb.write(num=0, R=255, G=0, B=0)
```

`num` 可使用 0、1、2；官方页面说明省略 `num` 或使用 `-1` 可代表全部。

亮度：

```python
rgb.brightness(9)
```

范围 0～9。

关闭：

```python
rgb.clear()
```

或者：

```python
rgb.write(color=0x000000)
```
