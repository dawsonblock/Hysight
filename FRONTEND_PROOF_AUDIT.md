# Frontend Proof Audit

## Supported toolchain matrix

- Node:
  - Declared in `frontend/package.json`: `20.x`
  - Pinned in repo-managed tool versions: `20.20.2`
  - Pinned in `frontend/.nvmrc`, `frontend/.node-version`, `frontend/.tool-versions`, and `package.json#volta`
- Yarn:
  - Declared and pinned at `1.22.22`
- Python:
  - Required for `scripts/proof_frontend.py` because the proof includes the backend-owned frontend fixture drift gate.
  - CI uses Python 3.11 plus `make venv` before `make proof-frontend`.

## What the proof really covers

- Runtime verification for Node and Yarn.
- Backend-owned frontend fixture drift gate.
- ESLint.
- Jest: 19 passing tests across 5 suites.
- Production build.

This is meaningful UI and boundary coverage. It is not just a static install/build smoke test.

## Proven

- Host drift is explicit. On this machine, `node --version` is `v25.9.0`, and `./.venv/bin/python scripts/proof_frontend.py` fails fast before doing any other work. That is correct fail-fast behavior.
- Supported-toolchain proof succeeded in a disposable Node `20.20.2` environment with Yarn `1.22.22` and a bootstrapped Python test environment.
- The workspace receipt was refreshed from that supported-toolchain proof and now records a current-snapshot pass in `artifacts/proof/frontend.json`.

## Mismatches between docs and reality

- Version pins are consistent across docs, repo manifests, and CI.
- The main friction point is environmental, not version drift: a frontend-only Node container is not enough to run `scripts/proof_frontend.py`. The proof wrapper also needs Python packaging support plus the backend test dependencies because it runs the fixture drift gate.
- That requirement is indirectly documented through the normal repo bootstrap flow (`make venv`), but it is easy to miss if someone treats the frontend proof as Node-only.

## Avoidable brittleness

- A stock `node:20.20.2` container is insufficient by itself. It lacks `python3-pip` and `python3-venv`, so containerized proof reproduction requires explicit Python bootstrap first.
- `yarn install --frozen-lockfile` emits multiple peer-dependency warnings. They do not currently break the proof, but they are ongoing upgrade risk.
- The copied receipt reflects the disposable proof environment, so the command path recorded in `artifacts/proof/frontend.json` points at `/tmp/Hysight` rather than the host workspace path.

## Commands and evidence

Host failure under unsupported Node:

```bash
./.venv/bin/python scripts/proof_frontend.py
```

Supported-toolchain proof used for the refreshed receipt:

```bash
docker run ... node:20.20.2 ... ./.venv/bin/python scripts/proof_frontend.py
```

Current evidence:

- Receipt: `artifacts/proof/frontend.json`
- Fixture drift JUnit: `test_reports/frontend-fixture-drift.xml`
- Jest JSON: `test_reports/frontend-jest.json`

## Narrow fix list

- Document explicitly that `make proof-frontend` depends on the baseline Python test environment, not only Node and Yarn.
- If containerized frontend proof is meant to be a supported operator path, provide a checked-in wrapper that bootstraps the required Python packages before running `scripts/proof_frontend.py`.
- Triage the current peer-dependency warnings before the next frontend dependency refresh.