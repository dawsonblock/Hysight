# Hysight-41 Proof Quarantine Ledger

This ledger marks which proof artifacts are authoritative for hysight-41 and which
artifacts remain historical only. Historical files are retained for audit continuity
but are not proof for hysight-41.

## Fresh And Authoritative For 41

- `artifacts/proof/release_env_hysight41.txt` — machine facts and release identity for this seal pass
- `artifacts/proof/release_local_core_hysight41.log` — fresh packaging, bootstrap, baseline, and autonomy run log
- `artifacts/proof/release_sidecar_hysight41.log` — fresh live sidecar receipt run plus additive parity evidence
- `artifacts/proof/release_sidecar_no_fallback_hysight41.txt` — explicit stopped-sidecar fail-closed evidence (`NO_FALLBACK_EXIT=1`)
- `artifacts/proof/release_frontend_hysight41.log` — fresh frontend install and proof log on Node 24.15.0 / Yarn 1.22.22
- `artifacts/proof/release_handoff_check_hysight41.log` — post-doc baseline and autonomy handoff verification log
- `artifacts/proof/pipeline.json` — fresh pipeline receipt (7/0)
- `artifacts/proof/backend-baseline.json` — fresh backend-baseline receipt (98/0, 1 deselected in pytest output)
- `artifacts/proof/contract.json` — fresh contract receipt (18/0)
- `artifacts/proof/baseline.json` — fresh aggregate baseline receipt (123/0)
- `artifacts/proof/autonomy-optional.json` — fresh bounded autonomy receipt (61/0)
- `artifacts/proof/live-sidecar.json` — fresh canonical live sidecar receipt (13 passed, 2 skipped, 0 failed)
- `artifacts/proof/frontend.json` — fresh frontend receipt (20/0)
- `FULL_PROOF_SUMMARY_HYSIGHT41.md` — version-specific full proof summary for this run
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT41.md` — version-specific optional proof summary for this run
- `RELEASE_SEAL_HYSIGHT41.md` — version-specific release seal for this run

## Historical And Ignored Summary Docs

- `FULL_PROOF_SUMMARY_HYSIGHT28.md`
- `FULL_PROOF_SUMMARY_HYSIGHT29.md`
- `FULL_PROOF_SUMMARY_HYSIGHT31.md`
- `FULL_PROOF_SUMMARY_HYSIGHT32.md`
- `FULL_PROOF_SUMMARY_HYSIGHT34.md`
- `FULL_PROOF_SUMMARY_HYSIGHT35.md`
- `FULL_PROOF_SUMMARY_HYSIGHT36.md`
- `FULL_PROOF_SUMMARY_HYSIGHT38.md`
- `FULL_PROOF_SUMMARY_HYSIGHT39.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT27.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT29.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT31.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT32.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT34.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT35.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT36.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT38.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT39.md`
- `RELEASE_SEAL_HYSIGHT29.md`
- `RELEASE_SEAL_HYSIGHT31.md`
- `RELEASE_SEAL_HYSIGHT32.md`
- `RELEASE_SEAL_HYSIGHT34.md`
- `RELEASE_SEAL_HYSIGHT35.md`
- `RELEASE_SEAL_HYSIGHT36.md`
- `RELEASE_SEAL_HYSIGHT38.md`
- `RELEASE_SEAL_HYSIGHT39.md`

## Historical And Ignored Receipts

- `artifacts/proof/integration.json` — not regenerated during the hysight-41 seal
- `artifacts/proof/live-mongo.json` — not regenerated during the hysight-41 seal
- `artifacts/proof/history/live-mongo-20260417T204618Z.json`
- `artifacts/proof/history/live-sidecar-20260416T215726Z.json`
- `artifacts/proof/history/live-sidecar-20260417T204720Z.json`
- `artifacts/proof/history/live-sidecar-20260417T205151Z.json`
- `artifacts/proof/history/live-sidecar-20260418T210440Z.json`
- `artifacts/proof/history/live-sidecar-20260418T211556Z.json`
- `artifacts/proof/history/live-sidecar-20260419T071751Z.json`
- `artifacts/proof/history/live-sidecar-20260419T084523Z.json`
- `artifacts/proof/history/live-sidecar-20260420T200840Z.json`
- `artifacts/proof/history/live-sidecar-20260420T210533Z.json`
- `artifacts/proof/history/live-sidecar-20260420T224208Z.json`
- `artifacts/proof/history/live-sidecar-20260420T231441Z.json`
- `artifacts/proof/history/live-sidecar-20260420T233431Z.json`

## Additional Historical Manual Artifacts

- Prior release quarantine ledgers under `artifacts/proof/release_quarantine_hysight*.md` for 31, 32, 34, 35, 36, and 38 remain historical only.
- Prior version-specific `release_env_hysight*.txt`, `release_local_core_hysight*.log`, `release_sidecar_hysight*.log`, `release_frontend_hysight*.log`, and `release_handoff_check_hysight*.log` files remain historical only unless listed above as fresh for 41.

## Missing Because Toolchain Unavailable

- None. Rust and the exact frontend runtime were available during this seal pass.

## Notes

- Receipt `repo_fingerprint` values record the tree snapshot at proof time.
- The environment artifact records both the clean pre-seal fingerprint and the last package-fingerprint snapshot after release docs and handoff logs were written.