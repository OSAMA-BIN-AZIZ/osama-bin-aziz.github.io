# V2free Python 安全后端

这个目录新增了一个可部署在独立服务器上的 Python API，用来支持：

- 远程 PostgreSQL 数据库连接。
- 用户注册、登录、订阅计划、订阅实例管理。
- 订阅内容的访问控制。
- 付费/订阅内容的加密存储（数据库泄漏时仍然更安全）。
- 管理后台可调用的仪表盘接口。

## 1. 远程数据库部署建议

推荐把数据库和 API 分别部署在两台服务器：

- **数据库服务器**：仅开放 PostgreSQL 5432 给 API 服务器的固定 IP。
- **API 服务器**：运行 FastAPI + Uvicorn/Gunicorn，并通过 Nginx/Caddy 暴露 HTTPS。
- **前端服务器**：只调用 API，不保存数据库密码。

`DATABASE_URL` 可以直接配置为远端主机，例如：

```env
DATABASE_URL=postgresql+psycopg://v2free_app:StrongPassword@10.20.30.40:5432/v2free_prod
```

## 2. 环境变量配置

复制示例配置：

```bash
cp backend/.env.example backend/.env
```

必须重点修改：

- `DATABASE_URL`：改成远程数据库地址。
- `JWT_SECRET_KEY`：至少 64 字节随机值。
- `JWT_REFRESH_SECRET_KEY`：独立随机值。
- `DATA_ENCRYPTION_KEY`：Fernet 密钥，用于加密订阅内容正文。
- `ADMIN_BOOTSTRAP_PASSWORD`：首次管理员账号密码。

可用以下命令生成加密密钥：

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

## 3. 安装与启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动时会自动：

- 建表。
- 检查并创建初始管理员账号。

## 4. 安全加固建议

### 数据库安全

- 远程数据库只允许 API 服务器访问。
- PostgreSQL 开启 TLS 和定期备份。
- 使用独立数据库账号，权限限制到单个库。
- 不在前端、静态页面、仓库历史中保存数据库密码。

### API 安全

- 反向代理强制 HTTPS。
- 开启速率限制、登录失败封禁、审计日志。
- JWT 访问令牌有效期默认 15 分钟，降低泄漏风险。
- 管理接口必须使用管理员令牌。

### 订阅内容安全

- 正文以 `Fernet` 加密后再入库。
- 只有通过权限校验的用户才能由 API 解密后返回。
- `premium` 内容要求订阅套餐包含高级内容权限。

## 5. 主要接口

- `GET /health`：健康检查。
- `POST /auth/register`：注册。
- `POST /auth/login`：登录并获取 JWT。
- `GET /users/me`：读取当前用户。
- `GET /plans`：获取套餐列表。
- `POST /plans`：管理员创建套餐。
- `POST /subscriptions`：管理员创建订阅。
- `GET /subscriptions/me`：当前用户的订阅。
- `POST /content`：管理员创建加密内容。
- `GET /content`：当前用户可见内容列表。
- `GET /content/{slug}`：读取单篇内容。
- `GET /admin/dashboard`：管理仪表盘数据。

## 6. 推荐部署结构

```text
Internet
   |
HTTPS
   |
Nginx / Caddy (API server)
   |
FastAPI app
   |
TLS + allow-list
   |
Remote PostgreSQL server
```

如果你需要，我下一步还可以继续补：

- Alembic 数据库迁移。
- Stripe / 支付宝 / 微信支付订阅支付。
- 邮件验证码 / 二次验证（2FA）。
- 管理后台页面与这个 Python API 的联调。
