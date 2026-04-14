.PHONY: \
	test-bootstrap \
	dev-bootstrap \
	test \
	test-pipeline \
	test-contract \
	test-backend-local \
	test-backend \
	test-mongo-live \
	test-sidecar \
	proof-sidecar \
	run-memvid-sidecar \
	run \
	run-sidecar \
	docker-build \
	docker-build-sidecar

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest
LIVE_MONGO_URL ?= mongodb://127.0.0.1:27017
LIVE_MONGO_DB_NAME ?= hysight_live
MEMORY_SERVICE_PORT ?= 3031
MEMORY_SERVICE_URL ?= http://localhost:$(MEMORY_SERVICE_PORT)

test-bootstrap:
	$(PIP) install -r backend/requirements-test.txt

dev-bootstrap:
	$(PIP) install -r backend/requirements-dev.txt

test: test-pipeline test-backend

test-pipeline:
	$(PYTEST) tests/test_hca_pipeline.py -q

test-contract:
	$(PYTEST) backend/tests/test_contract_conformance.py -q

test-backend-local:
	$(PYTEST) \
		backend/tests/test_hca.py \
		backend/tests/test_memory.py \
		backend/tests/test_server_bootstrap.py \
		-q

test-backend:
	$(PYTEST) backend/tests -q

test-mongo-live:
	RUN_MONGO_TESTS=1 MONGO_URL="$(LIVE_MONGO_URL)" DB_NAME="$(LIVE_MONGO_DB_NAME)" \
		$(PYTEST) backend/tests/test_status_live_mongo.py -q

test-sidecar:
	@curl --fail --silent "$(MEMORY_SERVICE_URL)/health" >/dev/null || { \
		echo "test-sidecar requires a healthy memvid sidecar at $(MEMORY_SERVICE_URL)/health. Start the sidecar first with make run-memvid-sidecar, or run make test for the mock-backed proof surface."; \
		exit 1; \
	}
	RUN_MEMVID_TESTS=1 MEMORY_BACKEND=rust MEMORY_SERVICE_URL="$(MEMORY_SERVICE_URL)" \
		$(PYTEST) backend/tests/test_memvid_sidecar.py -q

proof-sidecar:
	RUN_MEMVID_TESTS=1 MEMORY_SERVICE_URL="$(MEMORY_SERVICE_URL)" \
		$(PYTHON) scripts/run_tests.py --sidecar

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