# Hysight-41 Release Seal

**Release tag:** hysight-41
**Base commit:** `00ac024248272485bcf687635d7c7b1f97f567db`
**Sealed at:** 2026-04-21T05:29:12Z
**Classification:** **sealed full-proof release**

---

## 1. Executive Release Verdict

Hysight-main 41 is sealed as a **sealed full-proof release** for this exact release
package. The supported bootstrap paths passed fresh, all local-core proof surfaces
passed fresh, the bounded style-layer autonomy surface passed fresh, the live Rust
sidecar passed fresh, the backend failed closed when the stopped sidecar was referenced,
and the frontend passed fresh on the exact enforced runtime.

## 2. Repo Fingerprint

- Base commit: `00ac024248272485bcf687635d7c7b1f97f567db`
- Clean pre-seal fingerprint: `8278e8a724dc962475e47f7674f297b26f0e2d7d`
- Last package-fingerprint snapshot after handoff: `b56fb798e7ada6dfc57f1f84223cfde02185720b`

## 3. Machine Facts

- Platform: macOS 26.2, arm64
- Python: 3.9.7
- Rust: `rustc 1.94.0`, `cargo 1.94.0`
- Node: `v24.15.0`
- Yarn: `1.22.22`
- Repo path: `/Users/dawsonblock/Hysight`

## 4. Packaging Result

- `python3 -m venv .pkg-venv`
- `./.pkg-venv/bin/python -m pip install -U pip`
- `./.pkg-venv/bin/python -m pip install -e '.[dev]'`
- Result: ✅ PASS

## 5. Bootstrap Result

- `make venv`
- Result: ✅ PASS

## 6. Baseline Result

| Surface | Passed | Failed |
|---------|--------|--------|
| Pipeline | 7 | 0 |
| Backend baseline | 98 | 0 |
| Contract | 18 | 0 |
| **Baseline total** | **123** | **0** |

## 7. Autonomy Result

- Bounded autonomy optional: `61 passed, 0 failed`
- Receipt: `artifacts/proof/autonomy-optional.json`
- Result: ✅ PASS

## 8. Style-Layer Result

The bounded operator-style cognition/control layer remains present and freshly exercised
through the autonomy suite. This includes `style_profile.py`, `attention_controller.py`,
`supervisor.py`, and style-aware routing, checkpoint, budget, dedupe, and re-anchor
behavior. The layer is described only as bounded control logic, not as human-equivalent
intelligence or medical emulation.

## 9. Sidecar Result

- Canonical live sidecar receipt: `13 passed, 2 skipped, 0 failed`
- Additive parity evidence: `4 passed, 0 failed`
- Stopped-sidecar fail-closed evidence: `NO_FALLBACK_EXIT=1`
- Result: ✅ PASS

## 10. Frontend Result

- Exact runtime: Node `24.15.0`, Yarn `1.22.22`
- Fresh frontend receipt: `20 passed, 0 failed`
- Result: ✅ PASS

## 11. Fresh Receipts Counted

- `artifacts/proof/pipeline.json`
- `artifacts/proof/backend-baseline.json`
- `artifacts/proof/contract.json`
- `artifacts/proof/baseline.json`
- `artifacts/proof/autonomy-optional.json`
- `artifacts/proof/live-sidecar.json`
- `artifacts/proof/frontend.json`
- `artifacts/proof/release_handoff_check_hysight41.log`

Official receipt-counted total: **217 passed, 0 failed**

## 12. Historical Receipts Ignored

See `artifacts/proof/release_quarantine_hysight41.md` for the full quarantine ledger of
older summaries, older seals, older history receipts, and non-regenerated JSON receipts.

## 13. Remaining Limitations

- Live Mongo was not rerun and is not counted.
- The canonical sidecar receipt still contains two expected `supervisorctl` skips.
- Receipt fingerprints are proof-time snapshots; the environment artifact records the clean pre-seal fingerprint and the last package snapshot separately.

## 14. Final Release Classification

**sealed full-proof release**