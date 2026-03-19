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

## 4.1 已修复漏洞说明

下面整理了这次已经修复的两个关键问题，方便你直接在自述文件里核对。

### 漏洞一：`get_current_user_optional` 定义顺序错误，导致后端无法启动

- **位置**：`backend/app/main.py`
- **问题类型**：高危可用性缺陷 / 启动阻断问题
- **触发原因**：
  - `read_content()` 和 `list_content()` 在声明路由时，使用了 `Depends(get_current_user_optional)`。
  - 但旧版本里，`get_current_user_optional` 函数写在文件更靠后的位置。
  - Python 在创建路由函数时会立即解析这个默认依赖，因此在函数还没有定义时就引用它，会直接触发 `NameError`。
- **实际影响**：
  - `backend/app/main.py` 导入失败。
  - `uvicorn app.main:app` 无法启动。
  - 不管是开发环境、测试环境还是生产环境，只要加载这个模块，API 都会直接报错。
- **风险等级**：**Critical / P0**
- **修复方式**：
  - 将 `get_current_user_optional` 提前到内容路由之前定义。
  - 这样 `/content` 与 `/content/{slug}` 绑定 `Depends(...)` 时，目标函数已经存在。
- **修复结果**：
  - 模块可以正常导入。
  - Uvicorn/FastAPI 可以正常完成应用启动。

### 漏洞二：订阅鉴权未校验 `start_date` / `end_date`，可提前或超期访问付费内容

- **位置**：`backend/app/services.py`
- **问题类型**：高危权限绕过 / 订阅有效期校验缺失
- **旧逻辑问题**：
  - 旧版本只判断 `subscription.status` 是否为 `ACTIVE` 或 `TRIAL`。
  - `user_has_paid_access()` 与 `can_read_content()` 都没有校验订阅时间窗口。
  - 代码中也没有其他地方根据 `start_date` / `end_date` 自动回写状态，因此仅靠 `status` 无法保证权限准确。
- **可能造成的错误授权**：
  1. **未来生效的订阅被提前放行**  
     如果某个订阅状态已经被写成 `ACTIVE`，但 `start_date` 还没到，用户仍然会立即获得订阅内容访问权限。
  2. **已经过期的订阅继续放行**  
     如果订阅已经超过 `end_date`，但状态字段仍然保留为 `ACTIVE`，用户依旧可以继续读取订阅内容或高级内容。
- **实际影响**：
  - `subscriber` 可见内容可能被未到期用户提前访问。
  - `premium` 高级内容可能被已经过期的用户继续访问。
  - 这会造成付费内容权限失真，影响订阅计费与内容保护。
- **风险等级**：**High / P1**
- **修复方式**：
  - 新增 `subscription_is_current(subscription, today=None)` 统一判断订阅是否真正有效。
  - 该函数同时要求：
    - `status` 属于 `ACTIVE` 或 `TRIAL`
    - 并且满足 `start_date <= today <= end_date`
  - 然后让：
    - `user_has_paid_access()` 使用这个统一判断；
    - `can_read_content()` 在 `subscriber` 和 `premium` 分支里都使用这个统一判断。
- **修复结果**：
  - 未来订阅不会提前解锁内容。
  - 已过期订阅不会继续保留访问权限。
  - 订阅内容与高级内容的权限判断逻辑保持一致。

### 建议你重点核对的地方

如果后面继续扩展支付、续费、自动取消、定时任务等功能，建议持续遵守以下原则：

- **不要只依赖状态字段做权限判断**，状态字段可能滞后或被人工改错。
- **权限放行时要同时核验时间窗口**，尤其是订阅类业务。
- **鉴权辅助函数要尽量集中复用**，避免多个接口各自写一套逻辑后出现行为不一致。
- **新增路由依赖时要注意定义顺序**，避免再次出现模块导入时的 `NameError`。

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
