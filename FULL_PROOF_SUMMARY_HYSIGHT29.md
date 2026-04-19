# Hysight-main 29 full proof summary

## 1. Final classification
sealed full-proof release

## 2. Scope rule used
Only receipts regenerated from the clean release tree at `/tmp/hysight29-release-seal` during the 2026-04-19 seal run were counted as authoritative. Historical receipts remain present in the repository for audit history only and were not used as release evidence.

## 3. Release freeze and handoff check
- Root packaging install: PASS via `python -m pip install -e '.[dev]'`
- Supported bootstrap: PASS via `make venv`
- `.pkg-venv` contamination check: PASS; the supported proof path resolved imports from the repo-local `.venv`
- Release environment facts were written to `artifacts/proof/release_env.txt`

## 4. Fresh local-core proof
- HCA pipeline: 7 passed
- Backend baseline: 98 passed, 1 deselected
- Contract conformance: 18 passed
- Combined baseline: 123 passed, 0 skipped

## 5. Fresh autonomy proof
- Bounded autonomy optional surface: 50 passed, 0 skipped

## 6. Fresh sidecar proof
- Live Rust sidecar proof: 13 passed, 2 skipped
- The proof fell forward from localhost:3031 to localhost:3032 because the default port was occupied and unhealthy
- The two skips still require `supervisorctl` on the host PATH for restart orchestration

## 7. Fresh no-fallback result
With Rust memory mode configured and the sidecar unavailable, startup failed explicitly with `MemoryConfigurationError`. No silent fallback to the Python-local memory authority was observed.

## 8. Fresh frontend proof
- Runtime verification passed on Node 20.20.2 and Yarn 1.22.22
- Fixture drift gate: 1 passed
- Lint: PASS
- Jest: 5 suites and 19 tests passed
- Production build: PASS
- Combined frontend proof: 20 passed, 0 skipped

## 9. Fresh receipts counted
- `artifacts/proof/pipeline.json`
- `artifacts/proof/backend-baseline.json`
- `artifacts/proof/contract.json`
- `artifacts/proof/baseline.json`
- `artifacts/proof/autonomy-optional.json`
- `artifacts/proof/live-sidecar.json`
- `artifacts/proof/frontend.json`

## 10. Historical receipts ignored
- `artifacts/proof/integration.json`
- `artifacts/proof/live-mongo.json`
- prior `hysight27_*`, `hysight28_*`, and pre-seal `hysight29_*` support artifacts
- older summary and quarantine notes that predate this release seal

## 11. Remaining limitations
- The live Mongo proof was not rerun in this release seal and remains historical-only.
- Sidecar restart orchestration still skips the two `supervisorctl`-dependent checks on hosts without `supervisorctl`.

## 12. Conclusion
The current tree is now release-sealed against fresh evidence: the supported install and proof paths pass from a clean copied tree, the receipt counts match the exact current code, and historical receipts are quarantined rather than counted as fresh.
