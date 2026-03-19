# AI-Powered Real-Time Fraud Detection System

Enterprise-grade payment intelligence system detecting fraud in <200ms with Explainable AI (XAI) and Regulatory Compliance (RBI) features.

## 🚀 Key Features

### 1. Real-Time Risk Engine
- **Hybrid Scoring**: Combines XGBoost models, Graph Analysis (NetworkX), and Rule-Based logic.
- **Atomic Counters**: Redis-backed velocity tracking and global fraud rates updated in real-time.
- **Latency**: Sub-200ms decision latency for high-throughput payment gateways.

### 2. Operational Intelligence (New)
- **Live Dashboard**: Real-time metrics via `/metrics/dashboard` (Fraud Rate, Velocity, Volume).
- **Health Monitoring**: Self-healing background tasks checking Model Drift (PSI) and System Health.
- **Rate Limiting**: Protects scoring endpoints (100 req/min) using `slowapi`.

### 3. Compliance & Audit (RBI Accountability)
- **Audit Trails**: Dual-write logging to Redis Streams (Hot) and File System (Cold/Archival).
- **Explainability**: Narrative explanations for every fraud decision (SHAP-based) for customer transparency.
- **Decision Context**: Captures all model inputs, rule triggers, and risk scores.

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python 3.9+), Pydantic v2
- **Data Store**: Redis (Async), PostgreSQL (SQLAlchemy)
- **Event Streaming**: Kafka (confluent-kafka)
- **ML Ops**: MLflow, SHAP, Scikit-learn, XGBoost

## ⚡ Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.9+

### Setup
```bash
# 1. Start Infrastructure (Redis, Postgres, Kafka)
make infra

# 2. Start Backend API
make backend

# 3. Start Frontend Dashboard
make frontend
```

### Verification
Run the verification suite to ensure all components (Health, Rate Limiting, Metrics) are active:

```bash
make verify
```

## 📚 API Documentation
Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🧪 Testing
The system includes load tests (Locust) and functional verification tests (Pytest).

```bash
# Run functional verification
python -m pytest tests/test_verify_system.py -v

# Run load test (requires backend running)
locust -f tests/load_test.py
```
