# 掌控板 2.0（ESP32） 集成说明

接线、驱动和机械集成细节应在验证后补充；不得在此文件中保存凭据或主机路径。

## 官方API边界
板载入口：`from mpython import oled`。OLED为128×64单色：`oled.fill(0)`清屏，`oled.circle(x,y,r,1)`绘制空心圆，`oled.show()`刷新。勿用`fill_circle`替代空心圆。
官方源码：https://github.com/labplus-cn/mpython/blob/master/port/boards/mpython/modules/mpython.py
程序返回REPL后画面仍保持；实际点亮与屏幕结果需实物观察。
