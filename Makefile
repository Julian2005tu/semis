PY = ./venv/bin/python

.PHONY: seed seed-reset test backend frontend

# Wraps `python data/seed/load_seed.py run1 run2` with the credentials from backend/.env.
seed:
	cd backend && $(PY) -m scripts.seed run1 run2

seed-reset:
	cd backend && $(PY) -m scripts.seed --reset run1 --reset run2 run1 run2

test:
	cd backend && $(PY) -m unittest -v test_api

backend:
	cd backend && $(PY) main.py

frontend:
	cd frontend && npm run dev
