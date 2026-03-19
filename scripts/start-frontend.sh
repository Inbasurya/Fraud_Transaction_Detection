#!/usr/bin/env bash
set -euo pipefail

# ── AI Fraud Detection — Start Frontend ────────────────────
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR/frontend"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[FRONTEND]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# ── Kill any existing process on port 5173 ──────────────────
PORT=5173
if lsof -ti :$PORT >/dev/null 2>&1; then
    warn "Port $PORT is busy, killing existing process..."
    lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
    ok "Port $PORT freed"
fi

# ── Install deps if needed ──────────────────────────────────
if [ ! -d "node_modules" ]; then
    log "Installing npm dependencies..."
    npm install
    ok "Dependencies installed"
fi

# ── Start Vite ──────────────────────────────────────────────
log "Starting Vite on http://localhost:$PORT ..."
exec npx vite --host 0.0.0.0 --port $PORT
