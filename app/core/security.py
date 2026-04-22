"""API Key 安全：sk_live_<kid>_<secret> 格式，HMAC-SHA256+pepper hash，常量时间比较。

参考 plan v3 第 6 节安全设计：
- key 格式：sk_live_<kid>_<secret>
- kid 公开可定位（12 字符 base32）
- secret 256 bit 随机（43 字符 base64url）
- 数据库存 secret_hash = HMAC-SHA256(pepper, secret)，pepper 走环境变量
- 校验用 hmac.compare_digest 防时序攻击
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from app.core.config import get_settings

# 字符集 / 长度规范
_KID_BYTES = 8  # 12 字符 base32
_SECRET_BYTES = 32  # 43 字符 base64url


@dataclass(frozen=True, slots=True)
class GeneratedKey:
    """新生成的完整 Key（仅一次性返回，不可重建）。"""

    full_key: str  # sk_live_<kid>_<secret>，对外只展示这一次
    key_id: str  # 公开标识，可入库索引
    key_prefix: str  # "sk_live_"
    last4: str  # 末尾 4 字符，用于 UI 展示
    secret_hash: str  # HMAC-SHA256 hex，入库


def _b32(n_bytes: int) -> str:
    return base64.b32encode(secrets.token_bytes(n_bytes)).decode().rstrip("=").lower()


def _b64url(n_bytes: int) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(n_bytes)).decode().rstrip("=")


def _hash_secret(secret: str, pepper: str | None = None) -> str:
    p = pepper if pepper is not None else get_settings().PAID_API_KEY_PEPPER
    return hmac.new(p.encode(), secret.encode(), hashlib.sha256).hexdigest()


def generate_key(prefix: str | None = None) -> GeneratedKey:
    """生成新 API Key。返回值仅一次性可见。"""
    s = get_settings()
    key_prefix = prefix or s.PAID_API_KEY_PREFIX
    key_id = _b32(_KID_BYTES)
    secret = _b64url(_SECRET_BYTES)
    full_key = f"{key_prefix}{key_id}_{secret}"
    return GeneratedKey(
        full_key=full_key,
        key_id=key_id,
        key_prefix=key_prefix,
        last4=secret[-4:],
        secret_hash=_hash_secret(secret),
    )


def parse_key(full_key: str) -> tuple[str, str, str] | None:
    """解析 sk_live_<kid>_<secret>，返回 (prefix, key_id, secret)。格式错误返回 None。"""
    s = get_settings()
    if not full_key.startswith(s.PAID_API_KEY_PREFIX):
        return None
    rest = full_key[len(s.PAID_API_KEY_PREFIX) :]
    if "_" not in rest:
        return None
    key_id, _, secret = rest.partition("_")
    if not key_id or not secret:
        return None
    return s.PAID_API_KEY_PREFIX, key_id, secret


def verify_secret(secret: str, secret_hash: str, pepper: str | None = None) -> bool:
    """常量时间比较，防时序攻击。"""
    candidate = _hash_secret(secret, pepper)
    return hmac.compare_digest(candidate, secret_hash)
