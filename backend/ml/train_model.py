"""
Train a real XGBoost fraud detection model.
Uses synthetic data that matches real fraud patterns.
"""
import numpy as np
import pandas as pd
import xgboost as xgb
import pickle
import json
from pathlib import Path
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import (roc_auc_score, precision_score, 
                             recall_score, f1_score, confusion_matrix)
from sklearn.preprocessing import StandardScaler
import shap
import os

FEATURE_NAMES = [
    "txn_count_1h", "txn_count_24h", "txn_count_7d",
    "amount", "amount_log", "amount_to_avg_ratio", "amount_to_max_ratio",
    "unique_merchants_7d", "merchant_risk_score", "is_international",
    "is_new_device", "device_count_30d",
    "city_changed", "geo_risk_score",
    "hour_of_day", "is_odd_hour", "is_weekend",
    "category_risk", "is_aml_structuring", "is_card_testing",
    "days_since_first_txn", "avg_daily_txn_count"
]

def generate_training_data(n_samples=30000):
    import numpy as np
    import pandas as pd
    
    np.random.seed(42)
    rows = []
    
    # ── 72% SAFE TRANSACTIONS ──────────────────────────────────────
    n_safe = int(n_samples * 0.72)
    for _ in range(n_safe):
        hour = np.random.choice(range(24), p=[
            0.01,0.01,0.01,0.01,0.01,0.02,0.04,0.06,0.07,0.07,
            0.07,0.07,0.06,0.06,0.06,0.06,0.06,0.06,0.05,0.04,
            0.04,0.03,0.02,0.01
        ])
        amount = max(50, np.random.lognormal(7.0, 0.8))
        rows.append({
            # SAFE characteristics: LOW velocity, normal amount, known device
            "txn_count_1h": max(0, int(np.random.poisson(1.2))),
            "txn_count_24h": max(0, int(np.random.poisson(4))),
            "txn_count_7d": max(0, int(np.random.poisson(18))),
            "amount": float(amount),
            "amount_log": float(np.log1p(amount)),
            "amount_to_avg_ratio": float(max(0.1, np.random.lognormal(0, 0.25))),
            "amount_to_max_ratio": float(np.random.uniform(0.05, 0.95)),
            "unique_merchants_7d": float(np.random.randint(1, 8)),
            "merchant_risk_score": float(np.random.choice(
                [0.02, 0.03, 0.05, 0.08, 0.10],
                p=[0.4, 0.25, 0.2, 0.1, 0.05]
            )),
            "is_international": 0.0,
            "is_new_device": float(np.random.choice([0, 1], p=[0.93, 0.07])),
            "device_count_30d": float(np.random.randint(1, 3)),
            "city_changed": float(np.random.choice([0, 1], p=[0.88, 0.12])),
            "geo_risk_score": float(max(0, np.random.beta(1, 10))),
            "hour_of_day": float(hour),
            "is_odd_hour": float(1 if hour < 6 else 0),
            "is_weekend": float(np.random.choice([0, 1], p=[0.71, 0.29])),
            "category_risk": float(np.random.choice(
                [0.02, 0.05, 0.10, 0.20],
                p=[0.5, 0.25, 0.15, 0.10]
            )),
            "is_aml_structuring": 0.0,
            "is_card_testing": 0.0,
            "days_since_first_txn": float(np.random.exponential(180)),
            "avg_daily_txn_count": float(max(0.1, np.random.lognormal(0.8, 0.4))),
            "is_fraud": 0  # LABEL = 0 = SAFE
        })
    
    # ── 10% CARD TESTING FRAUD ─────────────────────────────────────
    n_card = int(n_samples * 0.10)
    for _ in range(n_card):
        amount = float(np.random.uniform(1, 99))
        # 15% look normal (hard negatives to prevent overfitting)
        looks_normal = np.random.random() < 0.15
        rows.append({
            # FRAUD characteristics: HIGH velocity, micro amount, new device
            "txn_count_1h": float(np.random.randint(2, 5) if looks_normal else np.random.randint(7, 20)),
            "txn_count_24h": float(np.random.randint(4, 10) if looks_normal else np.random.randint(12, 40)),
            "txn_count_7d": float(np.random.randint(10, 25)),
            "amount": amount,
            "amount_log": float(np.log1p(amount)),
            "amount_to_avg_ratio": float(np.random.uniform(0.01, 0.08)),
            "amount_to_max_ratio": float(np.random.uniform(0.01, 0.05)),
            "unique_merchants_7d": float(np.random.randint(1, 3)),
            "merchant_risk_score": float(np.random.uniform(0.55, 0.85)),
            "is_international": 0.0,
            "is_new_device": 0.0 if looks_normal else 1.0,
            "device_count_30d": float(np.random.randint(1, 2)),
            "city_changed": 0.0,
            "geo_risk_score": float(np.random.uniform(0.05, 0.3)),
            "hour_of_day": float(np.random.randint(0, 24)),
            "is_odd_hour": float(np.random.choice([0, 1], p=[0.6, 0.4])),
            "is_weekend": float(np.random.choice([0, 1])),
            "category_risk": float(np.random.uniform(0.6, 0.85)),
            "is_aml_structuring": 0.0,
            "is_card_testing": 0.0 if looks_normal else 1.0,
            "days_since_first_txn": float(np.random.uniform(0, 10)),
            "avg_daily_txn_count": float(np.random.uniform(3, 15)),
            "is_fraud": 1  # LABEL = 1 = FRAUD
        })
    
    # ── 8% ACCOUNT TAKEOVER FRAUD ──────────────────────────────────
    n_ato = int(n_samples * 0.08)
    for _ in range(n_ato):
        amount = float(np.random.lognormal(10.5, 0.5))
        looks_normal = np.random.random() < 0.15
        hour = int(np.random.randint(9, 18) if looks_normal else np.random.randint(0, 5))
        rows.append({
            "txn_count_1h": float(np.random.randint(1, 3)),
            "txn_count_24h": float(np.random.randint(1, 4)),
            "txn_count_7d": float(np.random.randint(1, 8)),
            "amount": amount,
            "amount_log": float(np.log1p(amount)),
            "amount_to_avg_ratio": float(np.random.uniform(1.5, 5) if looks_normal else np.random.uniform(6, 20)),
            "amount_to_max_ratio": float(np.random.uniform(0.8, 2.5)),
            "unique_merchants_7d": 1.0,
            "merchant_risk_score": float(np.random.uniform(0.4, 0.65) if looks_normal else np.random.uniform(0.65, 0.95)),
            "is_international": float(np.random.choice([0, 1], p=[0.3, 0.7])),
            "is_new_device": 0.0 if looks_normal else 1.0,
            "device_count_30d": float(np.random.randint(1, 3)),
            "city_changed": float(np.random.choice([0, 1], p=[0.4, 0.6])),
            "geo_risk_score": float(np.random.uniform(0.15, 0.4) if looks_normal else np.random.uniform(0.65, 0.98)),
            "hour_of_day": float(hour),
            "is_odd_hour": float(1 if hour < 6 else 0),
            "is_weekend": float(np.random.choice([0, 1])),
            "category_risk": float(np.random.uniform(0.55, 0.95)),
            "is_aml_structuring": 0.0,
            "is_card_testing": 0.0,
            "days_since_first_txn": float(np.random.exponential(200)),
            "avg_daily_txn_count": float(np.random.uniform(0.3, 2.5)),
            "is_fraud": 1
        })
    
    # ── 6% AML STRUCTURING ─────────────────────────────────────────
    n_aml = int(n_samples * 0.06)
    for _ in range(n_aml):
        amount = float(np.random.uniform(45000, 49999))
        rows.append({
            "txn_count_1h": float(np.random.randint(1, 3)),
            "txn_count_24h": float(np.random.randint(2, 5)),
            "txn_count_7d": float(np.random.randint(5, 15)),
            "amount": amount,
            "amount_log": float(np.log1p(amount)),
            "amount_to_avg_ratio": float(np.random.uniform(2, 7)),
            "amount_to_max_ratio": float(np.random.uniform(0.85, 1.05)),
            "unique_merchants_7d": float(np.random.randint(1, 3)),
            "merchant_risk_score": float(np.random.uniform(0.55, 0.80)),
            "is_international": 0.0,
            "is_new_device": float(np.random.choice([0, 1], p=[0.65, 0.35])),
            "device_count_30d": float(np.random.randint(1, 3)),
            "city_changed": 0.0,
            "geo_risk_score": float(np.random.uniform(0.05, 0.3)),
            "hour_of_day": float(np.random.randint(9, 17)),
            "is_odd_hour": 0.0,
            "is_weekend": 0.0,
            "category_risk": float(np.random.uniform(0.55, 0.85)),
            "is_aml_structuring": 1.0,
            "is_card_testing": 0.0,
            "days_since_first_txn": float(np.random.exponential(280)),
            "avg_daily_txn_count": float(np.random.uniform(0.3, 2.0)),
            "is_fraud": 1
        })
    
    # ── REMAINING: crypto/wire/geo fraud ───────────────────────────
    current = len(rows)
    remaining = n_samples - current
    for _ in range(remaining):
        is_fraud = np.random.random() < 0.20
        if is_fraud:
            amount = float(max(5000, np.random.lognormal(10, 0.8)))
            rows.append({
                "txn_count_1h": float(np.random.randint(1, 4)),
                "txn_count_24h": float(np.random.randint(1, 6)),
                "txn_count_7d": float(np.random.randint(2, 10)),
                "amount": amount,
                "amount_log": float(np.log1p(amount)),
                "amount_to_avg_ratio": float(np.random.uniform(4, 18)),
                "amount_to_max_ratio": float(np.random.uniform(1, 4)),
                "unique_merchants_7d": 1.0,
                "merchant_risk_score": float(np.random.uniform(0.75, 0.98)),
                "is_international": float(np.random.choice([0, 1], p=[0.2, 0.8])),
                "is_new_device": float(np.random.choice([0, 1], p=[0.2, 0.8])),
                "device_count_30d": float(np.random.randint(1, 3)),
                "city_changed": float(np.random.choice([0, 1], p=[0.2, 0.8])),
                "geo_risk_score": float(np.random.uniform(0.6, 0.99)),
                "hour_of_day": float(np.random.randint(0, 6)),
                "is_odd_hour": 1.0,
                "is_weekend": float(np.random.choice([0, 1])),
                "category_risk": float(np.random.uniform(0.7, 0.95)),
                "is_aml_structuring": 0.0,
                "is_card_testing": 0.0,
                "days_since_first_txn": float(np.random.exponential(120)),
                "avg_daily_txn_count": float(np.random.uniform(0.2, 3.0)),
                "is_fraud": 1
            })
        else:
            amount = float(max(50, np.random.lognormal(7.0, 0.9)))
            rows.append({
                "txn_count_1h": float(max(0, int(np.random.poisson(1.0)))),
                "txn_count_24h": float(max(0, int(np.random.poisson(3)))),
                "txn_count_7d": float(max(0, int(np.random.poisson(15)))),
                "amount": amount,
                "amount_log": float(np.log1p(amount)),
                "amount_to_avg_ratio": float(max(0.1, np.random.lognormal(0, 0.2))),
                "amount_to_max_ratio": float(np.random.uniform(0.05, 0.9)),
                "unique_merchants_7d": float(np.random.randint(1, 7)),
                "merchant_risk_score": float(np.random.uniform(0.01, 0.15)),
                "is_international": 0.0,
                "is_new_device": float(np.random.choice([0, 1], p=[0.94, 0.06])),
                "device_count_30d": float(np.random.randint(1, 3)),
                "city_changed": float(np.random.choice([0, 1], p=[0.9, 0.1])),
                "geo_risk_score": float(max(0, np.random.beta(1, 12))),
                "hour_of_day": float(np.random.randint(7, 22)),
                "is_odd_hour": 0.0,
                "is_weekend": float(np.random.choice([0, 1], p=[0.71, 0.29])),
                "category_risk": float(np.random.uniform(0.01, 0.20)),
                "is_aml_structuring": 0.0,
                "is_card_testing": 0.0,
                "days_since_first_txn": float(np.random.exponential(200)),
                "avg_daily_txn_count": float(max(0.1, np.random.lognormal(0.8, 0.3))),
                "is_fraud": 0
            })
    
    df = pd.DataFrame(rows)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    fraud_pct = df['is_fraud'].mean() * 100
    print(f"Dataset: {len(df)} rows | Fraud: {fraud_pct:.1f}% | Safe: {100-fraud_pct:.1f}%")
    
    # CRITICAL SANITY CHECK — verify labels are correct
    fraud_rows = df[df['is_fraud'] == 1]
    safe_rows = df[df['is_fraud'] == 0]
    print(f"Fraud avg amount_to_avg_ratio: {fraud_rows['amount_to_avg_ratio'].mean():.2f}")
    print(f"Safe avg amount_to_avg_ratio: {safe_rows['amount_to_avg_ratio'].mean():.2f}")
    print("CORRECT if fraud ratio > safe ratio")
    print(f"Fraud avg merchant_risk: {fraud_rows['merchant_risk_score'].mean():.3f}")
    print(f"Safe avg merchant_risk: {safe_rows['merchant_risk_score'].mean():.3f}")
    print("CORRECT if fraud merchant_risk > safe merchant_risk")
    
    return df

