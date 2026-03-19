# Python 远程数据库与安全订阅后端

这个目录新增了一个基于 **FastAPI + PostgreSQL** 的后端样板，目标是满足：

- 数据库部署在另一台服务器。
- 配置项尽量集中，方便上线与迁移。
- 网站账号、订阅、付费内容访问都能走统一 API。
- 订阅内容在数据库中加密存储，降低数据库泄露时的明文风险。
- 默认启用常见安全基线：HTTPS 跳转、Trusted Hosts、严格 CORS、安全响应头、登录限流、审计日志。

## 目录说明

- `main.py`：FastAPI 入口，包含认证、订阅、内容接口。
- `config.py`：集中式环境变量配置。
- `database.py`：SQLAlchemy 连接与会话。
- `models.py`：用户、套餐、订阅、加密内容、审计日志数据模型。
- `security.py`：密码哈希、JWT、Fernet 内容加密。
- `init_db.py`：初始化表结构并注入默认套餐。
- `.env.example`：远程数据库和安全参数配置模板。
- `requirements.txt`：依赖列表。

## 推荐部署结构

```text
[前端静态站 / CDN]
        |
        v
[反向代理 Nginx / Caddy + TLS]
        |
        v
[FastAPI 应用服务器]
        |
        | 私网 / 防火墙白名单 / TLS
        v
[PostgreSQL 数据库服务器]
```

### 远程数据库建议

1. **数据库单独部署在内网或受防火墙保护的服务器**，不要直接向公网开放 5432。
2. 只允许 FastAPI 服务器 IP 访问数据库端口。
3. 为业务创建单独数据库账号，例如 `v2free_app`，不要使用超级管理员账户。
4. 开启数据库备份与 WAL/快照，确保订阅数据可恢复。
5. 使用强密码并定期轮换，生产环境推荐再叠加 TLS 连接。

## 快速开始

### 1. 安装依赖

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 复制配置

```bash
cp .env.example .env
```

重点修改：

- `DATABASE_URL`：改成你的远程 PostgreSQL 地址。
- `JWT_SECRET_KEY`：改成高强度随机密钥。
- `CONTENT_ENCRYPTION_KEY`：必须改成你自己的 Fernet 密钥。
- `TRUSTED_HOSTS` / `CORS_ORIGINS`：换成你的正式域名。
- `ADMIN_BOOTSTRAP_EMAIL`：设置第一个后台管理员邮箱。

生成 Fernet 密钥：

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. 初始化数据库

```bash
python3 init_db.py
```

### 4. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 已提供的 API 能力

- 用户注册：`POST /api/v1/auth/register`
- 用户登录：`POST /api/v1/auth/token`
- 当前用户信息：`GET /api/v1/users/me`
- 套餐列表：`GET /api/v1/plans`
- 创建套餐（管理员）：`POST /api/v1/plans`
- 创建订阅：`POST /api/v1/subscriptions`
- 我的订阅：`GET /api/v1/subscriptions/me`
- 发布加密订阅内容（管理员）：`POST /api/v1/content`
- 订阅内容列表：`GET /api/v1/content`
- 阅读解密后的订阅内容：`GET /api/v1/content/{slug}`
- 健康检查：`GET /health`

## 安全设计说明

### 1. 账号安全

- 密码使用 `PBKDF2-HMAC-SHA256` 哈希，不保存明文。
- 登录接口带简单限流，降低暴力破解风险。
- JWT 只保存必要身份信息。

### 2. 内容安全

- 订阅正文通过 **Fernet** 对称加密后再写入数据库。
- 即使数据库表被导出，攻击者也无法直接读出订阅明文。
- 读取接口会再次校验是否具备有效订阅。

### 3. 传输与来源控制

- 可启用 HTTP->HTTPS 重定向。
- Trusted Hosts 限制 Host 头。
- CORS 只允许白名单域名。
- 安全响应头减少点击劫持、MIME 嗅探和非法嵌入风险。

### 4. 审计能力

- 登录成功/失败、注册、订阅开通、内容读取都会记录到 `access_audits`。
- 后续可以继续接入 SIEM、告警系统或 WAF 日志联动。

## 生产环境还建议你继续补充

- 使用 Redis 做分布式限流，替换当前进程内限流。
- 增加短信/邮箱验证码与 MFA。
- 接入支付回调与订单表。
- 为后台管理接口增加 IP 白名单和单点登录。
- 使用 Alembic 管理数据库迁移。
- 把密钥改存到 Vault / AWS Secrets Manager / 1Password Secrets Automation。
