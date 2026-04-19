# Hysight-main 27 optional-surface honesty ledger

## Fresh-vs-historical rule used for this audit

Only receipts generated during this run were used for classification. Older bundled receipts were treated as **historical** and ignored unless they were re-proved on the current revision.

## Surface classification for this run

| Surface | Fresh reality on this run | Classification |
| --- | --- | --- |
| Live Rust sidecar proof | Passed fresh: `scripts/run_tests.py --sidecar` => **13 passed, 2 skipped**; parity suite => **4 passed** | freshly passed within the committed proof scope |
| Sidecar no-fallback | Passed fresh: dead sidecar produced explicit `MemoryConfigurationError` | freshly proved now |
| Frontend proof on exact supported runtime | Ran fresh on Node **20.20.2** + Yarn **1.22.22** and **passed** after the backend-owned fixture exporter was synced with the current subsystem schema | freshly proved now |
| Canonical baseline proof | Passed fresh: **123 passed, 0 skipped** | prerequisite refreshed |
| Bounded autonomy optional proof | Passed fresh: **50 passed, 0 skipped** | prerequisite refreshed |
| Integration proof | Only historical bundled receipt present (`integration.json` from 2026-04-17) | historical / ignored |
| Live Mongo proof | Only historical bundled receipt present (`live-mongo.json` from 2026-04-17) | historical / ignored |

## Documentation mismatch ledger

| File | Exact claim | Fresh reality | Classification |
| --- | --- | --- | --- |
| `README.md` | Backend baseline expected count is listed as **96** | Fresh baseline proof on this revision produced **98 passed, 1 deselected** for backend baseline and **123 total** aggregate | harmless drift |
| `README.md` | Frontend proof is documented as a supported proof tier on the exact pinned runtime | Fresh proof was executed on Node **20.20.2** and Yarn **1.22.22** and now passes after syncing the generated fixture export path | no current mismatch |
| `OPTIONAL_PROOF_SUMMARY.md` | Prior optional verification summary references an older commit and earlier counts | It does not describe this revision and was ignored for classification | historical / ignored |

## Fresh receipts accepted for classification

- `artifacts/proof/baseline.json` (fresh, 2026-04-19)
- `artifacts/proof/autonomy-optional.json` (fresh, 2026-04-19)
- `artifacts/proof/live-sidecar.json` (fresh, 2026-04-19)
- `artifacts/proof/frontend.json` (fresh, 2026-04-19, passed after rerun)
- `artifacts/proof/hysight27_prereq.log`
- `artifacts/proof/hysight27_sidecar_proof.txt`
- `artifacts/proof/hysight27_sidecar_no_fallback.txt`
- `artifacts/proof/hysight27_frontend_live_rerun.log`

## Historical receipts ignored

- `artifacts/proof/backend-baseline.json` (older than the current run)
- `artifacts/proof/integration.json`
- `artifacts/proof/live-mongo.json`
- previous summary docs under the repo root that reference older commits or older proof counts
- the earlier failing transcript `artifacts/proof/hysight27_frontend_live.log`, which was superseded by the later passing rerun in the same session

## Conclusion

This repo cannot inherit a blanket “optional surfaces proved” label from historical receipts. In the current run, the committed sidecar proof scope passed fresh and the frontend surface was also freshly re-proved on the exact supported runtime.