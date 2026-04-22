# Omniknight Paid API - PROGRESS

> Subagent 接续工作的状态文件。

## 当前阶段
**Day 3 - 限流 + 幂等 + 计费（A3.1 ~ A3.3）**

## 已完成
- 2026-04-22 仓库初始化 + 基础文件
- 2026-04-22 em-develop 分支
- 2026-04-22 **Day 1 全部 (A1.1~A1.4)**：FastAPI 骨架 + Dockerfile + docker-compose + healthz/readyz
- 2026-04-22 **Day 2 全部 (A2.1~A2.5)**：
  - A2.1 ORM 模型 + Alembic init + 6 张 paid_* 表 migration
  - A2.2 API Key sk_live_<kid>_<secret> + HMAC-SHA256+pepper（含单测 4 例全过）
  - A2.3 鉴权服务 + Depends(require_api_key)，Redis 缓存校验
  - A2.4 统一错误响应 schema + ApiError 体系 + request_id 中间件
  - A2.5 seed 脚本（生产拒绝执行）

## 验证
- `pytest tests/unit/test_security.py` 4/4 通过
- `python -c "from app.main import app"` ok
- 6 张表注册到 Base.metadata：paid_api_keys / paid_api_key_audit_logs / paid_api_key_rollovers / paid_billing_events / paid_idempotency_keys / paid_usage_hourly

## 待办（Day 3）
- A3.1 Redis 令牌桶限流 (QPS + burst + quota + 并发 4 维度)
- A3.2 Idempotency-Key 幂等机制
- A3.3 billing_events 状态机 + 异步聚合到 paid_usage

## 关联
- Plan: ../../docs/plans/paid-api-bootstrap-plan.md
- GitHub Project: https://github.com/users/BmobSnail/projects/8
- 当前会话: 2026-04-22
