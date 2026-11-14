# 连接与固件

经典款 Type-C 的 USB 数据线接 CH343P，由桥接器连接 UART0(GPIO20/21)；精简直连款的 Type-C 接 GPIO18/19，不能混用。用户图可见 CH343 类桥接芯片布局，具体批次须读芯片丝印。

掌问此板型使用现有 MicroPython / 浏览器 Web Serial 通道。只有用户确认已装支持 UART0 REPL 的 ESP32_GENERIC_C3 固件时才能使用 Python 上传运行；出厂 LuatOS Lua 不是 MicroPython。选择主控不会刷写或改变设备模式。现阶段不将通用原生 USB 固件冒充本板已核实默认固件。

连接后先让用户查看 REPL 的 `import sys; print(sys.implementation)`，保存、代码检查、文件回读、运行提交、实际观察分别确认。GPIO20/21 保留给串口；GPIO18/19 并非经典款板载 USB 口，但外接原生 USB 时会占用。

外置Flash经典版必须核对DIO模式；QIO会占GPIO12/13，内置Flash变体也不能照用本板LED引脚。UART排针8/9的商品图和官网文字表互相冲突，按实物丝印核对，不自动改固件配置。

复用当前项目与代码历史，换板前保留草稿；不自动复位、改凭据、发烧录命令或上传模型文件。模型 STEP/STL 是安装参考，不是设备程序。
