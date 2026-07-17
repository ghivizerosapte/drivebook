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
- [ ] Per-module `AGENTS.md` as dirs are created (api → widget → admin → bots)

## Stage 1 — DB schema + SQL migrations
**Ready when:** migrations apply cleanly on empty Postgres; schema matches SPEC; `psql \d` shows tables + constraints.
- [ ] `api/migrations/001_init.sql`
- [ ] migrate runner
- [ ] docker-compose Postgres
- [ ] evidence: migrate output + `\d+`

## Stage 2 — Core API + DB race protection
**Ready when:** all SPEC endpoints respond; double-book same slot → one 201 one 409; idempotency key replays same booking.
- [ ] FastAPI app structure
- [ ] endpoints
- [ ] seed 100 instructors + slots
- [ ] evidence: curl booking + conflict

## Stage 3 — Load test race (100 parallel)
**Ready when:** k6 script run; summary shows ≤1 success for same slot; rest fail cleanly.
- [ ] `load/race-book.js`
- [ ] run k6 against live API
- [ ] paste summary in PLAN / commit artifact

## Stage 4 — Web Widget (Shadow DOM) + hosted page
**Ready when:** embed script mounts isolated UI; `/book` works; no city step; BSM-like airy orange palette.
- [ ] widget build
- [ ] hosted page
- [ ] embed.js

## Stage 5 — Admin / test panel
**Ready when:** can list instructors, open slots, force-cancel booking via UI.
- [ ] admin static UI

## Stage 6 — Telegram bot
**Ready when:** bot can list slots + create booking via API (token optional / dry-run mode).
- [ ] bots/telegram

## Stage 7 — WhatsApp adapter
**Ready when:** webhook receiver + outbound stub maps to same booking API.
- [ ] bots/whatsapp

---

## Architecture decisions log

| Date | Decision | Alternatives | Reason |
|------|----------|--------------|--------|
| 2026-07-17 | FastAPI + Postgres + asyncpg | Next.js+Supabase, Fastify | Independent API; SQL migrations explicit; bots share REST |
| 2026-07-17 | Port 8100 / PG 5433 | 8080/5432 | Avoid clash with llama-server :8080 |
| 2026-07-17 | Deposit = stub status machine | Real PSP | TZ: deposit stub only |

## Blockers
- None for Stage 1–2. If real Telegram/WhatsApp tokens missing at Stage 6–7 → ship dry-run + env-gated live mode.
