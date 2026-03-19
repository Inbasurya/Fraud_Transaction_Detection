"""Behavioral anomaly ensemble for banking transaction monitoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class IsolationBehaviorModel:
    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parents[1]
        self.data_paths = [
            base_dir.parents[1] / "data" / "bank_transactions_20000.csv",
            base_dir.parent / "data" / "bank_transactions_20000.csv",
        ]
        self.feature_columns = [
            "amount",
            "transaction_amount_ratio",
            "transaction_frequency_last_24h",
            "location_change_flag",
            "device_change_flag",
            "merchant_risk_score",
            "time_since_last_transaction",
            "unusual_time_activity",
            "account_transaction_velocity",
            "merchant_frequency",
        ]
        self.scaler = StandardScaler()
        self.isolation_forest = IsolationForest(
            n_estimators=260,
            contamination=0.04,
            random_state=42,
            n_jobs=-1,
        )
        self.local_outlier_factor = LocalOutlierFactor(
            n_neighbors=35,
            contamination=0.04,
            novelty=True,
        )
        self.autoencoder = MLPRegressor(
            hidden_layer_sizes=(32, 16, 32),
            activation="relu",
            solver="adam",
            learning_rate_init=0.001,
            max_iter=220,
            random_state=42,
        )
        self._trained = False
        self.dataset_stats: dict[str, Any] = {}
        self.model_metrics: dict[str, Any] = {}
        self.merchant_risk_lookup: dict[str, float] = {}
        self.global_fraud_rate = 0.04
        self.autoencoder_error_scale = 1.0

    def _load_dataset(self, dataset_path: str | None = None) -> pd.DataFrame:
        paths = [Path(dataset_path)] if dataset_path else []
        paths.extend(self.data_paths)
        for path in paths:
            if path.exists():
                df = pd.read_csv(path)
                logger.info("Loaded behavioral dataset from %s", path)
                return df
        raise FileNotFoundError("bank_transactions_20000.csv not found under data/ directories")

    @staticmethod
    def _safe_ts(df: pd.DataFrame) -> pd.Series:
        if "timestamp" in df.columns:
            return pd.to_datetime(df["timestamp"], errors="coerce")
        if "Time" in df.columns:
            base = pd.Timestamp("2025-01-01")
            return base + pd.to_timedelta(pd.to_numeric(df["Time"], errors="coerce").fillna(0), unit="s")
        return pd.to_datetime(df.index, errors="coerce")

    def _normalize_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        if "user_id" not in frame.columns:
            if "account_id" in frame.columns:
                frame["user_id"] = pd.factorize(frame["account_id"].astype(str))[0] + 1
            else:
                frame["user_id"] = (frame.index % 500) + 1

        if "amount" not in frame.columns and "Amount" in frame.columns:
            frame["amount"] = frame["Amount"]
        frame["amount"] = pd.to_numeric(frame.get("amount", 0.0), errors="coerce").fillna(0.0)

        frame["timestamp"] = self._safe_ts(frame)
        fallback_ts = frame["timestamp"].dropna().min() if not frame["timestamp"].dropna().empty else pd.Timestamp("2025-01-01")
        frame["timestamp"] = frame["timestamp"].fillna(fallback_ts)

        if "merchant" not in frame.columns:
            if "V1" in frame.columns:
                frame["merchant"] = "merchant_" + pd.qcut(frame["V1"], q=8, duplicates="drop").astype(str)
            else:
                frame["merchant"] = "UNKNOWN"
        frame["merchant"] = frame["merchant"].fillna("UNKNOWN").astype(str)

        if "location" not in frame.columns:
            if "location_city" in frame.columns:
                frame["location"] = frame["location_city"]
            elif "V2" in frame.columns:
                frame["location"] = "region_" + pd.qcut(frame["V2"], q=6, duplicates="drop").astype(str)
            else:
                frame["location"] = "UNKNOWN"
        frame["location"] = frame["location"].fillna("UNKNOWN").astype(str)

        if "device_type" not in frame.columns:
            if "V3" in frame.columns:
                median = pd.to_numeric(frame["V3"], errors="coerce").median()
                frame["device_type"] = np.where(pd.to_numeric(frame["V3"], errors="coerce").fillna(0) > median, "mobile", "web")
            else:
                frame["device_type"] = "UNKNOWN"
        frame["device_type"] = frame["device_type"].fillna("UNKNOWN").astype(str)

        if "is_fraud" in frame.columns:
            frame["target"] = pd.to_numeric(frame["is_fraud"], errors="coerce").fillna(0).astype(int)
        elif "Class" in frame.columns:
            frame["target"] = pd.to_numeric(frame["Class"], errors="coerce").fillna(0).astype(int)
        else:
            frame["target"] = 0
        return frame

    def _merchant_risk_map(self, frame: pd.DataFrame) -> dict[str, float]:
        grouped = frame.groupby("merchant")["target"].agg(["sum", "count"])
        smoothing = 16.0
        rates = (grouped["sum"] + (self.global_fraud_rate * smoothing)) / (grouped["count"] + smoothing)
        return rates.astype(float).to_dict()

    def _transaction_frequency_last_24h(self, frame: pd.DataFrame) -> pd.Series:
        values = np.zeros(len(frame), dtype=float)
        for _, idx in frame.groupby("user_id").groups.items():
            positions = np.asarray(list(idx))
            timestamps = frame.loc[positions, "timestamp"].astype("int64").to_numpy()
            window = np.int64(24 * 60 * 60 * 1_000_000_000)
            starts = np.searchsorted(timestamps, timestamps - window, side="left")
            values[positions] = (np.arange(len(positions)) - starts).astype(float)
        return pd.Series(values, index=frame.index)

    def _transaction_velocity_last_hour(self, frame: pd.DataFrame) -> pd.Series:
        values = np.zeros(len(frame), dtype=float)
        for _, idx in frame.groupby("user_id").groups.items():
            positions = np.asarray(list(idx))
            timestamps = frame.loc[positions, "timestamp"].astype("int64").to_numpy()
            window = np.int64(60 * 60 * 1_000_000_000)
            starts = np.searchsorted(timestamps, timestamps - window, side="left")
            values[positions] = (np.arange(len(positions)) - starts).astype(float)
        return pd.Series(values, index=frame.index)

    def _prepare_behavior_features(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = self._normalize_dataset(df)
        frame = frame.sort_values(["user_id", "timestamp", "amount"]).reset_index(drop=True)

        groups = frame.groupby("user_id", sort=False)
        frame["transaction_hour"] = frame["timestamp"].dt.hour.fillna(12).astype(float)
        frame["unusual_time_activity"] = frame["transaction_hour"].between(0, 5).astype(float)

        avg_amount = groups["amount"].expanding().mean().shift(1).reset_index(level=0, drop=True)
        frame["user_avg_amount"] = avg_amount.fillna(frame["amount"].median()).clip(lower=1.0)
        frame["transaction_amount_ratio"] = (frame["amount"] / frame["user_avg_amount"]).replace([np.inf, -np.inf], 1.0).fillna(1.0)

        prev_ts = groups["timestamp"].shift(1)
        delta_minutes = (frame["timestamp"] - prev_ts).dt.total_seconds().div(60.0)
        fallback_minutes = float(delta_minutes.dropna().median()) if not delta_minutes.dropna().empty else 24 * 60.0
        frame["time_since_last_transaction"] = delta_minutes.fillna(fallback_minutes).clip(lower=0.0)

        frame["transaction_frequency_last_24h"] = self._transaction_frequency_last_24h(frame)
        frame["account_transaction_velocity"] = self._transaction_velocity_last_hour(frame)

        prev_location = groups["location"].shift(1)
        prev_device = groups["device_type"].shift(1)
        frame["location_change_flag"] = ((prev_location != frame["location"]) & prev_location.notna()).astype(float)
        frame["device_change_flag"] = ((prev_device != frame["device_type"]) & prev_device.notna()).astype(float)

        merchant_seen = groups["merchant"].transform(lambda s: s.groupby(s).cumcount())
        tx_position = groups.cumcount().replace(0, np.nan)
        frame["merchant_frequency"] = (merchant_seen / tx_position).replace([np.inf, -np.inf], 0.0).fillna(0.0)

        frame["merchant_risk_score"] = frame["merchant"].map(self.merchant_risk_lookup).fillna(self.global_fraud_rate)

        features = frame[self.feature_columns].copy()
        for column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")
            features[column] = features[column].replace([np.inf, -np.inf], np.nan).fillna(features[column].median())
        return features

    @staticmethod
    def _sigmoid(values: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-values))

    def train(self, dataset_path: str | None = None) -> None:
        if self._trained and dataset_path is None:
            return
        df = self._load_dataset(dataset_path)
        normalized = self._normalize_dataset(df)
        self.global_fraud_rate = float(normalized["target"].mean()) if len(normalized) else 0.04
        self.merchant_risk_lookup = self._merchant_risk_map(normalized)
        x = self._prepare_behavior_features(normalized)
        y = normalized["target"].astype(int)

        x_scaled = self.scaler.fit_transform(x)
        normal_mask = y.to_numpy() == 0
        x_normal = x_scaled[normal_mask] if normal_mask.any() else x_scaled

        self.isolation_forest.fit(x_normal)
        self.local_outlier_factor.fit(x_normal)
        self.autoencoder.fit(x_normal, x_normal)

        iso_scores = self._sigmoid(-self.isolation_forest.decision_function(x_scaled) * 3.0)
        lof_scores = self._sigmoid(-self.local_outlier_factor.decision_function(x_scaled) * 2.5)
        recon = np.mean(np.square(self.autoencoder.predict(x_scaled) - x_scaled), axis=1)
        recon_scale = float(np.quantile(recon, 0.95)) or 1.0
        self.autoencoder_error_scale = recon_scale
        ae_scores = np.clip(recon / recon_scale, 0.0, 1.0)
        ensemble = np.clip((0.4 * iso_scores) + (0.3 * lof_scores) + (0.3 * ae_scores), 0.0, 1.0)

        self.dataset_stats = {
            "rows": int(len(df)),
            "features_used": self.feature_columns,
            "contamination": 0.04,
            "training_source": str(dataset_path) if dataset_path else "generated_bank_transactions",
            "fraud_ratio": round(float(y.mean()) if len(y) else 0.0, 6),
        }
        self.model_metrics = {
            "isolation_forest_avg_score": round(float(np.mean(iso_scores)), 6),
            "local_outlier_factor_avg_score": round(float(np.mean(lof_scores)), 6),
            "autoencoder_avg_score": round(float(np.mean(ae_scores)), 6),
            "ensemble_avg_score": round(float(np.mean(ensemble)), 6),
        }
        self._trained = True
        logger.info("Behavior anomaly ensemble trained with %d samples", len(df))

    def _ensure_trained(self) -> None:
        if not self._trained:
            self.train()

    def score(
        self,
        amount: float,
        transaction_amount_ratio: float,
        transaction_frequency_last_24h: float,
        location_change_flag: float,
        device_change_flag: float,
        merchant_risk_score: float,
        time_since_last_transaction: float,
        unusual_time_activity: float,
        account_transaction_velocity: float,
        merchant_frequency: float,
    ) -> dict[str, float]:
        self._ensure_trained()
        payload = np.array(
            [[
                amount,
                transaction_amount_ratio,
                transaction_frequency_last_24h,
                location_change_flag,
                device_change_flag,
                merchant_risk_score,
                time_since_last_transaction,
                unusual_time_activity,
                account_transaction_velocity,
                merchant_frequency,
            ]],
            dtype=float,
        )
        payload_scaled = self.scaler.transform(payload)

        isolation_score = float(self._sigmoid(-self.isolation_forest.decision_function(payload_scaled) * 3.0)[0])
        lof_score = float(self._sigmoid(-self.local_outlier_factor.decision_function(payload_scaled) * 2.5)[0])
        reconstructed = self.autoencoder.predict(payload_scaled)
        reconstruction_error = float(np.mean(np.square(reconstructed - payload_scaled), axis=1)[0])
        autoencoder_score = float(np.clip(reconstruction_error / max(self.autoencoder_error_scale, 1e-6), 0.0, 1.0))
        ensemble_score = float(np.clip((0.4 * isolation_score) + (0.3 * lof_score) + (0.3 * autoencoder_score), 0.0, 1.0))

        return {
            "ensemble_score": ensemble_score,
            "isolation_forest_score": isolation_score,
            "local_outlier_factor_score": lof_score,
            "autoencoder_score": autoencoder_score,
        }

    def metrics_payload(self) -> dict[str, Any]:
        self._ensure_trained()
        return {
            "dataset": self.dataset_stats,
            "models": {
                "Isolation Forest": {"status": "trained"},
                "Local Outlier Factor": {"status": "trained"},
                "Autoencoder": {"status": "trained"},
            },
            "summary": self.model_metrics,
        }

    def retrain(self, dataset_path: str | None = None) -> dict[str, Any]:
        if dataset_path:
            custom = Path(dataset_path)
            self.data_paths = [custom, *[path for path in self.data_paths if path != custom]]
        self._trained = False
        self.train(dataset_path)
        return self.metrics_payload()


behavior_model = IsolationBehaviorModel()
