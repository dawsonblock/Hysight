# Release Notes

## hysight-45 (2026-04-21)

**Base commit:** `189980254f92214198fff7d561ca0405c7ccce82`
**Classification:** sealed local-core release

- Baseline: 123/0 — pipeline, backend, contract suites
- Autonomy: 66/0 (+5 aggregate workspace tests)
- Frontend: 67/0 — all 5 stages (runtime-verify, fixture-drift, lint, Jest, build)
- Live sidecar: CARRY-FORWARD from hysight-42 (13/0, no sidecar code changed)
- Live Mongo: not rerun; historical only
- New: `GET /api/hca/autonomy/workspace` aggregate endpoint — all 9 workspace sections in a single round-trip via `asyncio.gather`
- New: `getAutonomyWorkspace()` in frontend API client + `useAutonomyPolling.js` migrated from 8-resource polling to single fetch
- Contract fix: `AutonomyRunLinkSummary` in `contract/schema.json` extended with `run_status`, `last_state`, `last_decision`
- See `RELEASE_SEAL_HYSIGHT45.md`, `FULL_PROOF_SUMMARY_HYSIGHT45.md`, and `OPTIONAL_PROOF_SUMMARY_HYSIGHT45.md` for version-specific proof evidence.

---

## hysight-42 (2026-04-21)

**Base commit:** `10966b3bc57905b298563145dba8450d610f9c1c`
**Classification:** sealed full-proof release

- Baseline: 123/0 — pipeline, backend, contract suites
- Autonomy: 61/0
- Live sidecar receipt: 13/0 (2 skipped) on fallback port `3032`
- Live sidecar parity: 4/0 (additive evidence)
- Sidecar no-fallback: PASS
- Frontend: 20/0 on Node `24.15.0` and Yarn `1.22.22`
- Live Mongo: not rerun; historical only
- Verification context: clean external unzip (`Hysight-main 42.zip`) for packaging/bootstrap/baseline/autonomy, plus detached exact-commit worktree reruns for sidecar/frontend
- Historical Hysight 27–41 summaries and older receipts remain audit history only and are not proof for 42
- See `RELEASE_SEAL_HYSIGHT42.md`, `FULL_PROOF_SUMMARY_HYSIGHT42.md`, and `OPTIONAL_PROOF_SUMMARY_HYSIGHT42.md` for version-specific proof evidence.

---

## hysight-41 (2026-04-21)

**Base commit:** `00ac024248272485bcf687635d7c7b1f97f567db`
**Classification:** sealed full-proof release

- Baseline: 123/0 — pipeline, backend, contract suites
- Autonomy: 61/0
- Live sidecar receipt: 13/0 (2 skipped, supervisorctl)
- Live sidecar parity: 4/0 (additive evidence)
- Sidecar no-fallback: PASS (`NO_FALLBACK_EXIT=1`)
- Frontend: 20/0 on Node `24.15.0` and Yarn `1.22.22`
- Live Mongo: not rerun; historical only
- Historical Hysight 27–39 summaries and non-regenerated receipts remain audit history only and are not proof for 41
- See `RELEASE_SEAL_HYSIGHT41.md`, `FULL_PROOF_SUMMARY_HYSIGHT41.md`, and `OPTIONAL_PROOF_SUMMARY_HYSIGHT41.md` for version-specific proof evidence.

---

## hysight-38 (2026-04-20)

**Commit:** `9a1bb3274476c0e7ea7e1af818ede4f235a5a51e`
**Classification:** sealed local-core release

- Baseline: 123/0 — pipeline, backend, contract suites
- Autonomy: 61/0
- Live sidecar: 13/0 (2 skipped, supervisorctl)
- Frontend: UNPROVEN (Node 20.x unavailable on seal host)
- See `RELEASE_SEAL_HYSIGHT38.md` and `FULL_PROOF_SUMMARY_HYSIGHT38.md` for full proof evidence.

---

This release consolidates the backend authority path, formalizes replay-backed
operator health visibility, and keeps optional deployment modes explicit rather
than coupling them to the default local proof surface.

## Observability

