from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.db import get_pool
from app import services as svc

router = APIRouter()
TZ = ZoneInfo("Europe/Chisinau")
PHONE_RE = re.compile(r"^\+?[0-9()\-\s]{8,20}$")
security = HTTPBasic(auto_error=False)


class BookingIn(BaseModel):
    slot_id: int
    student_name: str = Field(min_length=2, max_length=120)
    student_phone: str = Field(min_length=8, max_length=32)
    student_email: Optional[str] = Field(default=None, max_length=160)
    lesson_type: str = Field(default="standard", max_length=40)
    source: str = Field(default="site", max_length=40)
    lang: str = Field(default="ro", max_length=5)
    notes: Optional[str] = Field(default=None, max_length=500)

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


class WaitlistIn(BaseModel):
    student_name: str = Field(min_length=2, max_length=120)
    student_phone: str = Field(min_length=8, max_length=32)
    instructor_id: Optional[int] = None
    zone: Optional[str] = None
    preferred_starts_at: Optional[str] = None
    preferred_ends_at: Optional[str] = None
    lang: str = "ro"
    source: str = "site"


class EventIn(BaseModel):
    event_type: str
    channel: str = "site"
    payload: dict = Field(default_factory=dict)
    booking_id: Optional[int] = None
    slot_id: Optional[int] = None


def _row(r: asyncpg.Record) -> dict[str, Any]:
    d = dict(r)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif k == "rating" and v is not None:
            d[k] = float(v)
    return d


async def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "unknown") or "unknown"


async def require_admin(
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
    x_admin_password: Optional[str] = Header(default=None, alias="X-Admin-Password"),
):
    expected = os.environ.get("DRIVEBOOK_ADMIN_PASSWORD", "drivebook-admin")
    if x_admin_password and secrets.compare_digest(x_admin_password, expected):
        return True
    if credentials and secrets.compare_digest(credentials.password, expected):
        return True
    raise HTTPException(401, "Admin auth required", headers={"WWW-Authenticate": "Basic"})


@router.get("/health")
async def health():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"ok": True, "service": "drivebook", "city": settings.city, "tz": "Europe/Chisinau", "version": "2.0"}


@router.get("/v1/meta")
async def meta():
    pool = await get_pool()
    school = None
    async with pool.acquire() as conn:
        try:
            school = await conn.fetchrow("SELECT * FROM schools WHERE slug='chisinau'")
        except Exception:
            school = None
    return {
        "brand": settings.brand_name,
        "city": settings.city,
        "country": settings.country,
        "languages": ["ro", "ru", "en"],
        "default_lang": "ro",
        "slot_minutes": int(school["slot_minutes"]) if school else 90,
        "grace_minutes": int(school["grace_minutes"]) if school else 15,
        "deposit_required": bool(school["deposit_required"]) if school else False,
        "deposit_amount_cents": int(school["deposit_amount_cents"]) if school else 0,
        "lesson_types": [
            {"id": "standard", "title_ro": "Lecție 90 min", "title_ru": "Урок 90 мин", "title_en": "90 min lesson", "price_mdl": 350},
            {"id": "exam", "title_ro": "Pregătire examen", "title_ru": "К экзамену", "title_en": "Exam prep", "price_mdl": 400},
        ],
        "widget": {"embed": "/widget/embed.js", "book": "/book", "component": "booking-widget"},
        "ux": {"primary": "auto_best", "secondary": "pick_instructor"},
    }


