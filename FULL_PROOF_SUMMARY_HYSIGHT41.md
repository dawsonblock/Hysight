# Hysight-41 Full Proof Summary

**Release tag:** hysight-41
**Base commit:** `00ac024248272485bcf687635d7c7b1f97f567db`
**Sealed at:** 2026-04-21T05:29:12Z
**Classification:** **sealed full-proof release**

---

## 1. Executive Verdict

Hysight-main 41 is sealed as a version-specific **sealed full-proof release** for
this workspace revision. The supported bootstrap paths passed fresh, local-core
proof passed fresh, live Rust sidecar proof passed fresh, explicit fail-closed
sidecar behavior was demonstrated after shutdown, and the frontend proof passed
fresh on the exact enforced runtime.

## 2. Repo Fingerprint

- Base commit: `00ac024248272485bcf687635d7c7b1f97f567db`
- Clean pre-seal fingerprint: `8278e8a724dc962475e47f7674f297b26f0e2d7d`
- Last package-fingerprint snapshot after handoff: `b56fb798e7ada6dfc57f1f84223cfde02185720b`
- Proof-time receipt fingerprints:
  - local-core rerun: `52998b57bb3209c44bcac419539feddb8203baff`
  - live sidecar receipt: `9e3c774b34516f96b23843b55b54682fd666f4b2`
  - frontend receipt: `3549fd88e8184e9542180002f27d6c91cab7a4db`

These receipt fingerprints are snapshots at proof time. The environment artifact
preserves both the clean pre-seal fingerprint and the last package-fingerprint snapshot
after release artifacts were written.

## 3. Machine Facts

- Absolute repo path: `/Users/dawsonblock/Hysight`
- Platform: macOS 26.2, arm64
- Kernel: Darwin 25.2.0
- Python: 3.9.7
- Rust: `rustc 1.94.0`, `cargo 1.94.0`
- Node: `v24.15.0`
- Yarn: `1.22.22`

## 4. Root Packaging Result

- Fresh command: `./.pkg-venv/bin/python -m pip install -e '.[dev]'`
- Result: ✅ PASS
- Evidence: `artifacts/proof/release_local_core_hysight41.log`

## 5. Bootstrap Result

- Fresh command: `make venv`
- Result: ✅ PASS
- Evidence: `artifacts/proof/release_local_core_hysight41.log`

## 6. Fresh Baseline Result

| Step | Passed | Failed | Notes |
|------|--------|--------|-------|
| Pipeline | 7 | 0 | `artifacts/proof/pipeline.json` |
| Backend baseline | 98 | 0 | pytest output also reports 1 deselected |
| Contract | 18 | 0 | `artifacts/proof/contract.json` |
| **Baseline total** | **123** | **0** | `artifacts/proof/baseline.json` |

## 7. Fresh Autonomy Result

- Fresh command: `./.venv/bin/python scripts/run_tests.py --autonomy`
- Result: ✅ PASS
- Count: `61 passed, 0 failed`
- Receipt: `artifacts/proof/autonomy-optional.json`

## 8. Style-Layer Result

The fresh autonomy rerun exercises the bounded operator-style cognition/control layer
under `hca/src/hca/autonomy/`, including `style_profile.py`, `attention_controller.py`,
`supervisor.py`, and the style-aware checkpoint, route, budget, dedupe, and re-anchor
surfaces.

This layer is described as bounded control logic for work-style biasing,
prioritization, attention, and re-anchoring. It is not described here as
human-equivalent intelligence, medical diagnosis, or ADHD emulation.

## 9. Sidecar Result

- Canonical live sidecar receipt: ✅ PASS
- Fresh command: `./.venv/bin/python scripts/proof_sidecar.py` with `MEMORY_SERVICE_PORT=53104`
- Receipt result: `13 passed, 2 skipped, 0 failed`
- Receipt: `artifacts/proof/live-sidecar.json`
- Additive parity evidence: `4 passed, 0 failed` via `backend/tests/test_memvid_sidecar_parity.py --run-live`
- Additive fail-closed evidence: `artifacts/proof/release_sidecar_no_fallback_hysight41.txt` shows `NO_FALLBACK_EXIT=1` after the sidecar was stopped and the backend was started with `MEMORY_BACKEND=rust`

## 10. Frontend Result

- Fresh command: `yarn --cwd frontend install --frozen-lockfile` then `./.venv/bin/python scripts/proof_frontend.py`
- Exact runtime used: Node `24.15.0`, Yarn `1.22.22`
- Result: ✅ PASS
- Count: `20 passed, 0 failed`
- Covered stages: runtime-verification, fixture-drift, lint, jest, build
- Receipt: `artifacts/proof/frontend.json`

## 11. Fresh Receipts Counted

- `artifacts/proof/pipeline.json`
- `artifacts/proof/backend-baseline.json`
- `artifacts/proof/contract.json`
- `artifacts/proof/baseline.json`
- `artifacts/proof/autonomy-optional.json`
- `artifacts/proof/live-sidecar.json`
- `artifacts/proof/frontend.json`
- `artifacts/proof/release_handoff_check_hysight41.log`

Receipt-counted passing total: **217** (`123 + 61 + 13 + 20`)

Additional non-receipt evidence counted narratively but not in the `217` receipt total:

- sidecar parity: `4/0`
- no-fallback backend check: explicit fail-closed exit `1`

## 12. Historical Receipts Ignored

Historical summaries, seals, and non-regenerated receipts are quarantined in
`artifacts/proof/release_quarantine_hysight41.md` and are not proof for hysight-41.
That includes all older `FULL_PROOF_SUMMARY_HYSIGHT*.md`,
`OPTIONAL_PROOF_SUMMARY_HYSIGHT*.md`, `RELEASE_SEAL_HYSIGHT*.md`,
`artifacts/proof/integration.json`, `artifacts/proof/live-mongo.json`, and older
timestamped history receipts.

## 13. Remaining Limitations

- Live Mongo proof was not rerun in this seal and is not counted.
- The canonical sidecar receipt still includes two expected skips tied to `supervisorctl`-managed restart checks.
- Receipt fingerprints reflect proof-time snapshots; the release environment artifact records the clean pre-seal fingerprint and the last package snapshot separately.

## 14. Final Classification

**sealed full-proof release**

This classification is justified because packaging, bootstrap, baseline, autonomy,
live sidecar, explicit fail-closed sidecar behavior, and frontend proof all passed
fresh during the hysight-41 seal run.