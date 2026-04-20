# Optional Proof Summary — Hysight-main 35

**Sealed**: 2026-04-20T21:05:33Z  
**Commit**: `6162720ac0344d5e7f7a40eb7f13beb6b49d41bd`

This document covers all non-baseline (optional) proof steps for hysight-main 35.

---

## Autonomy Optional Proof

| Step | Tests | Passed | Failed | Skipped |
|------|-------|--------|--------|---------|
| autonomy-optional | 61 | 61 | 0 | 0 |

Receipt: `artifacts/proof/autonomy-optional.json` — `2026-04-20T21:02:42Z`

The autonomy subsystem implements a **bounded operator-style cognition/control layer**:
attention windowing, selective summarisation, checkpoint gating, and urgency-ranked
task scheduling. That framing is accurate for this codebase. The autonomy optional suite
tests all route endpoints, filtering logic, and status projection for this layer.

No autonomy changes were made in rev 35. The autonomy suite passes identically to rev 34
(61/61), confirming no regression from the `launch_unified.sh` addition.

---

## Sidecar Optional Proof

| Step | Tests | Passed | Failed | Skipped |
|------|-------|--------|--------|---------|
| sidecar (test_memvid_sidecar.py) | 15 | 13 | 0 | 2 |

Receipt: `artifacts/proof/live-sidecar.json` — `2026-04-20T21:05:33Z`

Skipped tests (2): supervisorctl-dependent persistence-restart tests.  
`supervisorctl` is not in PATH on this machine — skip is expected and acceptable.

No-fallback: static code confirms explicit HTTP 503 on sidecar unavailability (no silent fallback).
Evidence: `artifacts/proof/release_sidecar_no_fallback_hysight35.txt`

---

## Frontend Optional Proof

| Suite | Tests | Passed | Failed | Skipped |
|-------|-------|--------|--------|---------|
| Jest (5 suites) | 19 | 19 | 0 | 0 |

Frontend passed with Node v25.9.0 + `--ignore-engines` (pinned engine: Node 20.x).  
Rev 35 added no frontend source changes (`launch_unified.sh` is a bash script).  
All 19 tests pass, confirming no regression.  
Log: `artifacts/proof/release_frontend_hysight35.log`
