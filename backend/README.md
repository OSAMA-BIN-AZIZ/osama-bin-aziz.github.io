# V2free Python 安全后台

这个目录新增了一个可独立部署的 Python API 服务，用于把当前静态网站升级成“前台静态页面 + 远程数据库 + 安全订阅内容”的架构。

## 适合你的需求

- **远程数据库**：默认面向 PostgreSQL，`DATABASE_URL` 直接填写另一台服务器上的数据库地址即可。
- **配置方便**：所有关键参数都放在 `.env` 里，复制 `backend/.env.example` 就能开始。
- **网站功能更全**：包含注册、登录、套餐管理、订阅开通、内容发布、审计日志等基础能力。
- **订阅内容更安全**：付费内容在数据库中以加密密文保存，读取时再解密。
- **后台更安全**：密码使用 PBKDF2 哈希；接口使用 JWT 鉴权；管理员操作写入审计日志。

## 建议部署结构

1. **前台站点服务器**：继续托管当前静态页面，例如 Nginx / GitHub Pages / CDN。
2. **Python API 服务器**：部署 `FastAPI` 服务，只开放 HTTPS 入口。
3. **数据库服务器**：单独部署 PostgreSQL，只允许 API 服务器的 IP 访问 5432。
4. **反向代理**：在 API 服务器前面放 Nginx / Caddy，统一做 TLS、限流和安全头。

## 快速启动

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## 需要设置的关键环境变量

- `DATABASE_URL`：例如 `postgresql+psycopg://v2free_app:strong-password@10.0.0.20:5432/v2free`
- `JWT_SECRET`：至少 64 位随机字符串。
- `FERNET_SECRET`：使用 `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` 生成。
- `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD`：首次启动时自动初始化管理员。
- `CORS_ORIGINS`：填写允许访问 API 的前台域名和后台域名。

## 核心接口

- `GET /health`：检查服务和远程数据库连接状态。
- `POST /api/auth/register`：注册用户。
- `POST /api/auth/login`：登录并获取 JWT。
- `GET /api/me`：查看当前用户。
- `GET /api/me/subscriptions`：查看当前账号订阅。
- `GET /api/content`：内容列表。
- `GET /api/content/{slug}`：读取内容，订阅内容会进行权限校验。
- `POST /api/admin/plans`：管理员创建套餐。
- `POST /api/admin/subscriptions`：管理员为用户开通订阅。
- `POST /api/admin/content`：管理员发布内容，正文自动加密。
- `GET /api/admin/audits`：查看关键操作审计日志。

## 安全加固建议

- 数据库服务器不要暴露公网，至少通过安全组 / 防火墙限制来源 IP。
- API 服务器必须启用 HTTPS，并开启限流、WAF、`X-Frame-Options`、`Content-Security-Policy` 等安全头。
- 建议再增加短信/邮箱二次验证、登录失败阈值封禁和管理员单独的 VPN 入口。
- 若订阅内容非常敏感，建议把对象存储、数据库备份和日志都做独立加密。

## 前端如何接入

当前仓库里的 `admin.html` 还是静态演示页；后续只要把表单和表格数据源切到这些 API，就能逐步演进成真正可用的后台。
