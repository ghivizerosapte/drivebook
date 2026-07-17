# DriveBook
Independent multi-channel online booking module for a Chișinău driving school.

See [SPEC.md](./SPEC.md), [PLAN.md](./PLAN.md), [AGENTS.md](./AGENTS.md).

## Quick start
```bash
docker compose up -d db
cd api && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.migrate && python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8100
```

- API docs: http://127.0.0.1:8100/docs
- Book: http://127.0.0.1:8100/book
- Admin: http://127.0.0.1:8100/admin/