@router.get("/v1/instructors")
async def list_instructors(
    zone: Optional[str] = None,
    transmission: Optional[str] = None,
    language: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    pool = await get_pool()
    clauses = ["active = TRUE"]
    params: list[Any] = []
    if zone:
        params.append(f"%{zone}%")
        clauses.append(f"district ILIKE ${len(params)}")
    if transmission in ("manual", "automatic"):
        params.append(transmission)
        clauses.append(f"(transmission = ${len(params)} OR transmission = 'both')")
    if language:
        params.append(f"%{language}%")
        clauses.append(f"languages ILIKE ${len(params)}")
    if q:
        params.append(f"%{q.strip()}%")
        i = len(params)
        clauses.append(f"(name ILIKE ${i} OR district ILIKE ${i} OR car ILIKE ${i})")
    where = " AND ".join(clauses)
    async with pool.acquire() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM instructors WHERE {where}", *params)
        rows = await conn.fetch(
            f"""
            SELECT id, name, district, car, transmission, experience_years, rating, languages, bio
            FROM instructors WHERE {where}
            ORDER BY rating DESC, name
            LIMIT ${len(params)+1} OFFSET ${len(params)+2}
            """,
            *params,
            limit,
            offset,
        )
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


@router.get("/v1/instructors/{instructor_id}/calendar")
async def calendar(
    instructor_id: int,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
):
    now = datetime.now(TZ)
    start = datetime.fromisoformat(date_from) if date_from else now
    end = datetime.fromisoformat(date_to) if date_to else now + timedelta(days=21)
    if start.tzinfo is None:
        start = start.replace(tzinfo=TZ)
    if end.tzinfo is None:
        end = end.replace(tzinfo=TZ)
    pool = await get_pool()
    async with pool.acquire() as conn:
        inst = await conn.fetchval("SELECT id FROM instructors WHERE id=$1 AND active", instructor_id)
        if not inst:
            raise HTTPException(404, "Instructor not found")
        return await svc.instructor_calendar(conn, instructor_id, start, end)


@router.get("/v1/instructors/{instructor_id}/slots")
async def instructor_slots(
    instructor_id: int,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=300),
):
    return await list_slots(instructor_id=instructor_id, date_from=date_from, date_to=date_to, limit=limit)


