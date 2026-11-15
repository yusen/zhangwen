# Mosaico 与 micro:bit 实物配图

2026-11-15，按用户要求为掌问补充两张官方实物照片。ESP-Mosaico 使用官方 V1.2 硬件指南中的整机斜视照片；BBC micro:bit 从官网 V2 正反面合照中裁出正面，保留整块板和接口。只裁切、等比缩小及转换 WebP，不重绘产品细节。选择卡分别标明“V1.2 实物图”和“V2 实物图”，micro:bit 原有 V1 / V2 支持范围不变。

图片复用 `apps/web/src/boardImages.ts` 和 `BoardArtwork` 的离线配图机制，覆盖主控选择、项目器件、主控切换及空对话提示。原硬件包照片仍优先，失败时继续使用本地配图及带名称的示意图；没有新增硬件事实库，也没有修改用户安装的 Hardware Skill、机械档案或项目记录。

原图链接、来源页面、署名、原图与转换图 SHA256、裁切坐标和尺寸记录在 `apps/web/src/assets/boards/sources.json`。Mosaico 成品为 584×640，micro:bit 成品为 640×534；素材权利声明见 `THIRD_PARTY_NOTICES.md`。两张图随前端构建离线提供，运行时无需访问厂商网站。

TypeScript strict 与 Vite 构建通过，保留原有包大小提示。1440 像素桌面及 390 像素手机的主控选择截图已核对，图片完整、型号说明可见。本机 30801 的页面与构建产物一致，两张图片实际返回字节均与构建文件相同。浏览器与最终发布验证记录保存在本机 `.runtime/board-photos-20261115/` 和 `.runtime/gitee-sync-20261115-photos/`，最终状态另见同名 VALIDATION.json。

本轮仅更新显示资源；生产项目没有写入，服务没有重启，没有调用模型或操作真实设备。本机完整 Idea 开发保留，Gitee 按默认无 Idea 的部署清单导出。
