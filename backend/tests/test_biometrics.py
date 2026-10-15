"""
Unit & Security Tests for SecureVote Biometric Face Engine & Liveness System.
"""

import os
import pytest
import numpy as np
from app.core.biometrics.face_engine import FaceEngine, face_engine
from app.core.biometrics.liveness import LivenessEngine, liveness_engine
from app.core.biometrics.template_crypto import (
    compute_euclidean_distance,
    decrypt_face_template,
    encrypt_face_template,
)


def test_embedding_dimensions_and_norm():
    """Verify 128-dimensional embedding extraction and L2 normalization."""
    # Create synthetic test image
    test_img = np.zeros((160, 160, 3), dtype=np.uint8)
    test_img[40:120, 40:120] = [180, 150, 120]

    emb = face_engine.extract_embedding_from_image(test_img)
    assert len(emb) == 128
    norm = np.linalg.norm(emb)
    assert abs(norm - 1.0) < 1e-4


def test_encrypted_biometric_template_vault():
    """Test AES-256-GCM encryption roundtrip and integrity verification for face templates."""
    raw_embedding = [float(x) for x in np.random.randn(128)]
    raw_embedding = (np.array(raw_embedding) / np.linalg.norm(raw_embedding)).tolist()

    encrypted_blob = encrypt_face_template(raw_embedding)
    assert ":" in encrypted_blob

    # Decrypt
    decrypted = decrypt_face_template(encrypted_blob)
    assert len(decrypted) == 128
    assert np.allclose(raw_embedding, decrypted, atol=1e-5)

    # Tampered blob fails integrity
    parts = encrypted_blob.split(":")
    tampered_tag = "00" * 16
    bad_blob = f"{parts[0]}:{parts[1]}:{tampered_tag}"
    with pytest.raises(ValueError, match="integrity"):
        decrypt_face_template(bad_blob)


def test_liveness_challenge_and_spoof_detection():
    """Test active challenge-response liveness and rejection of static photo spoofs."""
    engine = LivenessEngine(timeout_seconds=10)
    chal = engine.issue_challenge(num_actions=2)
    assert len(chal.actions) == 2

    # Case 1: Static photo spoof (constant EAR and Yaw) -> REJECTED
    static_ear = [0.32, 0.32, 0.32, 0.32]
    static_yaw = [0.0, 0.0, 0.0, 0.0]
    passed1, msg1 = engine.verify_challenge_telemetry(chal.challenge_id, static_ear, static_yaw)
    assert passed1 is False
    assert "Spoof detected" in msg1

    # Case 2: Genuine blink + left turn sequence -> ACCEPTED
    chal2 = engine.issue_challenge(num_actions=2)
    chal2.actions = ["BLINK", "TURN_LEFT"]
    engine.active_challenges[chal2.challenge_id] = chal2

    genuine_ear = [0.34, 0.15, 0.35, 0.33]  # Clear blink below 0.22
    genuine_yaw = [0.0, -14.5, -12.0, 0.0]  # Clear left turn below -8.0
    passed2, msg2 = engine.verify_challenge_telemetry(chal2.challenge_id, genuine_ear, genuine_yaw)
    assert passed2 is True
    assert "verified successfully" in msg2


def test_lfw_real_pair_matching():
    """Test matching on actual LFW images if present."""
    lfw_img1 = "data/lfw/lfw-deepfunneled/lfw-deepfunneled/George_W_Bush/George_W_Bush_0001.jpg"
    lfw_img2 = "data/lfw/lfw-deepfunneled/lfw-deepfunneled/George_W_Bush/George_W_Bush_0002.jpg"
    lfw_impostor = "data/lfw/lfw-deepfunneled/lfw-deepfunneled/Colin_Powell/Colin_Powell_0001.jpg"

    if os.path.exists(lfw_img1) and os.path.exists(lfw_img2) and os.path.exists(lfw_impostor):
        emb1 = face_engine.extract_embedding_from_image(lfw_img1)
        emb2 = face_engine.extract_embedding_from_image(lfw_img2)
        emb_imp = face_engine.extract_embedding_from_image(lfw_impostor)

        # Genuine match distance should be smaller than impostor distance
        gen_dist = face_engine.compute_distance(emb1, emb2)
        imp_dist = face_engine.compute_distance(emb1, emb_imp)

        assert gen_dist < imp_dist, f"Genuine {gen_dist:.3f} not smaller than Impostor {imp_dist:.3f}"
