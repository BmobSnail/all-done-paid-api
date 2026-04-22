# Omniknight Paid API - PROGRESS

> Subagent 接续工作的状态文件。

## 当前阶段
**Day 5 - 业务接口（A5.1 ~ A5.4）**

## 已完成
- 2026-04-22 **Day 1 (A1.1~A1.4)** FastAPI 骨架 / Dockerfile / docker-compose / healthz/readyz
- 2026-04-22 **Day 2 (A2.1~A2.5)** 6 张 paid_* 表 / API Key + HMAC pepper / 鉴权 / 错误响应 / seed
- 2026-04-22 **Day 3 (A3.1~A3.3)** 4 维度 Lua 限流 / Idempotency-Key / billing 状态机+重算
- 2026-04-22 **Day 4 (A4.1~A4.4) LLM 适配层**：
  - A4.1 app/infra/llm/ 骨架：provider / siliconflow / result_types / agents / client / retry / observability
  - A4.2 Pydantic AI ==0.8.1 + MeihuaInterpret/SixGodInterpret 强类型，cast_signature 字段强约束
  - A4.3 Logfire 接入（按开关启停，可关停零副作用，可迁 OTel）
  - A4.4 tenacity 重试 + asyncio.Semaphore 并发 + 简易熔断 + 档位 fallback（primary→fallback→cheap）

## 验证
- `pytest tests/unit -q` 7/7 通过（含 LLM result_types 3 条）
- `python -m py_compile` LLM 全部 8 个文件语法通过
- `python -c "from app.infra.llm import provider, siliconflow, result_types, retry, observability"` 无 pydantic_ai 依赖路径全通
- main.py lifespan 已接 llm_client.init()

## 待办（Day 5）
- A5.1 POST /api/v1/divination/meihua/cast（纯计算）
- A5.2 POST /api/v1/divination/meihua/interpret（SSE 流式 + 鉴权 + 计费）
- A5.3 cast_signature 强约束 + 篡改拒绝集成测试
- A5.4 cast 结果 Redis 缓存

## 关联
- Plan: ../../docs/plans/paid-api-bootstrap-plan.md
- GitHub Project: https://github.com/users/BmobSnail/projects/8
- 当前会话: 2026-04-22
