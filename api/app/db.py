from __future__ import annotations

import asyncpg
from app.config import asyncpg_kwargs

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            min_size=2,
            max_size=20,
            command_timeout=30,
            **asyncpg_kwargs(),
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
