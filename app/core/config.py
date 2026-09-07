"""应用配置：pydantic-settings 加载 .env"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # 应用基础
    PAID_APP_NAME: str = "all-done-paid-api"
    PAID_APP_ENV: str = "development"
    PAID_LOG_LEVEL: str = "INFO"

    # Web
    PAID_WEB_HOST: str = "0.0.0.0"
    PAID_WEB_PORT: int = 8001
    PAID_WEB_CONCURRENCY: int = 4

    # Database
    PAID_DB_URL: str = "postgresql+asyncpg://omniknight:omniknight_dev@localhost:5433/omniknight"  # 历史遗留：PG 库名/用户名保持 omniknight（数据层不迁移，命名规范 v3.0 §4）
    PAID_DB_POOL_SIZE: int = 20
    PAID_DB_MAX_OVERFLOW: int = 10
    PAID_DB_POOL_TIMEOUT: int = 30

    # Redis
    PAID_REDIS_URL: str = "redis://localhost:6380/0"
    PAID_REDIS_MAX_CONNECTIONS: int = 50

    # API Key
    PAID_API_KEY_PEPPER: str = Field(default="dev_pepper_change_me_in_prod", min_length=16)
    PAID_API_KEY_PREFIX: str = "sk_live_"

    # Rate Limit
    PAID_DEFAULT_QPS_LIMIT: int = 10
    PAID_DEFAULT_CONCURRENCY_LIMIT: int = 20
    PAID_RATE_LIMIT_REDIS_PREFIX: str = "paid:rl"

    # Idempotency
    PAID_IDEMPOTENCY_TTL_SECONDS: int = 86400

    # LLM
    PAID_LLM_PROVIDER: str = "siliconflow"
    PAID_LLM_BASE_URL: str = "https://api.siliconflow.cn/v1"
    PAID_LLM_API_KEYS: str = ""
    PAID_LLM_MODEL_PRIMARY: str = "deepseek-ai/DeepSeek-V3.1-Terminus"
    PAID_LLM_MODEL_FALLBACK: str = "deepseek-ai/DeepSeek-V3.2-Exp"
    PAID_LLM_MODEL_CHEAP: str = "Qwen/Qwen3-8B"
    PAID_LLM_TIMEOUT_SECONDS: int = 60
    PAID_LLM_MAX_RETRIES: int = 3
    PAID_LLM_MAX_CONCURRENCY: int = 20
    PAID_LLM_STREAM_TIMEOUT_SECONDS: int = 120

    # Logfire
    PAID_LOGFIRE_ENABLED: bool = False
    PAID_LOGFIRE_TOKEN: str = ""
    PAID_LOGFIRE_ENV: str = "development"
    PAID_LOGFIRE_SERVICE_NAME: str = "all-done-paid-api"
    PAID_LOGFIRE_SCRUB_FIELDS: str = "Authorization,X-API-Key,Cookie,phone,email,id_card"

    # Cache
    PAID_MEIHUA_CAST_CACHE_TTL_SECONDS: int = 86400
    PAID_PROMPT_VERSION: str = "v1"

    # Internal
    PAID_INTERNAL_BYPASS_ENABLED: bool = False
    PAID_CORS_ALLOW_ORIGINS: str = ""

    @property
    def llm_api_keys_list(self) -> list[str]:
        return [k.strip() for k in self.PAID_LLM_API_KEYS.split(",") if k.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.PAID_CORS_ALLOW_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.PAID_APP_ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
