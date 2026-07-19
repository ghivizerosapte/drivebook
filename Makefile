.PHONY: run seed migrate

run:
	cd api && python -m uvicorn app.main:app --host 127.0.0.1 --port 8100 --reload

migrate:
	cd api && python -m app.migrate

seed:
	cd api && python -m app.seed --force
