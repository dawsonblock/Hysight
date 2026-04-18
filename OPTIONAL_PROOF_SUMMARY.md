# Optional Proof Summary

Scope
- Verify only the two optional proof surfaces from a fresh clone of commit `ef7815b0781ff2c1b7d4cbda0cb3f56d05af502c`.
- Fresh verification clone: `/tmp/hysight-main-4-verify.yzhpqn`

Machine Facts
- OS: macOS 26.2 / Darwin 25.2.0 / arm64
- Python: 3.9.7
- Rust: rustc 1.94.0 / cargo 1.94.0
- Host Node: v25.9.0
- Host Yarn: 1.22.22
- Workspace machine-facts transcript: `artifacts/proof/optional_env_facts.txt`

Bootstrap Gate
- `make clean-venv || true` recorded the expected `No rule to make target 'clean-venv'` message.
- `make venv` succeeded in the fresh clone.
- `./.venv/bin/python scripts/run_tests.py` succeeded in the fresh clone with 121 passed, 0 skipped.
- Workspace bootstrap transcript: `artifacts/proof/bootstrap_optional_verify.log`

Live Rust Sidecar Parity
- Supported startup path confirmed from the repo under test:
  - `make run-memvid-sidecar`
  - `cargo run --manifest-path memvid_service/Cargo.toml --release`
- Live sidecar launched from the fresh clone with isolated data on port `3041`.
- Health endpoint verified at `GET /health`.
- External-service proof receipt:
  - Fresh receipt: `/tmp/hysight-main-4-verify.yzhpqn/artifacts/proof/live-sidecar.json`
  - Fresh transcript: `/tmp/hysight-main-4-verify.yzhpqn/artifacts/proof/sidecar_parity_live.txt`
  - Result: `./.venv/bin/python scripts/run_tests.py --sidecar` passed with 13 passed, 2 skipped.
  - The two skipped tests were the `supervisorctl`-dependent restart cases in `backend/tests/test_memvid_sidecar.py`.
- Committed parity suite receipt-by-transcript:
  - `./.venv/bin/python -m pytest backend/tests/test_memvid_sidecar_parity.py -q -ra --run-live`
  - Result: 4 passed.
  - Coverage includes local-vs-rust contract parity, restart persistence, and explicit outage behavior.
- No-fallback proof:
  - Fresh transcript: `/tmp/hysight-main-4-verify.yzhpqn/artifacts/proof/sidecar_no_fallback.txt`
  - After the live sidecar was stopped, rust-backed backend startup failed explicitly with `MemoryConfigurationError` on the sidecar health probe.
  - This proves there is no silent fallback to the local python backend when `MEMORY_BACKEND=rust` is active.

Frontend Proof On Supported Toolchain
- Repo-declared supported runtime confirmed from the fresh clone:
  - `frontend/package.json` -> Node `20.x`, Yarn `1.22.22`
  - `frontend/.tool-versions` and `frontend/mise.toml` -> Node `20.20.2`, Yarn `1.22.22`
- Host Node `v25.9.0` was correctly treated as unsupported for proof.
- A portable supported toolchain was staged locally under `/tmp/hysight-node20-tools` and placed first on `PATH`.
- Frontend dependencies were installed under the supported runtime with:
  - `PATH=/tmp/hysight-node20-tools/node_modules/.bin:$PATH yarn --cwd /tmp/hysight-main-4-verify.yzhpqn/frontend install --frozen-lockfile`
- Fresh frontend proof receipt:
  - `/tmp/hysight-main-4-verify.yzhpqn/artifacts/proof/frontend.json`
- Fresh frontend proof transcript:
  - `/tmp/hysight-main-4-verify.yzhpqn/artifacts/proof/frontend_proof_live.log`
- Result: `/tmp/hysight-main-4-verify.yzhpqn/.venv/bin/python /tmp/hysight-main-4-verify.yzhpqn/scripts/proof_frontend.py` passed with 20 passed, 0 skipped.
- Covered stages:
  - runtime verification on Node `v20.20.2` / Yarn `1.22.22`
  - backend-owned frontend fixture drift gate: 1 passed
  - frontend lint: passed
  - frontend Jest: 19 passed across 5 suites
  - production build: passed

Residual Caveat
- The external-service sidecar suite still skips the two `supervisorctl`-gated restart tests when `supervisorctl` is unavailable.
- That is not a proof blocker here because the committed parity suite independently passed restart persistence and outage checks against real sidecars in the same clean clone.

Final Classification
- Live Rust sidecar parity: proved on this machine for commit `ef7815b0781ff2c1b7d4cbda0cb3f56d05af502c`.
- Frontend proof on the supported toolchain: proved on this machine with Node `20.20.2` and Yarn `1.22.22`.
- The optional surfaces are reproducible when run from a clean clone with the supported runtime constraints. They are not part of the default local baseline and still depend on explicit operator setup.