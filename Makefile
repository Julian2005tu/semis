PY = ./venv/bin/python

.PHONY: seed seed-reset test backend frontend

seed:
	cd backend && $(PY) -m scripts.seed

seed-reset:
	cd backend && $(PY) -m scripts.seed --reset

test:
	cd backend && $(PY) -m unittest -v test_api

backend:
	cd backend && $(PY) main.py

frontend:
	cd frontend && npm run dev
