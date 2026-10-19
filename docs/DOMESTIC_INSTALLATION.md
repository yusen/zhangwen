# 国内安装与更新

发布仓库为 https://gitee.com/zmh1979/ask-with-your-palm ，新版是本地 Web 平台。仓库原 Windows 桌面版仍保留在 Git 历史与原标签中；新版不会读取或搬迁旧桌面用户库。

## 一条命令

Windows 10/11 x64 的 PowerShell：

```powershell
irm https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.ps1 | iex
```

macOS 13.5+（Apple Silicon / Intel）：

```bash
curl -fsSL https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.sh | bash
```

这是联网安装器，需要下载固定版本的本地运行依赖。无需 Git 或管理员权限；Windows 需系统自带 tar（Windows 10 1803 起提供）。安装成功后创建桌面/应用入口。服务仅监听 127.0.0.1，浏览器使用桌面 Chrome / Edge。保存项目、上传校验和实际运行结果继续分开显示。

## 下载来源

| 内容 | 下载源 |
| --- | --- |
| 安装脚本、master 提交 SHA、固定提交源码 ZIP | gitee.com（原文件可能跳转 raw.giteeusercontent.com） |
| Node 24.14.0 | cdn.npmmirror.com，固定平台摘要 |
| Python 3.13.7 独立构建 20250918 | cdn.npmmirror.com，官方 SHA256SUMS 中的固定平台摘要 |
| 前端依赖 | registry.npmmirror.com，原锁文件版本及 integrity |
| Python 依赖 | pypi.tuna.tsinghua.edu.cn，原精确平台版本锁 |

三个运行时平台分别为 Windows x64、macOS arm64 与 macOS x64。准备 Python 时直接使用官方独立运行时的镜像，不下载 uv，不请求 GitHub。运行时下载失败或摘要不符会停止，保留原程序入口及用户数据；不会自动切换到其他下载源。镜像同步和网络仍可能失败，错误需按实际安装日志排查，不能保证每个地区始终可达。

先检查已有运行时及依赖，可用则复用；缺失才下载。本轮并未制作完整离线包。AI 模型服务仍需要用户配置的接口及网络，不由 Gitee 提供。

## 下载源与数据

安装器只有一个受信任来源：代码与更新取自本仓库的 Gitee 地址，Node、Python 独立运行时及前端、Python 依赖取自上表固定的国内镜像。没有备用渠道或海外回退，安装器也不接受网页或模型传入的任意下载 URL。早期文档里的 `-Source` / `ZHANGWEN_SOURCE` 开关已移除，照旧复制命令时请去掉这两个参数。

Windows 自定义目录、仅安装：

```powershell
& ([scriptblock]::Create((irm https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.ps1))) -InstallDir 'D:\Apps\掌问平台' -NoStart
```

macOS 自定义目录、仅安装：

```bash
curl -fsSL https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.sh | ZHANGWEN_INSTALL_DIR="$HOME/Apps/掌问平台" ZHANGWEN_NO_START=1 bash
```

从旧版本升级：先保存项目并关闭本地服务，使用原安装目录重新执行安装命令。安装器在新版本准备成功后切换，`data` 保持原位置；不要删除数据、复制旧桌面数据库或连接 V1 生产库。默认目录见 [部署指南](DEPLOYMENT.md)。

依赖源设置仅作用于安装及其子进程，不写全局 npm/pip 配置、不修改系统 PATH、代理、证书或凭据。npm 安装会将锁文件中默认 registry 的下载目标替换为镜像，仍核验 integrity；安装记录仅对两个受信任 registry 的相同包路径视为等价。

## 验证边界

运行时文件摘要校验、隔离安装及更新测试应分别记录。Windows 上的 macOS 下载/脚本检查不等于原生 Mac 安装验收；以实际平台运行结果为准。镜像连通性也不代表真实设备、刷写或模型调用成功。实际发布验证记录保留在开发工作区。
