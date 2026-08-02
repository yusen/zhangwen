# 掌问云端身份服务

独立 FastAPI 服务，只保存邮箱账号、验证挑战、用户画像、refresh/access 会话和审计事件；不保存项目、对话、产物或设备数据。

## 本地 PostgreSQL + Mailpit

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- API：`http://127.0.0.1:8200`
- Mailpit：`http://127.0.0.1:8025`
- PostgreSQL 只由 Compose 内部网络访问。

`.env` 中的 secret、数据库密码和生产 SMTP 凭据不得提交。公开部署、域名切换和生产 SMTP 配置必须保留人工确认点。

## 测试

常规测试使用临时 SQLite 与内存邮件器，不需要外部服务：

```powershell
$env:PYTHONPATH='services/cloud-auth-api'
.venv\Scripts\python.exe -m pytest services/cloud-auth-api/tests -q
```

PostgreSQL + Mailpit 集成测试默认跳过。启动 Compose 后显式设置以下变量再运行：

```powershell
$env:ZHANGWEN_CLOUD_AUTH_INTEGRATION_DATABASE_URL='postgresql://zhangwen:local-development-only@127.0.0.1:5432/zhangwen_auth'
$env:ZHANGWEN_CLOUD_AUTH_INTEGRATION_MAILPIT_URL='http://127.0.0.1:8025'
$env:ZHANGWEN_CLOUD_AUTH_SMTP_HOST='127.0.0.1'
$env:ZHANGWEN_CLOUD_AUTH_SMTP_PORT='1025'
.venv\Scripts\python.exe -m pytest services/cloud-auth-api/tests/test_postgres_mailpit_integration.py -q
```

该测试创建随机 `@example.invalid` 账号、从 Mailpit 读取验证码并完成邮箱验证，用来证明 PostgreSQL DDL、SMTP 传输和认证服务协同工作。不要把变量指向生产数据库或真实收件系统。
