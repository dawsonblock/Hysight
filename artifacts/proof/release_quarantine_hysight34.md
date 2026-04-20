# Release Quarantine Ledger — Hysight-main 34
Generated: 2026-04-20T20:05:31Z
Commit: 5d68ab48030e67571015c60316683dc9a772a0d4

This ledger classifies all proof artifacts present in the repository at release-34
seal time. Artifacts not listed as FRESH_34 are historical and do not represent the
state of this release.

---

## Fresh Artifacts (authoritative for hysight-main 34)

| File | Type | Result | Timestamp |
|------|------|--------|-----------|
| artifacts/proof/baseline.json | receipt | 123 passed | 2026-04-20T20:06:17 |
| artifacts/proof/autonomy-optional.json | receipt | 61 passed | 2026-04-20T20:06:23 |
| artifacts/proof/backend-baseline.json | receipt | 98 passed | 2026-04-20T20:07:47 |
| artifacts/proof/pipeline.json | receipt | 7 passed | 2026-04-20 |
| artifacts/proof/contract.json | receipt | 18 passed | 2026-04-20 |
| artifacts/proof/live-sidecar.json | receipt | 17 passed, 2 skipped | 2026-04-20T20:13:42 |
| artifacts/proof/release_env_hysight34.txt | log | machine facts | 2026-04-20 |
| artifacts/proof/release_local_core_hysight34.log | log | baseline+autonomy proof run | 2026-04-20 |
| artifacts/proof/release_sidecar_hysight34.log | log | sidecar proof run | 2026-04-20 |
| artifacts/proof/release_sidecar_no_fallback_hysight34.txt | log | no-fallback result | 2026-04-20 |
| artifacts/proof/release_frontend_hysight34.log | log | frontend skipped (Node mismatch) | 2026-04-20 |

---

## Optional / Supplemental (non-authoritative for 34)

| File | Classification | Notes |
|------|---------------|-------|
| artifacts/proof/frontend.json | HISTORICAL — rev 33 | Last fresh run 2026-04-19; frontend source unchanged in rev 34; Node 20 not available at seal time |
| artifacts/proof/integration.json | HISTORICAL — rev ~30 | Not re-run for rev 34; integration tests not part of baseline |
| artifacts/proof/live-mongo.json | HISTORICAL — rev ~30 | Not re-run; live-mongo step not in baseline |

---

## Historical / Quarantined (prior revision proofs — not authoritative for 34)

### artifacts/proof/ quarantined files

| File | From Revision | Quarantine Reason |
|------|--------------|-------------------|
| artifacts/proof/hysight27_negative_proofs.md | rev 27 | Superseded; historical record only |
| artifacts/proof/hysight27_optional_honesty.md | rev 27 | Superseded; historical record only |
| artifacts/proof/hysight27_route_integrity.md | rev 27 | Superseded; historical record only |
| artifacts/proof/hysight28_baseline_receipt_check.md | rev 28 | Superseded; historical record only |
| artifacts/proof/hysight28_receipt_quarantine.md | rev 28 | Superseded; historical record only |
| artifacts/proof/hysight29_receipt_quarantine.md | rev 29 | Superseded; historical record only |
| artifacts/proof/release_quarantine_hysight31.md | rev 31 | Superseded; historical record only |
| artifacts/proof/release_quarantine_hysight32.md | rev 32 | Superseded; historical record only |
| artifacts/proof/release_receipt_quarantine.md | rev <31 | Generic early quarantine log; historical |

### Root-level historical proof summary docs

| File | From Revision | Quarantine Reason |
|------|--------------|-------------------|
| FULL_PROOF_SUMMARY_HYSIGHT28.md | rev 28 | Superseded |
| FULL_PROOF_SUMMARY_HYSIGHT29.md | rev 29 | Superseded |
| FULL_PROOF_SUMMARY_HYSIGHT31.md | rev 31 | Superseded |
| FULL_PROOF_SUMMARY_HYSIGHT32.md | rev 32 | Superseded |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT27.md | rev 27 | Superseded |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT29.md | rev 29 | Superseded |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT31.md | rev 31 | Superseded |
| OPTIONAL_PROOF_SUMMARY_HYSIGHT32.md | rev 32 | Superseded |
| RELEASE_SEAL_HYSIGHT29.md | rev 29 | Superseded |
| RELEASE_SEAL_HYSIGHT31.md | rev 31 | Superseded |
| RELEASE_SEAL_HYSIGHT32.md | rev 32 | Superseded |

All quarantined files are **retained as read-only historical record**. They are not deleted.
The authoritative release state for hysight-main 34 is defined solely by the fresh artifacts
in the "Fresh Artifacts" table above.
