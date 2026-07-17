from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.db import get_pool

router = APIRouter()
TZ = ZoneInfo("Europe/Chisinau")
PHONE_RE = re.compile(r"^\+?[0-9()\-\s]{8,20}$")


class BookingIn(BaseModel):
    slot_id: int
    student_name: str = Field(min_length=2, max_length=120)
    student_phone: str = Field(min_length=8, max_length=32)
    student_email: Optional[str] = Field(default=None, max_length=160)
    lesson_type: str = Field(default="standard", max_length=40)
    source: str = Field(default="site", max_length=40)
    lang: str = Field(default="ro", max_length=5)
    notes: Optional[str] = Field(default=None, max_length=500)
    require_deposit: Optional[bool] = None

    @field_validator("student_phone")
    @classmethod
    def phone_ok(cls, v: str) -> str:
        v = v.strip()
        if not PHONE_RE.match(v):
            raise ValueError("Invalid phone")
        return v

    @field_validator("student_name")
    @classmethod
    def name_ok(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("lang")
    @classmethod
    def lang_ok(cls, v: str) -> str:
        v = v.lower()
        if v not in ("ro", "ru", "en"):
            raise ValueError("lang must be ro|ru|en")
        return v


def _row(r: asyncpg.Record) -> dict[str, Any]:
    d = dict(r)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif isinstance(v, float):
            pass
        elif hasattr(v, "__float__") and k == "rating":
            d[k] = float(v)
    return d


@router.get("/health")
async def health():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"ok": True, "service": "drivebook", "city": settings.city, "tz": "Europe/Chisinau"}


@router.get("/v1/meta")
async def meta():
    return {
        "brand": settings.brand_name,
        "city": settings.city,
        "country": settings.country,
        "languages": ["ro", "ru"],
        "default_lang": "ro",
        "lesson_types": [
            {"id": "standard", "title_ro": "Lecție 60 min", "title_ru": "Урок 60 мин", "price_mdl": 250},
            {"id": "intensive", "title_ro": "Intensiv 90 min", "title_ru": "Интенсив 90 мин", "price_mdl": 350},
            {"id": "exam", "title_ro": "Pregătire examen", "title_ru": "Подготовка к экзамену", "price_mdl": 300},
        ],
        "deposit_default_cents": settings.deposit_default_cents,
        "require_deposit_default": settings.require_deposit,
        "widget": {"embed": "/widget/embed.js", "book": "/book"},
    }


@router.get("/v1/instructors")
async def list_instructors(
    transmission: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    pool = await get_pool()
    clauses = ["active = TRUE"]
    params: list[Any] = []
    if transmission in ("manual", "automatic"):
        params.append(transmission)
        clauses.append(f"(transmission = ${len(params)} OR transmission = 'both')")
    if q:
        params.append(f"%{q.strip()}%")
        i = len(params)
        clauses.append(f"(name ILIKE ${i} OR district ILIKE ${i} OR car ILIKE ${i})")
    where = " AND ".join(clauses)
    params_total = list(params)
    params.extend([limit, offset])
    sql = f"""
        SELECT id, name, district, car, transmission, experience_years, rating, languages, bio
        FROM instructors WHERE {where}
        ORDER BY rating DESC, name
        LIMIT ${len(params)-1} OFFSET ${len(params)}
    """
    # fix param indices for limit/offset
    sql = f"""
        SELECT id, name, district, car, transmission, experience_years, rating, languages, bio
        FROM instructors WHERE {where}
        ORDER BY rating DESC, name
        LIMIT ${len(params_total)+1} OFFSET ${len(params_total)+2}
    """
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM instructors WHERE {where}", *params_total
        )
        rows = await conn.fetch(sql, *params_total, limit, offset)
    return {"total": total, "city": settings.city, "items": [_row(r) for r in rows]}


