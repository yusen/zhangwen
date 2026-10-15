# 仓库替换与一键部署计划

2026-10-15 用户授权将掌问 V4 替换到 yusen/zhangwen，并支持其他电脑简便部署。

- [x] 检查远程权限、旧 main 和 DeepSeek Harness 实际启动方式。
- [x] 增加 Windows 项目内 Node/Python 一键准备、缓存安装/构建/启动。
- [x] 将 74 包/817 文件硬件离线快照作为随包资源，经原加载器初始化；保留已有用户包。
- [x] 在不含本机数据/依赖/imports 的干净目录实际部署和启动验证。
- [x] 回归构建、26API/13协议/14浏览器；原 471 文件及817硬件资源摘要验证。
- [x] 排除数据/Key/设备备份，保留第三方来源声明；更新交接和验证。
- [x] 本地 bundle 与远程恢复标签保留旧 main，再以普通后继提交替换 main。
- [x] 回读远程提交与1444文件树一致，README下载/双击步骤已在远程可见。

不 force push，不改变仓库私有属性，不发布 npm，不访问生产旧库、真实模型或硬件。

初始发布提交a5d200dff106e4e18cf994a85c11ef7e2f257823，父提交为原main 7e0b34e。Git传输多次重置/超时后，改用GitHub官方Git Data API：二进制blob和每个子树/根树逐一SHA匹配，普通新提交以force=false更新main，再回读完整远程树。Windows隔离目录安装已通过；第二台实体电脑/macOS/Linux未实测，GitHub Actions独立于本地验证。
