# 屏幕与摄像头 API

验证级别：D（官方页面直接明确）；多功能组合为 C。

## 导入

```python
from unihiker_k10 import screen
from k10_base import Camera
```

## 摄像头预览

```python
camera = Camera()
screen.init(dir=2)
camera.init()
screen.show_camera(camera)
```

## 初始化

```python
screen.init(dir=2)
```

官方示例说明方向参数范围为 0～3，未传时默认值为 2。

## 背景与线宽

```python
screen.show_bg(color=0xFFFF00)
screen.set_width(width=5)
```

颜色使用 24 位十六进制 RGB 表示方式。

## 图形

```python
screen.draw_line(x0=0, y0=0, x1=80, y1=80, color=0x0000FF)
screen.draw_point(x=100, y=10, color=0xFF0000)

screen.draw_rect(
    x=120, y=100, w=80, h=120,
    bcolor=0xFF6666,
    fcolor=0x0000FF
)

screen.draw_circle(
    x=80, y=80, r=40,
    bcolor=0x00FF00,
    fcolor=0x0000FF
)
```

只画边框时可省略 `fcolor`。

## 文字

按坐标：

```python
screen.draw_text(
    text="你好",
    x=10,
    y=0,
    font_size=24,
    color=0xFF0000
)
```

按行：

```python
screen.draw_text(
    text="状态正常",
    line=2,
    font_size=24,
    color=0x00FF00
)
```

## 提交与清除

```python
screen.show_draw()
screen.clear()
```

绘制图元后需要 `show_draw()` 才显示。

## AI 图像帧

```python
image_data = ai.camera_capture()
screen.show_camera_img(image_data)
```

## 安全规则

- `screen.init()` 只做一次。
- `Camera.init()` 只做一次。
- AI 模式只在初始化或状态切换时调用。
- 不在 MQTT 回调、引脚中断或子线程中刷新屏幕。
- 普通数据面板建议 0.5～1 秒刷新一次。
- AI 帧循环可以更快，但不要在其中反复创建大量文本和图形对象。
