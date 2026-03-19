#!/usr/bin/env bash
set -euo pipefail

# ── AI Fraud Detection — Start Backend ─────────────────────
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[BACKEND]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }

# ── Activate venv ────────────────────────────────────────────
if [ -d "venv_mac" ]; then
    source venv_mac/bin/activate
    ok "Virtual environment activated (venv_mac)"
elif [ -d "venv311" ]; then
    source venv311/Scripts/activate 2>/dev/null || source venv311/bin/activate
    ok "Virtual environment activated (venv311)"
elif [ -d ".venv" ]; then
    source .venv/bin/activate
    ok "Virtual environment activated (.venv)"
fi

# ── Load .env ────────────────────────────────────────────────
if [ -f .env ]; then
    set -a
    source .env
    set +a
    ok "Environment loaded from .env"
fi

# ── Kill any existing process on port 8000 ──────────────────
PORT=8000
if lsof -ti :$PORT >/dev/null 2>&1; then
    warn "Port $PORT is busy, killing existing process..."
    lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
    ok "Port $PORT freed"
fi

# ── Install deps if needed ──────────────────────────────────
cd backend
if ! python -c "import fastapi" 2>/dev/null; then
    log "Installing Python dependencies..."
    pip install -r requirements.txt -q
    ok "Dependencies installed"
fi

# ── Run Alembic migrations ──────────────────────────────────
if command -v alembic >/dev/null 2>&1; then
    log "Running database migrations..."
    alembic upgrade head 2>&1 || warn "Migration failed (may already be applied)"
    ok "Migrations done"
fi

# ── Start uvicorn ───────────────────────────────────────────
log "Starting FastAPI on http://localhost:$PORT ..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload
