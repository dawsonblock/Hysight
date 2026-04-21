# Hysight-45 Proof Quarantine Ledger

This ledger marks which proof artifacts are authoritative for hysight-45 and which
artifacts remain historical only. Historical files are retained for audit continuity
but are not proof for hysight-45.

## Fresh And Authoritative For 45

- `artifacts/proof/pipeline.json` — pipeline receipt (7/0), confirmed during baseline run
- `artifacts/proof/backend-baseline.json` — backend-baseline receipt (98/0, 1 deselected)
- `artifacts/proof/contract.json` — contract receipt (18/0)
- `artifacts/proof/baseline.json` — aggregate baseline receipt (123/0)
- `artifacts/proof/autonomy-optional.json` — bounded autonomy receipt (66/0); +5 workspace tests
- `artifacts/proof/frontend.json` — frontend receipt (67/0); all 5 stages
- `FULL_PROOF_SUMMARY_HYSIGHT45.md` — version-specific full proof summary for this run
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT45.md` — version-specific optional proof summary for this run
- `RELEASE_SEAL_HYSIGHT45.md` — version-specific release seal for this run

## Carry-Forward (Not Re-run In This Pass)

- `artifacts/proof/release_live_sidecar_receipt_hysight42.json` — live sidecar last proved at hysight-42 (13/0)
- `artifacts/proof/release_sidecar_no_fallback_hysight42.txt` — sidecar fail-closed evidence from hysight-42
- No sidecar code was modified between hysight-42 and hysight-45

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
- `FULL_PROOF_SUMMARY_HYSIGHT41.md`
- `FULL_PROOF_SUMMARY_HYSIGHT42.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT27.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT29.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT31.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT32.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT34.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT35.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT36.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT38.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT39.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT41.md`
- `OPTIONAL_PROOF_SUMMARY_HYSIGHT42.md`
- `RELEASE_SEAL_HYSIGHT29.md`
- `RELEASE_SEAL_HYSIGHT31.md`
- `RELEASE_SEAL_HYSIGHT32.md`
- `RELEASE_SEAL_HYSIGHT34.md`
- `RELEASE_SEAL_HYSIGHT35.md`
- `RELEASE_SEAL_HYSIGHT36.md`
- `RELEASE_SEAL_HYSIGHT38.md`
- `RELEASE_SEAL_HYSIGHT39.md`
- `RELEASE_SEAL_HYSIGHT41.md`
- `RELEASE_SEAL_HYSIGHT42.md`

## Historical And Ignored Receipts

- `artifacts/proof/integration.json` — not regenerated during the hysight-45 seal
- `artifacts/proof/live-mongo.json` — not regenerated during the hysight-45 seal
- `artifacts/proof/history/live-mongo-20260417T204618Z.json`
- `artifacts/proof/history/live-sidecar-20260416T215726Z.json`
