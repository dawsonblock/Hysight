.PHONY: test-bootstrap dev-bootstrap

PYTHON ?= python

test-bootstrap:
	$(PYTHON) -m pip install -e ./hca -r backend/requirements-test.txt

dev-bootstrap:
	$(PYTHON) -m pip install -e ./hca -r backend/requirements-dev.txt