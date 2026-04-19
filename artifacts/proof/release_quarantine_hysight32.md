# Release quarantine ledger for Hysight-main 32

Release seal timestamp: 2026-04-19T22:48:40Z  
Workspace head: 61182bb045e948c3b190ba9904111b204efd3f7c  
Clean release tree: /tmp/hysight32-release-seal  
Repo fingerprint: 239d5ca45d4af85156ce51c00b13711fcd09ffda

This ledger marks which receipts and summary files are authoritative for Hysight-main 32 and which remain historical-only.

| Artifact | Classification | Reason |
| --- | --- | --- |
| artifacts/proof/pipeline.json | fresh and authoritative for 32 | regenerated from the clean release tree during the 32 seal run |
| artifacts/proof/backend-baseline.json | fresh and authoritative for 32 | regenerated from the clean release tree during the 32 seal run |
| artifacts/proof/contract.json | fresh and authoritative for 32 | regenerated from the clean release tree during the 32 seal run |
| artifacts/proof/baseline.json | fresh and authoritative for 32 | baseline proof passed fresh with 123 passed and 0 skipped |
| artifacts/proof/autonomy-optional.json | fresh and authoritative for 32 | autonomy proof passed fresh with 50 passed and 0 skipped |
| artifacts/proof/live-sidecar.json | fresh and authoritative for 32 | live Rust sidecar proof passed fresh with 13 passed and 2 skipped |
| artifacts/proof/frontend.json | fresh and authoritative for 32 | exact-runtime frontend proof passed fresh with 20 passed and 0 skipped |
| FULL_PROOF_SUMMARY_HYSIGHT32.md | fresh and authoritative for 32 | written from the fresh release-seal evidence only |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT32.md | fresh and authoritative for 32 | written from the fresh optional-lane evidence only |
| RELEASE_SEAL_HYSIGHT32.md | fresh and authoritative for 32 | operator-facing release verdict for this seal run |
| FULL_PROOF_SUMMARY_HYSIGHT28.md | historical and ignored | older release summary, not proof for 32 |
| FULL_PROOF_SUMMARY_HYSIGHT29.md | historical and ignored | older release summary, not proof for 32 |
| FULL_PROOF_SUMMARY_HYSIGHT31.md | historical and ignored | older release summary, not proof for 32 |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT29.md | historical and ignored | older optional summary, not proof for 32 |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT31.md | historical and ignored | older optional summary, not proof for 32 |
| RELEASE_SEAL_HYSIGHT29.md | historical and ignored | older release seal, not proof for 32 |
| RELEASE_SEAL_HYSIGHT31.md | historical and ignored | older release seal, not proof for 32 |
| artifacts/proof/integration.json | historical and ignored | not rerun during the 32 seal |
| artifacts/proof/live-mongo.json | historical and ignored | not rerun during the 32 seal |
| older hysight27_* , hysight28_* , hysight29_* , and hysight31_* proof artifacts | historical and ignored | audit history only |

No required proof surface is missing because of unavailable toolchains in this run. Rust and the exact frontend runtime were both available.
