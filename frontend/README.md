# Hysight Frontend

This package is the React frontend for Hysight. It uses the Create React App toolchain with CRACO overrides and talks to the FastAPI backend under `/api`.

## Runtime Expectations

- Local development assumes the backend is running on `http://localhost:8000`.
- The frontend dev server proxies `/api` requests to the backend automatically, so no environment variable is required for the default local workflow.
- Set `REACT_APP_BACKEND_URL` only when you need to target a different backend origin without relying on the dev proxy.
- Chat streaming uses `POST /api/hca/run/stream`.
- The operator console reads `GET /api/subsystems` to surface degraded dependencies and operating mode.
- Replay-backed approval context in chat and the operator console comes from the run summary returned by `GET /api/hca/run/{run_id}` and the approve/deny routes.
- The memory browser uses `GET /api/hca/memory/list` and `DELETE /api/hca/memory/{memory_id}`.

## Install

This package declares Yarn 1 as its package manager and targets Node 20 to
match `.github/workflows/frontend-proof.yml`.

`yarn install` now runs a preinstall runtime guard that fails with a clear
message when Node 20.x or Yarn 1.22.22 are not active.

If you use a version manager, switch to the pinned runtime first. The frontend
directory includes `.nvmrc`, `.node-version`, `.tool-versions`, `mise.toml`,
and a `volta` block in `package.json`, so the common Node version managers can
align with CI's Node 20 target without guesswork.

```bash
cd frontend

# nvm
nvm install 20
nvm use

# fnm reads .node-version
fnm use

# asdf reads .tool-versions
asdf install
asdf current

# mise reads mise.toml
mise install
mise current

# or confirm the pinned version directly
cat .node-version
```

If your version manager does not read those files automatically, select any
Node 20.x runtime manually before running Yarn commands.

```bash
yarn install
```

If you need a non-default backend origin, copy `.env.example` to `.env.local` and set `REACT_APP_BACKEND_URL`.

## Available Scripts

### `yarn start`

Runs the CRACO-backed development server. In local development, `/api` requests proxy to `http://localhost:8000` by default.

### `yarn test`

Runs the frontend test command through CRACO.

### `yarn build`

Builds the production bundle into `build/`.
