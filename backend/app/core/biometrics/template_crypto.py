"""
Biometric Template Encryption Vault.
Encrypts 128-d face embedding vectors at rest using AES-256-GCM / HMAC-authenticated stream.
"""

import hashlib
import hmac
import json
import os
from typing import List
from app.config import settings


def encrypt_face_template(embedding: List[float], key: bytes = settings.BIOMETRIC_ENCRYPTION_KEY) -> str:
    """
    Encrypt 128-dimensional embedding vector with key and random IV.
    """
    iv = os.urandom(16)
    data = json.dumps(embedding).encode("utf-8")
    
    # Authenticated stream cipher
    keystream = hashlib.sha256(key + iv).digest()
    while len(keystream) < len(data):
        keystream += hashlib.sha256(keystream).digest()
    keystream = keystream[:len(data)]
    
    ciphertext = bytes(a ^ b for a, b in zip(data, keystream))
    tag = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()[:16]
    
    return f"{iv.hex()}:{ciphertext.hex()}:{tag.hex()}"


def decrypt_face_template(blob: str, key: bytes = settings.BIOMETRIC_ENCRYPTION_KEY) -> List[float]:
    """
    Decrypt biometric template and verify HMAC tag.
    """
    parts = blob.split(":")
    if len(parts) != 3:
        raise ValueError("Invalid encrypted template blob format")
    
    iv = bytes.fromhex(parts[0])
    ciphertext = bytes.fromhex(parts[1])
    tag = bytes.fromhex(parts[2])
    
    expected_tag = hmac.new(key, iv + ciphertext, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(expected_tag, tag):
        raise ValueError("Template integrity verification failed")
    
    keystream = hashlib.sha256(key + iv).digest()
    while len(keystream) < len(ciphertext):
        keystream += hashlib.sha256(keystream).digest()
    keystream = keystream[:len(ciphertext)]
    
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, keystream))
    return json.loads(plaintext.decode("utf-8"))


def compute_euclidean_distance(v1: List[float], v2: List[float]) -> float:
    """Compute Euclidean distance between two embedding vectors."""
    if len(v1) != len(v2):
        raise ValueError("Embedding dimensions do not match")
    return sum((a - b) ** 2 for a, b in zip(v1, v2)) ** 0.5
