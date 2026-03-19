# Example API Responses

## GET /api/model/metrics

```json
{
  "kaggle_model": {
    "best_model": "XGBoost",
    "models": {
      "Random Forest": {"precision": 0.91, "recall": 0.86, "f1_score": 0.88, "roc_auc": 0.97},
      "XGBoost": {"precision": 0.94, "recall": 0.89, "f1_score": 0.91, "roc_auc": 0.98}
    }
  },
  "hybrid_weights": {
    "supervised_model_probability": 0.4,
    "behavioral_anomaly_score": 0.3,
    "graph_cluster_risk": 0.2,
    "rule_engine_score": 0.1
  }
}
```

## POST /api/process_transaction

```json
{
  "transaction_id": "TX1234567",
  "user_id": 120,
  "amount": 4199.44,
  "merchant": "Crypto Exchange X",
  "location": "Berlin",
  "device_type": "mobile",
  "timestamp": "2026-03-09T12:01:12"
}
```

## GET /api/fraud-network

```json
{
  "nodes": [{"id": "account_120", "type": "account", "cluster_label": 3, "cluster_risk": 0.78}],
  "edges": [{"source": "account_120", "target": "device_mobile", "risk": 0.81}],
  "community_count": 12,
  "cluster_labels": {"account_120": 3}
}
```

## GET /api/model/health

```json
{
  "status": "drift_warning",
  "feature_distribution": {"amount_psi": 0.25, "hour_psi": 0.13},
  "prediction_distribution": {"SAFE": 0.82, "SUSPICIOUS": 0.12, "FRAUD": 0.06},
  "fraud_rate_changes": {"current_fraud_rate": 0.06, "baseline_fraud_rate": 0.02, "delta": 0.04},
  "alerts": ["Amount feature distribution drift detected"]
}
```
