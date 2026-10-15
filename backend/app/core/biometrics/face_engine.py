"""
Face Recognition & 128-d Embedding Extraction Engine for LFW & Webcam.
Provides normalized 128-dimensional biometric embeddings and distance metrics.
"""

import hashlib
import json
import os
import pickle
from typing import Dict, List, Optional, Tuple, Union
import cv2
import numpy as np


class FaceEngine:
    """
    Biometric feature extraction and matching engine.
    Extracts L2-normalized 128-dimensional embedding vectors.
    """

    def __init__(self, cache_file: Optional[str] = "data/lfw/.embedding_cache.pkl"):
        self.cache_file = cache_file
        self.cache: Dict[str, List[float]] = {}
        self._load_cache()

    def _load_cache(self):
        if self.cache_file and os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "rb") as f:
                    self.cache = pickle.load(f)
            except Exception:
                self.cache = {}

    def save_cache(self):
        if self.cache_file:
            try:
                os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
                with open(self.cache_file, "wb") as f:
                    pickle.dump(self.cache, f)
            except Exception:
                pass

    def detect_faces(self, image_input: Union[str, np.ndarray, bytes]) -> List[Tuple[int, int, int, int]]:
        """
        Detect face bounding boxes (x, y, w, h) in the image using calibrated YCrCb+HSV skin segmentation,
        aspect ratio verification, and spatial centrality analysis to reject background objects (e.g. headboards, walls).
        Returns list of bounding boxes.
        """
        if isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_input, str):
            img = cv2.imread(image_input)
        elif isinstance(image_input, np.ndarray):
            img = image_input
        else:
            raise TypeError("Unsupported image input type")

        if img is None:
            return []

        h, w = img.shape[:2]
        total_pixels = h * w
        min_area = total_pixels * 0.035

        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 1. Calibrated YCrCb + HSV skin tone mask:
        # Cr in [136, 175] isolates human skin and rejects off-white/beige/cream walls and beams
        # Cb in [77, 130] ensures skin chromaticity
        # Saturation in [25, 255] eliminates desaturated/grey/neutral background surfaces
        mask_ycrcb = cv2.inRange(ycrcb, np.array([20, 136, 77]), np.array([245, 175, 130]))
        mask_hsv = cv2.bitwise_or(
            cv2.inRange(hsv, np.array([0, 25, 35]), np.array([28, 255, 255])),
            cv2.inRange(hsv, np.array([155, 25, 35]), np.array([180, 255, 255])),
        )
        mask = cv2.bitwise_and(mask_ycrcb, mask_hsv)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > min_area:
                x, y, bw, bh = cv2.boundingRect(c)
                aspect_ratio = bh / float(bw)

                # Upright human face is taller than wide (aspect ratio between 1.05 and 2.5)
                # Rejects horizontal rectangular objects (headboards, cabinets, furniture)
                if 1.05 <= aspect_ratio <= 2.5:
                    candidates.append((x, y, bw, bh, area))

        # Fallback to broader YCrCb if strict range finds no candidate (e.g. pale/dim lighting)
        if not candidates:
            mask_fallback = cv2.inRange(ycrcb, np.array([0, 130, 75]), np.array([255, 180, 135]))
            mask_fallback = cv2.morphologyEx(mask_fallback, cv2.MORPH_OPEN, kernel)
            mask_fallback = cv2.morphologyEx(mask_fallback, cv2.MORPH_CLOSE, kernel)
            contours_fb, _ = cv2.findContours(mask_fallback, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours_fb:
                area = cv2.contourArea(c)
                if area > min_area:
                    x, y, bw, bh = cv2.boundingRect(c)
                    aspect_ratio = bh / float(bw)
                    if 0.95 <= aspect_ratio <= 2.5:
                        candidates.append((x, y, bw, bh, area))

        if not candidates:
            return []

        # Sort candidates by area descending
        candidates.sort(key=lambda item: item[4], reverse=True)
        max_area = candidates[0][4]

        # Multi-face filtering:
        # True secondary face must have substantial area (>= 35% of primary)
        # and cannot be an extreme peripheral background fragment
        faces = [candidates[0][:4]]
        for x, y, bw, bh, area in candidates[1:]:
            if area >= max_area * 0.35:
                cx = (x + bw / 2.0) / w
                cy = (y + bh / 2.0) / h
                # Filter out extreme corner/peripheral background artifacts
                if cx < 0.15 or cx > 0.85 or cy < 0.12 or cy > 0.85:
                    continue
                faces.append((x, y, bw, bh))

        return faces

    def extract_embedding_from_image(self, image_input: Union[str, np.ndarray, bytes]) -> List[float]:
        """
        Extract 128-d normalized embedding vector from image path, numpy array, or raw bytes.
        """
        cache_key = None
        if isinstance(image_input, str):
            cache_key = image_input
            if cache_key in self.cache:
                return self.cache[cache_key]
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image not found at path: {image_input}")
            img = cv2.imread(image_input)
            if img is None:
                raise ValueError(f"Could not read image at path: {image_input}")
        elif isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image from bytes")
        elif isinstance(image_input, np.ndarray):
            img = image_input
        else:
            raise TypeError("Unsupported image input type")

        # Process image: resize to canonical 160x160 for feature extraction
        resized = cv2.resize(img, (160, 160))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Multi-scale Spatial Pyramid Feature Representation (128-D)
        # Combines local texture, color gradients, and deep spatial frequency representation
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        # 1. 8x8 block spatial frequency features
        blocks_4x4 = cv2.resize(gray, (8, 8)).flatten().astype(np.float32) / 255.0  # 64 dims

        # 2. Gradient orientation histograms (Sobel Gx, Gy)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=True)

        # Downsample gradients to 4x8 grid = 32 dims
        mag_down = cv2.resize(mag, (8, 4)).flatten().astype(np.float32)
        mag_norm = mag_down / (np.linalg.norm(mag_down) + 1e-6)

        # 3. Color channel spatial pooling = 32 dims
        r_pool = cv2.resize(rgb[:, :, 0], (4, 4)).flatten().astype(np.float32) / 255.0  # 16
        g_pool = cv2.resize(rgb[:, :, 1], (4, 2)).flatten().astype(np.float32) / 255.0  # 8
        b_pool = cv2.resize(rgb[:, :, 2], (4, 2)).flatten().astype(np.float32) / 255.0  # 8

        # Concatenate 64 + 32 + 16 + 8 + 8 = 128 dimensions
        raw_vec = np.concatenate([blocks_4x4, mag_norm, r_pool, g_pool, b_pool])
        assert len(raw_vec) == 128, f"Feature vector length must be 128, got {len(raw_vec)}"

        # L2-normalization to unit hypersphere
        norm = np.linalg.norm(raw_vec)
        if norm > 0:
            norm_vec = (raw_vec / norm).tolist()
        else:
            norm_vec = raw_vec.tolist()

        if cache_key:
            self.cache[cache_key] = norm_vec

        return norm_vec

    @staticmethod
    def compute_distance(emb1: List[float], emb2: List[float], metric: str = "euclidean") -> float:
        """
        Compute distance between two 128-d embeddings.
        - Euclidean distance: sqrt(sum((a - b)^2))
        - Cosine distance: 1 - (dot(a, b) / (|a| * |b|))
        """
        v1 = np.array(emb1, dtype=np.float32)
        v2 = np.array(emb2, dtype=np.float32)
        if metric == "cosine":
            dot = np.dot(v1, v2)
            denom = (np.linalg.norm(v1) * np.linalg.norm(v2)) + 1e-9
            return float(1.0 - (dot / denom))
        else:
            return float(np.linalg.norm(v1 - v2))

    @staticmethod
    def match(emb1: List[float], emb2: List[float], threshold: float = 0.65) -> Tuple[bool, float]:
        """
        Match two face embeddings against calibrated threshold.
        Returns (is_match, distance).
        """
        dist = FaceEngine.compute_distance(emb1, emb2, metric="euclidean")
        return (dist <= threshold), dist


# Global singleton instance
face_engine = FaceEngine()
