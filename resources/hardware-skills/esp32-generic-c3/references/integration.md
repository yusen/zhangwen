# ESP32-C3（通用 MicroPython） 集成说明

接线、驱动和机械集成细节应在验证后补充；不得在此文件中保存凭据或主机路径。

## 官方API边界
原生USB串口使用GPIO18/19；若板卡使用USB-UART桥，按桥接串口连接。不自动安装固件、不切换引导模式。
MicroPython 示例只使用通用 API：`import sys; print(sys.platform)`。外设端口须先核对开发板。
