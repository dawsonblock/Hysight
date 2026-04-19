# RELEASE_SEAL_HYSIGHT31

## 1. Executive release verdict
This tree is sealed as a clean release candidate for Hysight-main 31. The supported local-core proof path passed fresh from a clean copied tree, and the optional sidecar and frontend lanes were also freshly proved on this machine.

## 2. Repo fingerprint
- Workspace head: a1abb10a609d488f4541b3f4553feab041bf94e0
- Clean release tree: `/tmp/hysight31-release-seal`
- Repo fingerprint: `878d7cbe2b473c93ef15063c2509f89205cd7074`
- The clean-copy optional receipts use `commit_sha=local-worktree` because the release verification copy intentionally omitted `.git`; the head and fingerprint above tie them back to this exact sealed tree.

## 3. Machine facts
- OS: macOS 26.2 (25C56)
- Kernel: Darwin 25.2.0
- Architecture: arm64
- Python: 3.9.7
- rustc: 1.94.0
- cargo: 1.94.0
- Host Node: v25.9.0
- Frontend proof Node: v20.20.2
- Yarn: 1.22.22
- Release timestamp: 2026-04-19T21:27:45Z

## 4. Packaging result
PASS. Root editable install succeeded fresh.

## 5. Bootstrap result
PASS. `make venv` succeeded fresh and the supported proof path stayed clean.

## 6. Baseline result
- Pipeline: 7 passed
- Backend baseline: 98 passed
- Contract conformance: 18 passed
- Combined baseline: 123 passed, 0 skipped

## 7. Autonomy result
PASS. Bounded autonomy optional proof completed with 50 passed, 0 skipped.

## 8. Sidecar result
PASS. Live Rust sidecar proof completed with 13 passed and 2 skipped, and the live parity check completed with 4 passed. The fail-closed no-fallback check also passed with explicit `MemoryConfigurationError`.

## 9. Frontend result
PASS. The frontend proof completed with 20 passed, 0 skipped on Node 20.20.2 and Yarn 1.22.22.

## 10. Fresh receipts counted
- `artifacts/proof/pipeline.json`
- `artifacts/proof/backend-baseline.json`
- `artifacts/proof/contract.json`
- `artifacts/proof/baseline.json`
- `artifacts/proof/autonomy-optional.json`
- `artifacts/proof/live-sidecar.json`
- `artifacts/proof/frontend.json`

## 11. Historical receipts ignored
- `artifacts/proof/integration.json`
- `artifacts/proof/live-mongo.json`
- `FULL_PROOF_SUMMARY_HYSIGHT28.md`
- `FULL_PROOF_SUMMARY_HYSIGHT29.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT29.md`
- `RELEASE_SEAL_HYSIGHT29.md`

## 12. Remaining limitations
- Live Mongo was not rerun in this seal and remains historical only.
- Two supervisorctl-dependent restart checks still skip on hosts without `supervisorctl`.

## 13. Final release classification
sealed full-proof release
