.PHONY: infra infra-down infra-logs backend frontend dev clean status help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Infrastructure ───────────────────────────────────────────
infra: ## Start Docker infrastructure (Postgres, Redis, Kafka, MLflow, Kafka-UI)
	docker compose up -d
	@echo "\n✅ Infrastructure started"
	@echo "   Postgres  → localhost:5432"
	@echo "   Redis     → localhost:6379"
	@echo "   Kafka     → localhost:9092"
	@echo "   MLflow    → http://localhost:5000"
	@echo "   Kafka UI  → http://localhost:8080"

infra-down: ## Stop Docker infrastructure
	docker compose down
	@echo "✅ Infrastructure stopped"

infra-logs: ## Tail Docker infrastructure logs
	docker compose logs -f

# ── Backend ──────────────────────────────────────────────────
backend: ## Start FastAPI backend on :8000
	bash scripts/start-backend.sh

# ── Frontend ─────────────────────────────────────────────────
frontend: ## Start Vite frontend on :5173
	bash scripts/start-frontend.sh

# ── Full Stack ───────────────────────────────────────────────
dev: ## Start everything (infra + backend + frontend)
	bash scripts/start-dev.sh

# ── Testing ──────────────────────────────────────────────────
verify: ## Run functional verification suite (Check Health, Metrics, Rate Limits)
	python3 -m pytest tests/test_verify_system.py -v

test: ## Run unit tests
	python3 -m pytest tests/

load-test: ## Run Locust load test (requires backend running)
	locust -f tests/load_test.py --host=http://localhost:8000

# ── Utilities ────────────────────────────────────────────────
clean: ## Stop infra and kill backend/frontend processes
	-docker compose down
	-lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	-lsof -ti:5173 | xargs kill -9 2>/dev/null || true
	@echo "✅ All services stopped"

status: ## Show status of all services
	@echo "── Docker ──"
	@docker compose ps 2>/dev/null || echo "  Docker services not running"
	@echo "\n── Backend (port 8000) ──"
	@lsof -i:8000 2>/dev/null | head -3 || echo "  Not running"
	@echo "\n── Frontend (port 5173) ──"
	@lsof -i:5173 2>/dev/null | head -3 || echo "  Not running"

migrate: ## Run Alembic migrations
	cd backend && alembic upgrade head

logs-backend: ## Tail backend logs
	@echo "Backend runs in foreground — use 'make backend' in a separate terminal"
