"""
Strict Biometric FAR / FRR Evaluation Script on LFW Deep-Funneled Dataset.

Methodology Rules:
1. Calibration: Threshold theta* is tuned strictly on matchpairsDevTrain.csv (1,100 pairs)
   and mismatchpairsDevTrain.csv (1,100 pairs).
2. Testing: Evaluated strictly on matchpairsDevTest.csv (500 pairs) and
   mismatchpairsDevTest.csv (500 pairs). Never tuned on test split.
3. Outputs: Test FAR, Test FRR, EER, Accuracy, ROC curve, and DET curve.
"""

import csv
import os
import sys
import matplotlib.pyplot as plt
import numpy as np

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.core.biometrics.face_engine import face_engine


LFW_BASE_DIR = "data/lfw"
IMG_ROOT = os.path.join(LFW_BASE_DIR, "lfw-deepfunneled", "lfw-deepfunneled")


def get_image_path(name: str, num_str: str) -> str:
    """Build nested LFW image path."""
    num_int = int(num_str)
    filename = f"{name}_{num_int:04d}.jpg"
    return os.path.join(IMG_ROOT, name, filename)


def load_pairs_from_csv(csv_path: str, is_match: bool):
    """Load image pairs from match or mismatch CSV files."""
    pairs = []
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row or len(row) < 3:
                continue
            if is_match:
                name = row[0].strip()
                p1 = get_image_path(name, row[1].strip())
                p2 = get_image_path(name, row[2].strip())
            else:
                name1 = row[0].strip()
                p1 = get_image_path(name1, row[1].strip())
                name2 = row[2].strip()
                p2 = get_image_path(name2, row[3].strip())
            if os.path.exists(p1) and os.path.exists(p2):
                pairs.append((p1, p2))
    return pairs


def compute_pair_distances(pairs, desc: str = ""):
    """Extract embeddings and compute Euclidean distances for pairs."""
    distances = []
    print(f" -> Extracting embeddings for {len(pairs)} pairs ({desc})...")
    for idx, (p1, p2) in enumerate(pairs):
        try:
            emb1 = face_engine.extract_embedding_from_image(p1)
            emb2 = face_engine.extract_embedding_from_image(p2)
            dist = face_engine.compute_distance(emb1, emb2, metric="euclidean")
            distances.append(dist)
        except Exception as e:
            continue
        if (idx + 1) % 500 == 0 or (idx + 1) == len(pairs):
            print(f"    Processed {idx + 1}/{len(pairs)}...")
    return np.array(distances, dtype=np.float32)


def evaluate_threshold_metrics(genuine_dists, impostor_dists, threshold):
    """Compute FAR, FRR, and Accuracy for a given threshold."""
    # Genuine accepted if dist <= threshold; False Reject if dist > threshold
    frr = float(np.mean(genuine_dists > threshold))
    # Impostor rejected if dist > threshold; False Accept if dist <= threshold
    far = float(np.mean(impostor_dists <= threshold))
    accuracy = 1.0 - 0.5 * (frr + far)
    return far, frr, accuracy


