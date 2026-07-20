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


def _rec(r: asyncpg.Record) -> dict[str, Any]:
    d = dict(r)
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif k == "rating" and v is not None:
            d[k] = float(v)
        elif k == "details" and isinstance(v, dict):
            d[k] = v
    return d


async def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "unknown") or "unknown"


async def require_admin(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
    x_admin_password: Optional[str] = Header(default=None, alias="X-Admin-Password"),
):
    """Require admin role. Session (Bearer) is the primary path — this is
    what the admin panel's username/password login uses. X-Admin-Password /
    Basic Auth against DRIVEBOOK_ADMIN_PASSWORD is kept as a fallback for
    external tooling (curl, load scripts)."""
    pool = await get_pool()

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        async with pool.acquire() as conn:
            user = await svc.validate_session(conn, token)
        if not user:
            raise HTTPException(401, "Invalid or expired token")
        if user["role"] != "admin":
            raise HTTPException(403, "Admin role required")
        return user

    expected = os.environ.get("DRIVEBOOK_ADMIN_PASSWORD", "drivebook-admin")
    if x_admin_password and secrets.compare_digest(x_admin_password, expected):
        return True
    if credentials and secrets.compare_digest(credentials.password, expected):
        return True
    raise HTTPException(401, "Admin auth required", headers={"WWW-Authenticate": "Basic"})


async def require_supervisor(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
):
    """Require supervisor or admin role, checked against the users table."""
    pool = await get_pool()

    # Bearer token path (session-based auth)
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if token:
        async with pool.acquire() as conn:
            user = await svc.validate_session(conn, token)
        if not user:
            raise HTTPException(401, "Invalid or expired token")
        if user["role"] not in ("supervisor", "admin"):
            raise HTTPException(403, "Supervisor or admin role required")
        return user

    # Basic Auth path — validate credentials against users table
    if credentials:
        async with pool.acquire() as conn:
            user = await svc.authenticate_user(conn, credentials.username, credentials.password)
        if not user:
            raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Basic"})
        if user["role"] not in ("supervisor", "admin"):
            raise HTTPException(403, "Supervisor or admin role required")
        return user

    raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})


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
        "day_start": "07:00",
        "day_end": "21:00",
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
    return {"total": total, "city": settings.city, "items": [_rec(r) for r in rows]}


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
    return _rec(row)


