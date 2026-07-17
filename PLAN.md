# PLAN — DriveBook stages

Source of truth for progress. Mark `[x]` only with evidence.

**Repo:** `/Users/ghivi/Projects/drivebook`  
**Started:** 2026-07-17  
**Note:** `raw/final-prompt-v1.md` missing — using `SPEC.md` as TZ.

---

## Pre-start
- [x] New git repo (independent)
- [x] Root `AGENTS.md`
- [x] `PLAN.md` (this file)
- [x] `SPEC.md` (reconstructed TZ)
- [x] Per-module `AGENTS.md` as dirs are created (api → …) — api done

## Stage 1 — DB schema + SQL migrations
**Ready when:** migrations apply cleanly on empty Postgres; schema matches SPEC; `psql \d` shows tables + constraints.
- [x] `api/migrations/001_init.sql`
- [x] migrate runner
- [x] docker-compose Postgres
- [x] evidence: migrate output + `\d+`

## Stage 2 — Core API + DB race protection
**Ready when:** all SPEC endpoints respond; double-book same slot → one 201 one 409; idempotency key replays same booking.
- [x] FastAPI app structure
- [x] endpoints
- [x] seed 100 instructors + slots
- [x] evidence: curl booking + conflict

## Stage 3 — Load test race (100 parallel)
**Ready when:** k6 script run; summary shows ≤1 success for same slot; rest fail cleanly.
- [x] `load/race-book.js`
- [x] run k6 against live API
- [x] paste summary in PLAN / commit artifact

## Stage 4 — Web Widget (Shadow DOM) + hosted page
**Ready when:** embed script mounts isolated UI; `/book` works; no city step; BSM-like airy orange palette.
- [x] widget build
- [x] hosted page
- [x] embed.js

## Stage 5 — Admin / test panel
**Ready when:** can list instructors, open slots, force-cancel booking via UI.
- [x] admin static UI

## Stage 6 — Telegram bot
**Ready when:** bot can list slots + create booking via API (token optional / dry-run mode).
- [x] bots/telegram

## Stage 7 — WhatsApp adapter
**Ready when:** webhook receiver + outbound stub maps to same booking API.
- [x] bots/whatsapp

---

## Architecture decisions log

| Date | Decision | Alternatives | Reason |
|------|----------|--------------|--------|
| 2026-07-17 | FastAPI + Postgres + asyncpg | Next.js+Supabase, Fastify | Independent API; SQL migrations explicit; bots share REST |
| 2026-07-17 | Port 8100 / PG 5433 | 8080/5432 | Avoid clash with llama-server :8080 |
| 2026-07-17 | Deposit = stub status machine | Real PSP | TZ: deposit stub only |

## Blockers
- None for Stage 1–2. If real Telegram/WhatsApp tokens missing at Stage 6–7 → ship dry-run + env-gated live mode.


### Stage 3 evidence (2026-07-17)
```
success(200): 1
conflict(409): 99
other: 0
PASS: exactly one winner
DB: slot 288 status=booked; one booking Racer 6
```


### Stage 4–7 evidence (2026-07-17)
- `/book` 200, `/widget/embed.js` 200, `attachShadow` present
- `/admin/` 200, stats instructors=100
- Telegram dry-run booked #3
- WhatsApp dry-run booked #4
