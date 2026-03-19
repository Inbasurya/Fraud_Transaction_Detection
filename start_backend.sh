#!/bin/bash
cd /Users/inbasurya/Documents/AI_POWERD_FRAUD_TRANSACTION/fraud-detection-system/backend
exec /Users/inbasurya/Documents/AI_POWERD_FRAUD_TRANSACTION/fraud-detection-system/venv_mac/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
