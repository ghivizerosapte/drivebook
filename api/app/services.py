"""Domain helpers: best slots, calendar, events, rate limit, alternatives, auth, audit."""
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


# ── audit helper ────────────────────────────────────────────────────────────

async def emit_audit(
    conn: asyncpg.Connection,
    user_id: Optional[int],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO audit_log (user_id, action, target_type, target_id, details)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        """,
        user_id, action, target_type, target_id,
        __import__("json").dumps(details or {}),
    )


# ── event helper (kept for legacy) ──────────────────────────────────────────

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


# ── auth helpers ────────────────────────────────────────────────────────────

try:
    import argon2
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False


def hash_password(pw: str) -> str:
    """Shared by seed.py and the change-password endpoint."""
    if HAS_ARGON2:
        h = argon2.low_level.hash_secret(
            secret=pw.encode(), salt=secrets.token_bytes(16), time_cost=2,
            memory_cost=65536, parallelism=1, hash_len=32, type=argon2.low_level.Type.ID,
        )
        return h.decode()
    # fallback: SHA-256 (NOT for production — dev only)
    return "sha256:" + hashlib.sha256(pw.encode()).hexdigest()


def _verify_password(stored: str, password: str) -> bool:
    if stored.startswith("sha256:"):
        return "sha256:" + hashlib.sha256(password.encode()).hexdigest() == stored
    if stored.startswith("$argon2"):
        try:
            argon2.PasswordHasher().verify(stored, password)
            return True
        except argon2.exceptions.VerifyMismatchError:
            return False
    return False


async def authenticate_user(
    conn: asyncpg.Connection,
    username: str,
    password: str,
) -> Optional[dict]:
    """Verify password hash and return user dict, or None."""
    row = await conn.fetchrow(
        "SELECT id, username, role, password_hash, instructor_id, must_change_password "
        "FROM users WHERE username = $1",
        username,
    )
    if not row or not _verify_password(row["password_hash"], password):
        return None

    # update last_login
    await conn.execute(
        "UPDATE users SET last_login = now() WHERE id = $1",
        row["id"],
    )
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "instructor_id": row["instructor_id"],
        "must_change_password": row["must_change_password"],
    }


async def change_password(
    conn: asyncpg.Connection,
    user_id: int,
    old_password: str,
    new_password: str,
) -> bool:
    """Verify old_password, then set new_password and clear must_change_password.
    Returns False if old_password doesn't match (no change made)."""
    row = await conn.fetchrow("SELECT password_hash FROM users WHERE id = $1", user_id)
    if not row or not _verify_password(row["password_hash"], old_password):
        return False
    await conn.execute(
        "UPDATE users SET password_hash = $1, must_change_password = FALSE WHERE id = $2",
        hash_password(new_password), user_id,
    )
    return True


async def create_session(
    conn: asyncpg.Connection,
    user_id: int,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(TZ) + timedelta(hours=24)
    await conn.execute(
        """
        INSERT INTO sessions (token, user_id, expires_at, ip, user_agent, created_at)
        VALUES ($1, $2, $3, $4, $5, now())
        """,
        token, user_id, expires, ip, user_agent,
    )
    return token


async def validate_session(
    conn: asyncpg.Connection,
    token: str,
) -> Optional[dict]:
    row = await conn.fetchrow(
        """
        SELECT s.user_id, s.expires_at, u.username, u.role, u.instructor_id
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = $1 AND s.expires_at > now()
        """,
        token,
    )
    if not row:
        return None
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "instructor_id": row["instructor_id"],
        "expires_at": row["expires_at"].isoformat(),
    }


async def revoke_session(conn: asyncpg.Connection, token: str) -> None:
    await conn.execute("DELETE FROM sessions WHERE token = $1", token)


# ── moderation helpers ──────────────────────────────────────────────────────

async def submit_hide_request(
    conn: asyncpg.Connection,
    instructor_id: int,
    reason: str,
    scope: dict,
) -> int:
    """Create a hide request. Returns request id."""
    req_id = await conn.fetchval(
        """
        INSERT INTO hide_requests (instructor_id, reason, scope, status, created_at)
        VALUES ($1, $2, $3::jsonb, 'pending', now())
        RETURNING id
        """,
        instructor_id, reason, __import__("json").dumps(scope),
    )
    return req_id  # type: ignore[return-value]


async def get_pending_hide_requests(
    conn: asyncpg.Connection,
    limit: int = 50,
) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT hr.id, hr.instructor_id, i.name AS instructor_name,
               hr.reason, hr.scope, hr.status, hr.created_at
        FROM hide_requests hr
        JOIN instructors i ON i.id = hr.instructor_id
        WHERE hr.status = 'pending'
        ORDER BY hr.created_at DESC
        LIMIT $1
        """,
        limit,
    )
    out = []
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        d["scope"] = __import__("json").loads(d["scope"]) if isinstance(d["scope"], str) else d["scope"]
        out.append(d)
    return out


async def resolve_hide_request(
    conn: asyncpg.Connection,
    request_id: int,
    action: str,  # 'accept' or 'reject'
    admin_user_id: int,
) -> bool:
    """Apply or reject a hide request. Returns True if applied."""
    row = await conn.fetchrow(
        "SELECT * FROM hide_requests WHERE id = $1 AND status = 'pending'",
        request_id,
    )
    if not row:
        return False

    scope = row["scope"]
    if isinstance(scope, str):
        scope = __import__("json").loads(scope)

    if action == "accept":
        # Actually set is_hidden on the slots
        if scope.get("slot_ids"):
            await conn.execute(
                "UPDATE slots SET is_hidden = TRUE WHERE id = ANY($1::bigint[])",
                scope["slot_ids"],
            )
        elif scope.get("hide_starts_from"):
            hh, mm = scope["hide_starts_from"].split(":")
            hour, minute = int(hh), int(mm)
            clauses = [
                "(EXTRACT(HOUR FROM starts_at AT TIME ZONE 'Europe/Chisinau') * 60 + EXTRACT(MINUTE FROM starts_at AT TIME ZONE 'Europe/Chisinau')) >= $1"
            ]
            params: list[Any] = [hour * 60 + minute]
            if scope.get("date_from"):
                params.append(scope["date_from"])
                clauses.append(f"starts_at >= ${len(params)}")
            if scope.get("date_to"):
                params.append(scope["date_to"])
                clauses.append(f"starts_at <= ${len(params)}")
            params.append(True)
            await conn.execute(
                f"UPDATE slots SET is_hidden = ${len(params)} WHERE {' AND '.join(clauses)}",
                *params,
            )
        await conn.execute(
            "UPDATE hide_requests SET status = 'accepted', reviewed_at = now(), reviewed_by = $1 WHERE id = $2",
            admin_user_id, request_id,
        )
        return True
    elif action == "reject":
        await conn.execute(
            "UPDATE hide_requests SET status = 'rejected', reviewed_at = now(), reviewed_by = $1 WHERE id = $2",
            admin_user_id, request_id,
        )
        return False
    return False


async def count_unread_notifications(conn: asyncpg.Connection) -> int:
    return await conn.fetchval(
        "SELECT count(*) FROM hide_requests WHERE status = 'pending'",
    )


# ── slot helpers ────────────────────────────────────────────────────────────

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

    clauses = [
        "s.status = 'open'",
        "s.starts_at > now()",
        "i.active = TRUE",
        "COALESCE(s.is_hidden, FALSE) = FALSE",
    ]
    params: list[Any] = []
    if zone:
        params.append(f"%{zone}%")
        clauses.append(f"i.district ILIKE ${len(params)}")
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
               COALESCE(s.is_hidden, FALSE) AS is_hidden,
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
    items = [_serialize_slot(dict(r)) for r in rows]
    cache.set_json(cache_key, items, ttl_sec=30)
    return items


def _serialize_slot(it: dict[str, Any]) -> dict[str, Any]:
    for k, v in list(it.items()):
        if hasattr(v, "isoformat"):
            it[k] = v.isoformat()
        elif k == "rating" and v is not None:
            it[k] = float(v)
    # human labels for 90-min windows
    if it.get("starts_at") and it.get("ends_at"):
        try:
            s = datetime.fromisoformat(it["starts_at"])
            e = datetime.fromisoformat(it["ends_at"])
            it["label"] = f"{s.astimezone(TZ).strftime('%H:%M')}–{e.astimezone(TZ).strftime('%H:%M')}"
            it["starts_label"] = s.astimezone(TZ).strftime("%H:%M")
            it["ends_label"] = e.astimezone(TZ).strftime("%H:%M")
        except Exception:
            pass
    return it


async def instructor_calendar(
    conn: asyncpg.Connection,
    instructor_id: int,
    date_from: datetime,
    date_to: datetime,
    *,
    include_hidden: bool = False,
) -> dict[str, Any]:
    key = f"cal:{instructor_id}:{date_from.date()}:{date_to.date()}:h{int(include_hidden)}"
    cached = cache.get_json(key)
    if cached is not None:
        return cached

    if include_hidden:
        rows = await conn.fetch(
            """
            SELECT id, starts_at, ends_at, status, COALESCE(is_hidden, FALSE) AS is_hidden
            FROM slots
            WHERE instructor_id = $1 AND starts_at >= $2 AND starts_at < $3
            ORDER BY starts_at
            """,
            instructor_id,
            date_from,
            date_to,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, starts_at, ends_at, status, COALESCE(is_hidden, FALSE) AS is_hidden
            FROM slots
            WHERE instructor_id = $1 AND starts_at >= $2 AND starts_at < $3
              AND COALESCE(is_hidden, FALSE) = FALSE
            ORDER BY starts_at
            """,
            instructor_id,
            date_from,
            date_to,
        )
    days: dict[str, list] = {}
    for r in rows:
        day = r["starts_at"].astimezone(TZ).date().isoformat()
        s = r["starts_at"].astimezone(TZ)
        e = r["ends_at"].astimezone(TZ)
        days.setdefault(day, []).append(
            {
                "id": r["id"],
                "starts_at": r["starts_at"].isoformat(),
                "ends_at": r["ends_at"].isoformat(),
                "starts_label": s.strftime("%H:%M"),
                "ends_label": e.strftime("%H:%M"),
                "label": f"{s.strftime('%H:%M')}–{e.strftime('%H:%M')}",
                "status": r["status"],
                "is_hidden": bool(r["is_hidden"]),
                "free": r["status"] == "open" and not r["is_hidden"],
            }
        )
    out = {
        "instructor_id": instructor_id,
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "days": days,
        "slot_minutes": 90,
        "day_start": "07:00",
        "day_end": "21:00",
        "include_hidden": include_hidden,
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
          AND COALESCE(s.is_hidden, FALSE) = FALSE
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


async def rate_limit(
    conn: asyncpg.Connection,
    bucket_key: str,
    limit: int = 30,
    window_sec: int = 60,
) -> bool:
    """Sliding-window rate limiter using rate_limit_buckets table.
    Returns True if the request is allowed, False if rate-limited."""
    now = datetime.now(TZ)
    window_start = now - timedelta(seconds=window_sec)

    # Count requests in the window
    count = await conn.fetchval(
        """
        SELECT COALESCE(SUM(count), 0) FROM rate_limit_buckets
        WHERE bucket_key = $1 AND window_start >= $2
        """,
        bucket_key,
        window_start,
    )

    if count >= limit:
        return False

    # Insert a new bucket entry
    await conn.execute(
        """
        INSERT INTO rate_limit_buckets (bucket_key, window_start, count)
        VALUES ($1, $2, 1)
        ON CONFLICT (bucket_key, window_start)
        DO UPDATE SET count = rate_limit_buckets.count + 1
        """,
        bucket_key,
        now,
    )

    # Clean up old buckets
    await conn.execute(
        "DELETE FROM rate_limit_buckets WHERE window_start < $1",
        window_start,
    )

    return True
