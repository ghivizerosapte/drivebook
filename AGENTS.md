# DriveBook — independent online booking module

> Working memory for agents. Update when architecture decisions change.

## What this is

Standalone **online booking module** for a driving school (Chișinău, Moldova):
100 instructors, multi-channel embed (web widget, hosted page, Telegram, WhatsApp).
**Physically independent** — no imports from `avtostart` or other repos.

## Stack (locked 2026-07-17)

| Layer | Choice | Why |
|-------|--------|-----|
| API | **Python 3.11 + FastAPI + uvicorn** | Clear REST, easy bots, proven for concurrent I/O |
| DB | **PostgreSQL 16** (docker) + **SQL migration files** | Real constraints for race safety; not ORM-only |
| DB access | **asyncpg** (raw SQL) | Explicit SQL, no hidden magic |
| Widget | **Vanilla TS → bundled JS, Shadow DOM** | Zero host CSS leaks; drop-in embed |
| Load test | **k6** | Stage-3 race scenario |
| Bots | **aiogram 3** (TG), **HTTP webhook stub** (WA) | Thin clients over same API |
| Admin | **Static HTML + API** | Manual QA, no SPA framework tax |
| Money | **Deposit stub** only (`pending_deposit` → mock pay) | No real PSP in v1 |

**Rejected (documented):** Next.js+Supabase — would couple marketing + API; TZ asks independent module. tRPC — bots/embeds need plain REST.

## Ports

| Service | Port |
|---------|------|
| API | `8100` |
| Postgres | `5433` (host) → `5432` (container) |
| Admin static | served by API at `/admin` |
| Widget assets | served by API at `/widget/*` |
| Hosted book page | `/book` |

## Hard rules

1. **No city picker** — Chișinău only.
2. **Bilingual RO + RU** in widget/admin copy (i18n JSON).
3. Race safety: **DB UNIQUE + transactional claim**, not app locks alone.
4. Idempotency: `Idempotency-Key` header on `POST /v1/bookings`.
5. Migrations = **numbered `.sql` files** under `api/migrations/`; apply via script.
6. Stages in `PLAN.md` are sequential; do not skip readiness criteria.
7. Commit per stage; never one mega-commit.
8. Evidence required (command output / k6 summary) before marking stage done.
9. Do not copy code from `~/Projects/avtostart` into this tree (rewrite if needed).

## Repo layout

```
drivebook/
  AGENTS.md          # this file
  PLAN.md            # stage checklist
  SPEC.md            # product/API spec (reconstructed TZ)
  docker-compose.yml
  api/               # FastAPI + migrations + seed
  widget/            # Shadow DOM embed + hosted page sources
  admin/             # QA panel
  landing/           # marketing homepage (static HTML, embeds the widget), served at "/"
  bots/              # telegram + whatsapp adapters
  load/              # k6 scripts
```

## Quick start (after Stage 2)

```bash
docker compose up -d db
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.migrate && python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8100
```

## Open questions / blockers

- Source file `raw/final-prompt-v1.md` was **not found** on disk. Working from conversation + stage protocol → see `SPEC.md`. If a fuller TZ appears, merge into SPEC and re-plan deltas.

---


---

## Agent orchestration (local delegation)

You (Claude Code, Sonnet via Pro) are the sole "thinking" loop on this project.
You plan, you decide, you verify. You have one delegate: **local Qwen**, via a wrapper script.

**Script path:** `~/scripts/worker.py` (fallback: `~/Downloads/worker.py` if not yet moved)

### Calling the worker

```bash
python3 ~/scripts/worker.py "precise instruction" \
  --files api/app/main.py \
  --save-to drivebook/progress-notes.md
```

Flags: `--files` (context files, project paths or vault filenames), `--search KEYWORD`
(grep the Obsidian vault instead), `--stdin` (pipe context in), `--save-to FILE`
(append result to `$OBSIDIAN_VAULT/FILE` with timestamp; `--overwrite` replaces
instead of appending), `--tokens N` (response cap, default 4096).

### Golden rule

Qwen executes exactly what's written — no initiative, no reliable self-verification.
It has previously reported success on tasks where files were never actually written.

**Every worker.py call for code changes MUST be followed by a manual check before
the step counts as done** — this satisfies rule 8 (evidence required) above:

```bash
git diff --stat
cat <changed_file>
```

If nothing changed or the result is wrong: either fix it yourself, or re-issue the
task to Qwen with a more precise target (exact file, exact function, exact expected
output). Never mark a `PLAN.md` stage complete based on Qwen's own report alone.

### Scope for delegation

Delegate to Qwen: mechanical/rote code changes with a clear, narrow spec (add a
field, write a migration matching an existing pattern, write tests for a function
you specify). Do NOT delegate: stage planning, architecture calls, anything touching
the hard rules above, race-safety logic, or migration ordering — do those yourself.

### Escalation to Fable/Opus (manual, user-mediated)

You have no direct API access to Fable or Opus — they're used manually by the user
in claude.ai. Suggest escalation (don't block on it) for: architecture decisions with
lasting consequences, or final review before marking a major stage/PLAN.md milestone
done. Routine work stays with you + Qwen.
