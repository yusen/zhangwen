# 资料来源与适用范围

## 主要来源

1. K10 MicroPython `unihiker_k10` 代码模式  
   https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10

2. K10 硬件和参数  
   https://www.unihiker.com.cn/wiki/k10/jianjie

3. K10 常见问题  
   https://www.unihiker.com.cn/wiki/k10/FAQ

整理日期：2026-07-12。

## 页面观察到的固件信息

官方代码模式页面在整理时提供的固件压缩包名称为：

```text
micropython_unihiker_k10&Box_20260430_V0.9.8.zip
```

官方同时说明该 MicroPython 固件处于测试阶段，可能存在 Bug。

## 本包的验证级别

- **D：官方直接明确**  
  官方页面有明确导入、方法和参数示例。

- **C：官方明确，但组合使用需验证**  
  单项 API 明确，多个高负载功能组合需上板确认内存和时序。

- **B：官方示例存在缺口**  
  API 名称出现，但对象创建、返回结构或边界条件不完整。

- **A：已在指定固件上板验证**  
  只有实际测试后才能使用。初版包没有 A 级项目。

本包初版最多标记到 D/C/B，不声称已经上板验证。