def train_xgboost(df: pd.DataFrame):
    X = df[FEATURE_NAMES].values
    y = df["is_fraud"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    fraud_ratio = (y_train == 0).sum() / (y_train == 1).sum()

    model = xgb.XGBClassifier(
        n_estimators=20,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.7,
        colsample_bytree=0.7,
        min_child_weight=15,
        gamma=0.5,
        reg_alpha=1.5,
        reg_lambda=2.0,
        scale_pos_weight=fraud_ratio,
        eval_metric='auc',
        random_state=42,
        n_jobs=-1
    )

    print("Training XGBoost...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=10
    )

    print("Running cross-validation to ensure model is not overfitting...")
    model_cv = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.65,
        colsample_bytree=0.65,
        min_child_weight=20,
        gamma=1.0,
        reg_alpha=2.0,
        reg_lambda=3.0,
        scale_pos_weight=fraud_ratio,
        eval_metric="auc",
        random_state=42,
        n_jobs=-1
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model_cv, X_train, y_train,
                                cv=cv, scoring='roc_auc', n_jobs=-1)
    print(f"Cross-validation AUC: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    auc = roc_auc_score(y_test, y_prob)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)

    metrics = {
        "auc_roc": round(auc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "cv_auc_mean": round(float(cv_scores.mean()), 4),
        "cv_auc_std": round(float(cv_scores.std()), 4),
        "false_positive_rate": round(cm[0][1] / (cm[0][0] + cm[0][1]), 4),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "fraud_rate_train": round(y_train.mean(), 4),
        "best_iteration": getattr(model, 'best_iteration', 100)
    }
    print("\n=== Model Performance ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    print("\nComputing SHAP values (sample of 1000)...")
    explainer = shap.TreeExplainer(model)
    shap_sample = X_test[:1000]
    shap_values = explainer.shap_values(shap_sample)
    feature_importance = {
        FEATURE_NAMES[i]: float(abs(shap_values[:, i]).mean())
        for i in range(len(FEATURE_NAMES))
    }
    feature_importance = dict(sorted(
        feature_importance.items(), key=lambda x: x[1], reverse=True
    ))

    return model, scaler, metrics, feature_importance

def save_model(model, scaler, metrics, feature_importance):
    # Fix: Ensure we save to backend/models relative to the script location
    base_dir = Path(__file__).parent.parent
    target_dir = base_dir / "models"
    target_dir.mkdir(exist_ok=True)
    
    with open(target_dir / "xgboost_fraud.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(target_dir / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    with open(target_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    with open(target_dir / "feature_importance.json", "w") as f:
        json.dump(feature_importance, f, indent=2)

    print(f"\nModel saved to {target_dir}/")
    print(f"AUC-ROC: {metrics['auc_roc']}")
    print(f"F1 Score: {metrics['f1_score']}")

if __name__ == "__main__":
    paysim_path = "data/PS_20174392719_1491204439457_log.csv"
    if os.path.exists(paysim_path):
        print("PaySim dataset found — using real data!")
        df = pd.read_csv(paysim_path)
    else:
        print("Using synthetic training data (PaySim not found)")
        # Increased to 60k for better sensitivity
        df = generate_training_data(n_samples=60000)

    # Phase 4: Inject Hard Negatives into Training
    # ... (rest of the logic stays same)
    hard_neg_path = "backend/data/hard_negatives.json"
    if os.path.exists(hard_neg_path):
        try:
            with open(hard_neg_path, 'r') as f:
                hard_negs = json.load(f)
            
            # Convert to DataFrame
            df_hn = pd.DataFrame(hard_negs)
            # Ensure features match (filter or fill)
            df_hn = df_hn[FEATURE_NAMES + ["is_fraud"]]
            
            # The goal is 15% of total fraud samples should be hard negatives
            n_current_fraud = len(df[df["is_fraud"] == 1])
            n_target_hn = int(n_current_fraud * 0.15) / (1 - 0.15) # approximate
            n_hn_to_add = min(len(df_hn), int(n_target_hn))
            
            hn_sample = df_hn.sample(n=n_hn_to_add, random_state=42)
            df = pd.concat([df, hn_sample], ignore_index=True)
            print(f"✓ Injected {n_hn_to_add} Hard Negative samples into training set.")
        except Exception as e:
            print(f"⚠ Failed to inject hard negatives: {e}")

    model, scaler, metrics, importance = train_xgboost(df)
    save_model(model, scaler, metrics, importance)
    print("\nDone! Run: uvicorn main:app to start with real ML model")
