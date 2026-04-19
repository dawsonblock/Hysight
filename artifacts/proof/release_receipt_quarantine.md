# Release receipt quarantine for Hysight-main 29

Release timestamp: 2026-04-19T21:03:04Z
Release tree used for handoff verification: /tmp/hysight29-release-seal

This ledger marks which receipts are authoritative for the release seal and which remain historical-only.

| Receipt or artifact | Status | Reason |
| --- | --- | --- |
| artifacts/proof/pipeline.json | fresh and authoritative | regenerated in the clean release tree during the release-seal run |
| artifacts/proof/backend-baseline.json | fresh and authoritative | regenerated in the clean release tree during the release-seal run |
| artifacts/proof/contract.json | fresh and authoritative | regenerated in the clean release tree during the release-seal run |
| artifacts/proof/baseline.json | fresh and authoritative | fresh baseline receipt for 123 passed, 0 skipped |
| artifacts/proof/autonomy-optional.json | fresh and authoritative | fresh autonomy receipt for 50 passed, 0 skipped |
| artifacts/proof/live-sidecar.json | fresh and authoritative | live Rust sidecar proof passed fresh in the clean release tree |
| artifacts/proof/frontend.json | fresh and authoritative | exact-runtime frontend proof passed fresh on Node 20.20.2 and Yarn 1.22.22 |
| artifacts/proof/integration.json | historical and ignored | not rerun during this release seal |
| artifacts/proof/live-mongo.json | historical and ignored | not rerun during this release seal |
| artifacts/proof/hysight27_* | historical and ignored | retained for prior audit history only |
| artifacts/proof/hysight28_* | historical and ignored | retained for prior audit history only |
| artifacts/proof/hysight29_* pre-seal support logs | historical and ignored | pre-seal context only; not the authoritative release seal evidence |

No required receipt is missing because of toolchain unavailability in this seal run.
