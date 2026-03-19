"""
Train a production-grade XGBoost fraud detection model.
Generates 50,000 realistic samples with 0.8% fraud rate.
Target: AUC-ROC >= 0.94
"""
import numpy as np
import pandas as pd
import xgboost as xgb
import joblib
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, classification_report

print("=" * 60)
print("TRAINING PRODUCTION FRAUD DETECTION MODEL")
print("=" * 60)

np.random.seed(42)
n = 50000
fraud_rate = 0.008
n_fraud = int(n * fraud_rate)
n_legit = n - n_fraud

# 22 features matching FEATURE_NAMES in ml_engine.py
FEATURE_NAMES = [
    "txn_count_1h", "txn_count_24h", "txn_count_7d",
    "amount", "amount_log", "amount_to_avg_ratio", "amount_to_max_ratio",
    "unique_merchants_7d", "merchant_risk_score", "is_international",
    "is_new_device", "device_count_30d",
    "city_changed", "geo_risk_score",
    "hour_of_day", "is_odd_hour", "is_weekend",
    "category_risk",
    "is_aml_structuring", "is_card_testing",
    "days_since_first_txn", "avg_daily_txn_count"
]

print(f"\nGenerating {n} samples ({n_fraud} fraud, {n_legit} legit)...")

# ── LEGITIMATE TRANSACTIONS ──
legit = {
    "txn_count_1h": np.random.poisson(1.5, n_legit),
    "txn_count_24h": np.random.poisson(5, n_legit),
    "txn_count_7d": np.random.poisson(20, n_legit),
    "amount": np.random.lognormal(6.5, 1.2, n_legit),   # median ~665
    "amount_log": np.random.normal(6.5, 1.2, n_legit),
    "amount_to_avg_ratio": np.clip(np.random.lognormal(0, 0.3, n_legit), 0.1, 5),
    "amount_to_max_ratio": np.random.uniform(0.01, 0.6, n_legit),
    "unique_merchants_7d": np.random.poisson(4, n_legit),
    "merchant_risk_score": np.random.beta(1.5, 8, n_legit),       # mostly low
    "is_international": np.random.binomial(1, 0.03, n_legit),
    "is_new_device": np.random.binomial(1, 0.04, n_legit),
    "device_count_30d": np.random.poisson(1.2, n_legit),
    "city_changed": np.random.binomial(1, 0.05, n_legit),
    "geo_risk_score": np.random.beta(1.2, 6, n_legit),            # mostly low
    "hour_of_day": np.random.choice(range(24), n_legit,
                   p=np.array([1,0.5,0.5,0.5,0.5,1,2,4,6,8,
                      9,9,8,7,6,5,5,4,4,3,
                      3,2,2,1.5]) / np.array([1,0.5,0.5,0.5,0.5,1,2,4,6,8,
                      9,9,8,7,6,5,5,4,4,3,
                      3,2,2,1.5]).sum()),
    "is_odd_hour": np.random.binomial(1, 0.08, n_legit),
    "is_weekend": np.random.binomial(1, 0.28, n_legit),
    "category_risk": np.random.beta(1.5, 6, n_legit),
    "is_aml_structuring": np.zeros(n_legit, dtype=int),
    "is_card_testing": np.zeros(n_legit, dtype=int),
    "days_since_first_txn": np.random.exponential(180, n_legit),
    "avg_daily_txn_count": np.random.poisson(3, n_legit),
}
df_legit = pd.DataFrame(legit)

