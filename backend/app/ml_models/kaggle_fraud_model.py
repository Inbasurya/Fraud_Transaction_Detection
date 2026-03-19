"""Advanced fraud model training and inference utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import logging
import math
import os
import tempfile

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler
from sklearn.base import clone
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    make_scorer,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover
    XGBClassifier = None

try:
    from lightgbm import LGBMClassifier
except Exception:  # pragma: no cover
    LGBMClassifier = None

try:
    import shap
except Exception:  # pragma: no cover
    shap = None

logger = logging.getLogger(__name__)


@dataclass
class TrainedModel:
    name: str
    estimator: Any
    metrics: dict[str, Any]
    threshold: float
    cv_results: dict[str, Any]


class KaggleFraudModel:
    """Train, persist, explain, and serve the fraud ensemble."""

    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.data_paths = [
            base_dir / "data" / "bank_transactions_20000.csv",
            base_dir.parents[1] / "backend" / "data" / "bank_transactions_20000.csv",
            base_dir.parents[1] / "data" / "bank_transactions_20000.csv",
            base_dir / "ml" / "data" / "creditcard.csv",
            base_dir.parents[1] / "data" / "creditcard.csv",
        ]
        self.models_dir = base_dir / "ml" / "models"
        self.results_dir = base_dir.parents[1] / "results"
        self.artifact_path = self.models_dir / "fraud_model.pkl"
        self.scaler_path = self.models_dir / "scaler.pkl"
        self.anomaly_path = self.models_dir / "anomaly_model.pkl"

        self.feature_columns = [
            "amount",
            "user_avg_amount",
            "transaction_amount_ratio",
            "transaction_frequency_last_24h",
            "location_change_flag",
            "device_change_flag",
            "merchant_risk_score",
            "time_since_last_transaction",
            "unusual_time_activity",
            "account_transaction_velocity",
            "transaction_hour",
            "merchant_frequency",
            "amount_deviation",
        ]
        self.default_feature_values = {name: 0.0 for name in self.feature_columns}
        self.selected_feature_columns = list(self.feature_columns)
        self.scaler = StandardScaler()
        self.models: dict[str, TrainedModel] = {}
        self.best_model_name: str | None = None
        self.best_model = None
        self.anomaly_model: IsolationForest | None = None
        self.dataset_stats: dict[str, Any] = {}
        self.training_summary: dict[str, Any] = {}
        self.merchant_risk_lookup: dict[str, float] = {}
        self.global_fraud_rate = 0.05
        self.correlation_dropped: list[str] = []
        self.ensemble_weights = {
            "Random Forest": 0.45,
            "XGBoost": 0.35,
            "Anomaly Detection": 0.20,
        }
        self.deployed_supervised_models: list[str] = []
        self.model_status: dict[str, str] = {}
        self._shap_explainer = None
        self._trained = False
        self._load_artifact()

    @staticmethod
    def _feature_aliases() -> dict[str, str]:
        return {
            "transaction_amount_over_user_avg": "transaction_amount_ratio",
            "unusual_time_flag": "unusual_time_activity",
            "velocity": "account_transaction_velocity",
            "time_delta_minutes": "time_since_last_transaction",
        }

    def _resolve_feature_key(self, key: str, payload: dict[str, Any]) -> str | None:
        aliases = self._feature_aliases()
        if key in payload:
            return key
        canonical = aliases.get(key, key)
        if canonical in payload:
            return canonical
        for source, target in aliases.items():
            if target == key and source in payload:
                return source
        return None

    @staticmethod
    def _normalize_metric(value: float) -> float:
        return float(np.round(float(value), 6))

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1.0 / (1.0 + math.exp(-value))

    def _load_artifact(self) -> None:
        if not self.artifact_path.exists():
            return
        try:
            artifact = joblib.load(self.artifact_path)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to load persisted fraud model: %s", exc)
            return

        if not isinstance(artifact, dict) or "best_model" not in artifact:
            return

        self.selected_feature_columns = artifact.get("selected_feature_columns", self.selected_feature_columns)
        self.feature_columns = artifact.get("feature_columns", self.feature_columns)
        self.default_feature_values = artifact.get("default_feature_values", self.default_feature_values)
        self.scaler = artifact.get("scaler", self.scaler)
        self.best_model_name = artifact.get("best_model_name")
        self.best_model = artifact.get("best_model")
        self.anomaly_model = artifact.get("anomaly_model")
        self.merchant_risk_lookup = artifact.get("merchant_risk_lookup", {})
        self.global_fraud_rate = float(artifact.get("global_fraud_rate", self.global_fraud_rate))
        self.dataset_stats = artifact.get("dataset_stats", {})
        self.training_summary = artifact.get("training_summary", {})
        self.correlation_dropped = artifact.get("correlation_dropped", [])
        self.ensemble_weights = artifact.get("ensemble_weights", self.ensemble_weights)
        self.deployed_supervised_models = artifact.get("deployed_supervised_models", [])
        self.model_status = artifact.get("model_status", {})
        self.models = {}
        for name, info in artifact.get("models", {}).items():
            self.models[name] = TrainedModel(
                name=name,
                estimator=info["estimator"],
                metrics=info["metrics"],
                threshold=float(info["threshold"]),
                cv_results=info.get("cv_results", {}),
            )
        self._trained = True
        self._build_shap_explainer()

    def _resolve_data_path(self, dataset_path: str | None = None) -> Path:
        if dataset_path:
            path = Path(dataset_path)
            if path.exists():
                return path
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")

        for path in self.data_paths:
            if path.exists():
                return path
        raise FileNotFoundError("No fraud training dataset found in configured locations")

    def _load_dataset(self, dataset_path: str | None = None) -> pd.DataFrame:
        path = self._resolve_data_path(dataset_path)
        df = pd.read_csv(path)
        logger.info("Loaded fraud training dataset from %s", path)
        if {"amount", "merchant", "device_type", "timestamp", "is_fraud"}.issubset(df.columns):
            return self._normalize_bank_dataset(df)
        if {"Time", "Amount", "Class"}.issubset(df.columns):
            return self._normalize_creditcard_dataset(df)
        raise ValueError("Unsupported dataset schema")

    def _normalize_bank_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        frame["timestamp"] = frame["timestamp"].fillna(frame["timestamp"].dropna().min())
        if "user_id" not in frame.columns:
            frame["user_id"] = frame.get("account_id", 0)
        frame["user_id"] = pd.to_numeric(frame["user_id"], errors="coerce").fillna(0).astype(int)
        frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
        frame["merchant"] = frame["merchant"].fillna("UNKNOWN").astype(str)
        if "location" not in frame.columns:
            frame["location"] = frame.get("location_city", "UNKNOWN")
        frame["location"] = frame["location"].fillna("UNKNOWN").astype(str)
        frame["device_type"] = frame["device_type"].fillna("UNKNOWN").astype(str)
        frame["target"] = pd.to_numeric(frame["is_fraud"], errors="coerce").fillna(0).astype(int)
        return frame

    def _normalize_creditcard_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        base_ts = pd.Timestamp("2025-01-01")
        frame["timestamp"] = base_ts + pd.to_timedelta(frame["Time"].fillna(0), unit="s")
        frame["user_id"] = (frame.index % 500).astype(int) + 1
        frame["amount"] = pd.to_numeric(frame["Amount"], errors="coerce").fillna(0.0)
        frame["merchant"] = (
            "merchant_" + pd.qcut(frame["V1"], q=8, duplicates="drop").astype(str)
        ).fillna("merchant_unknown")
        frame["location"] = (
            "region_" + pd.qcut(frame["V2"], q=6, duplicates="drop").astype(str)
        ).fillna("region_unknown")
        frame["device_type"] = np.where(frame["V3"].fillna(0) > frame["V3"].median(), "mobile", "web")
        frame["target"] = pd.to_numeric(frame["Class"], errors="coerce").fillna(0).astype(int)
        return frame

    def _transaction_frequency_last_24h(self, frame: pd.DataFrame) -> pd.Series:
        values = np.zeros(len(frame), dtype=float)
        for _, idx in frame.groupby("user_id").groups.items():
            positions = np.asarray(list(idx))
            timestamps = frame.loc[positions, "timestamp"].astype("int64").to_numpy()
            window = np.int64(24 * 60 * 60 * 1_000_000_000)
            starts = np.searchsorted(timestamps, timestamps - window, side="left")
            counts = np.arange(len(positions)) - starts
            values[positions] = counts.astype(float)
        return pd.Series(values, index=frame.index)

    def _merchant_risk_map(self, frame: pd.DataFrame) -> dict[str, float]:
        if "target" not in frame.columns:
            return {}
        grouped = frame.groupby("merchant")["target"].agg(["sum", "count"])
        smoothing = 20.0
        risk = (grouped["sum"] + self.global_fraud_rate * smoothing) / (grouped["count"] + smoothing)
        return risk.astype(float).to_dict()

    def _engineer_features(
        self,
        df: pd.DataFrame,
        merchant_risk_lookup: dict[str, float] | None = None,
    ) -> tuple[pd.DataFrame, pd.Series]:
        frame = df.copy()
        frame = frame.sort_values(["user_id", "timestamp", "amount"]).reset_index(drop=True)

        frame["transaction_hour"] = frame["timestamp"].dt.hour.fillna(12).astype(float)
        hour = frame["transaction_hour"]
        frame["unusual_time_activity"] = ((hour <= 6) | (hour >= 22)).astype(float)
        frame["unusual_time_flag"] = frame["unusual_time_activity"]

        user_groups = frame.groupby("user_id", sort=False)
        prev_amount = user_groups["amount"].shift(1)
        expanding_mean = user_groups["amount"].expanding().mean().shift(1).reset_index(level=0, drop=True)
        expanding_std = user_groups["amount"].expanding().std().shift(1).reset_index(level=0, drop=True)
        frame["user_avg_amount"] = expanding_mean.fillna(frame["amount"].median()).clip(lower=1.0)
        frame["transaction_amount_ratio"] = (frame["amount"] / frame["user_avg_amount"]).replace([np.inf, -np.inf], 1.0).fillna(1.0)
        frame["transaction_amount_over_user_avg"] = frame["transaction_amount_ratio"]
        frame["amount_deviation"] = (
            (frame["amount"] - frame["user_avg_amount"]) / expanding_std.fillna(frame["amount"].std() or 1.0).clip(lower=1.0)
        ).replace([np.inf, -np.inf], 0.0).fillna(0.0)

        prev_ts = user_groups["timestamp"].shift(1)
        delta_minutes = (frame["timestamp"] - prev_ts).dt.total_seconds().div(60.0)
        fallback_minutes = float(delta_minutes.dropna().median()) if not delta_minutes.dropna().empty else 24 * 60.0
        frame["time_since_last_transaction"] = delta_minutes.fillna(fallback_minutes).clip(lower=0.0)

        prev_location = user_groups["location"].shift(1)
        prev_device = user_groups["device_type"].shift(1)
        frame["location_change_flag"] = ((prev_location != frame["location"]) & prev_location.notna()).astype(float)
        frame["device_change_flag"] = ((prev_device != frame["device_type"]) & prev_device.notna()).astype(float)
        frame["transaction_frequency_last_24h"] = self._transaction_frequency_last_24h(frame)
        frame["account_transaction_velocity"] = self._transaction_velocity_last_hour(frame)

        merchant_seen = user_groups["merchant"].transform(
            lambda s: s.groupby(s).cumcount()
        )
        tx_position = user_groups.cumcount().replace(0, np.nan)
        frame["merchant_frequency"] = (merchant_seen / tx_position).replace([np.inf, -np.inf], 0.0).fillna(0.0)

        lookup = merchant_risk_lookup or {}
        frame["merchant_risk_score"] = frame["merchant"].map(lookup).fillna(self.global_fraud_rate)

        # Safety: resolve aliases and create any missing feature columns
        aliases = self._feature_aliases()
        reverse_aliases = {v: k for k, v in aliases.items()}
        for col in self.feature_columns:
            if col in frame.columns:
                continue
            canonical = aliases.get(col)
            if canonical and canonical in frame.columns:
                frame[col] = frame[canonical]
                continue
            source = reverse_aliases.get(col)
            if source and source in frame.columns:
                frame[col] = frame[source]
                continue
            logger.warning("Feature '%s' not found after engineering; defaulting to 0.0", col)
            frame[col] = 0.0

        features = frame[self.feature_columns].copy()
        features = features.replace([np.inf, -np.inf], np.nan)
        for column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")
        features = features.fillna(0)

        target = frame["target"].astype(int)
        return features, target

    def _transaction_velocity_last_hour(self, frame: pd.DataFrame) -> pd.Series:
        values = np.zeros(len(frame), dtype=float)
        for _, idx in frame.groupby("user_id").groups.items():
            positions = np.asarray(list(idx))
            timestamps = frame.loc[positions, "timestamp"].astype("int64").to_numpy()
            window = np.int64(60 * 60 * 1_000_000_000)
            starts = np.searchsorted(timestamps, timestamps - window, side="left")
            values[positions] = (np.arange(len(positions)) - starts).astype(float)
        return pd.Series(values, index=frame.index)

    def _drop_correlated_features(self, x_train: pd.DataFrame, threshold: float = 0.95) -> list[str]:
        corr = x_train.corr().abs()
        upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        to_drop = [column for column in upper.columns if any(upper[column] > threshold)]
        return to_drop

    def _remove_outliers(self, x_train: pd.DataFrame, y_train: pd.Series) -> tuple[pd.DataFrame, pd.Series, int]:
        normal_mask = y_train == 0
        if normal_mask.sum() < 30:
            return x_train, y_train, 0

        detector = IsolationForest(
            n_estimators=150,
            contamination=0.02,
            random_state=42,
            n_jobs=-1,
        )
        normal_samples = x_train.loc[normal_mask]
        preds = detector.fit_predict(normal_samples)
        keep_normal = preds == 1

        keep_index = list(normal_samples.index[keep_normal]) + list(x_train.index[~normal_mask])
        keep_index = pd.Index(keep_index).sort_values()
        removed = int((~keep_normal).sum())
        return x_train.loc[keep_index].reset_index(drop=True), y_train.loc[keep_index].reset_index(drop=True), removed

    def _rebalance(self, x_train: pd.DataFrame, y_train: pd.Series) -> tuple[pd.DataFrame, pd.Series, str]:
        minority_count = int(y_train.sum())
        if minority_count >= 6:
            sampler = SMOTE(random_state=42, k_neighbors=min(5, minority_count - 1))
            method = "SMOTE"
        else:
            sampler = RandomUnderSampler(random_state=42)
            method = "RandomUnderSampler"
        x_resampled, y_resampled = sampler.fit_resample(x_train, y_train)
        return pd.DataFrame(x_resampled, columns=x_train.columns), pd.Series(y_resampled), method

    def _candidate_models(self) -> dict[str, tuple[Any | None, dict[str, list[Any]] | None]]:
        candidates: dict[str, tuple[Any | None, dict[str, list[Any]] | None]] = {
            "Logistic Regression": (
                LogisticRegression(max_iter=4000, class_weight="balanced", random_state=42),
                {
                    "C": [0.1, 0.5, 1.0, 2.0, 5.0],
                    "solver": ["lbfgs"],
                },
            ),
            "Random Forest": (
                RandomForestClassifier(class_weight="balanced", random_state=42, n_jobs=-1),
                {
                    "n_estimators": [200, 300, 400],
                    "max_depth": [8, 12, 16, None],
                    "min_samples_split": [2, 4, 8],
                    "min_samples_leaf": [1, 2, 4],
                    "max_features": ["sqrt", 0.8, None],
                },
            ),
        }
        if XGBClassifier is not None:
            candidates["XGBoost"] = (
                XGBClassifier(
                    random_state=42,
                    eval_metric="logloss",
                    n_estimators=250,
                    max_depth=5,
                    learning_rate=0.08,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    reg_alpha=0.0,
                    reg_lambda=1.0,
                ),
                {
                    "n_estimators": [180, 250, 320],
                    "max_depth": [3, 5, 7],
                    "learning_rate": [0.03, 0.06, 0.1],
                    "min_child_weight": [1, 3, 5],
                    "subsample": [0.7, 0.85, 1.0],
                    "colsample_bytree": [0.7, 0.85, 1.0],
                    "reg_alpha": [0.0, 0.05, 0.2],
                    "reg_lambda": [1.0, 2.0, 5.0],
                },
            )
        if LGBMClassifier is not None:
            candidates["LightGBM"] = (
                LGBMClassifier(
                    random_state=42,
                    verbose=-1,
                    class_weight="balanced",
                ),
                {
                    "n_estimators": [150, 250, 350],
                    "max_depth": [-1, 8, 12],
                    "learning_rate": [0.03, 0.06, 0.1],
                    "min_child_samples": [10, 20, 40],
                    "subsample": [0.7, 0.9, 1.0],
                    "reg_alpha": [0.0, 0.1, 0.5],
                    "reg_lambda": [0.0, 0.1, 1.0],
                },
            )
        return candidates

    def _tune_model(self, name: str, estimator: Any, params: dict[str, list[Any]], x_train: np.ndarray, y_train: pd.Series) -> tuple[Any, dict[str, Any]]:
        scorer = make_scorer(fbeta_score, beta=2)
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        search = RandomizedSearchCV(
            estimator=clone(estimator),
            param_distributions=params,
            n_iter=min(10, np.prod([len(v) for v in params.values()])),
            scoring=scorer,
            n_jobs=1,
            cv=cv,
            random_state=42,
            refit=True,
        )
        search.fit(x_train, y_train)
        results = {
            "best_params": search.best_params_,
            "best_cv_score": self._normalize_metric(search.best_score_),
        }
        logger.info("%s best CV score %.4f", name, search.best_score_)
        return search.best_estimator_, results

    def _pick_threshold(self, estimator: Any, x_val: np.ndarray, y_val: pd.Series) -> float:
        proba = estimator.predict_proba(x_val)[:, 1]
        precision, recall, thresholds = precision_recall_curve(y_val, proba)
        best_threshold = 0.5
        best_score = -1.0

        for idx, threshold in enumerate(thresholds):
            p = float(precision[idx])
            r = float(recall[idx])
            score = (1.5 * r) + (0.5 * p)
            if p >= 0.70 and score > best_score:
                best_score = score
                best_threshold = float(threshold)

        if best_score < 0:
            preds = (proba >= 0.5).astype(int)
            best_threshold = 0.45 if recall_score(y_val, preds, zero_division=0) < 0.9 else 0.5

        return round(float(best_threshold), 4)

    def _feature_importance(self, model: Any) -> list[dict[str, float | str]]:
        values = None
        if hasattr(model, "feature_importances_"):
            values = np.asarray(model.feature_importances_, dtype=float)
        elif hasattr(model, "coef_"):
            coef = np.asarray(model.coef_, dtype=float)
            values = np.abs(coef[0] if coef.ndim > 1 else coef)

        if values is None or len(values) != len(self.selected_feature_columns):
            values = np.zeros(len(self.selected_feature_columns), dtype=float)

        total = float(values.sum()) or 1.0
        ranked = [
            {
                "feature": feature,
                "importance": self._normalize_metric(float(value / total)),
            }
            for feature, value in zip(self.selected_feature_columns, values)
        ]
        ranked.sort(key=lambda item: item["importance"], reverse=True)
        return ranked

    def _evaluate(self, model: Any, x_test: np.ndarray, y_test: pd.Series, threshold: float) -> dict[str, Any]:
        y_prob = model.predict_proba(x_test)[:, 1]
        y_pred = (y_prob >= threshold).astype(int)
        cm = confusion_matrix(y_test, y_pred)
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        step = max(1, len(fpr) // 80)
        return {
            "accuracy": self._normalize_metric(accuracy_score(y_test, y_pred)),
            "precision": self._normalize_metric(precision_score(y_test, y_pred, zero_division=0)),
            "recall": self._normalize_metric(recall_score(y_test, y_pred, zero_division=0)),
            "f1_score": self._normalize_metric(f1_score(y_test, y_pred, zero_division=0)),
            "roc_auc": self._normalize_metric(roc_auc_score(y_test, y_prob)),
            "threshold": threshold,
            "confusion_matrix": cm.astype(int).tolist(),
            "roc_curve": {
                "fpr": [self._normalize_metric(v) for v in fpr[::step]],
                "tpr": [self._normalize_metric(v) for v in tpr[::step]],
            },
            "feature_importance": self._feature_importance(model),
        }

    def _fit_anomaly_model(self, x_train_scaled: np.ndarray, y_train: pd.Series) -> IsolationForest:
        anomaly = IsolationForest(
            n_estimators=220,
            contamination=max(0.01, min(0.12, float(y_train.mean()) * 1.4)),
            random_state=42,
            n_jobs=-1,
        )
        anomaly.fit(x_train_scaled[y_train.to_numpy() == 0])
        return anomaly

    def _anomaly_score(self, x_scaled: np.ndarray) -> np.ndarray:
        if self.anomaly_model is None:
            return np.zeros(x_scaled.shape[0], dtype=float)
        raw = self.anomaly_model.decision_function(x_scaled)
        return np.array([self._sigmoid(float(-value * 3.0)) for value in raw], dtype=float)

    def _rule_based_score(self, feature_row: dict[str, Any]) -> float:
        """Compute a rule-based fraud risk score from feature values."""
        score = 0.0
        checks = 0

        ratio = float(feature_row.get("transaction_amount_ratio",
                       feature_row.get("transaction_amount_over_user_avg", 1.0)))
        if ratio > 3.0:
            score += 1.0
        elif ratio > 2.0:
            score += 0.7
        elif ratio > 1.5:
            score += 0.3
        checks += 1

        unusual = float(feature_row.get("unusual_time_activity",
                        feature_row.get("unusual_time_flag", 0.0)))
        score += unusual
        checks += 1

        score += float(feature_row.get("device_change_flag", 0.0))
        checks += 1

        score += float(feature_row.get("location_change_flag", 0.0))
        checks += 1

        freq = float(feature_row.get("transaction_frequency_last_24h", 0.0))
        if freq >= 10:
            score += 1.0
        elif freq >= 5:
            score += 0.5
        checks += 1

        merchant_risk = float(feature_row.get("merchant_risk_score", self.global_fraud_rate))
        if merchant_risk > 0.15:
            score += 1.0
        elif merchant_risk > 0.10:
            score += 0.5
        checks += 1

        return float(np.clip(score / max(checks, 1), 0.0, 1.0))

    def _ensemble_probability(self, x_scaled: np.ndarray) -> np.ndarray:
        probs = np.zeros(x_scaled.shape[0], dtype=float)
        total_weight = 0.0

        for name, weight in self.ensemble_weights.items():
            if name == "Anomaly Detection":
                continue
            trained = self.models.get(name)
            weight = float(self.ensemble_weights.get(name, 0.0))
            if trained is None or weight <= 0:
                continue
            probs += trained.estimator.predict_proba(x_scaled)[:, 1] * weight
            total_weight += weight

        if total_weight == 0 and self.best_model is not None:
            probs += self.best_model.predict_proba(x_scaled)[:, 1]
            total_weight = 1.0

        anomaly_weight = float(self.ensemble_weights.get("Anomaly Detection", 0.0))
        if anomaly_weight > 0:
            probs += self._anomaly_score(x_scaled) * anomaly_weight
            total_weight += anomaly_weight

        if total_weight == 0:
            return np.zeros(x_scaled.shape[0], dtype=float)
        return np.clip(probs / total_weight, 0.0, 1.0)

    def _evaluate_ensemble(self, x_test_scaled: np.ndarray, y_test: pd.Series) -> dict[str, Any]:
        y_prob = self._ensemble_probability(x_test_scaled)
        y_pred = (y_prob >= 0.5).astype(int)
        cm = confusion_matrix(y_test, y_pred)
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        step = max(1, len(fpr) // 80)
        return {
            "accuracy": self._normalize_metric(accuracy_score(y_test, y_pred)),
            "precision": self._normalize_metric(precision_score(y_test, y_pred, zero_division=0)),
            "recall": self._normalize_metric(recall_score(y_test, y_pred, zero_division=0)),
            "f1_score": self._normalize_metric(f1_score(y_test, y_pred, zero_division=0)),
            "roc_auc": self._normalize_metric(roc_auc_score(y_test, y_prob)),
            "threshold": 0.5,
            "confusion_matrix": cm.astype(int).tolist(),
            "roc_curve": {
                "fpr": [self._normalize_metric(v) for v in fpr[::step]],
                "tpr": [self._normalize_metric(v) for v in tpr[::step]],
            },
        }

    def _save_visualizations(self, metrics: dict[str, Any], shap_payload: list[dict[str, Any]]) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mplconfig-"))
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        roc = metrics.get("roc_curve", {})
        fpr = roc.get("fpr", [])
        tpr = roc.get("tpr", [])

        if fpr and tpr:
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.plot(fpr, tpr, label=f"ROC AUC {metrics.get('roc_auc', 0):.3f}")
            ax.plot([0, 1], [0, 1], linestyle="--", color="grey")
            ax.set_title("Fraud Model ROC Curve")
            ax.set_xlabel("False Positive Rate")
            ax.set_ylabel("True Positive Rate")
            ax.legend(loc="lower right")
            fig.tight_layout()
            fig.savefig(self.results_dir / "fraud_model_roc_curve.png", dpi=140)
            plt.close(fig)

        cm = np.asarray(metrics.get("confusion_matrix", [[0, 0], [0, 0]]))
        fig, ax = plt.subplots(figsize=(5, 4))
        image = ax.imshow(cm, cmap="Blues")
        ax.set_title("Fraud Model Confusion Matrix")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_xticks([0, 1], labels=["Legit", "Fraud"])
        ax.set_yticks([0, 1], labels=["Legit", "Fraud"])
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, int(cm[i, j]), ha="center", va="center", color="black")
        fig.colorbar(image, ax=ax)
        fig.tight_layout()
        fig.savefig(self.results_dir / "fraud_model_confusion_matrix.png", dpi=140)
        plt.close(fig)

        if shap_payload:
            fig, ax = plt.subplots(figsize=(7, 4))
            top = shap_payload[:10]
            features = [item["feature"] for item in top][::-1]
            values = [item["importance"] for item in top][::-1]
            ax.barh(features, values, color="#d1495b")
            ax.set_title("Top Fraud Indicators (SHAP)")
            ax.set_xlabel("Mean |SHAP value|")
            fig.tight_layout()
            fig.savefig(self.results_dir / "fraud_model_shap_importance.png", dpi=140)
            plt.close(fig)

    def _build_shap_explainer(self) -> None:
        if shap is None or self.best_model is None:
            self._shap_explainer = None
            return
        try:
            if hasattr(self.best_model, "feature_importances_"):
                self._shap_explainer = shap.TreeExplainer(self.best_model)
            elif hasattr(self.best_model, "coef_"):
                self._shap_explainer = shap.LinearExplainer(self.best_model, np.zeros((1, len(self.selected_feature_columns))))
            else:
                self._shap_explainer = None
        except Exception:
            self._shap_explainer = None

    def _global_shap_payload(self, x_sample: np.ndarray) -> list[dict[str, Any]]:
        if self._shap_explainer is None or shap is None or x_sample.size == 0:
            return self._feature_importance(self.best_model)[:10]

        try:
            shap_values = self._shap_explainer.shap_values(x_sample)
            if isinstance(shap_values, list):
                shap_values = shap_values[-1]
            values = np.abs(np.asarray(shap_values)).mean(axis=0)
            ranking = [
                {"feature": feature, "importance": self._normalize_metric(value)}
                for feature, value in zip(self.selected_feature_columns, values)
            ]
            ranking.sort(key=lambda item: item["importance"], reverse=True)
            return ranking
        except Exception:
            return self._feature_importance(self.best_model)[:10]

    def _serialize_artifact(self) -> None:
        self.models_dir.mkdir(parents=True, exist_ok=True)
        artifact = {
            "feature_columns": self.feature_columns,
            "selected_feature_columns": self.selected_feature_columns,
            "default_feature_values": self.default_feature_values,
            "scaler": self.scaler,
            "best_model_name": self.best_model_name,
            "best_model": self.best_model,
            "models": {
                name: {
                    "estimator": data.estimator,
                    "metrics": data.metrics,
                    "threshold": data.threshold,
                    "cv_results": data.cv_results,
                }
                for name, data in self.models.items()
            },
            "anomaly_model": self.anomaly_model,
            "dataset_stats": self.dataset_stats,
            "training_summary": self.training_summary,
            "merchant_risk_lookup": self.merchant_risk_lookup,
            "global_fraud_rate": self.global_fraud_rate,
            "correlation_dropped": self.correlation_dropped,
            "ensemble_weights": self.ensemble_weights,
            "deployed_supervised_models": self.deployed_supervised_models,
            "model_status": self.model_status,
        }
        joblib.dump(artifact, self.artifact_path)
        joblib.dump(self.scaler, self.scaler_path)
        if self.anomaly_model is not None:
            joblib.dump(self.anomaly_model, self.anomaly_path)

    def train(self, dataset_path: str | None = None) -> None:
        if self._trained and dataset_path is None:
            return

        df = self._load_dataset(dataset_path)
        self.global_fraud_rate = float(df["target"].mean())
        self.merchant_risk_lookup = self._merchant_risk_map(df)
        x, y = self._engineer_features(df, merchant_risk_lookup=self.merchant_risk_lookup)
        self.default_feature_values = {column: float(x[column].median()) for column in x.columns}

        x_train_full, x_test, y_train_full, y_test = train_test_split(
            x,
            y,
            test_size=0.2,
            random_state=42,
            stratify=y,
        )
        x_train_base, x_val, y_train_base, y_val = train_test_split(
            x_train_full,
            y_train_full,
            test_size=0.2,
            random_state=42,
            stratify=y_train_full,
        )

        self.correlation_dropped = self._drop_correlated_features(x_train_base)
        self.selected_feature_columns = [col for col in x.columns if col not in self.correlation_dropped]
        x_train_base = x_train_base[self.selected_feature_columns].reset_index(drop=True)
        x_val = x_val[self.selected_feature_columns].reset_index(drop=True)
        x_test = x_test[self.selected_feature_columns].reset_index(drop=True)

        x_train_base, y_train_base, outliers_removed = self._remove_outliers(x_train_base, y_train_base.reset_index(drop=True))
        x_resampled, y_resampled, rebalance_method = self._rebalance(x_train_base, y_train_base)

        self.scaler = StandardScaler()
        x_train_scaled = self.scaler.fit_transform(x_resampled)
        x_val_scaled = self.scaler.transform(x_val)
        x_test_scaled = self.scaler.transform(x_test)

        self.models = {}
        self.model_status = {}
        if XGBClassifier is None:
            self.model_status["XGBoost"] = "unavailable: missing OpenMP runtime or xgboost import failed"
        if LGBMClassifier is None:
            self.model_status["LightGBM"] = "unavailable: lightgbm not installed"
        for name, model_config in self._candidate_models().items():
            estimator, params = model_config
            if estimator is None or params is None:
                self.model_status[name] = "unavailable"
                continue
            try:
                tuned_model, cv_results = self._tune_model(name, estimator, params, x_train_scaled, y_resampled)
                threshold = self._pick_threshold(tuned_model, x_val_scaled, y_val.reset_index(drop=True))
                metrics = self._evaluate(tuned_model, x_test_scaled, y_test.reset_index(drop=True), threshold)
                metrics["cv_best_score"] = cv_results["best_cv_score"]
                self.models[name] = TrainedModel(
                    name=name,
                    estimator=tuned_model,
                    metrics=metrics,
                    threshold=threshold,
                    cv_results=cv_results,
                )
                self.model_status[name] = "trained"
            except Exception as exc:
                self.model_status[name] = f"skipped: {exc}"
                logger.warning("Skipping %s training: %s", name, exc)

        if not self.models:
            raise RuntimeError("No supervised models were successfully trained")

        self.best_model_name = max(
            self.models,
            key=lambda name: (
                self.models[name].metrics["roc_auc"],
                self.models[name].metrics["recall"],
                self.models[name].metrics["f1_score"],
            ),
        )
        self.best_model = self.models[self.best_model_name].estimator
        self.deployed_supervised_models = [name for name in ("Random Forest", "XGBoost") if name in self.models]

        if "Random Forest" not in self.models and self.best_model_name not in self.deployed_supervised_models:
            self.deployed_supervised_models.insert(0, self.best_model_name)
        if "XGBoost" not in self.models:
            fallback = "LightGBM" if "LightGBM" in self.models else "Logistic Regression" if "Logistic Regression" in self.models else self.best_model_name
            self.ensemble_weights = {
                "Random Forest": 0.45 if "Random Forest" in self.models else 0.0,
                "XGBoost": 0.0,
                fallback: 0.35,
                "Anomaly Detection": 0.20,
            }

        self.anomaly_model = self._fit_anomaly_model(self.scaler.transform(x_train_base), y_train_base.reset_index(drop=True))
        ensemble_metrics = self._evaluate_ensemble(x_test_scaled, y_test.reset_index(drop=True))
        self._build_shap_explainer()
        shap_payload = self._global_shap_payload(x_test_scaled[: min(len(x_test_scaled), 500)])
        self._save_visualizations(ensemble_metrics, shap_payload)

        comparison_rows = []
        for name, data in self.models.items():
            comparison_rows.append(
                {
                    "model": name,
                    "accuracy": data.metrics["accuracy"],
                    "precision": data.metrics["precision"],
                    "recall": data.metrics["recall"],
                    "f1_score": data.metrics["f1_score"],
                    "roc_auc": data.metrics["roc_auc"],
                    "cv_best_score": data.metrics["cv_best_score"],
                    "threshold": data.threshold,
                }
            )
        comparison_rows.append({"model": "Hybrid Ensemble", **{k: ensemble_metrics[k] for k in ("accuracy", "precision", "recall", "f1_score", "roc_auc")}, "cv_best_score": None, "threshold": 0.5})
        comparison_df = pd.DataFrame(comparison_rows)

        self.results_dir.mkdir(parents=True, exist_ok=True)
        comparison_df.to_csv(self.results_dir / "model_comparison.csv", index=False)

        self.dataset_stats = {
            "rows": int(len(df)),
            "fraud_samples": int(y.sum()),
            "non_fraud_samples": int((y == 0).sum()),
            "fraud_ratio": self._normalize_metric(float(y.mean())),
            "features_used": self.selected_feature_columns,
            "correlation_dropped": self.correlation_dropped,
            "selected_best_model": self.best_model_name,
            "outliers_removed": outliers_removed,
            "class_imbalance_strategy": rebalance_method,
        }
        self.training_summary = {
            "best_model": self.best_model_name,
            "best_model_metrics": self.models[self.best_model_name].metrics,
            "ensemble_metrics": ensemble_metrics,
            "shap_top_features": shap_payload,
            "model_status": self.model_status,
        }
        self._serialize_artifact()
        self._trained = True
        logger.info("Fraud training complete. Best model: %s", self.best_model_name)

    def _ensure_trained(self) -> None:
        if not self._trained:
            self.train()

    def _prepare_inference_features(self, features: dict[str, Any] | None = None, *, amount: float | None = None, hour: int | None = None, avg_user_spend: float | None = None) -> pd.DataFrame:
        payload = dict(self.default_feature_values)
        if amount is not None:
            payload["amount"] = float(amount)
        if hour is not None:
            payload["transaction_hour"] = float(hour)
            unusual_key = self._resolve_feature_key("unusual_time_activity", payload)
            if unusual_key is not None:
                payload[unusual_key] = 1.0 if 0 <= int(hour) <= 5 else 0.0
        if avg_user_spend is not None:
            payload["user_avg_amount"] = max(float(avg_user_spend), 1.0)
            ratio = float(amount or payload["amount"]) / max(float(avg_user_spend), 1.0)
            ratio_key = self._resolve_feature_key("transaction_amount_ratio", payload)
            if ratio_key is not None:
                payload[ratio_key] = ratio
        if features:
            for key, value in features.items():
                resolved = self._resolve_feature_key(key, payload)
                if resolved is not None:
                    payload[resolved] = 0.0 if value is None else float(value)
        row = pd.DataFrame([{column: payload.get(column, self.default_feature_values.get(column, 0.0)) for column in self.selected_feature_columns}])
        return row

    def predict_scores(self, features: dict[str, Any]) -> dict[str, Any]:
        self._ensure_trained()
        row = self._prepare_inference_features(features)
        row_scaled = self.scaler.transform(row)

        model_scores: dict[str, float] = {}
        for name, trained in self.models.items():
            model_scores[name] = float(trained.estimator.predict_proba(row_scaled)[0, 1])

        anomaly_score = float(self._anomaly_score(row_scaled)[0])
        best_model_probability = model_scores.get(self.best_model_name, 0.0)
        rule_score = self._rule_based_score(row.iloc[0].to_dict())

        # Hybrid fraud score: 0.5 ML + 0.3 anomaly + 0.2 rule-based
        hybrid_score = (
            0.5 * best_model_probability
            + 0.3 * anomaly_score
            + 0.2 * rule_score
        )
        return {
            "best_model_probability": float(np.clip(best_model_probability, 0.0, 1.0)),
            "ensemble_probability": float(np.clip(hybrid_score, 0.0, 1.0)),
            "anomaly_probability": float(np.clip(anomaly_score, 0.0, 1.0)),
            "rule_based_score": float(np.clip(rule_score, 0.0, 1.0)),
            "model_scores": {name: self._normalize_metric(score) for name, score in model_scores.items()},
            "ensemble_weights": {"ml_model": 0.5, "anomaly_detection": 0.3, "rule_based": 0.2},
        }

    def predict_probability(self, amount: float, hour: int, features: dict[str, Any] | None = None) -> float:
        self._ensure_trained()
        payload = self._prepare_inference_features(features, amount=amount, hour=hour, avg_user_spend=(features or {}).get("user_avg_amount"))
        payload_scaled = self.scaler.transform(payload)

        ml_score = float(self._ensemble_probability(payload_scaled)[0])
        anomaly_score = float(self._anomaly_score(payload_scaled)[0])
        rule_score = self._rule_based_score(payload.iloc[0].to_dict())

        # Hybrid fraud score: 0.5 ML + 0.3 anomaly + 0.2 rule-based
        hybrid = 0.5 * ml_score + 0.3 * anomaly_score + 0.2 * rule_score
        return float(np.clip(hybrid, 0.0, 1.0))

    def merchant_risk_score(self, merchant: str | None) -> float:
        self._ensure_trained()
        if not merchant:
            return self.global_fraud_rate
        return float(self.merchant_risk_lookup.get(str(merchant), self.global_fraud_rate))

    def shap_explanation(
        self,
        features: dict[str, Any] | None = None,
        *,
        amount: float | None = None,
        hour: int | None = None,
        avg_user_spend: float | None = None,
    ) -> dict[str, Any]:
        self._ensure_trained()
        row = self._prepare_inference_features(features, amount=amount, hour=hour, avg_user_spend=avg_user_spend)
        row_scaled = self.scaler.transform(row)
        shap_values: dict[str, float] = {feature: 0.0 for feature in self.selected_feature_columns}

        if self._shap_explainer is not None:
            try:
                values = self._shap_explainer.shap_values(row_scaled)
                if isinstance(values, list):
                    values = values[-1]
                flat = np.asarray(values)[0]
                shap_values = {feature: self._normalize_metric(value) for feature, value in zip(self.selected_feature_columns, flat)}
            except Exception:
                shap_values = {feature: 0.0 for feature in self.selected_feature_columns}

        ranked = sorted(shap_values.items(), key=lambda item: abs(item[1]), reverse=True)
        reasons: list[str] = []
        raw = row.iloc[0].to_dict()

        if raw.get("transaction_amount_ratio", 1.0) > 2.5:
            reasons.append("Transaction amount is far above the user's normal spend")
        if raw.get("transaction_frequency_last_24h", 0.0) >= 5:
            reasons.append("High transaction frequency detected in the last 24 hours")
        if raw.get("location_change_flag", 0.0) >= 1:
            reasons.append("Location changed from the previous transaction")
        if raw.get("device_change_flag", 0.0) >= 1:
            reasons.append("Device changed from the previous transaction")
        if raw.get("unusual_time_activity", 0.0) >= 1:
            reasons.append("Transaction occurred during unusual hours")
        if raw.get("merchant_risk_score", self.global_fraud_rate) > max(0.1, self.global_fraud_rate * 1.5):
            reasons.append("Merchant has elevated fraud risk")

        for feature, value in ranked[:3]:
            if value <= 0:
                continue
            humanized = feature.replace("_", " ")
            reason = f"{humanized.title()} increased the fraud score"
            if reason not in reasons:
                reasons.append(reason)

        return {
            "feature_values": {key: self._normalize_metric(value) for key, value in row.iloc[0].to_dict().items()},
            "shap_values": shap_values,
            "top_features": [{"feature": key, "impact": self._normalize_metric(value)} for key, value in ranked[:10]],
            "reasons": reasons[:6],
        }

    def metrics_payload(self) -> dict[str, Any]:
        self._ensure_trained()
        return {
            "dataset": self.dataset_stats,
            "models": {name: data.metrics | {"cv_results": data.cv_results} for name, data in self.models.items()},
            "best_model": self.best_model_name,
            "ensemble": self.training_summary.get("ensemble_metrics", {}),
            "feature_importance": self.training_summary.get("shap_top_features", []),
            "artifacts": {
                "model_path": str(self.artifact_path),
                "scaler_path": str(self.scaler_path),
                "anomaly_model_path": str(self.anomaly_path),
                "roc_curve_path": str(self.results_dir / "fraud_model_roc_curve.png"),
                "confusion_matrix_path": str(self.results_dir / "fraud_model_confusion_matrix.png"),
                "shap_plot_path": str(self.results_dir / "fraud_model_shap_importance.png"),
            },
            "model_status": self.model_status,
            "ensemble_weights": self.ensemble_weights,
        }

    def retrain(self, dataset_path: str | None = None) -> dict[str, Any]:
        self._trained = False
        self.models = {}
        self.best_model_name = None
        self.best_model = None
        self._shap_explainer = None
        self.train(dataset_path)
        return self.metrics_payload()


kaggle_model = KaggleFraudModel()
