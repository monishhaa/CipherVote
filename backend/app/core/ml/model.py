"""
ML Anomaly Detection Pipeline for SecureVote.
Implements Random Forest (Supervised) and Isolation Forest (Unsupervised) models.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split


class AnomalyDetectionPipeline:
    def __init__(self):
        self.rf_model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=12)
        self.if_model = IsolationForest(n_estimators=100, contamination=0.20, random_state=42)
        self.is_trained = False

    def train_and_evaluate(
        self, X: np.ndarray, y: np.ndarray
    ) -> Dict[str, Any]:
        """
        Train both models on 80% split and evaluate on 20% independent test split.
        """
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42, stratify=y
        )

        # 1. Supervised Random Forest Training
        self.rf_model.fit(X_train, y_train)
        rf_preds = self.rf_model.predict(X_test)
        rf_probs = self.rf_model.predict_proba(X_test)[:, 1]

        # 2. Unsupervised Isolation Forest Training
        # Train IF on normal instances (y == 0) for pure novelty detection
        X_train_normal = X_train[y_train == 0]
        self.if_model.fit(X_train_normal)
        if_raw = self.if_model.predict(X_test)
        # Convert IsolationForest labels (-1 for anomaly, 1 for normal) to binary (1 for anomaly, 0 for normal)
        if_preds = np.where(if_raw == -1, 1, 0)
        if_scores = -self.if_model.score_samples(X_test)

        self.is_trained = True

        # Metrics computation
        metrics = {
            "random_forest": {
                "accuracy": float(accuracy_score(y_test, rf_preds)),
                "precision": float(precision_score(y_test, rf_preds)),
                "recall": float(recall_score(y_test, rf_preds)),
                "f1": float(f1_score(y_test, rf_preds)),
                "roc_auc": float(roc_auc_score(y_test, rf_probs)),
                "confusion_matrix": confusion_matrix(y_test, rf_preds).tolist(),
            },
            "isolation_forest": {
                "accuracy": float(accuracy_score(y_test, if_preds)),
                "precision": float(precision_score(y_test, if_preds)),
                "recall": float(recall_score(y_test, if_preds)),
                "f1": float(f1_score(y_test, if_preds)),
                "roc_auc": float(roc_auc_score(y_test, if_scores)),
                "confusion_matrix": confusion_matrix(y_test, if_preds).tolist(),
            },
            "test_samples_count": len(y_test),
        }
        return metrics

    def predict_session(self, feature_vector: List[float]) -> Tuple[bool, float]:
        """
        Predict whether an incoming login session is an attack.
        Returns (is_anomaly, anomaly_probability).
        """
        if not self.is_trained:
            # Simple rule-based fallback if untrained
            ear_var = feature_vector[9]
            failed_tries = feature_vector[2]
            is_anomaly = (ear_var < 0.0001 or failed_tries >= 3)
            return is_anomaly, 0.85 if is_anomaly else 0.05

        x = np.array(feature_vector, dtype=np.float32).reshape(1, -1)
        prob = float(self.rf_model.predict_proba(x)[0, 1])
        is_anomaly = prob >= 0.50
        return is_anomaly, prob


# Global singleton
ml_pipeline = AnomalyDetectionPipeline()
