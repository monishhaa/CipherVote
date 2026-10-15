"""
Unit Tests for Machine Learning Pipeline and Attack Resistance.
"""

import pytest
import numpy as np
from app.core.ml.feature_extractor import FEATURE_NAMES, extract_features_from_session
from app.core.ml.log_simulator import generate_login_dataset, generate_single_session_log
from app.core.ml.model import AnomalyDetectionPipeline


def test_feature_extractor():
    """Verify 12 numerical features are correctly extracted from session log."""
    sample_log = {
        "login_hour": 14.5,
        "failed_share_attempts": 2,
        "request_rate_per_min": 1.2,
        "ip_subnet_change": 0,
        "user_agent_entropy": 3.1,
        "time_since_open_sec": 4500,
        "challenge_duration_ms": 4200,
        "biometric_distance": 0.38,
        "ear_variance": 0.0042,
        "yaw_range_degrees": 24.5,
        "session_retry_count": 1,
    }

    features = extract_features_from_session(sample_log)
    assert len(features) == 12
    assert features[0] == 14.5
    assert features[1] == 0.0  # not night time
    assert features[2] == 2.0


def test_ml_pipeline_training_and_evaluation():
    """Verify Random Forest and Isolation Forest train and achieve high F1 on synthetic data."""
    X, y, _ = generate_login_dataset(total_samples=1000, attack_ratio=0.20)
    assert len(X) == 1000
    assert len(y) == 1000

    pipeline = AnomalyDetectionPipeline()
    metrics = pipeline.train_and_evaluate(X, y)

    rf_f1 = metrics["random_forest"]["f1"]
    if_f1 = metrics["isolation_forest"]["f1"]

    assert rf_f1 > 0.85, f"Random Forest F1 ({rf_f1:.2f}) should exceed 0.85"
    assert if_f1 > 0.50, f"Isolation Forest F1 ({if_f1:.2f}) should exceed 0.50"


def test_ml_single_session_prediction():
    """Verify that a brute force / spoof feature vector is flagged as anomaly."""
    pipeline = AnomalyDetectionPipeline()
    X, y, _ = generate_login_dataset(total_samples=500, attack_ratio=0.25)
    pipeline.train_and_evaluate(X, y)

    # Normal session feature vector
    normal_vec = [14.0, 0.0, 0.0, 1.0, 0.0, 3.2, 2000.0, 4500.0, 0.32, 0.005, 25.0, 0.0]
    is_anomaly_norm, prob_norm = pipeline.predict_session(normal_vec)
    assert is_anomaly_norm is False

    # Brute force attack feature vector
    attack_vec = [2.5, 1.0, 15.0, 85.0, 2.0, 5.2, 100.0, 1200.0, 0.95, 0.00005, 1.0, 12.0]
    is_anomaly_atk, prob_atk = pipeline.predict_session(attack_vec)
    assert is_anomaly_atk is True
    assert prob_atk > 0.70
