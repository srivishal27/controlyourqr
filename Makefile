.PHONY: help venv install dev test lint icons vendor clean

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

help:
	@echo "make install   Create .venv and install dev dependencies"
	@echo "make dev       Run the development server on http://127.0.0.1:5000"
	@echo "make serve     Run gunicorn locally, as production does"
	@echo "make test      Run the test suite"
	@echo "make icons     Regenerate favicon / touch icon / brand mark"
	@echo "make vendor    Rebuild the vendored QR encoder from upstream source"
	@echo "make clean     Remove build artefacts"

$(VENV):
	python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip

install: $(VENV)
	$(PIP) install --quiet -r requirements-dev.txt
	@echo "Ready. Run 'make dev'."

dev: install
	FLASK_ENV=development $(PY) wsgi.py

serve: install
	FLASK_ENV=production $(VENV)/bin/gunicorn --config gunicorn.conf.py wsgi:application

test: install
	$(VENV)/bin/pytest -q

icons:
	python3 tools/make_icons.py

vendor:
	./tools/build-vendor.sh

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov
