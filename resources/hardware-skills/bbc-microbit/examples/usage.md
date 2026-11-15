# BBC micro:bit（V1 / V2） 使用示例

1. 先运行本地硬件组合校验。
2. 根据验证结果确认供电、总线和驱动。


```python
# 用途：micro:bit 点阵自检；无外接器件。
from microbit import display, Image, sleep
display.show(Image.HAPPY)
sleep(600)
display.clear()
print("MICROBIT_DISPLAY_TEST_RETURNED")
```
屏幕现象须由用户观察；打印标记不代表实物已验收。
