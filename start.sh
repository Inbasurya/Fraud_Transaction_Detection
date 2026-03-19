#!/usr/bin/env bash
set -euo pipefail

# ─── AI Fraud Detection System — Startup Script ───────────────

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${BLUE}[START]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail()  { echo -e "${RED}[FAIL]${NC} $1"; }

# ─── 1) Copy .env if needed ──────────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        ok "Created .env from .env.example"
    else
        warn "No .env or .env.example found"
    fi
fi

# ─── 2) Start Docker infrastructure ──────────────────────────
log "Starting Docker containers (postgres, redis, kafka, mlflow)…"
docker compose up -d --build 2>&1 | tail -5
ok "Docker containers started"

# ─── 3) Wait for PostgreSQL ──────────────────────────────────
log "Waiting for PostgreSQL…"
for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U frauduser -d frauddb -q 2>/dev/null; then
        ok "PostgreSQL is ready"
        break
    fi
    if [ "$i" = "30" ]; then
        fail "PostgreSQL not ready after 30s"
        exit 1
    fi
    sleep 1
done

# ─── 4) Wait for Redis ───────────────────────────────────────
log "Waiting for Redis…"
for i in $(seq 1 15); do
    if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
        ok "Redis is ready"
        break
    fi
    if [ "$i" = "15" ]; then
        fail "Redis not ready after 15s"
        exit 1
    fi
    sleep 1
done

# ─── 5) Wait for Kafka ───────────────────────────────────────
log "Waiting for Kafka…"
for i in $(seq 1 30); do
    if docker compose exec -T kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1; then
        ok "Kafka is ready"
        break
    fi
    if [ "$i" = "30" ]; then
        warn "Kafka may not be ready — continuing anyway"
        break
    fi
    sleep 1
done

# ─── 6) Run Alembic migrations ───────────────────────────────
log "Running database migrations…"
cd backend
if command -v alembic >/dev/null 2>&1; then
    alembic upgrade head 2>&1 || warn "Alembic migration failed (may already be applied)"
    ok "Database migrations applied"
else
    warn "alembic not installed — skipping migrations"
fi
cd "$DIR"

# ─── 7) Train ML model if not present ────────────────────────
if [ ! -f ml_models/fraud_xgb.pkl ]; then
    log "Training ML model (first run)…"
    python -m backend.ml.train_paysim 2>&1 | tail -5 || warn "ML training failed"
    ok "ML model trained"
else
    ok "ML model already exists"
fi

# ─── 8) Install frontend deps if needed ──────────────────────
if [ ! -d frontend/node_modules ]; then
    log "Installing frontend dependencies…"
    cd frontend
    npm install 2>&1 | tail -3
    cd "$DIR"
    ok "Frontend dependencies installed"
fi

# ─── 9) Start backend ────────────────────────────────────────
log "Starting FastAPI backend on port 8000…"
cd "$DIR"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
ok "Backend started (PID: $BACKEND_PID)"

# ─── 10) Start frontend ──────────────────────────────────────
log "Starting Vite frontend on port 5173…"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd "$DIR"
ok "Frontend started (PID: $FRONTEND_PID)"

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  AI Fraud Detection System is running!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend:    ${BLUE}http://localhost:5173${NC}"
echo -e "  Backend API: ${BLUE}http://localhost:8000${NC}"
echo -e "  API Docs:    ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  MLflow:      ${BLUE}http://localhost:5001${NC}"
echo -e "  Kafka UI:    ${BLUE}http://localhost:8080${NC}"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop all services"
echo ""

# Trap cleanup
cleanup() {
    echo ""
    log "Shutting down…"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    ok "Services stopped. Docker containers still running (use 'docker compose down' to stop)"
}
trap cleanup EXIT INT TERM

wait
