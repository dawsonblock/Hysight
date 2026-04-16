# BOOTSTRAP

- Where the Python package lives: `./hca`
- How it is installed: `make venv` creates `.venv`, installs baseline requirements, and installs `./hca` editable through `backend/requirements-test.txt`
- What command proves it: `python scripts/run_tests.py`
- How frontend proof is bootstrapped: `make test-bootstrap-frontend` installs the pinned Yarn dependencies under Node 20 / Yarn 1.22.22, and `make proof-frontend` runs the canonical frontend proof wrapper
- What failure looks like: the proof runner or backend launcher reports that the Python runtime package must resolve from `./hca`, shows the mismatched path or `sys.prefix`, and tells you to run `make venv`