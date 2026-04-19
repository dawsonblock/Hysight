# OPTIONAL_PROOF_SUMMARY_HYSIGHT27

## 1. Executive verdict

**Classification: optional surfaces freshly proved**

Reason: the repo's committed live Rust sidecar proof scope passed fresh in this run, the sidecar no-fallback check also passed fresh, and the frontend proof now passes fresh on the exact supported runtime after the backend-owned fixture exporter was synced to the current subsystem schema.

## 2. Machine facts

- Date of run: 2026-04-19 UTC
- Initial audit target: current clean workspace HEAD selected interactively after no distinct “Hysight-main 27.zip” was found
- Current proof state: post-repair workspace rerun after syncing the backend-owned frontend fixture exporter
- Commit: `aad7d10251c53b2b97c989dd3b750124d93d74fe`
- OS: macOS 26.2
- Kernel / arch: Darwin 25.2.0 / arm64
- Python: 3.9.7
- Rust: rustc 1.94.0
- Cargo: 1.94.0
- System Node: 25.9.0
- Supported runtime staged for proof: Node 20.20.2 from a portable local download
- Yarn: 1.22.22
- Absolute repo path: `/Users/dawsonblock/Hysight`

Machine-facts transcript: `artifacts/proof/hysight27_optional_env.txt`

## 3. Repo fingerprint

- Fingerprint command executed: `find . -type f | sort | shasum | shasum` with generated/runtime directories excluded
- Result: `d7279460257480c3d919562d0e7ecf5b88c5b3ee`

## 4. Prerequisite truth check

Commands run:
- `python3 -m venv .pkg-venv`
- `./.pkg-venv/bin/python -m pip install -U pip`
- `./.pkg-venv/bin/python -m pip install -e '.[dev]'`
- `make venv`
- `./.venv/bin/python scripts/run_tests.py`
- `./.venv/bin/python scripts/run_tests.py --autonomy`

Fresh results:
- Root meta-project editable install: **passed**
- Supported bootstrap (`make venv`): **passed**
- Canonical baseline proof: **123 passed, 0 skipped**
  - Pipeline: 7 passed
  - Backend baseline: 98 passed, 1 deselected
  - Contract: 18 passed
- Bounded autonomy optional proof: **50 passed, 0 skipped**

Transcript: `artifacts/proof/hysight27_prereq.log`

## 5. Live Rust sidecar result

Commands run:
- `cargo run --manifest-path memvid_service/Cargo.toml --release` with isolated `MEMORY_DATA_DIR` and port `3041`
- `MEMORY_SERVICE_URL=http://127.0.0.1:3041 MEMORY_BACKEND=rust ./.venv/bin/python scripts/run_tests.py --sidecar`
- `./.venv/bin/python -m pytest backend/tests/test_memvid_sidecar_parity.py -q -ra --run-live`

Fresh result:
- Sidecar health endpoint reachable
- Live sidecar proof: **13 passed, 2 skipped**
- Live parity suite: **4 passed**

Interpretation:
- The repo's committed live sidecar proof scope **passed fresh** on this revision.
- Two restart-specific cases were skipped because `supervisorctl` is not present, so this result should not be read as proof of those skipped restart-only cases.

Receipts:
- `artifacts/proof/live-sidecar.json`
- `test_reports/pytest/backend-live-sidecar-proof.xml`
- `artifacts/proof/hysight27_sidecar_proof.txt`

## 6. No-fallback result

Command run:
- with the sidecar stopped, `MEMORY_BACKEND=rust MEMORY_SERVICE_URL=http://127.0.0.1:3041 ./.venv/bin/python ... create_app()`

Fresh result:
- **Explicit failure observed**
- Error: `MemoryConfigurationError` on the sidecar health probe with connection refused

Interpretation:
- No silent fallback to Python-local memory was observed.
- This negative proof **passed**.

Receipt:
- `artifacts/proof/hysight27_sidecar_no_fallback.txt`

## 7. Frontend result