- `GET /api/subsystems` is the release-facing operator health endpoint.
- The endpoint is always available, even when optional integrations are not.
- Subsystem reporting is split by `database`, `memory`, `storage`, `llm`,
  and the bounded `autonomy` control plane for degraded-mode diagnosis.
- The autonomy surface now exposes kill-switch state, pending escalations,
  recent active run links, per-agent budget ledgers, the last evaluator
  decision, and the latest checkpoint summary without creating a second
  execution authority.
- `POST /api/status` and `GET /api/status` remain optional and intentionally
  return `503` when Mongo-backed persistence is not configured.

## Subsystem Health

- `database`
  - `disabled` when `MONGO_URL` and `DB_NAME` are unset.
  - `healthy` when Mongo-backed `/api/status` persistence is reachable.
  - `unhealthy` when Mongo is configured but the backend client is unavailable
    or ping fails.
- `memory`
  - `healthy` in the default python-backed mode.
  - `healthy` in Rust sidecar mode only when `/health` succeeds.
  - `unhealthy` when sidecar mode is configured but unreachable or invalid.
- `storage`
  - Reports whether the HCA storage root and memory storage are writable.
- `llm`
  - Reports whether `EMERGENT_LLM_KEY` is configured.

## Deployment Notes

- The default supported local mode remains:
  - python in-process memory
  - no required Mongo instance
  - no required Rust sidecar
- Mongo-backed `/api/status` persistence remains an explicit optional mode.
  - Configure both `MONGO_URL` and `DB_NAME`, or leave both unset.
  - Partial Mongo configuration fails fast at startup.
- Rust memvid sidecar mode remains an explicit optional mode.
  - Configure `MEMORY_BACKEND=rust` and a healthy `MEMORY_SERVICE_URL`.
  - Backend startup validates the sidecar via `/health` and fails fast when it
    is unreachable.
- Credentialed browser access remains fail-closed.
  - `CORS_ORIGINS` must be an explicit comma-separated allowlist of absolute
    origins.
- The repo root is now an honest workspace/meta-project.
  - `python -m pip install -e '.[dev]'` at the root installs tooling only.
  - The supported runtime/bootstrap path remains `make venv`, which installs editable `./hca` through `backend/requirements-test.txt`.
- Proof receipts now land under `artifacts/proof/`, with timestamped live
  history receipts under `artifacts/proof/history/` for the live Mongo and
  live sidecar harnesses.
- Aggregate receipts now declare `covered_proof_steps` and
  `omitted_proof_steps`, and frontend receipts declare the exact covered stage
  names so proof claims stay scoped to what actually ran.

## Proof Commands

- Default local proof surface:

```bash
python scripts/run_tests.py
```

Current enforced baseline contract in the runner:

- HCA pipeline proof: `7 passed`
- Backend baseline proof: `98 passed, 1 deselected`
- Contract conformance proof: `18 passed`
- Overall baseline proof: `123 passed, 0 skipped`
- Autonomy optional proof: `61 passed, 0 failed`

## Release Seal Status for Hysight-main 36 (2026-04-20)

- Release verdict: `sealed local-core release`
- Commit: `78b5affefe6780694e69512e14e75038fda68dee`
- What changed: new commit from hysight-35 (`6162720ac`); repo fingerprint `49ea69aec5af3ff97aa93e07031d5bd5ae2350da`.
- Packaging install passed fresh.
- `make venv` passed fresh.
- Baseline: 123 passed, 0 failed (7 pipeline + 98 backend-baseline + 18 contract).
- Autonomy optional: 61 passed, 0 failed.
- Sidecar optional: 13 passed, 2 skipped (supervisorctl not in PATH — expected), 0 failed. No-fallback: N/A (backend not running as standalone service; structural enforcement via `MEMORY_BACKEND=rust`).
- Frontend: UNPROVEN — Node 20.x unavailable (host has v25.9.0, frontend pins 20.x).
- Live Mongo not rerun; remains historical only.
- Historical Hysight 27–35 summary files remain in the tree for audit context only and are not proof for 36.

## Release Seal Status for Hysight-main 35 (2026-04-20)

