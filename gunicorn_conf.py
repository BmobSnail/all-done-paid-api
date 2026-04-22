"""gunicorn 配置：生产部署用 gunicorn -k uvicorn.workers.UvicornWorker -c gunicorn_conf.py"""
import os

bind = f"{os.getenv('PAID_WEB_HOST', '0.0.0.0')}:{os.getenv('PAID_WEB_PORT', '8001')}"
workers = int(os.getenv("PAID_WEB_CONCURRENCY", "4"))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = int(os.getenv("PAID_GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("PAID_GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("PAID_LOG_LEVEL", "info").lower()

forwarded_allow_ips = "*"
proxy_allow_ips = "*"
