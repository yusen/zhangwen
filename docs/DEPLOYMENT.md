# 本地 Web 部署与更新

## 新电脑：下载、解压、双击

Windows 10/11 x64：从 https://github.com/yusen/zhangwen 下载完整 ZIP 并解压，双击根目录 `start-web.bat`。首次联网准备环境后自动打开 http://127.0.0.1:3080。后续双击复用缓存；不需要 Git、npm 命令或系统 Python。请放在当前用户有写权限的目录，勿直接在 ZIP 中运行。

仓库目前私有，下载需要授权账号；也可以由仓库所有者分发下载的源码 ZIP。没有发布 npm 包，因此不提供尚不可用的 npx 命令。部署体验参考 DeepSeek Harness 的“本地服务 + 自动打开浏览器”，设备仍由浏览器 Web Serial 持有。

使用桌面版 Chrome/Edge，设备需已安装 MicroPython；串口驱动取决于板卡，启动器不自动修改驱动。首次使用 AI 在网页「API 设置」填写自己的 Key。数据与 Key 均不随仓库分发。

## 启动器做什么

`start-web.bat` 调用本项目的 PowerShell 脚本；ExecutionPolicy Bypass 仅作用于本次进程，不修改系统执行策略。

1. 官方下载 Node 24.14.0、uv 0.8.22，验证脚本内固定 SHA-256 后解压到 `.runtime/`。
2. 通过 uv 准备项目内 Python 3.13.7 与 `.venv/`；已有本项目虚拟环境则保留。
3. 使用 `requirements-web-lock.txt` 和 `package-lock.json` 安装依赖。
4. TypeScript strict 检查并构建页面，启动单一 FastAPI 服务，只绑定 `127.0.0.1`。
5. 全新 `.data/` 使用原 Hardware Skill 加载器安装随包的 74 个原硬件包及新增 2 包。共 76 包，Web 可见 74 包 / 5 款主控 / K10 68 个模块。已有用户包保留，不覆盖。

运行环境、依赖和构建各自缓存；源码变化触发构建，锁文件变化触发安装，失败步骤不会记录成功，可重新启动继续。首次需要 nodejs.org、GitHub、PyPI、registry.npmjs.org；下载失败会在窗口显示具体原因。不静默改国内镜像或系统凭据，不需要管理员权限。

```powershell
# 仅安装和构建，不启动
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap-windows.ps1 -PrepareOnly
# 指定端口或不打开浏览器
.\start-web.bat --port 3082 --no-open
```

Ctrl+C 停止；同目录或端口已有服务时会提示，不会强杀其他程序。改端口会改变浏览器草稿/串口授权的 Origin；已保存项目仍来自相同数据目录。

## 有开发环境时

Node.js 22+、Python 3.11+。进入源码目录执行 `npm run setup`，再 `npm start`；`npm run web` 合并准备与启动。macOS/Linux 走此路径，启动器不自动安装其系统运行环境，当前尚无这两个系统的实机记录。

`npm start -- --no-open` 仅运行已有构建。开发命令与测试见 README。首次启动不用调用模型或连接设备。

## 更新和回退

先 Ctrl+C 停服务，备份完整 `.data/`，再更新代码。Git checkout：`git pull --ff-only`，双击启动会安装变化的依赖并重建。ZIP 用户：解压新版到新目录，先保留旧目录，再将停止状态下的 `.data/` 副本放入新版。不要复制 `.venv/`、`node_modules/` 或 `.runtime/` 到新路径；它们可重新生成。

建议更新前也备份整个旧程序目录。回退旧代码时恢复相配套的数据备份，不让旧代码打开已经迁移过的新数据库。首次部署各电脑互相独立，没有云同步；跨电脑迁移已保存项目需搬运完整 `.data/`。浏览器未保存草稿、串口授权和 IndexedDB 设备备份不会随 `.data/` 搬迁，请先保存/导出。

旧桌面仓库由 Git 历史和 `backup/desktop-before-mu-web-20261015` 标签保留。可在独立目录克隆后切换该标签查看旧资料，勿直接覆盖正在使用的新版目录。旧 V1 用户数据库不在仓库中，新平台不自动读取它。

## 范围

本版仍为本机单用户 MVP，无公网/LAN 服务、桌面壳、固件烧录或多文件部署。原 471 项源码/资产摘要不变，`resources/hardware-skills/` 的 817 文件与离线快照摘要一致。资料可见不等于所有板卡、固件与接线已经实测；掌控 2.0 独立 COM 验收和浏览器 Fake 测试沿用既有记录。
