.PHONY: \
	venv \
	test-bootstrap \
	test-bootstrap-integration \
	dev-bootstrap \
	test \
	test-pipeline \
	test-contract \
	test-backend-baseline \
	test-backend-integration \
	proof-mongo-live \
	test-mongo-live \
	test-sidecar \
	proof-sidecar \
	run-memvid-sidecar \
	run \
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

venv:
	python -m venv $(VENV_DIR)
	@echo "Created $(VENV_DIR). Activate it with: source $(VENV_DIR)/bin/activate"

test-bootstrap:
	$(PIP) install -r backend/requirements-test.txt

test-bootstrap-integration:
	$(PIP) install -r backend/requirements-test.txt -r backend/requirements-integration.txt

dev-bootstrap:
	$(PIP) install -r backend/requirements-dev.txt

test:
	$(PYTHON) scripts/run_tests.py

test-pipeline:
	$(PYTEST) tests/test_hca_pipeline.py -q

test-contract:
	$(PYTEST) backend/tests/test_contract_conformance.py -q

test-backend-baseline:
	$(PYTEST) \
		backend/tests/test_hca.py \
		backend/tests/test_memory.py \
		backend/tests/test_server_bootstrap.py \
		-q

test-backend-integration:
	$(PYTEST) backend/tests/test_memvid_sidecar.py -q --run-integration

proof-mongo-live:
	$(PYTHON) scripts/proof_mongo_live.py --image "$(LIVE_MONGO_IMAGE)" --port "$(LIVE_MONGO_PORT)" --db-name "$(LIVE_MONGO_DB_NAME)"

test-mongo-live:
	RUN_MONGO_TESTS=1 MONGO_URL="$(LIVE_MONGO_URL)" DB_NAME="$(LIVE_MONGO_DB_NAME)" \
		$(PYTEST) backend/tests/test_status_live_mongo.py -q --run-live

test-sidecar:
	@curl --fail --silent "$(MEMORY_SERVICE_URL)/health" >/dev/null || { \
		echo "test-sidecar requires a healthy memvid sidecar at $(MEMORY_SERVICE_URL)/health. Start the sidecar first with make run-memvid-sidecar."; \
		exit 1; \
	}
	RUN_MEMVID_TESTS=1 MEMORY_BACKEND=rust MEMORY_SERVICE_URL="$(MEMORY_SERVICE_URL)" \
		$(PYTEST) backend/tests/test_memvid_sidecar.py -q --run-live

proof-sidecar:
	MEMORY_SERVICE_URL="$(MEMORY_SERVICE_URL)" MEMORY_SERVICE_PORT="$(MEMORY_SERVICE_PORT)" \
		$(PYTHON) scripts/proof_sidecar.py

run-memvid-sidecar:
	MEMORY_SERVICE_PORT="$(MEMORY_SERVICE_PORT)" \
		cargo run --manifest-path memvid_service/Cargo.toml --release

run:
	./scripts/run_backend.sh

run-sidecar:
	# MEMORY_SERVICE_URL defaults to http://localhost:$(MEMORY_SERVICE_PORT) when unset
	MEMORY_BACKEND=rust MEMORY_SERVICE_URL="$(MEMORY_SERVICE_URL)" ./scripts/run_backend.sh

docker-build:
	docker build -f backend/Dockerfile -t hysight-backend .

docker-build-sidecar:
	docker build -f memvid_service/Dockerfile -t hysight-sidecar .