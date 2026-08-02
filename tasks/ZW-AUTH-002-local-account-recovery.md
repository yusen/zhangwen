# ZW-AUTH-002 云认证未配置时的本机账号恢复

状态：已完成（2026-07-28）

## 问题

当前开发桌面只显示邮箱登录，但 Sidecar 未配置 `ZHANGWEN_CLOUD_AUTH_BASE_URL`。旧本机账号
仍保存在认证库中，用户点击登录或忘记密码只会得到 `CLOUD_AUTH_NOT_CONFIGURED`，无法访问
原账号绑定的本机项目。

已只读确认存在一个本机主账号（账号和显示名称已脱敏）、`auth_kind=local`。原密码只保存派生值，
不能查看或还原。

## 目标

1. 云认证未配置且存在旧本机账号时，登录页自动显示本机账号登录，而不是不可用的邮箱表单。
2. 云认证已配置时保持现有邮箱注册、验证、登录、找回密码和画像流程。
3. 提供仅限本机维护的密码重置工具：密码隐藏输入、不进入命令行或日志；修改前备份认证库；
   只允许重置 `auth_kind=local` 的活动账号；成功后撤销该账号全部旧会话。
4. 不删除、重建或重新归属项目，不启用 `ZHANGWEN_AUTH_DISABLED`，不改变设备/CAD 安全边界。

## 方案

- `GET /api/auth/status` 增加 `cloudAuthConfigured` 与 `hasLocalAccounts`。
- `AuthGate` 根据状态选择邮箱登录或本机登录；本机登录复用既有 `/api/auth/login`。
- `AuthRepository.reset_local_password()` 在单一 SQLite 事务中更新随机盐密码派生值并删除旧会话。
- 根目录 `reset-local-password.bat` 调用 `scripts-dev/reset-local-account-password.py`。工具先列出
  本机账号、要求精确确认短语，再通过 `getpass` 两次隐藏输入密码并建立带时间戳备份。

## 验收

- [x] 云认证未配置 + 本机账号存在时自动显示“本机账号登录”。
- [x] 正确本机密码可以进入原账号，错误密码仍返回统一错误。
- [x] 云认证已配置时邮箱流程保持不变。
- [x] 重置只接受本机活动账号，密码规则与注册一致，旧会话全部失效。
- [x] 重置前产生可恢复数据库备份，命令行、输出和日志不包含密码。
- [x] contracts、前端认证测试、后端认证测试、strict TypeScript 和 production build 通过。

## 安全边界

- 不读取或回显密码 hash、盐、refresh token 或 session token。
- 不接受 `--password` 参数；新密码只能在本机交互终端隐藏输入。
- 不重置云账号，不删除认证库，不开启认证绕过。
- 不执行真实 Provider、串口、上传、复位、Flash、安装或发布。

## Decision Log

- 2026-07-28：不把 `CLOUD_AUTH_NOT_CONFIGURED` 当作密码错误；优先恢复已有本机账号入口。
- 2026-07-28：不直接写一个临时明文密码。使用本机隐藏输入工具，避免密码进入聊天、进程参数或日志。
- 2026-07-28：重置密码同时撤销旧会话，防止遗失 token 在新密码生效后继续访问。
- 2026-07-28：旧短会话失效时仍保留刚读取到的云认证/本机账号能力，不能再次退回不可用的邮箱入口。