@router.get("/v1/instructors/{instructor_id}/calendar")
async def calendar(
    instructor_id: int,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    include_hidden: bool = Query(False, description="Admin/instructor: show hidden slots"),
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
        return await svc.instructor_calendar(
            conn, instructor_id, start, end, include_hidden=include_hidden
        )


@router.post("/v1/auth/login")
async def auth_login(
    request: Request,
    payload: "AuthLoginIn",
):
    """Authenticate user and return session token."""
    ip = await _client_ip(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await svc.authenticate_user(conn, payload.username, payload.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    async with pool.acquire() as conn:
        token = await svc.create_session(conn, user["id"], ip=ip)
        await svc.emit_audit(conn, user["id"], "login", details={"ip": ip})
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "instructor_id": user["instructor_id"],
            "must_change_password": user["must_change_password"],
        },
    }


class AuthLoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class AuthLogoutIn(BaseModel):
    token: str


@router.post("/v1/auth/logout")
async def auth_logout(payload: AuthLogoutIn):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await svc.revoke_session(conn, payload.token)
    return {"ok": True}


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


@router.post("/v1/auth/change-password")
async def auth_change_password(
    payload: ChangePasswordIn,
    authorization: Optional[str] = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    token = authorization[7:]
    pool = await get_pool()
    async with pool.acquire() as conn:
        session_user = await svc.validate_session(conn, token)
        if not session_user:
            raise HTTPException(401, "Invalid or expired token")
        ok = await svc.change_password(conn, session_user["user_id"], payload.old_password, payload.new_password)
        if not ok:
            raise HTTPException(401, "Current password is incorrect")
        await svc.emit_audit(conn, session_user["user_id"], "change_password")
    return {"ok": True}


@router.post("/v1/auth/verify")
async def auth_verify(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Verify session token. Returns user info."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token:
        raise HTTPException(401, "Missing token")
    pool = await get_pool()
    async with pool.acquire() as conn:
        session = await svc.validate_session(conn, token)
    if not session:
        raise HTTPException(401, "Invalid or expired token")
    return {"ok": True, "user": session}


class HideSlotsIn(BaseModel):
    """Hide or show slots for an instructor (drivers hide times they won't work)."""
    is_hidden: bool = True
    slot_ids: Optional[list[int]] = None
    # hide all slots starting at/after this local time, e.g. "18:00"
    hide_starts_from: Optional[str] = None
    # optional date range filter
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    # reason for hiding (required for instructor requests)
    reason: Optional[str] = Field(default=None, max_length=500)


@router.patch("/v1/instructors/{instructor_id}/slots/visibility")
async def set_slot_visibility(
    instructor_id: int,
    payload: HideSlotsIn,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """
    Authenticated: instructor requests hide with reason (→ moderation).
    Admin/supervisor can apply directly.
    """
    ip = await _client_ip(request)
    # extract token
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    pool = await get_pool()
    async with pool.acquire() as conn:
        user = None
        if token:
            user = await svc.validate_session(conn, token)
        inst = await conn.fetchval("SELECT id FROM instructors WHERE id=$1", instructor_id)
        if not inst:
            raise HTTPException(404, "Instructor not found")

        if not user:
            raise HTTPException(401, "Authentication required")

        # Instructor requests → moderation queue
        if user["role"] == "instructor" and user["instructor_id"] != instructor_id:
            raise HTTPException(403, "Can only modify own slots")

        is_instructor = user["role"] == "instructor"

        if is_instructor:
            # Create hide request (pending moderation)
            if not payload.reason:
                raise HTTPException(400, "Instructor must provide a reason for hiding slots")
            scope = payload.model_dump(exclude={"reason"}, exclude_none=True)
            req_id = await svc.submit_hide_request(conn, instructor_id, payload.reason, scope)
            await svc.emit_audit(conn, user["id"], "hide_request",
                                 target_type="instructor", target_id=instructor_id,
                                 details={"reason": payload.reason, "scope": scope, "request_id": req_id, "ip": ip})
            return {"ok": True, "request_id": req_id, "status": "pending", "message": "Request submitted for admin review"}

        # Admin/supervisor: apply directly
        if payload.slot_ids:
            result = await conn.execute(
                "UPDATE slots SET is_hidden = $1 WHERE instructor_id = $2 AND id = ANY($3::bigint[])",
                payload.is_hidden, instructor_id, payload.slot_ids,
            )
        elif payload.hide_starts_from:
            hh, mm = payload.hide_starts_from.split(":")
            hour, minute = int(hh), int(mm)
            clauses = ["instructor_id = $1",
                       "(EXTRACT(HOUR FROM starts_at AT TIME ZONE 'Europe/Chisinau') * 60 + EXTRACT(MINUTE FROM starts_at AT TIME ZONE 'Europe/Chisinau')) >= $2"]
            params: list[Any] = [instructor_id, hour * 60 + minute]
            if payload.date_from:
                params.append(payload.date_from)
                clauses.append(f"starts_at >= ${len(params)}")
            if payload.date_to:
                params.append(payload.date_to)
                clauses.append(f"starts_at <= ${len(params)}")
            params.append(payload.is_hidden)
            result = await conn.execute(
                f"UPDATE slots SET is_hidden = ${len(params)} WHERE {' AND '.join(clauses)}",
                *params,
            )
        else:
            raise HTTPException(400, "Provide slot_ids or hide_starts_from (e.g. '18:00')")

        svc.invalidate_slot_caches(instructor_id)
        n = int(result.split()[-1]) if result else 0
        await svc.emit_audit(conn, user["id"], "hide_apply" if not payload.is_hidden else "hide_revoke",
                             target_type="instructor", target_id=instructor_id,
                             details={"updated": n, "is_hidden": payload.is_hidden, "ip": ip})
        return {"ok": True, "updated": n, "is_hidden": payload.is_hidden}


@router.get("/v1/admin/moderation")
async def get_moderation_queue(_: bool = Depends(require_admin)):
    """Admin: pending hide requests with reasons."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        items = await svc.get_pending_hide_requests(conn)
        unread = await svc.count_unread_notifications(conn)
    return {"items": items, "unread": unread}


@router.post("/v1/admin/moderation/{request_id}/resolve")
async def resolve_hide_request(
    request_id: int,
    action: str = Query(..., description="'accept' or 'reject'"),
    _: bool = Depends(require_admin),
    request: Request = None,
):
    """Admin: accept or reject a hide request."""
    if action not in ("accept", "reject"):
        raise HTTPException(400, "action must be 'accept' or 'reject'")
    # get admin user from basic auth header
    admin_id = None
    ip = await _client_ip(request)
    pool = await get_pool()
    async with pool.acquire() as conn:
        ok = await svc.resolve_hide_request(conn, request_id, action, admin_id or 1)
        await svc.emit_audit(conn, admin_id or 1, "hide_accept" if action == "accept" else "hide_reject",
                             target_type="hide_request", target_id=request_id,
                             details={"action": action, "ip": ip})
    if not ok:
        raise HTTPException(404, "Request not found or already resolved")
    return {"ok": True, "action": action}


@router.get("/v1/admin/notifications")
async def get_notifications(_: bool = Depends(require_admin)):
    """Admin: unread notification count."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        unread = await svc.count_unread_notifications(conn)
    return {"unread": unread}


@router.get("/v1/admin/dashboard")
async def admin_dashboard(_: bool = Depends(require_admin)):
    """Admin: slot loads, active bookings, instructor info."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # slots loaded by district and hour
        slot_load = await conn.fetch(
            """
            SELECT date_trunc('hour', s.starts_at AT TIME ZONE 'Europe/Chisinau') AS hour,
                   i.district,
                   COUNT(*) AS total,
                   SUM(CASE WHEN s.status = 'booked' THEN 1 ELSE 0 END) AS booked,
                   SUM(CASE WHEN s.status = 'open' AND COALESCE(s.is_hidden, FALSE) = FALSE THEN 1 ELSE 0 END) AS open_visible
            FROM slots s
            JOIN instructors i ON i.id = s.instructor_id
            WHERE s.starts_at >= now() - interval '7 days'
              AND s.starts_at < now() + interval '7 days'
            GROUP BY hour, i.district
            ORDER BY hour, i.district
            """
        )
        # top booked instructors this week
        top_instructors = await conn.fetch(
            """
            SELECT i.id, i.name, i.district, COUNT(b.id) AS bookings
            FROM instructors i
            JOIN slots s ON s.instructor_id = i.id
            JOIN bookings b ON b.slot_id = s.id
            WHERE s.starts_at >= now() - interval '7 days'
              AND b.status = 'confirmed'
            GROUP BY i.id, i.name, i.district
            ORDER BY bookings DESC
            LIMIT 20
            """
        )
        # stats
        instructors = await conn.fetchval("SELECT COUNT(*) FROM instructors WHERE active")
        open_slots = await conn.fetchval("SELECT COUNT(*) FROM slots WHERE status='open' AND COALESCE(is_hidden, FALSE) = FALSE")
        booked = await conn.fetchval("SELECT COUNT(*) FROM slots WHERE status='booked'")
        bookings_total = await conn.fetchval("SELECT COUNT(*) FROM bookings")
        pending = await conn.fetchval("SELECT COUNT(*) FROM hide_requests WHERE status='pending'")

    return {
        "stats": {
            "city": settings.city,
            "instructors": instructors,
            "open_slots": open_slots,
            "booked_slots": booked,
            "bookings_total": bookings_total,
            "pending_hide_requests": pending,
        },
        "slot_load": [_rec(r) for r in slot_load],
        "top_instructors": [_rec(r) for r in top_instructors],
    }


@router.get("/v1/admin/audit-log")
async def get_audit_log(
    limit: int = Query(100, ge=1, le=500),
    user_id: Optional[int] = None,
    _=Depends(require_supervisor),
):
    """Audit log — supervisor and admin only."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if user_id:
            rows = await conn.fetch(
                "SELECT * FROM audit_log WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                user_id, limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT $1",
                limit,
            )
    return {"items": [_rec(r) for r in rows]}




@router.get("/v1/instructors/{instructor_id}/slots")
async def instructor_slots(
    instructor_id: int,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=300),
    include_hidden: bool = False,
):
    return await list_slots(
        instructor_id=instructor_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        include_hidden=include_hidden,
    )


@router.get("/v1/slots")
async def list_slots(
    instructor_id: Optional[int] = None,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=300),
    include_hidden: bool = False,
):
    """Public booking: hidden slots excluded. Admin may pass include_hidden=true."""
    pool = await get_pool()
    now = datetime.now(TZ)
    clauses = ["s.starts_at >= $1", "i.active = TRUE"]
    params: list[Any] = [now]
    if not include_hidden:
        clauses.append("s.status = 'open'")
        clauses.append("COALESCE(s.is_hidden, FALSE) = FALSE")
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
                   COALESCE(s.is_hidden, FALSE) AS is_hidden,
                   i.name AS instructor_name, i.district, i.car, i.transmission, i.rating
            FROM slots s JOIN instructors i ON i.id = s.instructor_id
            WHERE {where}
            ORDER BY s.starts_at ASC
            LIMIT ${len(params)}
            """,
            *params,
        )
    items = []
    for r in rows:
        d = _rec(r)
        try:
            s = datetime.fromisoformat(d["starts_at"])
            e = datetime.fromisoformat(d["ends_at"])
            d["starts_label"] = s.astimezone(TZ).strftime("%H:%M")
            d["ends_label"] = e.astimezone(TZ).strftime("%H:%M")
            d["label"] = f"{d['starts_label']}–{d['ends_label']}"
        except Exception:
            pass
        items.append(d)
    return {"items": items}


class HideSlotsIn(BaseModel):
    """Hide or show slots for an instructor (drivers hide times they won't work)."""
    is_hidden: bool = True
    slot_ids: Optional[list[int]] = None
    # hide all slots starting at/after this local time, e.g. "18:00"
    hide_starts_from: Optional[str] = None
    # optional date range filter
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@router.patch("/v1/instructors/{instructor_id}/slots/visibility")
async def set_slot_visibility(instructor_id: int, payload: HideSlotsIn):
    """Instructor: hide/unhide own slots. Admin can call same endpoint."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        inst = await conn.fetchval("SELECT id FROM instructors WHERE id=$1", instructor_id)
        if not inst:
            raise HTTPException(404, "Instructor not found")

        if payload.slot_ids:
            result = await conn.execute(
                """
                UPDATE slots SET is_hidden = $1
                WHERE instructor_id = $2 AND id = ANY($3::bigint[])
                """,
                payload.is_hidden,
                instructor_id,
                payload.slot_ids,
            )
        elif payload.hide_starts_from:
            # hide by local wall-clock time on starts_at
            hh, mm = payload.hide_starts_from.split(":")
            hour, minute = int(hh), int(mm)
            clauses = ["instructor_id = $1", "(EXTRACT(HOUR FROM starts_at AT TIME ZONE 'Europe/Chisinau') * 60 + EXTRACT(MINUTE FROM starts_at AT TIME ZONE 'Europe/Chisinau')) >= $2"]
            params: list[Any] = [instructor_id, hour * 60 + minute]
            if payload.date_from:
                params.append(payload.date_from)
                clauses.append(f"starts_at >= ${len(params)}")
            if payload.date_to:
                params.append(payload.date_to)
                clauses.append(f"starts_at <= ${len(params)}")
            params.append(payload.is_hidden)
            result = await conn.execute(
                f"UPDATE slots SET is_hidden = ${len(params)} WHERE {' AND '.join(clauses)}",
                *params,
            )
        else:
            raise HTTPException(400, "Provide slot_ids or hide_starts_from (e.g. '18:00')")

        svc.invalidate_slot_caches(instructor_id)
        # "UPDATE 3" -> 3
        n = int(result.split()[-1]) if result else 0
        return {"ok": True, "updated": n, "is_hidden": payload.is_hidden}


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
    return _rec(row) if row else None


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
                      AND COALESCE(is_hidden, FALSE) = FALSE
                    RETURNING id, starts_at, instructor_id
                    """,
                    payload.slot_id,
                )
                if not claimed:
                    alts = await svc.alternatives(conn, payload.slot_id)
                    slot = await conn.fetchrow(
                        "SELECT id, status, COALESCE(is_hidden,FALSE) AS is_hidden FROM slots WHERE id=$1",
                        payload.slot_id,
                    )
                    if not slot:
                        raise HTTPException(404, "Slot not found")
                    if slot["is_hidden"]:
                        raise HTTPException(409, detail={"message": "Slot hidden by instructor", "alternatives": alts})
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
    return {"items": [_rec(r) for r in rows]}


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
    return {"items": [_rec(r) for r in rows]}


@router.get("/v1/admin/waitlist")
async def admin_waitlist(_: bool = Depends(require_admin)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM waitlist ORDER BY created_at DESC LIMIT 100"
        )
    return {"items": [_rec(r) for r in rows]}


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
