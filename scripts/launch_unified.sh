#!/usr/bin/env bash
# scripts/launch_unified.sh — launch Hysight backend + frontend together
#
# Usage:
#   ./scripts/launch_unified.sh                       # python memory backend (default)
#   MEMORY_BACKEND=rust ./scripts/launch_unified.sh   # rust sidecar mode
#
# Both processes run as children of this script.  Ctrl-C (or SIGTERM) stops both.
#
# Environment variables (all optional):
#   BACKEND_PORT        — backend HTTP port          (default: 8000)
#   FRONTEND_PORT       — frontend dev-server port   (default: 3000)
#   MEMORY_BACKEND      — "python" or "rust"         (default: python)
#   MEMORY_SERVICE_URL  — required when MEMORY_BACKEND=rust
#   HCA_STORAGE_ROOT    — absolute path              (default: <repo>/storage)
#   MEMORY_STORAGE_DIR  — must be inside HCA_STORAGE_ROOT

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
BOOTSTRAP_HINT="See BOOTSTRAP.md for the supported bootstrap path."

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
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
MEMORY_BACKEND="${MEMORY_BACKEND:-python}"
HCA_STORAGE_ROOT="${HCA_STORAGE_ROOT:-$REPO_ROOT/storage}"
MEMORY_STORAGE_DIR="${MEMORY_STORAGE_DIR:-$HCA_STORAGE_ROOT/memory}"

# ── Validate MEMORY_BACKEND ───────────────────────────────────────────────
case "$MEMORY_BACKEND" in
  python|rust) ;;
  *)
    echo "ERROR: MEMORY_BACKEND must be 'python' or 'rust'." >&2
    exit 1
    ;;
esac

# ── Validate storage paths ────────────────────────────────────────────────
if [[ "$HCA_STORAGE_ROOT" != /* ]]; then
  echo "ERROR: HCA_STORAGE_ROOT must be an absolute path when set." >&2
  exit 1
fi
if [[ "$MEMORY_STORAGE_DIR" != /* ]]; then
  echo "ERROR: MEMORY_STORAGE_DIR must be an absolute path when set." >&2
  exit 1
fi
case "$MEMORY_STORAGE_DIR" in
  "$HCA_STORAGE_ROOT"/*) ;;
  *)
    echo "ERROR: MEMORY_STORAGE_DIR must be inside HCA_STORAGE_ROOT." >&2
    exit 1
    ;;
esac

# ── Validate python-mode constraint ──────────────────────────────────────
if [ "$MEMORY_BACKEND" = "python" ] && [ -n "${MEMORY_SERVICE_URL:-}" ]; then
  echo "ERROR: MEMORY_SERVICE_URL must be unset unless MEMORY_BACKEND=rust." >&2
  exit 1
fi

export MEMORY_BACKEND
export HCA_STORAGE_ROOT
export MEMORY_STORAGE_DIR

# ── Resolve Python interpreter ────────────────────────────────────────────
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  DEFAULT_PYTHON="$REPO_ROOT/.venv/bin/python"
else
  DEFAULT_PYTHON="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
fi
PYTHON="${PYTHON:-$DEFAULT_PYTHON}"

if [ -z "$PYTHON" ] || ! [ -x "$PYTHON" ]; then
  echo "ERROR: Python interpreter not found. Run: make venv" >&2
  echo "       $BOOTSTRAP_HINT" >&2
  exit 1
fi

# ── Check uvicorn ─────────────────────────────────────────────────────────
if ! "$PYTHON" -c "import uvicorn" 2>/dev/null; then
  echo "ERROR: uvicorn not installed. Run: make venv" >&2
  echo "       $BOOTSTRAP_HINT" >&2
  exit 1
fi

# ── Check hca editable install ────────────────────────────────────────────
export HYSIGHT_EXPECTED_HCA_DIR="$REPO_ROOT/hca/src/hca"
if ! "$PYTHON" - <<'PY' >/dev/null 2>&1
import importlib.util, os, pathlib, sys
expected = pathlib.Path(os.environ["HYSIGHT_EXPECTED_HCA_DIR"]).resolve()
spec = importlib.util.find_spec("hca")
origin = None
if spec is not None and spec.origin is not None:
    origin = pathlib.Path(spec.origin).resolve().parent
sys.exit(0 if origin == expected else 1)
PY
then
  echo "ERROR: hca package not installed from ./hca. Run: make venv" >&2
  echo "       $BOOTSTRAP_HINT" >&2
  exit 1
fi

# ── Check memory_service ──────────────────────────────────────────────────
if ! "$PYTHON" -c "import memory_service" 2>/dev/null; then
  echo "ERROR: memory_service package not found. Run: make venv" >&2
  echo "       $BOOTSTRAP_HINT" >&2
  exit 1
fi

# ── Rust sidecar checks ───────────────────────────────────────────────────
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
    echo "         make run-memvid-sidecar" >&2
    echo "       $BOOTSTRAP_HINT" >&2
    exit 1
  fi
  echo "Sidecar healthy ✓"
fi

# ── Resolve yarn / node for frontend ─────────────────────────────────────
YARN_BIN="$(command -v yarn 2>/dev/null || true)"
if [ -z "$YARN_BIN" ]; then
  echo "WARNING: yarn not found — frontend will not be started." >&2
  LAUNCH_FRONTEND=0
else
  LAUNCH_FRONTEND=1
fi

# ── Print banner ──────────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║  Hysight — unified launcher                   ║"
echo "╠═══════════════════════════════════════════════╣"
printf "║  memory backend : %-27s║\n" "$MEMORY_BACKEND"
printf "║  run storage    : %-27s║\n" "$HCA_STORAGE_ROOT"
printf "║  backend port   : %-27s║\n" "$PORT"
if [ "$LAUNCH_FRONTEND" = "1" ]; then
printf "║  frontend port  : %-27s║\n" "$FRONTEND_PORT"
fi
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── Trap to kill all children on exit ────────────────────────────────────
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Shutting down…"
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ── Launch backend ────────────────────────────────────────────────────────
echo "Starting backend  → http://localhost:$PORT …"
"$PYTHON" -m uvicorn backend.server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --reload &
BACKEND_PID=$!

# ── Launch frontend ───────────────────────────────────────────────────────
if [ "$LAUNCH_FRONTEND" = "1" ]; then
  echo "Starting frontend → http://localhost:$FRONTEND_PORT …"
  (
    cd "$FRONTEND_DIR"
    PORT="$FRONTEND_PORT" \
    REACT_APP_API_URL="http://localhost:$PORT" \
    "$YARN_BIN" --ignore-engines start
  ) &
  FRONTEND_PID=$!
fi

echo ""
echo "Both services started.  Press Ctrl-C to stop."
echo ""

# ── Wait for any child to exit (unexpected) ───────────────────────────────
wait -n 2>/dev/null || wait
