"""Apply ordered SQL migrations from api/migrations/*.sql"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg

from app.config import asyncpg_kwargs

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


async def ensure_migrations_table(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


async def applied_versions(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {r["version"] for r in rows}


async def migrate() -> list[str]:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise SystemExit(f"No migrations in {MIGRATIONS_DIR}")

    conn = await asyncpg.connect(**asyncpg_kwargs())
    applied: list[str] = []
    try:
        await ensure_migrations_table(conn)
        done = await applied_versions(conn)
        for f in files:
            version = f.name
            if version in done:
                print(f"skip {version}")
                continue
            sql = f.read_text(encoding="utf-8")
            async with conn.transaction():
                # 001_init also creates schema_migrations — IF NOT EXISTS safe
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations(version) VALUES ($1) ON CONFLICT DO NOTHING",
                    version,
                )
            print(f"apply {version}")
            applied.append(version)
    finally:
        await conn.close()
    return applied


def main() -> None:
    applied = asyncio.run(migrate())
    print(f"done: {len(applied)} new migration(s)")


if __name__ == "__main__":
    main()
