# 掌控板 2.0（ESP32） 使用示例

1. 先运行本地硬件组合校验。
2. 根据验证结果确认供电、总线和驱动。

## 最小示例
```python
# 掌控板 2.0 · OLED 空心圆
from mpython import oled

oled.fill(0)
oled.circle(64, 32, 24, 1)
oled.show()
print("ZW_CIRCLE_OK: center=(64,32), radius=24, outline")
```
