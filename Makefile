PY = ./venv/bin/python

.PHONY: seed test backend frontend

# Wraps `python data/seed/load_seed.py --rebuild` with the credentials from backend/.env:
# deletes all seed data, then loads every data/seed/runN folder in ascending order.
seed:
	cd backend && $(PY) -m scripts.seed --rebuild

test:
	cd backend && $(PY) -m unittest -v test_api

backend:
	cd backend && $(PY) main.py

frontend:
	cd frontend && npm run dev
