# Hysight-main 29 full proof summary

## 1. Final classification
fresh full proof complete

## 2. Scope rule used
Only fresh receipts and transcripts generated during the current 2026-04-19 run were counted. Historical receipts remained present in the tree but were explicitly ignored for classification.

## 3. Hardening upgrades completed
- Kept one execution authority: autonomous work still becomes ordinary HCA runs on the shared runtime and replay spine.
- Tightened the bounded autonomy supervisor with monotonic durable budget-ledger updates for newly observed steps and retries.
- Preserved durable trigger dedupe and restart-safe observe-over-relaunch behavior.
- Extended the operator control plane so the backend and console surface kill switch state, pending escalations, recent active runs, budget ledgers, dedupe coverage, last evaluator decision, and latest checkpoint summary.
- Re-synchronized proof and release docs with the fresh counts now in force.

## 4. Fresh local-core proof
- Root editable install: PASS
- make venv: PASS
- HCA pipeline: 7 passed
- Backend baseline: 98 passed, 1 deselected
- Contract conformance: 18 passed
- Combined baseline: 123 passed, 0 skipped

## 5. Fresh autonomy proof
- Bounded autonomy optional surface: 50 passed, 0 skipped

## 6. Fresh sidecar proof
- Live Rust sidecar proof: 13 passed, 2 skipped
- Live parity proof: 4 passed
- The two skips require supervisorctl on the host PATH for restart orchestration.

## 7. Fresh no-fallback result
With Rust memory mode configured and the sidecar down, startup failed explicitly with MemoryConfigurationError. No silent fallback to the Python-local memory authority was observed.

## 8. Fresh frontend proof
- Runtime verification passed on Node 20.20.2 and Yarn 1.22.22
- Fixture drift gate: 1 passed
- Lint: PASS
- Jest: 5 suites and 19 tests passed
- Production build: PASS
- Combined frontend proof: 20 passed, 0 skipped

## 9. Fresh receipts counted
- artifacts/proof/pipeline.json
- artifacts/proof/backend-baseline.json
- artifacts/proof/contract.json
- artifacts/proof/baseline.json
- artifacts/proof/autonomy-optional.json
- artifacts/proof/live-sidecar.json
- artifacts/proof/frontend.json

## 10. Historical receipts ignored
- artifacts/proof/integration.json
- artifacts/proof/live-mongo.json
- all hysight27_* artifacts under artifacts/proof
- prior Hysight 28 summary files

## 11. Remaining limitations
- The live Mongo proof was not rerun in this pass and remains historical-only.
- Sidecar restart orchestration still skips the two supervisorctl-dependent checks on hosts without supervisorctl.

## 12. Conclusion
The bounded operator build is now materially harder to dispute on this revision: local-core proof is fresh, autonomy proof is fresh, requested optional surfaces are freshly proved, and the operator-facing control plane exposes the safety state that explains why autonomy started, waited, escalated, or stopped.