Commands run:
- portable Node 20 staged locally and prepended to `PATH`
- `yarn --cwd frontend install --frozen-lockfile`
- `./.venv/bin/python scripts/proof_frontend.py`

Fresh result:
- Runtime verification: **passed** on Node **20.20.2** and Yarn **1.22.22**
- Frontend fixture-drift gate: **passed** after syncing the backend-owned fixture exporter with the current `SubsystemsResponse` shape
- Frontend proof: **passed (20 passed, 0 skipped)**

Interpretation:
- The frontend surface is **freshly proved now** on the exact supported runtime.
- The earlier drift in this session was real, but it has now been corrected and re-proved with a fresh passing receipt.

Receipts:
- `artifacts/proof/frontend.json`
- `test_reports/frontend-fixture-drift.xml`
- `artifacts/proof/hysight27_frontend_live_rerun.log`

Note:
- `artifacts/proof/hysight27_frontend_live.log` is retained as the earlier failing diagnostic transcript from this same session, but it is superseded by the passing rerun receipt and is not used for the final classification.

## 8. Route-to-runtime integrity

Result: **PASS**

Findings:
- Autonomy routes delegate to the supervisor and storage; they do not execute tools directly.
- `AutonomySupervisor.launch_run()` calls `Runtime.create_autonomous_run(...)`.
- The resulting run is a normal HCA run with `autonomy_agent_id`, `autonomy_trigger_id`, and `autonomy_mode` metadata.
- Observation and continuation use the standard event log and persisted run state.

Report:
- `artifacts/proof/hysight27_route_integrity.md`

## 9. Negative proofs

Fresh results:
- Sidecar-down explicit failure: **passed**
- High-risk autonomy escalation checks: **2 passed**
- Restart duplicate prevention checks: **6 passed**
- Kill-switch enforcement checks: **3 passed**

Report:
- `artifacts/proof/hysight27_negative_proofs.md`
- supporting transcript: `artifacts/proof/hysight27_negative_proofs.txt`

## 10. Fresh receipts generated

- `artifacts/proof/baseline.json`
- `artifacts/proof/autonomy-optional.json`
- `artifacts/proof/live-sidecar.json`
- `artifacts/proof/frontend.json`
- `artifacts/proof/hysight27_optional_env.txt`
- `artifacts/proof/hysight27_prereq.log`
- `artifacts/proof/hysight27_sidecar_notes.txt`
- `artifacts/proof/hysight27_sidecar_live.log`
- `artifacts/proof/hysight27_sidecar_proof.txt`
- `artifacts/proof/hysight27_sidecar_no_fallback.txt`
- `artifacts/proof/hysight27_frontend_notes.txt`
- `artifacts/proof/hysight27_frontend_live.log`
- `artifacts/proof/hysight27_route_integrity.md`
- `artifacts/proof/hysight27_negative_proofs.md`
- `artifacts/proof/hysight27_optional_honesty.md`
- `test_reports/pytest/backend-live-sidecar-proof.xml`
- `test_reports/frontend-fixture-drift.xml`

## 11. Historical receipts ignored

These were present in the repo but were **not** used for classification because they were not generated in this run:

- `artifacts/proof/integration.json`
- `artifacts/proof/live-mongo.json`
- `artifacts/proof/backend-baseline.json`
- earlier optional-summary markdown files referencing older commits and older proof counts

## 12. Blockers

- No remaining proof blocker was observed in the current rerun.
- Earlier in this session, the frontend fixture exporter lagged the backend subsystem schema; that mismatch was corrected and the frontend proof was re-run successfully.
- No blocker prevented the sidecar proof from running.

## 13. Final classification for the current workspace state

**optional surfaces freshly proved**

Rationale under the requested rules:
- prerequisites were freshly re-proved
- live sidecar proof and no-fallback proof both passed fresh
- frontend proof was re-run fresh on the exact supported runtime and passed
- therefore the optional surfaces exercised in this run are **freshly proved**