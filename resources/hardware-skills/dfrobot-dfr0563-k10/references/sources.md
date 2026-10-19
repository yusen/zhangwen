# 资料来源

| sourceId | 类型 | URL/标识 | 支持的事实 | 核对状态 |
|---|---|---|---|---|
| vendor-board:k10-compatibility | UNIHIKER 官方兼容列表 | https://www.unihiker.com.cn/wiki/k10/compatibility2 | K10/Mind+ 兼容清单中的 SKU、类别与接口方向 | 已定位 |
| vendor-product:dfr0563 | DFRobot Wiki/官方产品资料 | https://wiki.dfrobot.com.cn/_SKU_DFR0563__Gravity__3.7V_Li_Battery_Fuel_Gauge_3.7V%E9%94%82%E7%94%B5%E6%B1%A0%E7%94%B5%E9%87%8F%E8%AE%A1 | 产品身份、接口和电气参数入口 | 是（页面已定位，关键参数仍待逐项人工复核） |
| official:k10-unihiker-k10 | 行空板 K10 官方代码模式库 | https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10 | unihiker_k10 模块、固件及已公开外部硬件 API | 已核对 |

## 证据边界

- 搜索摘要不作为独立官方证据；机器字段采用保守接入基线，详细额定值应回到上表页面复核。
- K10 兼容页写作 DFR0063；DFRobot 官方 Wiki 显示 DFR0063 实为 LCD1602，电量计正确 SKU 为 DFR0563。