@router.get("/v1/instructors/{instructor_id}")
async def get_instructor(instructor_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, district, car, transmission, experience_years, rating, languages, bio
            FROM instructors WHERE id=$1 AND active=TRUE
            """,
            instructor_id,
        )
    if not row:
        raise HTTPException(404, "Instructor not found")
    return _row(row)


@router.get("/v1/slots")
async def list_slots(
    instructor_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(100, ge=1, le=300),
):
    pool = await get_pool()
    now = datetime.now(TZ)
    clauses = ["s.status = 'open'", "s.starts_at >= $1", "i.active = TRUE"]
    params: list[Any] = [now]
    if instructor_id:
        params.append(instructor_id)
        clauses.append(f"s.instructor_id = ${len(params)}")
    if date_from:
        params.append(date_from)
        clauses.append(f"s.starts_at >= ${len(params)}")
    if date_to:
        params.append(date_to)
        clauses.append(f"s.starts_at <= ${len(params)}")
    params.append(limit)
    where = " AND ".join(clauses)
    sql = f"""
        SELECT s.id, s.instructor_id, s.starts_at, s.ends_at, s.status,
               i.name AS instructor_name, i.district, i.car, i.transmission, i.rating
        FROM slots s
        JOIN instructors i ON i.id = s.instructor_id
        WHERE {where}
        ORDER BY s.starts_at ASC
        LIMIT ${len(params)}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return {"items": [_row(r) for r in rows]}


async def _fetch_booking(conn: asyncpg.Connection, booking_id: int) -> Optional[dict]:
    row = await conn.fetchrow(
        """
        SELECT b.*, s.starts_at, s.ends_at, i.name AS instructor_name,
               i.district, i.car, i.transmission
        FROM bookings b
        JOIN slots s ON s.id = b.slot_id
        JOIN instructors i ON i.id = s.instructor_id
        WHERE b.id = $1
        """,
        booking_id,
    )
    return _row(row) if row else None


@router.post("/v1/bookings")
async def create_booking(
    payload: BookingIn,
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    body_hash = hashlib.sha256(
        json.dumps(payload.model_dump(), sort_keys=True, default=str).encode()
    ).hexdigest()
    key = (idempotency_key or "").strip() or None

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Idempotent replay
        if key:
            existing = await conn.fetchrow(
                "SELECT * FROM idempotency_records WHERE key=$1", key
            )
            if existing:
                if existing["request_hash"] != body_hash:
                    raise HTTPException(422, "Idempotency-Key reused with different body")
                response.status_code = existing["status_code"]
                return json.loads(existing["response_body"])

        require_dep = (
            payload.require_deposit
            if payload.require_deposit is not None
            else settings.require_deposit
        )
        status = "pending_deposit" if require_dep else "confirmed"
        dep_status = "pending" if require_dep else "none"
        dep_amount = settings.deposit_default_cents if require_dep else 0

        try:
            async with conn.transaction():
                # Line 1: atomic claim
                claimed = await conn.fetchrow(
                    """
                    UPDATE slots SET status = 'booked'
                    WHERE id = $1 AND status = 'open' AND starts_at > now()
                    RETURNING id, starts_at
                    """,
                    payload.slot_id,
                )
                if not claimed:
                    # distinguish missing vs taken
                    slot = await conn.fetchrow("SELECT id, status FROM slots WHERE id=$1", payload.slot_id)
                    if not slot:
                        raise HTTPException(404, "Slot not found")
                    raise HTTPException(409, "Slot already taken")

                try:
                    booking_id = await conn.fetchval(
                        """
                        INSERT INTO bookings (
                            slot_id, student_name, student_phone, student_email,
                            lesson_type, source, lang, notes, status,
                            deposit_amount_cents, deposit_status, idempotency_key
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                        RETURNING id
                        """,
                        payload.slot_id,
                        payload.student_name,
                        payload.student_phone,
                        payload.student_email,
                        payload.lesson_type,
                        payload.source[:40],
                        payload.lang,
                        payload.notes,
                        status,
                        dep_amount,
                        dep_status,
                        key,
                    )
                except asyncpg.UniqueViolationError as e:
                    # Line 2: UNIQUE(slot_id) or idempotency
                    raise HTTPException(409, f"Conflict: {e.constraint_name or 'unique'}") from e

                booking = await _fetch_booking(conn, booking_id)
                out = {"ok": True, "booking": booking}
                if key:
                    await conn.execute(
                        """
                        INSERT INTO idempotency_records(key, request_hash, status_code, response_body, booking_id)
                        VALUES ($1,$2,$3,$4::jsonb,$5)
                        ON CONFLICT (key) DO NOTHING
                        """,
                        key,
                        body_hash,
                        200,
                        json.dumps(out, default=str),
                        booking_id,
                    )
                return out
        except HTTPException:
            raise


@router.get("/v1/bookings/{booking_id}")
async def get_booking(booking_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        b = await _fetch_booking(conn, booking_id)
    if not b:
        raise HTTPException(404, "Booking not found")
    return b


@router.post("/v1/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, slot_id, status FROM bookings WHERE id=$1 FOR UPDATE",
                booking_id,
            )
            if not row:
                raise HTTPException(404, "Booking not found")
            if row["status"] == "cancelled":
                return {"ok": True, "booking": await _fetch_booking(conn, booking_id)}
            if row["status"] == "completed":
                raise HTTPException(400, "Cannot cancel completed booking")
            await conn.execute(
                "UPDATE bookings SET status='cancelled', updated_at=now() WHERE id=$1",
                booking_id,
            )
            await conn.execute(
                "UPDATE slots SET status='open' WHERE id=$1 AND status='booked'",
                row["slot_id"],
            )
            return {"ok": True, "booking": await _fetch_booking(conn, booking_id)}


@router.post("/v1/bookings/{booking_id}/deposit/mock-pay")
async def mock_pay_deposit(booking_id: int):
    """Deposit stub — no real PSP."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, status, deposit_status FROM bookings WHERE id=$1 FOR UPDATE",
                booking_id,
            )
            if not row:
                raise HTTPException(404, "Booking not found")
            if row["status"] == "cancelled":
                raise HTTPException(400, "Booking cancelled")
            await conn.execute(
                """
                UPDATE bookings
                SET deposit_status='paid', status='confirmed', updated_at=now()
                WHERE id=$1
                """,
                booking_id,
            )
            return {
                "ok": True,
                "stub": True,
                "message": "Mock deposit paid",
                "booking": await _fetch_booking(conn, booking_id),
            }


@router.get("/v1/admin/bookings")
async def admin_bookings(limit: int = Query(50, ge=1, le=200)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.id, b.student_name, b.student_phone, b.lesson_type, b.source,
                   b.lang, b.status, b.deposit_status, b.created_at,
                   s.starts_at, i.name AS instructor_name, i.district
            FROM bookings b
            JOIN slots s ON s.id = b.slot_id
            JOIN instructors i ON i.id = s.instructor_id
            ORDER BY b.created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return {"items": [_row(r) for r in rows]}


@router.get("/v1/admin/stats")
async def admin_stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        instructors = await conn.fetchval("SELECT COUNT(*) FROM instructors WHERE active")
        open_slots = await conn.fetchval("SELECT COUNT(*) FROM slots WHERE status='open'")
        booked = await conn.fetchval("SELECT COUNT(*) FROM slots WHERE status='booked'")
        bookings = await conn.fetchval("SELECT COUNT(*) FROM bookings")
    weekly = instructors * 6 * 6
    return {
        "city": settings.city,
        "instructors": instructors,
        "open_slots": open_slots,
        "booked_slots": booked,
        "bookings_total": bookings,
        "capacity": {
            "weekly_lessons": weekly,
            "monthly_lessons_approx": int(weekly * 4.3),
            "target_utilization": 0.72,
            "expected_monthly": int(weekly * 4.3 * 0.72),
        },
        "traffic_estimate": {
            "peak_concurrent": max(80, int(instructors * 1.2)),
            "peak_rps": round(max(80, instructors * 1.2) * 12 / 90, 2),
        },
    }
