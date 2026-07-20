from __future__ import annotations

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://drivebook:drivebook@127.0.0.1:5433/drivebook?sslmode=disable",
    )
    # asyncpg wants postgresql:// without +asyncpg
    api_host: str = "127.0.0.1"
    api_port: int = 8100
    brand_name: str = "DriveBook"
    city: str = "Chișinău"
    country: str = "MD"
    deposit_default_cents: int = 10000  # 100 MDL stub
    require_deposit: bool = False

    class Config:
        env_prefix = "DRIVEBOOK_"
        extra = "ignore"


settings = Settings()
