# DriveBook DESIGN v2 — module ↔ channels

Independent booking microservice at `/Users/ghivi/Projects/drivebook`.
Stack locked: **FastAPI + Postgres** (independent deploy; equivalent to “Fastify as separate service”). Redis optional (in-process cache fallback).

---

## 1) Schema (diff to 001_init)

### Already in 001
- `instructors`, `slots` UNIQUE`(instructor_id, starts_at)`, `bookings` UNIQUE`(slot_id)`, deposit stub columns, `idempotency_records`

### Added in 002_v2.sql
```
schools (
  slug PK, name, default_lang, deposit_required DEFAULT false,
  deposit_amount_cents DEFAULT 0, grace_minutes DEFAULT 15,
  slot_minutes DEFAULT 90, admin_password_hash
)

ALTER slots ADD COLUMN held_until TIMESTAMPTZ;
ALTER bookings ADD COLUMN channel TEXT;  -- alias/source analytics
ALTER bookings ADD COLUMN confirmed_at TIMESTAMPTZ;
ALTER bookings ADD COLUMN reminder_24h_sent_at, reminder_2h_sent_at TIMESTAMPTZ;

waitlist (
  id, instructor_id?, preferred_starts_at?, preferred_ends_at?,
  student_name, student_phone, lang, source, status open|notified|booked|cancelled,
  created_at
)

events (
  id, event_type, channel, payload JSONB, booking_id?, slot_id?,
  ip, created_at
)

rate_limit_buckets (
  bucket_key PK, window_start, count
)
```

**Grace period:** not a separate table — enforced when generating/filtering slots: no two open/booked intervals for same instructor closer than `grace_minutes`. Seed uses 90‑min lessons + 15‑min gap.

**Deposit:** columns exist; API `POST /v1/bookings/{id}/deposit/mock-pay` isolated; widget never shows deposit unless `school.deposit_required`.

---

## 2) OpenAPI fragment (core)

```yaml
openapi: 3.0.3
info: { title: DriveBook API, version: "2.0.0" }
paths:
  /health:
    get:
      summary: Liveness
  /v1/meta:
    get:
      summary: Brand, school flags, lesson types, i18n
  /v1/instructors:
    get:
      parameters:
        - { name: zone, in: query, schema: { type: string } }       # district
        - { name: transmission, in: query, schema: { enum: [manual, automatic] } }
        - { name: language, in: query, schema: { type: string } }
        - { name: q, in: query }
        - { name: limit, in: query }
  /v1/instructors/{id}:
    get: {}
  /v1/instructors/{id}/calendar:
    get:
      summary: 14–21 day grid free/busy (90m slots)
      parameters:
        - { name: from, in: query, required: true }
        - { name: to, in: query, required: true }
  /v1/slots:
    get:
      parameters:
        - { name: instructor_id, in: query }
        - { name: from, in: query }
        - { name: to, in: query }
  /v1/slots/best:
    get:
      summary: Auto-pick nearest open slots (primary UX entry)
      parameters:
        - { name: zone, in: query }
        - { name: language, in: query }
        - { name: transmission, in: query }
        - { name: limit, in: query, schema: { default: 5 } }
  /v1/bookings:
    post:
      parameters:
        - { name: Idempotency-Key, in: header, required: true }
      requestBody:
        content:
          application/json:
            schema:
              required: [slot_id, student_name, student_phone]
              properties:
                slot_id: { type: integer }
                student_name: { type: string }
                student_phone: { type: string }
                student_email: { type: string }
                source: { type: string, description: "site|instagram|facebook|telegram|whatsapp|embed" }
                lang: { enum: [ro, ru, en] }
      responses:
        "200": { description: Created / idempotent replay }
        "409": { description: Slot taken; body includes alternatives[] }
  /v1/bookings/{id}:
    get: {}
  /v1/bookings/{id}/cancel:
    post: {}
  /v1/bookings/{id}/status:
    get: {}
  /v1/bookings/{id}/deposit/mock-pay:
    post:
      summary: Isolated deposit stub — NOT in MVP widget flow
  /v1/waitlist:
    post:
      summary: Join waitlist when 2 weeks full
  /v1/events:
    post:
      summary: Client analytics (slot_viewed, etc.)
  /v1/admin/*:
    description: Password-gated QA tools
```

**Race:** `UPDATE slots SET status='booked' WHERE id=$1 AND status='open' RETURNING` + UNIQUE(slot_id) on bookings.  
**409 body:** `{ detail, alternatives: [ {slot_id, starts_at, instructor_name} ] }`

---

## 3) Admin / test panel plan

| Area | Capability |
|------|------------|
| Auth | HTTP Basic / `X-Admin-Password` vs `schools.admin_password_hash` (env fallback `DRIVEBOOK_ADMIN_PASSWORD`) |
| Instructors | list, toggle active, create test instructor + generate 14d schedule |
| Bookings | list, cancel, filter by source |
| Time sim | create booking with `starts_at = now()+5m` / past date for reminder testing |
| API console | mini-Postman: method, path, body, show raw JSON |
| Webhooks | log table for TG/WA inbound + re-trigger button |
| Waitlist | list open entries, notify-on-cancel dry-run |
| Load | link to k6 race script results |

Path: `/admin/` (static) + protected `/v1/admin/*`.

---

## 4) Architecture module ↔ channels

```
                    ┌─────────────────────────────────────┐
                    │         DriveBook Core API          │
                    │  FastAPI :8100  ·  Postgres :5433   │
                    │  cache (Redis|memory)  ·  events    │
                    └──────────────┬──────────────────────┘
           ┌───────────┬───────────┼───────────┬───────────┐
           ▼           ▼           ▼           ▼           ▼
     Web Component  Hosted /book  Telegram    WhatsApp    IG/FB
     <script embed> book.?source  bot thin    Cloud API   link→hosted
     Shadow DOM     mobile-first  keyboards   day lists   QR
           │           │           │           │           │
           └───────────┴───────────┴───────────┴───────────┘
                         source= channel on booking + events
```

**Cache:** key `cal:{instructor_id}:{from}:{to}` TTL 60s; invalidate on book/cancel.  
**Realtime:** optional later via LISTEN/NOTIFY or Supabase Realtime; MVP uses short TTL + 409 alternatives.  
**Reminders:** cron/worker scans `reminder_*_sent_at` null & `starts_at` windows (24h, 2h).

---

## UX flow (widget) — 3–4 screens

1. **Auto-best** — top N nearest slots (zone/lang/tx filters optional chips)
2. **Or pick instructor** → **calendar 14d** free/busy
3. **Name + phone**
4. **Confirm** (+ cancel/reschedule later via link)

No deposit UI on MVP.
