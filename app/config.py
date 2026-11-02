from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Algorithm = Literal["token_bucket", "sliding_log", "sliding_counter"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RATEGATE_", env_file=".env")

    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50  # connections shared by all requests
    redis_pool_timeout: float = 5.0  # seconds to wait for a free connection
    algorithm: Algorithm = "token_bucket"

    # Token bucket
    capacity: int = 10  # max tokens in a bucket (burst size)
    refill_rate: float = 1.0  # tokens added per second

    # Sliding window log and sliding window counter
    limit: int = 10  # max requests per window
    window_seconds: float = 10.0  # window length


settings = Settings()
