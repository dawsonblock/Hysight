# Optional Proof Summary — Hysight-main 34

**Sealed**: 2026-04-20T20:05:31Z  
**Commit**: `5d68ab48030e67571015c60316683dc9a772a0d4`

This document covers all non-baseline (optional) proof steps for hysight-main 34.

---

## Autonomy Optional Proof

| Step | Tests | Passed | Failed | Skipped |
|------|-------|--------|--------|---------|
| autonomy-optional | 61 | 61 | 0 | 0 |

Receipt: `artifacts/proof/autonomy-optional.json` — `2026-04-20T20:06:23Z`

The autonomy subsystem implements a **bounded operator-style cognition/control layer**:
attention windowing, selective summarisation, checkpoint gating, and urgency-ranked
task scheduling. That framing is accurate for this codebase. The autonomy optional suite
tests all route endpoints, filtering logic, and status projection introduced in this layer.

---

## Sidecar Optional Proof

| Step | Tests | Passed | Failed | Skipped |
|------|-------|--------|--------|---------|
| sidecar (test_memvid_sidecar.py + test_memvid_sidecar_parity.py) | 19 | 17 | 0 | 2 |

Receipt: `artifacts/proof/live-sidecar.json` — `2026-04-20T20:13:42Z`

Skipped tests (2): supervisorctl-dependent persistence-restart tests.  
`supervisorctl` is not in PATH on this machine — skip is expected and acceptable.

No-fallback confirmed (see `release_sidecar_no_fallback_hysight34.txt`).

---

## Frontend Optional Proof

**Status**: SKIPPED  
Node 20.x required; v25.9.0 active. No frontend changes in this revision.  
Historical baseline retained: `artifacts/proof/frontend.json` (2026-04-19).

---

## Summary

| Proof Step | Status | Count |
|-----------|--------|-------|
| autonomy-optional | ✅ passed | 61/61 |
| sidecar | ✅ passed | 17/19 (2 skip) |
| frontend | ⚠️ skipped | Node version mismatch |
