# SPEC — DriveBook v1 (reconstructed TZ)

> Original path `raw/final-prompt-v1.md` was not found. This SPEC merges:
> conversation requirements (MD/Chișinău, bilingual, no city, BSM-like flow,
> 100 instructors, multi-channel embed, deposit stub) + staged protocol.

## Product

- **Market:** Moldova, **Chișinău only** (no city selection).
- **Languages:** Romanian + Russian (`lang=ro|ru`, default `ro`).
- **Scale:** 100 active instructors; horizon ~14 days of slots.
- **Channels:** site embed (Shadow DOM), hosted `/book`, Telegram, WhatsApp, Facebook/IG via link/iframe.

## Booking flow (BSM-inspired, no postcode/city)

1. Gearbox filter (Manual / Automatic / Any)
2. Pick instructor (list + rating)
3. Pick slot from instructor calendar
4. Contact form (name, phone, optional email)
5. Confirm → booking `confirmed` or `pending_deposit` (if deposit required flag)
6. Deposit stub: `POST /v1/bookings/{id}/deposit/mock-pay` → `confirmed`

## Domain model

### instructors
- id, name, district (Chișinău sector), car, transmission (`manual|automatic|both`)
- experience_years, rating, languages, bio, active, created_at

### slots
- id, instructor_id, starts_at, ends_at, status (`open|held|booked|cancelled`)
- **UNIQUE (instructor_id, starts_at)**
- status transitions under transaction

### bookings
- id, slot_id **UNIQUE**, student_name, student_phone, student_email
- lesson_type, source, lang, notes
- status (`pending_deposit|confirmed|cancelled|completed`)
- deposit_amount_cents, deposit_status (`none|pending|paid|waived`)
- idempotency_key **UNIQUE NULL**
- created_at, updated_at

### idempotency_keys (optional dual)
- key PRIMARY KEY, booking_id, request_hash, response_json, created_at

## API (versioned `/v1`)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | liveness |
| GET | `/v1/meta` | brand, lesson types, langs, city fixed Chișinău |
| GET | `/v1/instructors` | query: transmission, q, limit, offset |
| GET | `/v1/instructors/{id}` | |
| GET | `/v1/slots` | instructor_id?, date_from?, date_to?, limit |
| POST | `/v1/bookings` | Header `Idempotency-Key` recommended; body slot_id + student |
| GET | `/v1/bookings/{id}` | |
| POST | `/v1/bookings/{id}/cancel` | releases slot if cancellable |
| POST | `/v1/bookings/{id}/deposit/mock-pay` | stub |
| GET | `/v1/admin/bookings` | recent |
| GET | `/v1/admin/stats` | capacity/load snapshot |

### Race / claim algorithm

```sql
BEGIN;
UPDATE slots SET status = 'booked'
 WHERE id = $1 AND status = 'open'
 RETURNING id;
-- if no row → 409
INSERT INTO bookings (...);
COMMIT;
```

Also: `UNIQUE(slot_id)` on bookings as second line of defence.

### Idempotency

- If `Idempotency-Key` seen → return stored response (same status code + body).
- Key bound to request body hash; mismatch → 422.

## Widget

- `embed.js` creates host node + **Shadow DOM**
- Hosted page `/book?source=&lang=`
- No city step
- Palette: BSM-like (orange CTA `#F9812A`, dark text `#2E2E36`, white/air, Titillium/system sans)
- Sources: `site`, `telegram`, `instagram`, `facebook`, `whatsapp`, `embed`

## Load model (100 instructors)

- ~6 lessons/day × 6 days × 100 = 3600 lessons/week capacity
- Peak RPS estimate ~16 (documented in admin stats)
- Stage 3 proves single-slot mutual exclusion under 100 VUs

## Non-goals v1

- Real payment PSP
- Multi-city
- Instructor self-service calendar UI (admin seed only)
- Marketing CMS site (this repo is booking module only)
