#!/usr/bin/env bash
set -euo pipefail

# ── AI Fraud Detection — Full Dev Startup ──────────────────
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${BLUE}[DEV]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    log "Shutting down..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null && echo "  Backend stopped"
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "  Frontend stopped"
    ok "Services stopped. Docker infra still running (use 'make infra-down' to stop)"
}
trap cleanup EXIT INT TERM

# ── 1) Copy .env if needed ──────────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        ok "Created .env from .env.example"
    else
        fail "No .env file found"
        exit 1
    fi
fi

# ── 2) Start Docker infrastructure ─────────────────────────
log "Starting Docker infrastructure..."
docker compose up -d 2>&1 | tail -5
ok "Docker containers starting"

# ── 3) Wait for PostgreSQL ──────────────────────────────────
log "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U postgres -d frauddb -q 2>/dev/null; then
        ok "PostgreSQL is ready"
        break
    fi
    if [ "$i" = "30" ]; then
        warn "PostgreSQL may not be ready yet — continuing anyway"
    fi
    sleep 1
done

# ── 4) Wait for Redis ──────────────────────────────────────
log "Waiting for Redis..."
for i in $(seq 1 15); do
    if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
        ok "Redis is ready"
        break
    fi
    if [ "$i" = "15" ]; then
        warn "Redis may not be ready yet — continuing anyway"
    fi
    sleep 1
done

# ── 5) Wait for Kafka ──────────────────────────────────────
log "Waiting for Kafka..."
for i in $(seq 1 30); do
    if docker compose exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:9092 >/dev/null 2>&1; then
        ok "Kafka is ready"
        break
    fi
    if [ "$i" = "30" ]; then
        warn "Kafka may not be ready — continuing anyway"
    fi
    sleep 1
done

# ── 6) Start Backend ──────────────────────────────────────
log "Starting backend..."
bash "$DIR/scripts/start-backend.sh" &
BACKEND_PID=$!
sleep 3
ok "Backend starting (PID: $BACKEND_PID)"

# ── 7) Start Frontend ─────────────────────────────────────
log "Starting frontend..."
bash "$DIR/scripts/start-frontend.sh" &
FRONTEND_PID=$!
sleep 2
ok "Frontend starting (PID: $FRONTEND_PID)"

# ── 8) Done ────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════=${NC}"
echo -e "${GREEN}  AI Fraud Detection System is running!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════=${NC}"
echo ""
echo -e "  Frontend:     ${CYAN}http://localhost:5173${NC}"
echo -e "  Backend API:  ${CYAN}http://localhost:8000${NC}"
echo -e "  API Docs:     ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  Health:       ${CYAN}http://localhost:8000/health${NC}"
echo -e "  MLflow:       ${CYAN}http://localhost:5000${NC}"
echo -e "  Kafka UI:     ${CYAN}http://localhost:8080${NC}"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop backend + frontend"
echo ""

wait
