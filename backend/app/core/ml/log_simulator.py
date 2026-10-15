"""
Synthetic Authentication & Login Log Generator for SecureVote ML Engine.
Generates balanced realistic logs of normal voting sessions and multi-vector attacks.
"""

import csv
import json
import random
from typing import Dict, List, Tuple
import numpy as np
from .feature_extractor import FEATURE_NAMES, extract_features_from_session


ATTACK_TYPES = [
    "NORMAL",
    "BRUTE_FORCE_SHARES",
    "STOLEN_SHARE_PROBE",
    "BIOMETRIC_STATIC_SPOOF",
    "OFF_HOURS_BOTNET",
    "TOKEN_REPLAY_ATTACK",
]


def generate_single_session_log(label: str) -> Dict[str, any]:
    """Generate one session event record based on category."""
    if label == "NORMAL":
        hour = random.choices(
            [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
            weights=[1, 2, 3, 4, 3, 4, 3, 2, 2, 1, 1, 1],
        )[0]
        return {
            "label": "NORMAL",
            "is_attack": 0,
            "login_hour": hour + random.uniform(-0.4, 0.4),
            "failed_share_attempts": 0 if random.random() > 0.05 else 1,
            "request_rate_per_min": random.uniform(0.5, 3.0),
            "ip_subnet_change": 0 if random.random() > 0.08 else 1,
            "user_agent_entropy": random.uniform(2.5, 3.8),
            "time_since_open_sec": random.uniform(300, 18000),
            "challenge_duration_ms": random.uniform(3200, 6800),
            "biometric_distance": random.uniform(0.20, 0.52),
            "ear_variance": random.uniform(0.0025, 0.0085),  # Clear blink variance
            "yaw_range_degrees": random.uniform(16.0, 32.0),
            "session_retry_count": 0 if random.random() > 0.04 else 1,
        }

    elif label == "BRUTE_FORCE_SHARES":
        return {
            "label": "BRUTE_FORCE_SHARES",
            "is_attack": 1,
            "login_hour": random.uniform(0, 24),
            "failed_share_attempts": random.randint(5, 35),
            "request_rate_per_min": random.uniform(15.0, 120.0),
            "ip_subnet_change": random.choice([1, 2]),
            "user_agent_entropy": random.uniform(4.2, 5.5),
            "time_since_open_sec": random.uniform(10, 25000),
            "challenge_duration_ms": random.uniform(500, 2000),
            "biometric_distance": random.uniform(0.65, 1.20),
            "ear_variance": random.uniform(0.0001, 0.001),
            "yaw_range_degrees": random.uniform(0.0, 4.0),
            "session_retry_count": random.randint(5, 20),
        }

    elif label == "STOLEN_SHARE_PROBE":
        return {
            "label": "STOLEN_SHARE_PROBE",
            "is_attack": 1,
            "login_hour": random.uniform(8, 22),
            "failed_share_attempts": random.randint(1, 4),
            "request_rate_per_min": random.uniform(2.0, 8.0),
            "ip_subnet_change": random.choice([1, 2]),
            "user_agent_entropy": random.uniform(3.5, 4.8),
            "time_since_open_sec": random.uniform(600, 15000),
            "challenge_duration_ms": random.uniform(2000, 12000),
            "biometric_distance": random.uniform(0.72, 1.35),  # High mismatch distance
            "ear_variance": random.uniform(0.002, 0.006),
            "yaw_range_degrees": random.uniform(12.0, 25.0),
            "session_retry_count": random.randint(1, 5),
        }

    elif label == "BIOMETRIC_STATIC_SPOOF":
        return {
            "label": "BIOMETRIC_STATIC_SPOOF",
            "is_attack": 1,
            "login_hour": random.uniform(9, 21),
            "failed_share_attempts": 0,
            "request_rate_per_min": random.uniform(1.0, 4.0),
            "ip_subnet_change": 0,
            "user_agent_entropy": random.uniform(2.8, 3.8),
            "time_since_open_sec": random.uniform(1200, 14000),
            "challenge_duration_ms": random.uniform(800, 2500),
            "biometric_distance": random.uniform(0.25, 0.55),
            "ear_variance": random.uniform(0.00001, 0.00008),  # Flat static photo!
            "yaw_range_degrees": random.uniform(0.0, 1.5),     # No head movement
            "session_retry_count": random.randint(0, 2),
        }

    elif label == "OFF_HOURS_BOTNET":
        return {
            "label": "OFF_HOURS_BOTNET",
            "is_attack": 1,
            "login_hour": random.uniform(1.5, 4.8),  # Deep night
            "failed_share_attempts": random.randint(2, 10),
            "request_rate_per_min": random.uniform(8.0, 45.0),
            "ip_subnet_change": 2,  # Foreign IP / VPN
            "user_agent_entropy": random.uniform(4.5, 5.8),
            "time_since_open_sec": random.uniform(50, 10000),
            "challenge_duration_ms": random.uniform(600, 2200),
            "biometric_distance": random.uniform(0.68, 1.15),
            "ear_variance": random.uniform(0.0001, 0.0015),
            "yaw_range_degrees": random.uniform(0.0, 5.0),
            "session_retry_count": random.randint(3, 12),
        }

    else:  # TOKEN_REPLAY_ATTACK
        return {
            "label": "TOKEN_REPLAY_ATTACK",
            "is_attack": 1,
            "login_hour": random.uniform(10, 18),
            "failed_share_attempts": 0,
            "request_rate_per_min": random.uniform(10.0, 60.0),
            "ip_subnet_change": random.choice([0, 1]),
            "user_agent_entropy": random.uniform(3.0, 4.0),
            "time_since_open_sec": random.uniform(2000, 16000),
            "challenge_duration_ms": random.uniform(3000, 5500),
            "biometric_distance": random.uniform(0.28, 0.48),
            "ear_variance": random.uniform(0.003, 0.007),
            "yaw_range_degrees": random.uniform(18.0, 28.0),
            "session_retry_count": random.randint(2, 8),
        }


def generate_login_dataset(
    total_samples: int = 10000, attack_ratio: float = 0.20
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Generate synthetic dataset of N session logs.
    Returns (X_features, y_labels, raw_attack_types).
    """
    num_attacks = int(total_samples * attack_ratio)
    num_normals = total_samples - num_attacks

    raw_records = []
    # Generate normal sessions
    for _ in range(num_normals):
        raw_records.append(generate_single_session_log("NORMAL"))

    # Generate attack sessions evenly across attack types
    attack_types = [t for t in ATTACK_TYPES if t != "NORMAL"]
    for _ in range(num_attacks):
        atk = random.choice(attack_types)
        raw_records.append(generate_single_session_log(atk))

    random.shuffle(raw_records)

    X = np.array([extract_features_from_session(r) for r in raw_records], dtype=np.float32)
    y = np.array([r["is_attack"] for r in raw_records], dtype=np.int32)
    labels = [r["label"] for r in raw_records]

    return X, y, labels
