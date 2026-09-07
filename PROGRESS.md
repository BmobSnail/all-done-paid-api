# All-Done Paid API - PROGRESS

> 📌 历史快照文档，按 all-done 命名更新标题；过程记录保留原貌。

> Subagent 接续工作的状态文件。

## 当前阶段
**MVP 完成 ✅ — 等待人工执行 DNS / SSL / 部署 + smoke 验收**

## 已完成
- 2026-04-22 **Day 1 (A1.1~A1.4)** FastAPI 骨架 / Dockerfile / docker-compose / healthz/readyz
- 2026-04-22 **Day 2 (A2.1~A2.5)** 6 张 paid_* 表 / API Key + HMAC pepper / 鉴权 / 错误响应 / seed
- 2026-04-22 **Day 3 (A3.1~A3.3)** 4 维度 Lua 限流 / Idempotency-Key / billing 状态机+重算
- 2026-04-22 **Day 4 (A4.1~A4.4)** LLM 适配层
- 2026-04-22 **Day 5 (A5.1~A5.4) 业务接口**：cast / interpret(SSE) / 篡改防护 / cast 缓存
- 2026-04-22 **Day 6 (A6.1~A6.3) 测试 + CI**：unit 28/28 + integration 4 / .github/workflows/ci.yml
- 2026-04-23 **Day 7 (A7.1~A7.3) 部署 + 文档**：
  - A7.1 deploy/nginx.api-paid-test.conf（geo 白名单 + SSE 禁缓冲）+ deploy/deploy.sh（打包 → SCP → docker compose up → healthz 烟测）
  - A7.2 scripts/export_openapi.py（含 pydantic_ai stub 兜底）→ docs/openapi.json + docs/index.html(Scalar)
  - A7.3 tests/smoke/locustfile.py（cast 高频 + interpret SSE 真消费）+ tests/smoke/README.md（含上线 checklist）

## 验证
- `pytest tests/unit -q` 28/28 通过
- `python -m scripts.export_openapi` → 4 paths 导出成功
- `py_compile` locustfile / export_openapi / deploy 全通过

## 待人工执行
1. DNS A 记录 api-paid-test.all-done.cn → 服务器 IP
2. `sudo certbot --nginx -d api-paid-test.all-done.cn -m ops@all-done.cn -n --agree-tos`
3. 上传 `deploy/nginx.api-paid-test.conf` → `/etc/nginx/conf.d/`，补白名单 IP，`nginx -t && systemctl reload nginx`
4. 准备 `.env.production`（参考 `.env.example`）
5. 执行 `bash deploy/deploy.sh`
6. `python -m scripts.seed` 生成 admin key（一次性记录）
7. 跑 `tests/smoke/locustfile.py` 验收 P95 / 错误率
8. `docs/` 静态托管（GitHub Pages 或同域 /docs/）

## 关联
- Plan: ../../docs/plans/paid-api-bootstrap-plan.md
- GitHub Project: https://github.com/users/BmobSnail/projects/8
- 当前会话: 2026-04-22
