"""Domain helpers: best slots, calendar, events, rate limit, alternatives."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import asyncpg

from app import cache
from app.config import settings

TZ = ZoneInfo("Europe/Chisinau")


async def emit_event(
    conn: asyncpg.Connection,
    event_type: str,
    channel: str = "unknown",
    payload: Optional[dict] = None,
    booking_id: Optional[int] = None,
    slot_id: Optional[int] = None,
    ip: Optional[str] = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO events (event_type, channel, payload, booking_id, slot_id, ip)
        VALUES ($1, $2, $3::jsonb, $4, $5, $6)
        """,
        event_type,
        channel or "unknown",
        __import__("json").dumps(payload or {}),
        booking_id,
        slot_id,
        ip,
    )


async def rate_limit(
    conn: asyncpg.Connection,
    key: str,
    limit: int,
    window_sec: int = 60,
) -> bool:
    """Return True if allowed, False if limited."""
    now = datetime.now(TZ)
    row = await conn.fetchrow(
        "SELECT window_start, count FROM rate_limit_buckets WHERE bucket_key=$1",
        key,
    )
    if not row or (now - row["window_start"]).total_seconds() >= window_sec:
        await conn.execute(
            """
            INSERT INTO rate_limit_buckets(bucket_key, window_start, count)
            VALUES ($1, $2, 1)
            ON CONFLICT (bucket_key) DO UPDATE
            SET window_start = EXCLUDED.window_start, count = 1
            """,
            key,
            now,
        )
        return True
    if row["count"] >= limit:
        return False
    await conn.execute(
        "UPDATE rate_limit_buckets SET count = count + 1 WHERE bucket_key=$1",
        key,
    )
    return True


async def best_slots(
    conn: asyncpg.Connection,
    *,
    zone: Optional[str] = None,
    language: Optional[str] = None,
    transmission: Optional[str] = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    cache_key = f"best:{zone}:{language}:{transmission}:{limit}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached

    clauses = ["s.status = 'open'", "s.starts_at > now()", "i.active = TRUE"]
    params: list[Any] = []
    if zone:
        params.append(zone)
        clauses.append(f"i.district ILIKE ${len(params)}")
        params[-1] = f"%{zone}%"
    if language:
        params.append(f"%{language}%")
        clauses.append(f"i.languages ILIKE ${len(params)}")
    if transmission in ("manual", "automatic"):
        params.append(transmission)
        clauses.append(f"(i.transmission = ${len(params)} OR i.transmission = 'both')")
    params.append(limit)
    where = " AND ".join(clauses)
    rows = await conn.fetch(
        f"""
        SELECT s.id, s.instructor_id, s.starts_at, s.ends_at, s.status,
               i.name AS instructor_name, i.district, i.car, i.transmission,
               i.rating, i.languages
        FROM slots s
        JOIN instructors i ON i.id = s.instructor_id
        WHERE {where}
        ORDER BY s.starts_at ASC, i.rating DESC
        LIMIT ${len(params)}
        """,
        *params,
    )
    items = [dict(r) for r in rows]
    for it in items:
        for k, v in list(it.items()):
            if hasattr(v, "isoformat"):
                it[k] = v.isoformat()
            elif k == "rating":
                it[k] = float(v)
    cache.set_json(cache_key, items, ttl_sec=30)
    return items


async def instructor_calendar(
    conn: asyncpg.Connection,
    instructor_id: int,
    date_from: datetime,
    date_to: datetime,
) -> dict[str, Any]:
    key = f"cal:{instructor_id}:{date_from.date()}:{date_to.date()}"
    cached = cache.get_json(key)
    if cached is not None:
        return cached

    rows = await conn.fetch(
        """
        SELECT id, starts_at, ends_at, status
        FROM slots
        WHERE instructor_id = $1 AND starts_at >= $2 AND starts_at < $3
        ORDER BY starts_at
        """,
        instructor_id,
        date_from,
        date_to,
    )
    days: dict[str, list] = {}
    for r in rows:
        day = r["starts_at"].astimezone(TZ).date().isoformat()
        days.setdefault(day, []).append(
            {
                "id": r["id"],
                "starts_at": r["starts_at"].isoformat(),
                "ends_at": r["ends_at"].isoformat(),
                "status": r["status"],
                "free": r["status"] == "open",
            }
        )
    out = {
        "instructor_id": instructor_id,
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "days": days,
        "slot_minutes": 90,
    }
    cache.set_json(key, out, ttl_sec=60)
    return out


async def alternatives(
    conn: asyncpg.Connection,
    slot_id: int,
    limit: int = 5,
) -> list[dict[str, Any]]:
    row = await conn.fetchrow(
        """
        SELECT s.starts_at, s.instructor_id, i.district
        FROM slots s JOIN instructors i ON i.id = s.instructor_id
        WHERE s.id = $1
        """,
        slot_id,
    )
    if not row:
        return []
    center = row["starts_at"]
    window_lo = center - timedelta(days=2)
    window_hi = center + timedelta(days=2)
    rows = await conn.fetch(
        """
        SELECT s.id AS slot_id, s.starts_at, s.ends_at,
               i.name AS instructor_name, i.district
        FROM slots s
        JOIN instructors i ON i.id = s.instructor_id
        WHERE s.status = 'open' AND s.starts_at > now()
          AND s.id <> $1
          AND (i.district = $2 OR (s.starts_at >= $3 AND s.starts_at <= $4))
        ORDER BY abs(extract(epoch from (s.starts_at - $5::timestamptz)))
        LIMIT $6
        """,
        slot_id,
        row["district"],
        window_lo,
        window_hi,
        center,
        limit,
    )
    out = []
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        out.append(d)
    return out


def new_cancel_token() -> str:
    return secrets.token_urlsafe(16)


def invalidate_slot_caches(instructor_id: Optional[int] = None) -> None:
    cache.invalidate_prefix("best:")
    if instructor_id:
        cache.invalidate_prefix(f"cal:{instructor_id}:")
    else:
        cache.invalidate_prefix("cal:")
