# PROJECT_CONTEXT: AI-Powered Fraud Detection System

## 🎯 Core Mission
The primary purpose of this project is to provide a real-time, high-accuracy fraud detection and prevention system for financial transactions. It leverages machine learning (XGBoost), rule-based engines, and behavioral pattern matching (Redis) to block fraudulent transactions, warn customers via SMS, and provide a comprehensive dashboard for manual investigation.

## 🏗 System Architecture
The project is split into a modern full-stack architecture with a focus on real-time data streaming.

### Folder Structure
- `/backend`: FastAPI-based server handling risk scoring, features, and WebSocket streaming.
  - `/core`: Engines for risk scoring, ML processing, rule evaluation, and behavioral memory.
  - `/routers`: API endpoints and WebSocket handlers for live transaction streaming.
  - `/ml`: Training scripts and model evaluation.
  - `/kafka`: Infrastructure for handling high-volume transaction messages.
- `/frontend`: React + Vite dashboard for real-time monitoring and investigation.
  - `/src/pages`: Key views like Dashboard, Alerts, Graph visualization, and Customer Intelligence.
  - `/src/context`: Management of real-time transaction state and stats.
- `/data`: Storage for transaction logs and synthetic dataset generation.
- `/models`: Serialized ML models (`xgboost_fraud.pkl`) and scalers.

### Data Flow
1. **Streaming:** Synthetic transactions are generated and pushed via Kafka/Local simulation.
2. **Scoring:** The Backend evaluates transactions through a 4-stage ensemble (45% ML, 25% Rules, 20% Behavioral, 10% Graph):
   - **ML Engine (45%):** XGBoost model with SHAP explanations and Waterfall Plots.
   - **Rule Engine (25%):** Deterministic logic (e.g., AML Structuring R007).
   - **Behavioral DNA (20%):** Redis-based profiling for deviation detection.
   - **Graph Engine (10%):** Network science for fraud ring identification.
3. **Actions:** Transactions are labeled (safe, suspicious, fraudulent) and actions are taken (Approve, Block, SMS Alert).
4. **Broadcast:** Results are pushed via WebSockets to the Frontend for live updates.

## 💻 Tech Stack
- **Backend:** Python 3.9+, FastAPI, Redis (for memory), Kafka (for data pipeline), SQLAlchemy/SQLite (for persistent data).
- **Frontend:** React 18, Vite, Tailwind CSS, Recharts (for analytics), D3/React-force-graph (for fraud networks), Framer Motion (for animations).
- **AI/ML:** XGBoost (main classifier), SHAP (model explainability), Scikit-learn (preprocessing).

## 🛡 State Machine & Gatekeeper Logic (Phase 5)
Transactions follow a strict state machine based on the final ensemble risk score:

| Risk Score | Action | Logic | Triggered Action |
|------------|--------|-------------|------------------|
| **>= 85** | `403_forbidden` | Hard Stop | Card Freeze (Redis) + "CRITICAL" SMS |
| **50 - 70** | `pending` | Step-up Auth | "FraudGuard Alert" Warning SMS |
| **30 - 49** | `monitor` | Monitor | Augmented logging |
| **< 30** | `approve` | Immediate clearance | Immediate clearance |

### Production SMS Templates
- **Warning (50-70):** "FraudGuard Alert: A suspicious transaction of ₹[Amount] at [Merchant] is being attempted. If this is not you, please respond immediately."
- **Blocking (>= 85):** "CRITICAL: Your card was blocked for a fraudulent transaction of ₹[Amount] at [Merchant]. Contact support to unfreeze."

## 🤖 Agent Roles
- **Fintech Security Engineer:** Responsible for implementing backend logic (SMS, Memory, Gatekeeper), fixing bugs, and ensuring paper alignment.
- **Architect Advisor:** Monitors global project context and ensures architectural consistency.

## 📍 Current State
- **Working Features:**
  - Real-time transaction streaming with **Gatekeeper Hard-Stops** (403 Forbidden).
  - Automated SMS alerts with **Production Security Templates** (₹ Currency support).
  - Card Freeze (Redis) for high-risk detection.
  - Multi-engine Ensemble (45% ML, 25% Rule, 20% DNA, 10% Graph).
  - Hard-Negative injected training set (AUC 0.88).
- **Immediate Next Goal:**
  - Conduct full performance benchmarks under load (sub-15ms target).

## ⚠️ Key Constraints
- **Security:** Use `.env` for Twilio; use `asyncio.to_thread` for non-blocking I/O.
- **Performance:** Risk scoring must happen in <15ms end-to-end.
- **Accuracy:** Gold standard AUC-ROC target is 94.1%.
