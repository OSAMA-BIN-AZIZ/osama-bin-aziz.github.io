# 域名发布地址页

当前仓库除了静态页面，还新增了一个可独立部署的 Python 安全后端，位于 `backend/`，用于满足远程数据库、订阅管理与加密内容访问控制需求。

## 新增能力

- 支持将 PostgreSQL 部署到其他服务器，通过 `DATABASE_URL` 直接连接远程数据库。
- 使用 FastAPI + SQLAlchemy 编写 Python 后端。
- 提供用户注册、登录、套餐、订阅、加密内容、管理员仪表盘等接口。
- 订阅正文采用 Fernet 加密后再入库，增强数据库泄漏场景下的安全性。
- 通过 `.env` 即可完成 API、数据库、密钥、管理员账号等配置。

## 快速开始

```bash
cp backend/.env.example backend/.env
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

详细部署与安全建议请查看：`backend/README.md`。

另外，针对最近修复的后端安全/可用性漏洞，已经在 `backend/README.md` 中新增“已修复漏洞说明”章节，方便直接查看漏洞成因、影响范围、修复方式与复现/排查要点。
