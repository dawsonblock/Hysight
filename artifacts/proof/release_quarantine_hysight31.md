# Release quarantine ledger for Hysight-main 31

Release seal timestamp: 2026-04-19T21:27:45Z  
Workspace head: a1abb10a609d488f4541b3f4553feab041bf94e0  
Clean release tree: /tmp/hysight31-release-seal  
Repo fingerprint: 878d7cbe2b473c93ef15063c2509f89205cd7074

This ledger marks which receipts and summary files are authoritative for Hysight-main 31 and which remain historical-only.

| Artifact | Classification | Reason |
| --- | --- | --- |
| artifacts/proof/pipeline.json | fresh and authoritative for 31 | regenerated from the clean release tree during the 31 seal run |
| artifacts/proof/backend-baseline.json | fresh and authoritative for 31 | regenerated from the clean release tree during the 31 seal run |
| artifacts/proof/contract.json | fresh and authoritative for 31 | regenerated from the clean release tree during the 31 seal run |
| artifacts/proof/baseline.json | fresh and authoritative for 31 | baseline proof passed fresh with 123 passed and 0 skipped |
| artifacts/proof/autonomy-optional.json | fresh and authoritative for 31 | autonomy proof passed fresh with 50 passed and 0 skipped |
| artifacts/proof/live-sidecar.json | fresh and authoritative for 31 | live Rust sidecar proof passed fresh with 13 passed and 2 skipped |
| artifacts/proof/frontend.json | fresh and authoritative for 31 | exact-runtime frontend proof passed fresh with 20 passed and 0 skipped |
| FULL_PROOF_SUMMARY_HYSIGHT31.md | fresh and authoritative for 31 | written from the fresh release-seal evidence only |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT31.md | fresh and authoritative for 31 | written from the fresh optional-lane evidence only |
| RELEASE_SEAL_HYSIGHT31.md | fresh and authoritative for 31 | operator-facing release verdict for this seal run |
| FULL_PROOF_SUMMARY_HYSIGHT28.md | historical and ignored | older release summary, not proof for 31 |
| FULL_PROOF_SUMMARY_HYSIGHT29.md | historical and ignored | older release summary, not proof for 31 |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT29.md | historical and ignored | older optional summary, not proof for 31 |
| RELEASE_SEAL_HYSIGHT29.md | historical and ignored | older release seal, not proof for 31 |
| artifacts/proof/integration.json | historical and ignored | not rerun during the 31 seal |
| artifacts/proof/live-mongo.json | historical and ignored | not rerun during the 31 seal |
| older hysight27_* and hysight28_* proof artifacts | historical and ignored | audit history only |
| pre-seal hysight29 support logs and notes | historical and ignored | retained for audit trail only |

No required proof surface is missing because of unavailable toolchains in this run. Rust and the exact frontend runtime were both available.
