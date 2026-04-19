# Hysight-main 32 full proof summary

## 1. Executive verdict
sealed full-proof release

## 2. Repo fingerprint
- Workspace head: `61182bb045e948c3b190ba9904111b204efd3f7c`
- Clean release tree: `/tmp/hysight32-release-seal`
- Repo fingerprint: `239d5ca45d4af85156ce51c00b13711fcd09ffda`
- The clean-copy optional receipts show `commit_sha=local-worktree` because the verification copy intentionally omitted `.git`; the head and fingerprint above bind those receipts to this exact 32 tree.

## 3. Machine facts
- OS: macOS 26.2 (25C56)
- Kernel: Darwin 25.2.0 on arm64
- Python: 3.9.7
- rustc: 1.94.0
- cargo: 1.94.0
- Host Node: v25.9.0
- Frontend proof Node: v20.20.2
- Yarn: 1.22.22
- Release seal timestamp: 2026-04-19T22:48:40Z

## 4. Root packaging result
PASS. The root meta-project install path succeeded fresh through `python -m pip install -e '.[dev]'`.

## 5. Bootstrap result
PASS. `make venv` succeeded fresh in the clean release tree, and the supported proof path did not resolve imports through `.pkg-venv`.

## 6. Fresh baseline result
- Pipeline: 7 passed
- Backend baseline: 98 passed, 1 deselected
- Contract conformance: 18 passed
- Combined baseline: 123 passed, 0 skipped

## 7. Fresh autonomy result
- Bounded autonomy optional: 50 passed, 0 skipped

## 8. Sidecar result
- Live Rust sidecar proof: 13 passed, 2 skipped
- Live sidecar parity: 4 passed
- The live proof ran against `http://localhost:3032`.
- The two skips remain the supervisorctl-dependent restart checks.

## 9. Frontend result
- Runtime verification passed on Node 20.20.2 and Yarn 1.22.22
- Fixture drift gate: 1 passed
- Lint: PASS
- Jest: 5 suites and 19 tests passed
- Production build: PASS
- Combined frontend proof: 20 passed, 0 skipped

## 10. Fresh receipts counted
- `artifacts/proof/pipeline.json`
- `artifacts/proof/backend-baseline.json`
- `artifacts/proof/contract.json`
- `artifacts/proof/baseline.json`
- `artifacts/proof/autonomy-optional.json`
- `artifacts/proof/live-sidecar.json`
- `artifacts/proof/frontend.json`
- `artifacts/proof/release_env_hysight32.txt`
- `artifacts/proof/release_import_check_hysight32.log`

## 11. Historical receipts ignored
- `artifacts/proof/integration.json`
- `artifacts/proof/live-mongo.json`
- `FULL_PROOF_SUMMARY_HYSIGHT28.md`
- `FULL_PROOF_SUMMARY_HYSIGHT29.md`
- `FULL_PROOF_SUMMARY_HYSIGHT31.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT29.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT31.md`
- `RELEASE_SEAL_HYSIGHT29.md`
- `RELEASE_SEAL_HYSIGHT31.md`
- older Hysight 27 and 28 support artifacts

## 12. Remaining limitations
- Live Mongo proof was not rerun in the 32 seal and remains historical only.
- Two sidecar restart checks still skip on hosts without `supervisorctl` in PATH.

## 13. Final classification
sealed full-proof release
