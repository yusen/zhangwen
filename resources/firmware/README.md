# 默认官方固件

2026-10-18在线核对。manifest.json固定来源、大小、SHA-256、写入偏移与版本，运行期间只从本地读取，不自动下载或追踪预览版。

| 主控 | 默认镜像 | 依据 |
|---|---|---|
| 掌控板2.0 | mPython v2.6.0 | labplus-cn/mpython最新非预发行Release；原厂合并包含0x1000填充，从0写入 |
| 掌控板3.0 | 官方在线平台当前默认包 | online.mpython.cn的FirmwareModal默认mpython_v3.bin；实际CDN地址在manifest，Last-Modified 2026-07-01，内嵌MicroPython v1.26.1-1.g7f275c0a5 on 2026-06-05；厂商未公开发行版本号，不称为上游MicroPython最新版本 |
| 行空板K10 | 官方文档MicroPython 0.9.8 | 大写K10文档路径，官方Google Drive原包，非Arduino固件 |
| XIAO ESP32S3 Sense | MicroPython v1.29.0 | SEEED_XIAO_ESP32S3板级稳定版，未承诺Sense摄像头支持 |
| 通用ESP32-C3 | MicroPython v1.29.0 | ESP32_GENERIC_C3稳定版，至少4MiB Flash |

所有本地镜像偏移均为0。浏览器核对镜像与芯片，按写入扇区备份到IndexedDB并尝试下载，保持原串口互斥，写后SHA回读；支持仍连通时恢复本次范围。没有整片擦除，没有自动实物验收。K10官方Windows教程先整片擦除，本平台只覆盖镜像范围，不能声称等同出厂恢复。

MicroPython与掌控2.0许可证原文分别见MICROPYTHON-LICENSE.txt、MPYTHON-LICENSE.txt和MPYTHON3-LICENSE.txt。厂商板级固件包含其自有驱动/资源，保留原版权，不把MicroPython的MIT授权扩展为全部第三方资源授权。K10镜像按官方公开下载来源原样保存，权利属于DFRobot及其上游。逐项来源见manifest；本轮仅本地加入，未发布这些文件。
