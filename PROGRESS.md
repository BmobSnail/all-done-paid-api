# Omniknight Paid API - PROGRESS

> Subagent 接续工作的状态文件。

## 当前阶段
**Day 2 - 数据模型 + 鉴权（A2.1 ~ A2.5）**

## 已完成
- 2026-04-22 仓库初始化：README / .gitignore / .env.example / PROGRESS.md
- 2026-04-22 em-develop 分支创建
- 2026-04-22 **A1.1** 仓库基础文件齐全（剩 LICENSE 待补，可后置）
- 2026-04-22 **A1.2** FastAPI 骨架 + gunicorn_conf.py + Dockerfile + docker-compose.yml
- 2026-04-22 **A1.3** pyproject.toml + requirements.txt + requirements-dev.txt（依赖按 plan v3 第 2 节锁版本）
- 2026-04-22 **A1.4** PG (asyncpg) + Redis (async) infra + /healthz + /readyz + lifespan

## 验证
- `python3 -c "from app.main import app"` 通过
- 路由注册正确：/healthz /readyz /docs /openapi.json

## 待办（Day 2）
- A2.1 Alembic 初始化 + 4 张表 migration (paid_*)
- A2.2 API Key sk_live_<kid>_<secret> + HMAC-SHA256+pepper
- A2.3 鉴权中间件 (Bearer + Redis 缓存)
- A2.4 错误响应统一 schema
- A2.5 seed 脚本

## 关联
- Plan: ../../docs/plans/paid-api-bootstrap-plan.md
- GitHub Project: https://github.com/users/BmobSnail/projects/8
- 当前会话: 2026-04-22