- Release verdict: `sealed full-proof release`
- Commit: `6162720ac0344d5e7f7a40eb7f13beb6b49d41bd`
- What changed: `scripts/launch_unified.sh` (new unified backend+frontend launcher), `Makefile` (`run-unified`, `run-unified-sidecar` targets), `scripts/check_repo_integrity.py` (registered new script). No Python, Rust, or React source changes.
- Packaging install passed fresh.
- `make venv` passed fresh.
- Baseline: 123 passed, 0 failed (7 pipeline + 98 backend-baseline + 18 contract).
- Autonomy optional: 61 passed, 0 failed.
- Sidecar optional: 13 passed, 2 skipped (supervisorctl not in PATH — expected), 0 failed. No-fallback confirmed (static code verified).
- Frontend: 19 passed, 0 failed (Node v25.9.0 with --ignore-engines).
- Live Mongo not rerun; remains historical only.
- Historical Hysight 27–34 summary files remain in the tree for audit context only and are not proof for 35.

## Release Seal Status for Hysight-main 34 (2026-04-20)

- Release verdict: `sealed local-core release`
- Commit: `5d68ab48030e67571015c60316683dc9a772a0d4`
- Packaging install passed fresh.
- `make venv` passed fresh.
- Baseline: 123 passed, 0 failed (7 pipeline + 98 backend-baseline + 18 contract).
- Autonomy optional: 61 passed, 0 failed.
- Sidecar optional: 17 passed, 2 skipped (supervisorctl not in PATH — expected), 0 failed. No-fallback confirmed.
- Frontend: skipped — Node 20.x required, v25.9.0 active; no frontend changes in this revision.
- Live Mongo not rerun; remains historical only.
- Historical Hysight 27–32 summary files remain in the tree for audit context only and are not proof for 34.

## Release Seal Status for Hysight-main 32 (2026-04-19)

- Release verdict: `sealed full-proof release` (historical)
- Packaging install passed fresh from a clean copied tree for this exact revision.
- `make venv` passed fresh from the same clean tree.
- `.pkg-venv` did not contaminate the supported proof path.
- Fresh optional evidence counted in this seal: live Rust sidecar, live parity, fail-closed no-fallback behavior, and frontend proof on Node 20.20.2 / Yarn 1.22.22.
- Live Mongo was not rerun in this seal and remains historical only.
- Historical Hysight 28, 29, and 31 summary files remain in the tree for audit context only and are not proof for 32.

- Optional frontend proof:

```bash
make test-bootstrap-frontend
make proof-frontend
```

- Optional live Rust sidecar proof:

```bash
make run-memvid-sidecar
make proof-sidecar
```

- Optional live Rust sidecar proof on an alternate localhost port:

```bash
MEMORY_SERVICE_PORT=3032 make run-memvid-sidecar
MEMORY_SERVICE_PORT=3032 make proof-sidecar
```

- Optional live Mongo-backed `/api/status` proof:

```bash
make proof-mongo-live
```

- Release-seal optional evidence for Hysight-main 32 on 2026-04-19 was refreshed with:

```bash
make proof-sidecar
python scripts/proof_frontend.py
python -m pytest backend/tests/test_memvid_sidecar_parity.py -q --run-live -ra --strict-markers
```

- The sidecar harness now falls forward to the next free localhost port when
  the default `http://localhost:3031` target is occupied or unhealthy, so the
  default `make proof-sidecar` path can still complete on hosts where `3031`
  is reserved by another local listener.

- Live Mongo support remains available, but Mongo receipts were not regenerated
  during this seal pass and are therefore historical only.

Narrow already-running-Mongo path when you do not want the disposable harness:

```bash
make test-mongo-live
```

Override the connection target when needed:

```bash
LIVE_MONGO_URL=mongodb://127.0.0.1:27017 \
LIVE_MONGO_DB_NAME=hysight_live \
make test-mongo-live
```

## Current Limitations

- Optional live Mongo and live Rust sidecar modes are supported, but remain
  explicit opt-in proof surfaces rather than part of the default service-free
  local proof path.
- The frontend operator surface is still JavaScript-first and does not yet have
  a full static TypeScript migration.
- `backend/server.py` is now an adapter layer, but the backend refactor should
  still receive dedicated verification before release sign-off.
