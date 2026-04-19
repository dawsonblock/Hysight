# Hysight-main 28 full proof summary

## 1. Final classification
fresh full proof complete

## 2. Audit rule used
Only fresh execution from the clean isolated copy counted toward this result. Bundled receipts and older history artifacts were not trusted.

## 3. Clean execution environment
- Clean copy path: /tmp/hysight-main-28-verify2.HX9G0r
- Generated on: 2026-04-19
- OS: macOS 26.2 arm64
- Python: 3.9.7
- Rust: 1.94.0
- Node: 20.20.2
- Yarn: 1.22.22
- Repo fingerprint: 97ebe1a1cb1b35990a5b19d8373e329eae1d6ba7

## 4. Fresh prerequisite bootstrap
- Root editable install: PASS
- Supported bootstrap via make venv: PASS

## 5. Fresh local core proof
- Pipeline proof: 7 passed
- Backend baseline proof: 98 passed, 1 deselected
- Contract conformance proof: 18 passed
- Combined baseline result: 123 passed, 0 skipped

## 6. Fresh bounded autonomy proof
- Optional autonomy surface: 50 passed, 0 skipped

## 7. Fresh live sidecar proof
- Live sidecar proof: 13 passed, 2 skipped
- Live parity suite: 4 passed
- The two skips were restart hooks that require supervisorctl on the host PATH.

## 8. Fresh no-fallback proof
After the live sidecar was stopped, rust-backed startup failed explicitly with MemoryConfigurationError. No silent fallback to the Python-local memory backend was observed.

## 9. Fresh frontend proof
- Runtime verification: PASS on Node 20.20.2 and Yarn 1.22.22
- Fixture drift gate: 1 passed
- Lint: PASS
- Jest: 5 suites and 19 tests passed
- Production build: PASS
- Combined frontend proof result: 20 passed, 0 skipped

## 10. Receipt reconciliation result
A bundled backend-baseline receipt still reflected 96 passing tests. The clean-copy rerun regenerated that receipt at 98 passed, 1 deselected. The stale bundled figure was not used for classification.

## 11. Historical receipt quarantine
Older artifacts remained present in the tree, including the Hysight 27 logs and older optional receipts. They were treated as historical context only and were not counted toward this Hysight-main 28 classification.

## 12. Evidence files used
- artifacts/proof/hysight28_receipt_env.txt
- artifacts/proof/hysight28_prereq.log
- artifacts/proof/hysight28_baseline_receipt_refresh.log
- artifacts/proof/hysight28_autonomy.log
- artifacts/proof/hysight28_sidecar.log
- artifacts/proof/hysight28_sidecar_no_fallback.txt
- artifacts/proof/hysight28_frontend.log
- artifacts/proof/pipeline.json
- artifacts/proof/backend-baseline.json
- artifacts/proof/contract.json
- artifacts/proof/baseline.json
- artifacts/proof/autonomy-optional.json
- artifacts/proof/live-sidecar.json
- artifacts/proof/frontend.json

## 13. Conclusion
The workspace now has a reconciled fresh proof set for Hysight-main 28. Local core proof, autonomy proof, live sidecar proof, fail-closed sidecar behavior, and frontend proof all ran again from the clean isolated copy and passed.
