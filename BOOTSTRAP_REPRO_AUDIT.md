# Bootstrap Repro Audit

## Verdict

- A fresh clean-start clone reached the declared local baseline proof surface using the documented README quick-start commands only.
- No undocumented manual repair step was required for the baseline backend proof path.

## Exact clean-start command transcript

```bash
tmpdir=$(mktemp -d /tmp/hysight-bootstrap-audit.XXXXXX)
echo "BOOTSTRAP_AUDIT_DIR=$tmpdir"
git clone --depth 1 "file:///Users/dawsonblock/Hysight" "$tmpdir"
cd "$tmpdir"
make venv
cp .env.example .env
make test-bootstrap
make test
```

Observed result highlights:

- `make venv` created `.venv`, upgraded `pip`, and installed `backend/requirements-test.txt` including editable `./hca`.
- `cp .env.example .env` succeeded without extra prep.
- `make test-bootstrap` completed without requiring any additional hidden state.
- `make test` ran `scripts/run_tests.py` and passed the declared baseline: 7 pipeline, 96 backend baseline, 18 contract conformance, 121 total passed.

## Proven

- The repo-local `.venv` bootstrap is reproducible from a fresh clone.
- The documented baseline proof command produces fresh receipts from the documented path.
- The published bootstrap instructions are sufficient for the default local proof surface.
- Root `python -m pip install -e '.[dev]'` is a tooling-only workspace install and is not part of the supported runtime bootstrap path, which remains `make venv` plus editable `./hca`.

## Undocumented manual steps

- None for the default local backend proof path.

## Mismatches and friction

- `make test-bootstrap` is redundant immediately after `make venv`, because `make venv` already installs the same baseline Python requirements.
- `source .venv/bin/activate` is useful interactively but not required when following the documented `make` targets exactly.

## Minimal patch plan

- No blocker patch is required for the baseline bootstrap path.
- Optional cleanup only: document that `make test-bootstrap` is redundant after `make venv` so operators understand there is one real bootstrap source of truth.