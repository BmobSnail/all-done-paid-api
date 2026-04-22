# Omniknight Paid API

> 独立的付费 API 服务（梅花易数等占卜工具的 LLM 解读）
> 含 API Key 鉴权 / 限流 / 计费 / SSE 流式 / 幂等

## 项目背景

本项目从 Omniknight 主仓库的 backend 中独立出来，专门承担**对外付费 API**职责。
原 backend 继续服务前端/小程序内部 API，本项目走独立域名 `api-paid.all-done.cn`。

详见上层 plan：`docs/plans/paid-api-bootstrap-plan.md`（Omniknight 主仓库）

## 技术栈

| 组件 | 版本 | 用途 |
|---|---|---|
| FastAPI | >=0.135,<0.136 | 业务入口 + SSE |
| Pydantic AI | ==0.8.1 | LLM 编排 + 强类型输出 |
| OpenAI SDK | >=2.32,<2.33 | 调 SiliconFlow（OpenAI 兼容） |
| SQLAlchemy | 2.x async | ORM |
| asyncpg | 0.30+ | PG 驱动 |
| redis-py | 6.4+ async | 缓存/限流/幂等 |
| Logfire | >=4.14,<5 | LLM 可观测 |
| gunicorn | 23+ | 生产 WSGI |

## 架构

```
api-paid.all-done.cn
   ↓
Nginx 反代 (8001)
   ↓
FastAPI + gunicorn (多 worker)
   ↓
- PG (共享老库, 新表 paid_*)
- Redis (独立，限流/缓存/幂等)
- SiliconFlow (LLM)
```

## 本地开发

```bash
cp .env.example .env
docker compose up -d           # 起 PG + Redis
pip install -r requirements-dev.txt
alembic upgrade head           # 建表
python scripts/seed.py         # 创建默认 admin key
uvicorn app.main:app --reload  # 启动开发模式
```

## 部署

预发：`api-paid-test.all-done.cn`
生产：`api-paid.all-done.cn`

```bash
bash deploy.sh
```

## 开发约定

- **commit message** 必须使用 `/gitlab-commit-message` skill（见主仓库 CLAUDE.md）
- **依赖版本一律锁定**（避免 0.x 库 breaking change）
- **业务层不直接 import openai/pydantic_ai**，统一走 `app/infra/llm/`
- **新表必须加 `paid_` prefix**，与老库隔离
- **永不动老库的 users/orders 表**（只读）

## 进度跟踪

GitHub Project: https://github.com/users/BmobSnail/projects/8
