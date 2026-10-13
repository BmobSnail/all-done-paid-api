#!/usr/bin/env bash
# ⚠️ 已废弃（2026-09-03）：本脚本是预发阶段的临时部署路径（目标域名 api-paid-test.all-done.cn 无 DNS 解析）。
# 生产部署按 v3.0 规范路径：compose 项目 all-done-paid + docker-compose.prod.yml
# （容器 all-done-paid，127.0.0.1:8001），对外域名 **pay.all-done.cn**（nginx vhost + certbot 证书）。
# 保留本脚本仅作历史参考，请勿再用它部署。
#
# 历史前置（一次性，由人工执行）：
#   1. DNS A 记录 api-paid-test.all-done.cn → 服务器 IP（未配置）
#   2. ssh omniknight "sudo certbot --nginx -d api-paid-test.all-done.cn --agree-tos -m ops@all-done.cn -n"
#   3. ssh omniknight "sudo mkdir -p /opt/all-done/api-paid && sudo chown ubuntu /opt/all-done/api-paid"
#   4. 把 deploy/nginx.api-paid-test.conf 上传到 /etc/nginx/conf.d/，sudo nginx -t && sudo systemctl reload nginx
#   5. 准备 .env.production（PAID_API_KEY_PEPPER / PAID_LLM_API_KEYS / PAID_DB_URL / PAID_REDIS_URL 等）
#
# 历史逻辑：把代码打包 → SCP → 服务器 docker compose build/up → 烟测 healthz。
set -euo pipefail

REMOTE="${REMOTE_HOST:-omniknight}"  # 历史遗留：服务器登录用户名/ssh 别名 omniknight，不改
REMOTE_DIR="${REMOTE_DIR:-/opt/all-done/api-paid}"
ENV_FILE="${ENV_FILE:-.env.production}"

cd "$(dirname "$0")/.."

if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE，请先填好（拷贝 .env.example 改）。" >&2
  exit 1
fi

TMP_TAR="$(mktemp -t paid-api-XXXXX).tar.gz"
trap 'rm -f "$TMP_TAR"' EXIT

echo "[1/4] 打包源码..."
tar --exclude=.git --exclude=__pycache__ --exclude=.venv --exclude='*.pyc' \
  --exclude=tests/integration --exclude=node_modules \
  -czf "$TMP_TAR" \
  app alembic alembic.ini docker-compose.yml Dockerfile gunicorn_conf.py \
  pyproject.toml requirements.txt scripts deploy

echo "[2/4] 上传到 $REMOTE:$REMOTE_DIR ..."
ssh "$REMOTE" "mkdir -p $REMOTE_DIR"
scp "$TMP_TAR" "$REMOTE:$REMOTE_DIR/release.tar.gz"
scp "$ENV_FILE" "$REMOTE:$REMOTE_DIR/.env"

echo "[3/4] 远端解压 + 构建 + up ..."
ssh "$REMOTE" bash -se <<EOF
set -euo pipefail
cd $REMOTE_DIR
tar -xzf release.tar.gz
rm release.tar.gz
sudo docker compose -f docker-compose.yml up -d --build api
EOF

echo "[4/4] 烟测 healthz ..."
sleep 3
ssh "$REMOTE" "curl -fsS http://127.0.0.1:8001/healthz" && echo " ✅ healthz OK"
ssh "$REMOTE" "curl -fsS http://127.0.0.1:8001/readyz"  && echo " ✅ readyz  OK"

echo "🎉 部署完成：https://api-paid-test.all-done.cn/healthz"
