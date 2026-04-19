# RELEASE_SEAL_HYSIGHT29

## 1. Executive release verdict
The current Hysight-main 29 tree is sealed on this machine. The supported install, bootstrap, baseline, autonomy, sidecar, and frontend proof paths all passed fresh from a clean copied tree.

## 2. Repo fingerprint
- Branch: main
- Head SHA: 519889213d3310828ba8229d83d4ffd4e5fa1702
- Tracked tree SHA-256: 7d8d8cddd3f267325a2ca247348ed2a1058c112831c4b41ac1f9b2f1b3f5c9df
- Source repo path: /Users/dawsonblock/Hysight
- Clean release tree: /tmp/hysight29-release-seal

## 3. Machine facts
- OS: macOS 26.2 (25C56)
- Kernel: Darwin 25.2.0
- Architecture: arm64
- Python: 3.9.7
- rustc: 1.94.0
- cargo: 1.94.0
- Host Node: v25.9.0
- Release-proof Node: v20.20.2
- Yarn: 1.22.22
- Release timestamp: 2026-04-19T21:03:04Z

## 4. Packaging result
PASS. `python -m pip install -e '.[dev]'` completed fresh in the clean release tree.

## 5. Bootstrap result
PASS. `make venv` completed fresh in the clean release tree, and the `.pkg-venv` contamination check stayed clean.

## 6. Baseline result
- HCA pipeline: 7 passed
- Backend baseline: 98 passed, 1 deselected
- Contract conformance: 18 passed
- Combined baseline: 123 passed, 0 skipped

## 7. Autonomy result
PASS. Bounded autonomy optional proof completed with 50 passed, 0 skipped.

## 8. Sidecar result
PASS. Live Rust sidecar proof completed with 13 passed and 2 skipped. The run fell forward to localhost:3032 because localhost:3031 was occupied and unhealthy. The fail-closed no-fallback check also passed with explicit MemoryConfigurationError.

## 9. Frontend result
PASS. The frontend proof completed with 20 passed, 0 skipped on Node 20.20.2 and Yarn 1.22.22.

## 10. Fresh receipts counted
- artifacts/proof/pipeline.json
- artifacts/proof/backend-baseline.json
- artifacts/proof/contract.json
- artifacts/proof/baseline.json
- artifacts/proof/autonomy-optional.json
- artifacts/proof/live-sidecar.json
- artifacts/proof/frontend.json

## 11. Historical receipts ignored
- artifacts/proof/integration.json
- artifacts/proof/live-mongo.json
- historical hysight27, hysight28, and pre-seal hysight29 support artifacts and notes

## 12. Remaining limitations
- The live Mongo proof was not rerun in this seal and remains historical only.
- Two sidecar restart checks still skip on hosts without `supervisorctl` in PATH.

## 13. Final release classification
sealed full-proof release