def run_evaluation():
    print("=" * 75)
    print(" LFW BIOMETRIC FAR / FRR EVALUATION (Strict DevTrain / DevTest Splits)")
    print("=" * 75)

    # 1. Load DevTrain Pairs
    train_match_csv = os.path.join(LFW_BASE_DIR, "matchpairsDevTrain.csv")
    train_mismatch_csv = os.path.join(LFW_BASE_DIR, "mismatchpairsDevTrain.csv")

    train_genuine_pairs = load_pairs_from_csv(train_match_csv, is_match=True)
    train_impostor_pairs = load_pairs_from_csv(train_mismatch_csv, is_match=False)

    print(f"[1] Loaded DevTrain Data:")
    print(f"    - Genuine Pairs  : {len(train_genuine_pairs)} from matchpairsDevTrain.csv")
    print(f"    - Impostor Pairs : {len(train_impostor_pairs)} from mismatchpairsDevTrain.csv")

    train_gen_dists = compute_pair_distances(train_genuine_pairs, "DevTrain Genuine")
    train_imp_dists = compute_pair_distances(train_impostor_pairs, "DevTrain Impostor")

    # 2. Calibrate Optimal Threshold theta* on DevTrain ONLY
    thresholds = np.linspace(0.0, 1.5, 300)
    best_diff = 1.0
    optimal_threshold = 0.65
    train_eer = 0.0

    for th in thresholds:
        far, frr, _ = evaluate_threshold_metrics(train_gen_dists, train_imp_dists, th)
        diff = abs(far - frr)
        if diff < best_diff:
            best_diff = diff
            optimal_threshold = th
            train_eer = (far + frr) / 2.0

    print(f"\n[2] DevTrain Calibration Results (Threshold Tuning):")
    print(f"    - Optimal Threshold (theta*) : {optimal_threshold:.4f}")
    print(f"    - DevTrain Equal Error Rate  : {train_eer * 100:.2f}%")

    # Save cache
    face_engine.save_cache()

    # 3. Independent Testing on DevTest ONLY
    test_match_csv = os.path.join(LFW_BASE_DIR, "matchpairsDevTest.csv")
    test_mismatch_csv = os.path.join(LFW_BASE_DIR, "mismatchpairsDevTest.csv")

    test_genuine_pairs = load_pairs_from_csv(test_match_csv, is_match=True)
    test_impostor_pairs = load_pairs_from_csv(test_mismatch_csv, is_match=False)

    print(f"\n[3] Loaded DevTest Data (Independent Evaluation):")
    print(f"    - Genuine Pairs  : {len(test_genuine_pairs)} from matchpairsDevTest.csv")
    print(f"    - Impostor Pairs : {len(test_impostor_pairs)} from mismatchpairsDevTest.csv")

    test_gen_dists = compute_pair_distances(test_genuine_pairs, "DevTest Genuine")
    test_imp_dists = compute_pair_distances(test_impostor_pairs, "DevTest Impostor")

    # Save cache
    face_engine.save_cache()

    # 4. Evaluate Test Metrics at theta*
    test_far, test_frr, test_acc = evaluate_threshold_metrics(
        test_gen_dists, test_imp_dists, optimal_threshold
    )

    # Compute ROC Curve points on Test Split
    roc_far = []
    roc_tar = []  # True Accept Rate = 1 - FRR
    roc_frr = []

    for th in thresholds:
        far, frr, _ = evaluate_threshold_metrics(test_gen_dists, test_imp_dists, th)
        roc_far.append(far)
        roc_tar.append(1.0 - frr)
        roc_frr.append(frr)

    roc_far = np.array(roc_far)
    roc_tar = np.array(roc_tar)
    roc_frr = np.array(roc_frr)

    # Find Test EER
    test_eer_idx = np.argmin(np.abs(roc_far - roc_frr))
    test_eer = (roc_far[test_eer_idx] + roc_frr[test_eer_idx]) / 2.0

    print(f"\n[4] FINAL INDEPENDENT TEST RESULTS (on DevTest at theta* = {optimal_threshold:.4f}):")
    print(f"    ==================================================")
    print(f"    * Test Accuracy                 : {test_acc * 100:.2f}%")
    print(f"    * False Accept Rate (FAR)       : {test_far * 100:.2f}%")
    print(f"    * False Reject Rate (FRR)       : {test_frr * 100:.2f}%")
    print(f"    * Test Equal Error Rate (EER)   : {test_eer * 100:.2f}%")
    print(f"    ==================================================")

    # 5. Generate High-Resolution Plots
    os.makedirs("evaluation/plots", exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Subplot 1: Distance Distributions
    ax1.hist(test_gen_dists, bins=30, alpha=0.65, color="#10B981", label="Genuine Pairs (Same Identity)", density=True)
    ax1.hist(test_imp_dists, bins=30, alpha=0.65, color="#EF4444", label="Impostor Pairs (Different Identity)", density=True)
    ax1.axvline(optimal_threshold, color="#1E293B", linestyle="--", linewidth=2, label=f"Calibrated Threshold (theta*={optimal_threshold:.2f})")
    ax1.set_title("LFW Test Distance Distribution (Euclidean)", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Biometric Euclidean Distance")
    ax1.set_ylabel("Probability Density")
    ax1.legend(loc="upper right", frameon=True)
    ax1.grid(True, linestyle=":", alpha=0.6)

    # Subplot 2: ROC Curve (FAR vs TAR)
    ax2.plot(roc_far * 100, roc_tar * 100, color="#3B82F6", linewidth=2.5, label=f"SecureVote Face Engine (EER: {test_eer*100:.1f}%)")
    ax2.plot([0, 100], [0, 100], color="#94A3B8", linestyle="--", label="Random Guess")
    ax2.scatter([test_far * 100], [(1 - test_frr) * 100], color="#DC2626", s=80, zorder=5, label=f"Operating Point (FAR: {test_far*100:.1f}%, FRR: {test_frr*100:.1f}%)")
    ax2.set_title("ROC Curve on LFW DevTest", fontsize=13, fontweight="bold")
    ax2.set_xlabel("False Accept Rate (FAR %)")
    ax2.set_ylabel("True Accept Rate (TAR % = 1 - FRR)")
    ax2.set_xlim([0, 100])
    ax2.set_ylim([0, 105])
    ax2.legend(loc="lower right", frameon=True)
    ax2.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    plot_path = "evaluation/plots/lfw_roc_curve.png"
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"\n[5] Saved High-Resolution ROC/DET Curve Figure to: {plot_path}")

    return {
        "optimal_threshold": float(optimal_threshold),
        "test_accuracy": float(test_acc),
        "test_far": float(test_far),
        "test_frr": float(test_frr),
        "test_eer": float(test_eer),
        "plot_path": plot_path,
    }


if __name__ == "__main__":
    run_evaluation()
