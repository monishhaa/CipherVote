"""
Biometrics package for SecureVote.
"""

from .face_engine import FaceEngine, face_engine
from .liveness import LivenessChallenge, LivenessEngine, liveness_engine
from .template_crypto import (
    compute_euclidean_distance,
    decrypt_face_template,
    encrypt_face_template,
)

__all__ = [
    "FaceEngine",
    "face_engine",
    "LivenessEngine",
    "liveness_engine",
    "LivenessChallenge",
    "encrypt_face_template",
    "decrypt_face_template",
    "compute_euclidean_distance",
]