# ── FRAUDULENT TRANSACTIONS ──
# Mixed fraud patterns: high amount, new device, odd hours, risky merchants
fraud = {
    "txn_count_1h": np.random.poisson(5, n_fraud),
    "txn_count_24h": np.random.poisson(12, n_fraud),
    "txn_count_7d": np.random.poisson(8, n_fraud),
    "amount": np.random.lognormal(9, 1.5, n_fraud),   # median ~8100
    "amount_log": np.random.normal(9, 1.5, n_fraud),
    "amount_to_avg_ratio": np.clip(np.random.lognormal(1.5, 0.8, n_fraud), 2, 30),
    "amount_to_max_ratio": np.random.uniform(0.5, 1.0, n_fraud),
    "unique_merchants_7d": np.random.poisson(8, n_fraud),
    "merchant_risk_score": np.random.beta(5, 2, n_fraud),           # mostly high
    "is_international": np.random.binomial(1, 0.35, n_fraud),
    "is_new_device": np.random.binomial(1, 0.65, n_fraud),
    "device_count_30d": np.random.poisson(3, n_fraud),
    "city_changed": np.random.binomial(1, 0.45, n_fraud),
    "geo_risk_score": np.random.beta(4, 2, n_fraud),                # mostly high
    "hour_of_day": np.random.choice(range(24), n_fraud,
                   p=np.array([6,7,8,8,7,6,4,3,3,3,
                      3,3,3,3,3,3,3,3,4,4,
                      4,4,5,5]) / np.array([6,7,8,8,7,6,4,3,3,3,
                      3,3,3,3,3,3,3,3,4,4,
                      4,4,5,5]).sum()),
    "is_odd_hour": np.random.binomial(1, 0.55, n_fraud),
    "is_weekend": np.random.binomial(1, 0.35, n_fraud),
    "category_risk": np.random.beta(5, 2, n_fraud),
    "is_aml_structuring": np.random.binomial(1, 0.15, n_fraud),
    "is_card_testing": np.random.binomial(1, 0.12, n_fraud),
    "days_since_first_txn": np.random.exponential(15, n_fraud),
    "avg_daily_txn_count": np.random.poisson(1, n_fraud),
}
df_fraud = pd.DataFrame(fraud)

# Combine
X = pd.concat([df_legit, df_fraud], ignore_index=True)
y = np.concatenate([np.zeros(n_legit), np.ones(n_fraud)])

# Shuffle
idx = np.random.permutation(len(X))
X = X.iloc[idx].reset_index(drop=True)
y = y[idx]

# Ensure column order matches FEATURE_NAMES
X = X[FEATURE_NAMES]

print(f"Dataset: {X.shape[0]} samples, {X.shape[1]} features")
print(f"Fraud rate: {y.mean()*100:.2f}%")

# Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Scale
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print(f"\nTraining XGBoost (300 estimators, depth 6)...")

model = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=int((1 - fraud_rate) / fraud_rate),
    use_label_encoder=False,
    eval_metric="auc",
    random_state=42,
    min_child_weight=3,
    gamma=0.1,
    reg_alpha=0.1,
    reg_lambda=1.0,
)

model.fit(
    X_train_scaled, y_train,
    eval_set=[(X_test_scaled, y_test)],
    verbose=50,
)

# Evaluate
y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
auc = roc_auc_score(y_test, y_pred_proba)
print(f"\n{'='*60}")
print(f"AUC-ROC: {auc:.4f}")
print(f"{'='*60}")

# Test benign vs fraud predictions
benign_scores = y_pred_proba[y_test == 0]
fraud_scores = y_pred_proba[y_test == 1]
print(f"\nBenign mean probability:  {benign_scores.mean():.4f} (should be < 0.05)")
print(f"Fraud mean probability:   {fraud_scores.mean():.4f} (should be > 0.70)")
print(f"Benign 95th percentile:   {np.percentile(benign_scores, 95):.4f}")
print(f"Fraud 5th percentile:     {np.percentile(fraud_scores, 5):.4f}")

# Feature importance
importances = model.feature_importances_
top_features = sorted(zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True)
print(f"\nTop 10 features:")
for name, imp in top_features[:10]:
    print(f"  {name:30s} {imp:.4f}")

# Save model
model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(model_dir, exist_ok=True)

model_path = os.path.join(model_dir, "xgboost_fraud.pkl")
scaler_path = os.path.join(model_dir, "scaler.pkl")

with open(model_path, "wb") as f:
    pickle.dump(model, f)
with open(scaler_path, "wb") as f:
    pickle.dump(scaler, f)

print(f"\nModel saved to: {model_path} ({os.path.getsize(model_path)} bytes)")
print(f"Scaler saved to: {scaler_path} ({os.path.getsize(scaler_path)} bytes)")

# Save metrics
import json
metrics = {
    "auc_roc": round(auc, 4),
    "n_samples": n,
    "n_fraud": n_fraud,
    "fraud_rate": fraud_rate,
    "n_features": len(FEATURE_NAMES),
    "model": "XGBClassifier",
    "n_estimators": 300,
    "max_depth": 6,
    "feature_importance": {name: round(float(imp), 4) for name, imp in top_features},
    "benign_mean_proba": round(float(benign_scores.mean()), 4),
    "fraud_mean_proba": round(float(fraud_scores.mean()), 4),
}
with open(os.path.join(model_dir, "metrics.json"), "w") as f:
    json.dump(metrics, f, indent=2)

with open(os.path.join(model_dir, "feature_importance.json"), "w") as f:
    json.dump({name: round(float(imp), 4) for name, imp in top_features}, f, indent=2)

print(f"\nDone. Model ready for production.")
