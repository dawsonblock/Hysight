# Hysight-main 31 optional proof summary

## 1. Executive verdict
Optional surfaces were freshly proved for Hysight-main 31 in the release-seal run.

## 2. Machine facts
- OS: macOS 26.2 (25C56)
- Architecture: arm64
- Python: 3.9.7
- rustc/cargo: available and used
- Frontend proof runtime: Node 20.20.2 and Yarn 1.22.22

## 3. Sidecar result
- Live Rust sidecar proof: 13 passed, 2 skipped
- Live sidecar parity: 4 passed
- The run automatically moved from localhost:3031 to localhost:3032 because the default port was occupied and unhealthy.

## 4. No-fallback result
With `MEMORY_BACKEND=rust` and the sidecar unavailable, backend startup failed explicitly with `MemoryConfigurationError`. No silent Python-local fallback was observed.

## 5. Frontend result
- Runtime verification: PASS
- Fixture drift gate: 1 passed
- Lint: PASS
- Jest: 5 suites and 19 tests passed
- Production build: PASS
- Combined frontend proof: 20 passed, 0 skipped

## 6. Historical optional receipts ignored
- `artifacts/proof/live-mongo.json`
- older Hysight 27, 28, and 29 optional logs and summaries
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT29.md`

## 7. Optional-surface classification
fresh optional surfaces proved for Hysight-main 31
