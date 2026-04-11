# Hysight Frontend

This package is the React frontend for Hysight. It uses the Create React App toolchain with CRACO overrides and talks to the FastAPI backend under `/api`.

## Runtime Expectations

- Set `REACT_APP_BACKEND_URL` to the backend origin, for example `http://localhost:8000`.
- Chat streaming uses `POST /api/hca/run/stream`.
- The memory browser uses `GET /api/hca/memory/list` and `DELETE /api/hca/memory/{memory_id}`.

## Install

Examples below use `npm`, but the package also declares a Yarn 1 package manager.

```bash
npm install
```

## Available Scripts

### `npm start`

Runs the CRACO-backed development server.

### `npm test`

Runs the frontend test command through CRACO.

### `npm run build`

Builds the production bundle into `build/`.
