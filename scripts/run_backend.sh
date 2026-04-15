#!/usr/bin/env bash
# scripts/run_backend.sh — start the Hysight backend locally (no containers)
#
# Usage:
#   ./scripts/run_backend.sh              # python memory backend (default)
#   MEMORY_BACKEND=rust ./scripts/run_backend.sh   # rust sidecar mode

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
EXPECTED_HCA_AUTHORITY="The Python runtime package lives under ./hca and is installed editable as part of repo bootstrap."
BOOTSTRAP_HINT="See BOOTSTRAP.md for the supported bootstrap path."

# Change to repo root early so relative imports (memory_service, hca) are
# resolvable by Python regardless of the caller's working directory.
cd "$REPO_ROOT"

# ── Load .env files if present ────────────────────────────────────────────
set -a
if [ -f "$REPO_ROOT/.env" ]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
fi
if [ -f "$BACKEND_DIR/.env" ]; then
  # shellcheck disable=SC1091
  source "$BACKEND_DIR/.env"
fi
set +a

PORT="${BACKEND_PORT:-8000}"
MEMORY_BACKEND="${MEMORY_BACKEND:-python}"
HCA_STORAGE_ROOT="${HCA_STORAGE_ROOT:-$REPO_ROOT/storage}"
MEMORY_STORAGE_DIR="${MEMORY_STORAGE_DIR:-$HCA_STORAGE_ROOT/memory}"

case "$MEMORY_BACKEND" in
  python|rust)
    ;;
  *)
    echo "ERROR: MEMORY_BACKEND must be either 'python' or 'rust'." >&2
    exit 1
    ;;
esac

if [[ "$HCA_STORAGE_ROOT" != /* ]]; then
  echo "ERROR: HCA_STORAGE_ROOT must be an absolute path when set." >&2
  exit 1
fi

if [[ "$MEMORY_STORAGE_DIR" != /* ]]; then
  echo "ERROR: MEMORY_STORAGE_DIR must be an absolute path when set." >&2
  exit 1
fi

case "$MEMORY_STORAGE_DIR" in
  "$HCA_STORAGE_ROOT"/*)
    ;;
  *)
    echo "ERROR: MEMORY_STORAGE_DIR must be inside HCA_STORAGE_ROOT." >&2
    exit 1
    ;;
esac

if [ "$MEMORY_BACKEND" = "python" ] && [ -n "${MEMORY_SERVICE_URL:-}" ]; then
  echo "ERROR: MEMORY_SERVICE_URL must be unset unless MEMORY_BACKEND=rust." >&2
  exit 1
fi

export MEMORY_BACKEND
export HCA_STORAGE_ROOT
export MEMORY_STORAGE_DIR

echo ""
echo "═══════════════════════════════════════════════"
echo "  Hysight backend"
echo "  memory backend : $MEMORY_BACKEND"
echo "  run storage    : $HCA_STORAGE_ROOT"
echo "  memory storage : $MEMORY_STORAGE_DIR"
echo "  port           : $PORT"
echo "═══════════════════════════════════════════════"
echo ""

# ── Validate prerequisites ────────────────────────────────────────────────

# Python
if ! command -v python &>/dev/null && ! command -v python3 &>/dev/null; then
  echo "ERROR: python not found. Install Python 3.11+ and try again." >&2
  echo "       $BOOTSTRAP_HINT" >&2
  exit 1
fi
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  DEFAULT_PYTHON="$REPO_ROOT/.venv/bin/python"
else
  DEFAULT_PYTHON="$(command -v python3 || command -v python)"
fi
PYTHON="${PYTHON:-$DEFAULT_PYTHON}"

# uvicorn
if ! "$PYTHON" -c "import uvicorn" 2>/dev/null; then
  echo "ERROR: uvicorn not installed." >&2
  echo "       Run: make venv" >&2
  echo "       $BOOTSTRAP_HINT" >&2
  exit 1
fi

export HYSIGHT_EXPECTED_HCA_DIR="$REPO_ROOT/hca/src/hca"
if ! "$PYTHON" - <<'PY' >/dev/null 2>&1
import importlib.util
import os
import pathlib
import sys

expected = pathlib.Path(os.environ["HYSIGHT_EXPECTED_HCA_DIR"]).resolve()
spec = importlib.util.find_spec("hca")
origin = None
if spec is not None and spec.origin is not None:
    origin = pathlib.Path(spec.origin).resolve().parent
sys.exit(0 if origin == expected else 1)
PY
then
  echo "ERROR: $EXPECTED_HCA_AUTHORITY" >&2
  echo "       Repair:" >&2
  echo "         make venv" >&2
  echo "       $BOOTSTRAP_HINT" >&2
  exit 1
fi

# memory_service importable
if ! "$PYTHON" -c "import memory_service" 2>/dev/null; then
  echo "ERROR: memory_service package not found on sys.path." >&2
  echo "       Run: make venv" >&2
  echo "       $BOOTSTRAP_HINT" >&2
  exit 1
fi

# rust sidecar checks
if [ "$MEMORY_BACKEND" = "rust" ]; then
  if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl not found. Install curl and try again." >&2
    exit 1
  fi
  if [ -z "${MEMORY_SERVICE_URL:-}" ]; then
    echo "ERROR: MEMORY_BACKEND=rust requires MEMORY_SERVICE_URL to be set." >&2
    echo "       Example: MEMORY_SERVICE_URL=http://localhost:3031" >&2
    echo "       $BOOTSTRAP_HINT" >&2
    exit 1
  fi
  echo "Probing sidecar at $MEMORY_SERVICE_URL/health …"
  if ! curl --fail --silent --connect-timeout 2 --max-time 5 \
    "$MEMORY_SERVICE_URL/health" >/dev/null; then
    echo "ERROR: memvid sidecar not reachable at $MEMORY_SERVICE_URL/health." >&2
    echo "       Start the sidecar first:" >&2
    echo "         cargo run --manifest-path memvid_service/Cargo.toml --release" >&2
    echo "       Or use Docker: docker compose -f compose.yml -f compose.sidecar.yml up" >&2
    echo "       $BOOTSTRAP_HINT" >&2
    exit 1
  fi
  echo "Sidecar healthy ✓"
fi

echo ""
echo "Starting backend on http://localhost:$PORT …"
echo "Health check : curl http://localhost:$PORT/api/"
echo ""

exec "$PYTHON" -m uvicorn backend.server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --reload
