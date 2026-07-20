VENV = api/.venv
PY   = $(VENV)/bin/python

.PHONY: install run migrate seed

install:
	python3 -m venv $(VENV)
	$(PY) -m pip install -q -r api/requirements.txt

run: $(VENV)
	cd api && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100 --reload

migrate: $(VENV)
	cd api && .venv/bin/python -m app.migrate

seed: $(VENV)
	cd api && .venv/bin/python -m app.seed --force

$(VENV):
	@echo "No venv — run: make install"
	@exit 1