@router.get("/v1/slots")
async def list_slots(
    instructor_id: Optional[int] = None,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
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
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT s.id, s.instructor_id, s.starts_at, s.ends_at, s.status,
                   i.name AS instructor_name, i.district, i.car, i.transmission, i.rating
            FROM slots s JOIN instructors i ON i.id = s.instructor_id
            WHERE {where}
            ORDER BY s.starts_at ASC
            LIMIT ${len(params)}
            """,
            *params,
        )
    return {"items": [_row(r) for r in rows]}


@router.get("/v1/slots/best")
async def slots_best(
    zone: Optional[str] = None,
    language: Optional[str] = None,
    transmission: Optional[str] = None,
    limit: int = Query(5, ge=1, le=20),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        items = await svc.best_slots(
            conn, zone=zone, language=language, transmission=transmission, limit=limit
        )
    return {"items": items, "mode": "auto_best"}


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
    request: Request,
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(400, "Idempotency-Key header is required")
    key = idempotency_key.strip()
    body_hash = hashlib.sha256(
        json.dumps(payload.model_dump(), sort_keys=True, default=str).encode()
    ).hexdigest()
    ip = await _client_ip(request)
    pool = await get_pool()

    async with pool.acquire() as conn:
        if not await svc.rate_limit(conn, f"ip:{ip}:book", limit=30, window_sec=60):
            raise HTTPException(429, "Too many booking attempts from this IP")
        if not await svc.rate_limit(conn, f"phone:{payload.student_phone}:book", limit=10, window_sec=3600):
            raise HTTPException(429, "Too many booking attempts for this phone")

        existing = await conn.fetchrow("SELECT * FROM idempotency_records WHERE key=$1", key)
        if existing:
            if existing["request_hash"] != body_hash:
                raise HTTPException(422, "Idempotency-Key reused with different body")
            response.status_code = existing["status_code"]
            return json.loads(existing["response_body"])

        try:
            async with conn.transaction():
                claimed = await conn.fetchrow(
                    """
                    UPDATE slots SET status = 'booked'
                    WHERE id = $1 AND status = 'open' AND starts_at > now()
                    RETURNING id, starts_at, instructor_id
                    """,
                    payload.slot_id,
                )
                if not claimed:
                    alts = await svc.alternatives(conn, payload.slot_id)
                    slot = await conn.fetchrow("SELECT id, status FROM slots WHERE id=$1", payload.slot_id)
                    if not slot:
                        raise HTTPException(404, "Slot not found")
                    raise HTTPException(
                        status_code=409,
                        detail={"message": "Slot already taken", "alternatives": alts},
                    )

                cancel_token = secrets.token_urlsafe(16)
                try:
                    booking_id = await conn.fetchval(
                        """
                        INSERT INTO bookings (
                            slot_id, student_name, student_phone, student_email,
                            lesson_type, source, channel, lang, notes, status,
                            deposit_amount_cents, deposit_status, idempotency_key,
                            cancel_token, confirmed_at
                        ) VALUES (
                            $1,$2,$3,$4,$5,$6,$6,$7,$8,'confirmed',0,'none',$9,$10, now()
                        ) RETURNING id
                        """,
                        payload.slot_id,
                        payload.student_name,
                        payload.student_phone,
                        payload.student_email,
                        payload.lesson_type,
                        payload.source[:40],
                        payload.lang,
                        payload.notes,
                        key,
                        cancel_token,
                    )
                except asyncpg.UniqueViolationError as e:
                    alts = await svc.alternatives(conn, payload.slot_id)
                    raise HTTPException(
                        409,
                        detail={"message": f"Conflict: {e.constraint_name}", "alternatives": alts},
                    ) from e

                booking = await _fetch_booking(conn, booking_id)
                await svc.emit_event(
                    conn,
                    "booking_created",
                    channel=payload.source,
                    payload={"source": payload.source, "lang": payload.lang},
                    booking_id=booking_id,
                    slot_id=payload.slot_id,
                    ip=ip,
                )
                out = {"ok": True, "booking": booking}
                await conn.execute(
                    """
                    INSERT INTO idempotency_records(key, request_hash, status_code, response_body, booking_id)
                    VALUES ($1,$2,200,$3::jsonb,$4) ON CONFLICT (key) DO NOTHING
                    """,
                    key,
                    body_hash,
                    json.dumps(out, default=str),
                    booking_id,
                )
                svc.invalidate_slot_caches(claimed["instructor_id"])
                return out
        except HTTPException:
            raise


@router.get("/v1/bookings/{booking_id}")
@router.get("/v1/bookings/{booking_id}/status")
async def get_booking(booking_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        b = await _fetch_booking(conn, booking_id)
    if not b:
        raise HTTPException(404, "Booking not found")
    return b


@router.post("/v1/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: int, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, slot_id, status, source FROM bookings WHERE id=$1 FOR UPDATE",
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
            slot = await conn.fetchrow(
                "UPDATE slots SET status='open' WHERE id=$1 AND status='booked' RETURNING instructor_id",
                row["slot_id"],
            )
            await svc.emit_event(
                conn,
                "booking_cancelled",
                channel=row["source"] or "unknown",
                booking_id=booking_id,
                slot_id=row["slot_id"],
                ip=await _client_ip(request),
            )
            # notify waitlist (mark notified — real push later)
            await conn.execute(
                """
                UPDATE waitlist SET status='notified'
                WHERE status='open'
                  AND (instructor_id IS NULL OR instructor_id = $1)
                """,
                slot["instructor_id"] if slot else None,
            )
            if slot:
                svc.invalidate_slot_caches(slot["instructor_id"])
            return {"ok": True, "booking": await _fetch_booking(conn, booking_id)}


@router.post("/v1/bookings/{booking_id}/deposit/mock-pay")
async def mock_pay_deposit(booking_id: int):
    """Isolated deposit stub — not in MVP widget flow."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, status FROM bookings WHERE id=$1 FOR UPDATE", booking_id
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
                "message": "Mock deposit paid (not part of MVP UX)",
                "booking": await _fetch_booking(conn, booking_id),
            }


