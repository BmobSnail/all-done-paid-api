# Smoke 压测说明

## 目的
- 上线前快速验证 cast / interpret 在真实部署上能跑通
- 摸 cast 在带缓存场景的稳定吞吐 / interpret 首 token 时延

## 跑法

```bash
pip install locust
export PAID_SMOKE_API_KEY=sk_live_xxxxxxxx   # 来自 scripts/seed.py 输出
locust -f tests/smoke/locustfile.py \
  --host https://pay.all-done.cn \
  -u 20 -r 5 -t 2m \
  --headless --csv=smoke
```

## 验收标准
| 指标 | 期望 |
| --- | --- |
| cast P95 | < 50ms（命中缓存）/ < 150ms（首次） |
| interpret 首 token | < 3s（primary tier，SiliconFlow 正常） |
| 整组失败率 | < 1% |
| Redis 与 PG 连接池峰值 | 不超过 PAID_*_POOL_SIZE 的 80% |

## MVP 上线 review checklist
- [ ] DNS 与 SSL 已生效（curl https://pay.all-done.cn/healthz 200）
- [ ] nginx 反代已生效（pay.all-done.cn → 127.0.0.1:8001；IP 白名单仅预发方案需要，生产开放）
- [ ] `.env.production` 已填 PAID_API_KEY_PEPPER / PAID_LLM_API_KEYS / PAID_DB_URL / PAID_REDIS_URL
- [ ] `python -m scripts.seed` 已生成至少 1 个内部 admin key（输出全 key 一次性记录到密管）
- [ ] cast 缓存已生效（重复请求 cached=true）
- [ ] interpret SSE 收到 partial+done，cast_signature 与请求一致
- [ ] Logfire 控制台能看到 `llm.meihua.interpret*` span（若 PAID_LOGFIRE_ENABLED=true）
- [ ] CI ci.yml 在最新 main 上绿
- [ ] OpenAPI 文档站可访问（docs/index.html 部署到静态托管）
