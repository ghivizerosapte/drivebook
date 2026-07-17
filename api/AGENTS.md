# api/ — Core booking API

## Scope
FastAPI app, SQL migrations, seed, static mounts for widget/admin later.

## Rules
- SQL only via asyncpg; no SQLAlchemy models as source of truth
- Schema changes = new `migrations/00N_*.sql` file, never edit applied migrations
- DB claim for slots must use `UPDATE ... WHERE status='open' RETURNING`
- Config via env: `DATABASE_URL`, default `postgresql://drivebook:drivebook@127.0.0.1:5433/drivebook`
- Port 8100

## Layout
```
api/
  AGENTS.md
  requirements.txt
  migrations/
    001_init.sql
  app/
    __init__.py
    config.py
    db.py
    migrate.py
    seed.py
    main.py
    routes/
```

## Commands
```bash
python -m app.migrate
python -m app.seed
uvicorn app.main:app --port 8100
```
