# Omniknight Paid API - PROGRESS

> Subagent 接续工作的状态文件。

## 当前阶段
**Day 4 - LLM 适配层（A4.1 ~ A4.4）**

## 已完成
- 2026-04-22 **Day 1 (A1.1~A1.4)** FastAPI 骨架 / Dockerfile / docker-compose / healthz/readyz
- 2026-04-22 **Day 2 (A2.1~A2.5)** 6 张 paid_* 表 / API Key + HMAC pepper / 鉴权 / 错误响应 / seed
- 2026-04-22 **Day 3 (A3.1~A3.3)**:
  - A3.1 Redis 令牌桶限流，4 维度（QPS / 分钟 burst / 日 quota / 并发）+ Lua 原子
  - A3.2 Idempotency-Key 幂等：Redis 短期 + PG 长期 + 冲突检测 + 占位 reserve
  - A3.3 billing 状态机（pending→committed/failed→reversed）+ 异步聚合 paid_usage_hourly + 重算脚本

## 验证
- `pytest tests/unit -q` 4/4 通过
- `python -c "from app.services import billing, idempotency, rate_limit"` ok
- 重算脚本 `python -m scripts.recompute_usage --since ... --until ...` 可运行

## 待办（Day 4）
- A4.1 omniknight/infra/llm/ 模块骨架（provider/siliconflow/agents/result_types/client）
- A4.2 Pydantic AI ==0.8.1 + MeihuaInterpret result_type
- A4.3 Logfire 接入 + 脱敏 scrubber + 可关停开关
- A4.4 重试 + 超时 + circuit breaker + fallback

## 关联
- Plan: ../../docs/plans/paid-api-bootstrap-plan.md
- GitHub Project: https://github.com/users/BmobSnail/projects/8
- 当前会话: 2026-04-22
