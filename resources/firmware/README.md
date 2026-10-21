# 默认官方固件

manifest.json固定来源、大小、SHA-256、写入偏移与版本，运行期间只从本地读取，不自动下载或追踪预览版。2026-10-21 按用户最新指定将 K10 默认固件切回 Mind+ 设备包中的 V0.9.8；其他镜像沿用 2026-10-18 的核对记录。

| 主控 | 默认镜像 | 依据 |
|---|---|---|
| 掌控板2.0 | mPython v2.6.0 | labplus-cn/mpython最新非预发行Release；原厂合并包含0x1000填充，从0写入 |
| 掌控板3.0 | 官方在线平台当前默认包 | online.mpython.cn的FirmwareModal默认mpython_v3.bin；实际CDN地址在manifest，Last-Modified 2026-07-01，内嵌MicroPython v1.26.1-1.g7f275c0a5 on 2026-06-05；厂商未公开发行版本号，不称为上游MicroPython最新版本 |
| 行空板K10 | Mind+ K10 MicroPython V0.9.8 | 用户指定的 dev-DFRobot-unihikerK10@0.0.5 包内 micropython_unihiker_k10_V0.9.8.bin；完整16MiB，保持原始字节，不表示是上游最新版 |
| XIAO ESP32S3 Sense | MicroPython v1.29.0 | SEEED_XIAO_ESP32S3板级稳定版，未承诺Sense摄像头支持 |
| 通用ESP32-C3 | MicroPython v1.29.0 | ESP32_GENERIC_C3稳定版，至少4MiB Flash |

所有本地镜像偏移均为0。浏览器写前核对镜像大小、SHA-256、芯片与容量，保持原串口互斥，直接覆盖镜像所在扇区；不备份、不做 Flash 回读或写后摘要校验、不做整片擦除。写入完成与重启后的 MicroPython、文件系统及板载功能验收分别记录，不能将写入完成视作实物功能通过。普通 main.py 上传的备份和回读校验保持原流程。

MicroPython与掌控2.0许可证原文分别见MICROPYTHON-LICENSE.txt、MPYTHON-LICENSE.txt和MPYTHON3-LICENSE.txt。厂商板级固件包含其自有驱动/资源，保留原版权，不把MicroPython的MIT授权扩展为全部第三方资源授权。K10 V0.9.8 镜像从用户指定的本机 Mind+ 设备包原样复制，权利属于DFRobot及其上游，来源包、原文件名、大小与摘要见manifest；没有为它猜测在线下载地址，也未提交发布。此文件与此前 Google Drive 来源的 16,498,431 字节镜像不同，以本次用户指定的 16,777,216 字节及 SHA-256 为准。
