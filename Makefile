.PHONY: \
	dev \
	venv \
	test-bootstrap \
	test-bootstrap-frontend \
	test-bootstrap-integration \
	dev-bootstrap \
	test \
	test-pipeline \
	test-contract \
	test-backend-baseline \
	test-backend-integration \
	proof-frontend \
	proof-mongo-live \
	test-mongo-live \
	test-sidecar \
	proof-sidecar \
	test-fixture-drift \
	run-memvid-sidecar \
	run \
	run-unified \
	run-unified-sidecar \
	run-sidecar \
	docker-build \
	docker-build-sidecar

VENV_DIR ?= .venv
VENV_PYTHON := $(if $(wildcard $(VENV_DIR)/bin/python),$(abspath $(VENV_DIR)/bin/python),python)
PYTHON ?= $(VENV_PYTHON)
PIP ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest
LIVE_MONGO_PORT ?= 27017
LIVE_MONGO_URL ?= mongodb://127.0.0.1:$(LIVE_MONGO_PORT)
LIVE_MONGO_DB_NAME ?= hysight_live
LIVE_MONGO_IMAGE ?= mongo:7
MEMORY_SERVICE_PORT ?= 3031
MEMORY_SERVICE_URL ?= http://localhost:$(MEMORY_SERVICE_PORT)

dev: venv

venv:
	python -m venv $(VENV_DIR)
	$(abspath $(VENV_DIR))/bin/python -m pip install --upgrade pip
	$(abspath $(VENV_DIR))/bin/python -m pip install -r backend/requirements-test.txt
	@echo "Created $(VENV_DIR), installed baseline requirements, and installed editable ./hca. Next: make test"

test-bootstrap:
	$(PIP) install -r backend/requirements-test.txt

test-bootstrap-frontend:
	cd frontend && yarn install --frozen-lockfile

test-bootstrap-integration:
	$(PIP) install -r backend/requirements-test.txt -r backend/requirements-integration.txt

dev-bootstrap:
	$(PIP) install -r backend/requirements-dev.txt

test:
	$(PYTHON) scripts/run_tests.py

test-pipeline:
	$(PYTHON) scripts/run_tests.py --baseline-step pipeline

test-contract:
	$(PYTHON) scripts/run_tests.py --baseline-step contract

test-backend-baseline:
	$(PYTHON) scripts/run_tests.py --baseline-step backend-baseline

test-backend-integration:
	$(PYTHON) scripts/run_tests.py --integration

proof-frontend:
	$(PYTHON) scripts/proof_frontend.py

proof-mongo-live:
	$(PYTHON) scripts/proof_mongo_live.py --image "$(LIVE_MONGO_IMAGE)" --port "$(LIVE_MONGO_PORT)" --db-name "$(LIVE_MONGO_DB_NAME)"

test-mongo-live:
	RUN_MONGO_TESTS=1 MONGO_URL="$(LIVE_MONGO_URL)" DB_NAME="$(LIVE_MONGO_DB_NAME)" \
		$(PYTHON) scripts/run_tests.py --mongo-live

test-sidecar:
	RUN_MEMVID_TESTS=1 MEMORY_BACKEND=rust MEMORY_SERVICE_URL="$(MEMORY_SERVICE_URL)" \
		$(PYTHON) scripts/run_tests.py --sidecar

proof-sidecar:
	MEMORY_SERVICE_URL="$(MEMORY_SERVICE_URL)" MEMORY_SERVICE_PORT="$(MEMORY_SERVICE_PORT)" \
		$(PYTHON) scripts/proof_sidecar.py

test-fixture-drift:
	$(PYTEST) backend/tests/test_server_bootstrap.py -q --check-fixture-drift -k generated_frontend_api_fixtures_match_backend_export

run-memvid-sidecar:
	MEMORY_SERVICE_PORT="$(MEMORY_SERVICE_PORT)" \
		cargo run --manifest-path memvid_service/Cargo.toml --release

run:
	./scripts/run_backend.sh

run-unified:
	./scripts/launch_unified.sh

run-unified-sidecar:
	MEMORY_BACKEND=rust MEMORY_SERVICE_URL="$(MEMORY_SERVICE_URL)" ./scripts/launch_unified.sh

run-sidecar:
	# MEMORY_SERVICE_URL defaults to http://localhost:$(MEMORY_SERVICE_PORT) when unset
	MEMORY_BACKEND=rust MEMORY_SERVICE_URL="$(MEMORY_SERVICE_URL)" ./scripts/run_backend.sh

docker-build:
	docker build -f backend/Dockerfile -t hysight-backend .

docker-build-sidecar:
	docker build -f memvid_service/Dockerfile -t hysight-sidecar .