@router.post("/v1/waitlist")
async def join_waitlist(payload: WaitlistIn, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        wid = await conn.fetchval(
            """
            INSERT INTO waitlist (
                instructor_id, preferred_starts_at, preferred_ends_at, zone,
                student_name, student_phone, lang, source, status
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'open')
            RETURNING id
            """,
            payload.instructor_id,
            payload.preferred_starts_at,
            payload.preferred_ends_at,
            payload.zone,
            payload.student_name,
            payload.student_phone,
            payload.lang,
            payload.source,
        )
        await svc.emit_event(
            conn,
            "waitlist_joined",
            channel=payload.source,
            payload={"waitlist_id": wid},
            ip=await _client_ip(request),
        )
    return {"ok": True, "waitlist_id": wid}


@router.post("/v1/events")
async def post_event(payload: EventIn, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await svc.emit_event(
            conn,
            payload.event_type,
            channel=payload.channel,
            payload=payload.payload,
            booking_id=payload.booking_id,
            slot_id=payload.slot_id,
            ip=await _client_ip(request),
        )
    return {"ok": True}


@router.get("/v1/admin/bookings")
async def admin_bookings(limit: int = Query(50, ge=1, le=200), _: bool = Depends(require_admin)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.id, b.student_name, b.student_phone, b.lesson_type, b.source,
                   b.channel, b.lang, b.status, b.deposit_status, b.created_at,
                   s.starts_at, i.name AS instructor_name, i.district
            FROM bookings b
            JOIN slots s ON s.id = b.slot_id
            JOIN instructors i ON i.id = s.instructor_id
            ORDER BY b.created_at DESC LIMIT $1
            """,
            limit,
        )
    return {"items": [_row(r) for r in rows]}


@router.get("/v1/admin/stats")
async def admin_stats(_: bool = Depends(require_admin)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        instructors = await conn.fetchval("SELECT COUNT(*) FROM instructors WHERE active")
        open_slots = await conn.fetchval("SELECT COUNT(*) FROM slots WHERE status='open'")
        booked = await conn.fetchval("SELECT COUNT(*) FROM slots WHERE status='booked'")
        bookings = await conn.fetchval("SELECT COUNT(*) FROM bookings")
        waitlist = await conn.fetchval("SELECT COUNT(*) FROM waitlist WHERE status='open'")
        events_24h = await conn.fetchval(
            "SELECT COUNT(*) FROM events WHERE created_at > now() - interval '24 hours'"
        )
    weekly = instructors * 6 * 6  # approx with 90m fewer per day; still capacity model
    return {
        "city": settings.city,
        "instructors": instructors,
        "open_slots": open_slots,
        "booked_slots": booked,
        "bookings_total": bookings,
        "waitlist_open": waitlist,
        "events_24h": events_24h,
        "capacity": {
            "weekly_lessons": weekly,
            "monthly_lessons_approx": int(weekly * 4.3),
            "visible_slots_est": instructors * 8 * 14,
            "target_utilization": 0.72,
        },
        "traffic_estimate": {
            "peak_concurrent": max(80, int(instructors * 1.2)),
            "peak_rps": round(max(80, instructors * 1.2) * 12 / 90, 2),
        },
    }


@router.get("/v1/admin/events")
async def admin_events(limit: int = Query(50, ge=1, le=200), _: bool = Depends(require_admin)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, event_type, channel, payload, booking_id, slot_id, ip, created_at "
            "FROM events ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    return {"items": [_row(r) for r in rows]}


@router.get("/v1/admin/waitlist")
async def admin_waitlist(_: bool = Depends(require_admin)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM waitlist ORDER BY created_at DESC LIMIT 100"
        )
    return {"items": [_row(r) for r in rows]}


@router.post("/v1/admin/sim/booking")
async def admin_sim_booking(
    minutes_from_now: int = 5,
    _: bool = Depends(require_admin),
):
    """Create a slot+booking in the near future for reminder testing."""
    pool = await get_pool()
    start = datetime.now(TZ) + timedelta(minutes=minutes_from_now)
    end = start + timedelta(minutes=90)
    async with pool.acquire() as conn:
        inst = await conn.fetchval("SELECT id FROM instructors WHERE active LIMIT 1")
        async with conn.transaction():
            sid = await conn.fetchval(
                """
                INSERT INTO slots (instructor_id, starts_at, ends_at, status)
                VALUES ($1,$2,$3,'open')
                ON CONFLICT (instructor_id, starts_at) DO UPDATE SET status='open'
                RETURNING id
                """,
                inst,
                start,
                end,
            )
            bid = await conn.fetchval(
                """
                INSERT INTO bookings (
                    slot_id, student_name, student_phone, source, channel, lang, status,
                    deposit_status, cancel_token, confirmed_at
                ) VALUES ($1,'Sim Student','+37360000000','admin','admin','ro','confirmed','none',$2,now())
                ON CONFLICT (slot_id) DO NOTHING
                RETURNING id
                """,
                sid,
                secrets.token_urlsafe(12),
            )
            if bid:
                await conn.execute("UPDATE slots SET status='booked' WHERE id=$1", sid)
        return {"ok": True, "slot_id": sid, "booking_id": bid, "starts_at": start.isoformat()}
