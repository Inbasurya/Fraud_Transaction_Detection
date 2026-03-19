# Run Guide

## 1) Backend

```bash
cd backend
./venv/bin/uvicorn app.main:app --reload --port 8000
```

## 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

## 3) Streaming Transactions

```bash
cd ..
python transaction_streamer.py --rate 1
```

## 4) Key Endpoints

- `POST /api/transaction/simulate`
- `POST /api/process_transaction`
- `GET /api/fraud_alerts`
- `GET /api/account_intelligence`
- `GET /api/model_metrics`
- `GET /api/model/metrics`
- `GET /api/model/health`
- `GET /api/fraud-network`
- `GET /api/experiments/metrics`
- `GET /api/explain/{transaction_id}`

## 5) Redis Streams (optional)

If Redis is available at `REDIS_URL`, the streaming engine auto-switches to Redis Streams mode.
Otherwise it safely falls back to in-memory queue.
