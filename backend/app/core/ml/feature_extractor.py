"""
Feature Engineering for SecureVote Login & Authentication Logs.
Extracts 12 numerical features from session telemetry.
"""

from typing import Any, Dict, List
import numpy as np

FEATURE_NAMES = [
    "login_hour",
    "is_night_time",
    "failed_share_attempts",
    "request_rate_per_min",
    "ip_subnet_change",
    "user_agent_entropy",
    "time_since_open_sec",
    "challenge_duration_ms",
    "biometric_distance",
    "ear_variance",
    "yaw_range_degrees",
    "session_retry_count",
]


def extract_features_from_session(log_data: Dict[str, Any]) -> List[float]:
    """
    Transform raw session log record into 12-dimensional numerical feature vector.
    """
    hour = float(log_data.get("login_hour", 14))
    is_night = 1.0 if (hour < 6 or hour > 22) else 0.0
    failed_attempts = float(log_data.get("failed_share_attempts", 0))
    req_rate = float(log_data.get("request_rate_per_min", 1.0))
    ip_change = float(log_data.get("ip_subnet_change", 0))
    ua_entropy = float(log_data.get("user_agent_entropy", 3.2))
    time_since_open = float(log_data.get("time_since_open_sec", 1800))
    challenge_dur = float(log_data.get("challenge_duration_ms", 4500))
    bio_dist = float(log_data.get("biometric_distance", 0.35))
    ear_var = float(log_data.get("ear_variance", 0.0045))
    yaw_range = float(log_data.get("yaw_range_degrees", 22.0))
    retry_count = float(log_data.get("session_retry_count", 0))

    return [
        hour,
        is_night,
        failed_attempts,
        req_rate,
        ip_change,
        ua_entropy,
        time_since_open,
        challenge_dur,
        bio_dist,
        ear_var,
        yaw_range,
        retry_count,
    ]
