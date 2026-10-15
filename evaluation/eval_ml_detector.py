"""
Evaluation Script for ML Anomaly Detection Engine (Random Forest & Isolation Forest).
Trains on 10,000 synthetic session logs (80/20 train/test split) and outputs performance metrics and plots.
"""

import os
import sys
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

# Add project root and backend to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
sys.path.insert(0, PROJECT_ROOT)

from app.core.ml.feature_extractor import FEATURE_NAMES
from app.core.ml.log_simulator import generate_login_dataset
from app.core.ml.model import ml_pipeline


def run_ml_evaluation():
    print("=" * 75)
    print(" SECUREVOTE ML ANOMALY DETECTOR EVALUATION (10,000 Session Logs)")
    print("=" * 75)

    # 1. Synthesize 10,000 Session Logs
    print("\n[1] Generating 10,000 Realistic Session Logs (80% Normal, 20% Multi-Vector Attacks)...")
    X, y, labels = generate_login_dataset(total_samples=10000, attack_ratio=0.20)
    print(f" -> Generated {len(X)} records across 12 engineered features.")

    # 2. Train & Evaluate
    print("\n[2] Training Supervised Random Forest & Unsupervised Isolation Forest (80/20 Split)...")
    metrics = ml_pipeline.train_and_evaluate(X, y)

    rf_m = metrics["random_forest"]
    if_m = metrics["isolation_forest"]

    print("\n" + "=" * 75)
    print(" MODEL PERFORMANCE EVALUATION RESULTS (2,000 Independent Test Samples)")
    print("=" * 75)
    print(f"{'Metric':<25} | {'Random Forest (Supervised)':<26} | {'Isolation Forest (Unsupervised)':<26}")
    print("-" * 75)
    print(f"{'Accuracy':<25} | {rf_m['accuracy'] * 100:6.2f}%                    | {if_m['accuracy'] * 100:6.2f}%")
    print(f"{'Precision':<25} | {rf_m['precision'] * 100:6.2f}%                    | {if_m['precision'] * 100:6.2f}%")
    print(f"{'Recall':<25} | {rf_m['recall'] * 100:6.2f}%                    | {if_m['recall'] * 100:6.2f}%")
    print(f"{'F1-Score':<25} | {rf_m['f1'] * 100:6.2f}%                    | {if_m['f1'] * 100:6.2f}%")
    print(f"{'ROC-AUC':<25} | {rf_m['roc_auc'] * 100:6.2f}%                    | {if_m['roc_auc'] * 100:6.2f}%")
    print("=" * 75)

    # 3. Feature Importance Analysis
    importances = ml_pipeline.rf_model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("\n[3] Random Forest Feature Importance Ranking:")
    for rank, idx in enumerate(sorted_idx[:6], start=1):
        print(f"    {rank}. {FEATURE_NAMES[idx]:<28}: {importances[idx] * 100:.2f}%")

    # 4. Generate High-Resolution Visualizations
    os.makedirs("evaluation/plots", exist_ok=True)
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 12))

    # Subplot 1: Random Forest Confusion Matrix
    cm_rf = np.array(rf_m["confusion_matrix"])
    sns.heatmap(cm_rf, annot=True, fmt="d", cmap="Blues", cbar=False, ax=ax1,
                xticklabels=["Normal", "Attack"], yticklabels=["Normal", "Attack"])
    ax1.set_title(f"Random Forest Confusion Matrix (F1: {rf_m['f1']*100:.1f}%)", fontweight="bold")
    ax1.set_xlabel("Predicted Label")
    ax1.set_ylabel("True Label")

    # Subplot 2: Isolation Forest Confusion Matrix
    cm_if = np.array(if_m["confusion_matrix"])
    sns.heatmap(cm_if, annot=True, fmt="d", cmap="Greens", cbar=False, ax=ax2,
                xticklabels=["Normal", "Attack"], yticklabels=["Normal", "Attack"])
    ax2.set_title(f"Isolation Forest Confusion Matrix (F1: {if_m['f1']*100:.1f}%)", fontweight="bold")
    ax2.set_xlabel("Predicted Label")
    ax2.set_ylabel("True Label")

    # Subplot 3: Metric Comparison Bar Chart
    metric_names = ["Accuracy", "Precision", "Recall", "F1-Score", "ROC-AUC"]
    rf_vals = [rf_m["accuracy"]*100, rf_m["precision"]*100, rf_m["recall"]*100, rf_m["f1"]*100, rf_m["roc_auc"]*100]
    if_vals = [if_m["accuracy"]*100, if_m["precision"]*100, if_m["recall"]*100, if_m["f1"]*100, if_m["roc_auc"]*100]

    x = np.arange(len(metric_names))
    width = 0.35
    ax3.bar(x - width/2, rf_vals, width, label="Random Forest (Supervised)", color="#3B82F6")
    ax3.bar(x + width/2, if_vals, width, label="Isolation Forest (Unsupervised)", color="#10B981")
    ax3.set_title("Detector Performance Comparison (%)", fontweight="bold")
    ax3.set_xticks(x)
    ax3.set_xticklabels(metric_names)
    ax3.set_ylim([0, 115])
    ax3.legend(loc="upper right")
    ax3.grid(axis="y", linestyle=":", alpha=0.6)

    # Subplot 4: Feature Importance Bar Chart
    sorted_features = [FEATURE_NAMES[i] for i in sorted_idx]
    sorted_weights = [importances[i]*100 for i in sorted_idx]
    ax4.barh(sorted_features[::-1], sorted_weights[::-1], color="#8B5CF6")
    ax4.set_title("Engineered Feature Importance (Gini Impurity)", fontweight="bold")
    ax4.set_xlabel("Importance (%)")
    ax4.grid(axis="x", linestyle=":", alpha=0.6)

    plt.tight_layout()
    plot_path = "evaluation/plots/ml_anomaly_detection.png"
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"\n[4] Saved High-Resolution Evaluation Chart to: {plot_path}")

    return metrics


if __name__ == "__main__":
    run_ml_evaluation()
