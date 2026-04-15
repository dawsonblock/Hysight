# BOOTSTRAP

- Where the Python package lives: `./hca`
- How it is installed: `make venv` creates `.venv`, installs baseline requirements, and installs `./hca` editable through `backend/requirements-test.txt`
- What command proves it: `python scripts/run_tests.py`
- What failure looks like: the proof runner or backend launcher reports that the Python runtime package must resolve from `./hca`, shows the mismatched path or `sys.prefix`, and tells you to run `make venv`