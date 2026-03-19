# V2free 安全远程数据库方案

这个仓库现在包含两部分：

1. **现有静态入口页**：用于展示最新网址与后台原型。
2. **新增 Python 后端**：基于 FastAPI + PostgreSQL，支持把数据库单独部署在别的服务器上，并重点强化订阅链接安全。

## 新增能力

- 远程 PostgreSQL 数据库配置，默认强制 SSL。
- 用户注册、登录、套餐查询、订阅创建、订阅链接轮换。
- 管理员统计接口与审计日志表。
- 订阅内容采用短时效签名链接，支持一键失效旧链接。
- 密码使用 PBKDF2-HMAC-SHA256 高迭代哈希，不明文存储。
- 所有关键参数集中放在 `.env`，方便迁移到独立数据库服务器。

## 目录结构

```text
backend/
  config.py      # 安全配置与远程数据库校验
  database.py    # SQLAlchemy 连接池与会话
  main.py        # FastAPI 应用与接口
  models.py      # 用户 / 套餐 / 订阅 / 审计日志
  schemas.py     # 请求响应模型
  security.py    # 密码哈希与签名令牌
.env.example     # 远程数据库部署模板
tests/           # 基础安全测试
```

## 快速开始

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

重点变量：

- `DATABASE_URL`：主库地址，建议单独部署到内网数据库服务器。
- `READ_DATABASE_URL`：可选只读库地址，后续可扩展读写分离。
- `APP_SECRET_KEY`：接口访问令牌签名密钥。
- `SUBSCRIPTION_SIGNING_KEY`：订阅链接签名密钥，必须与主密钥分离。
- `ADMIN_EMAIL`：首次启动时自动创建管理员账号。

### 3. 运行服务

```bash
export $(grep -v '^#' .env | xargs)
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 4. 初始化数据库

应用首次启动会自动建表，并创建默认管理员账号：

- 账号：`ADMIN_EMAIL`
- 初始密码：`ChangeMeNow!123456`

> 首次登录后请立刻修改为高强度密码，并建议通过运维系统注入环境变量，而不是把密钥提交到仓库。

## 推荐部署拓扑

### Web 服务器

- 部署 FastAPI 应用与反向代理（Nginx / Caddy）。
- 只开放 80/443 给公网。
- 后端应用端口仅允许本机或内网访问。

### 数据库服务器

- 单独一台或独立容器，禁止公网直连。
- PostgreSQL 仅允许应用服务器固定 IP 访问。
- 必须启用 TLS / `sslmode=require`。
- 建议开启自动备份、WAL 归档、失败登录告警。

### 订阅内容安全建议

- 订阅链接不要永久固定，当前实现默认 **10 分钟短时效签名**。
- 用户可主动轮换订阅链接，旧链接立刻失效。
- 订阅下发接口只返回当前订阅配置，不暴露数据库结构。
- 将真实节点信息放在订阅生成服务或节点控制面，不直接暴露后台数据库。

## 主要接口

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/me`
- `GET /api/v1/plans`
- `POST /api/v1/subscriptions`
- `GET /api/v1/subscriptions/mine`
- `POST /api/v1/subscriptions/{id}/rotate-link`
- `GET /subscribe/{signed_token}`
- `GET /api/v1/admin/stats`
- `GET /healthz`

## 安全设计说明

### 1. 远程数据库

配置层会校验 `DATABASE_URL` 是否使用 PostgreSQL，并在开启 `REQUIRE_DB_SSL=true` 时自动补齐 `sslmode=require`，避免应用误连明文数据库。

### 2. 密码安全

使用 Python 标准库 `pbkdf2_hmac`，迭代次数设置为 310000，且每个用户独立盐值。

### 3. 访问令牌

接口访问令牌与订阅链接令牌使用 **两套不同密钥**，降低单点泄露风险。

### 4. 审计

注册、登录、创建订阅、轮换订阅链接都会写入 `audit_logs`，方便后续接 SIEM 或告警系统。

## 后续你可以继续扩展

- 接入 Stripe / 支付宝 / 微信支付。
- 增加 MFA、登录限流、验证码。
- 增加节点池、工单系统、邮件通知。
- 将 `READ_DATABASE_URL` 扩展成只读查询链路。
- 把订阅下发结果改造成按用户实时生成 Clash / Sing-box 配置。
