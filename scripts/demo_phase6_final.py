"""
Interactive Demo Script for Phase 6: Scale Benchmarks, Comparisons & Final Report.
Demonstrates:
1. Large-Scale Cryptographic Benchmarks (1k, 2.5k, 5k voters)
2. Empirical Blockchain vs. Hash-Chain Ledger Comparison
3. Helios & Belenios Comparison Matrix
4. Generating Final Project Report (REPORT.md)
"""

import os
import sys

# Add project root and backend to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
sys.path.insert(0, PROJECT_ROOT)

from evaluation.eval_scale_benchmark import run_scale_benchmarks
from evaluation.eval_comparison import run_comparative_evaluation
from evaluation.generate_final_report import generate_report


def run_phase6_demo():
    print("=" * 75)
    print(" SECUREVOTE FINAL SCALE BENCHMARKS, COMPARISONS & REPORT (Phase 6)")
    print("=" * 75)

    # 1. Scale Benchmarks
    print("\n[1] Running Large-Scale Cryptographic Benchmarks...")
    run_scale_benchmarks(scale_sizes=[1000, 2500, 5000])

    # 2. Blockchain vs Hash-Chain Comparison
    print("\n[2] Running Blockchain vs Hash-Chain Comparison Benchmark...")
    run_comparative_evaluation()

    # 3. Generate Final Report
    print("\n[3] Generating Final Consolidated Research Report (REPORT.md)...")
    generate_report()

    print("\n" + "=" * 75)
    print(" ALL PHASE 6 BENCHMARKS & FINAL DELIVERABLES PRODUCED (100%)")
    print(" Report Markdown : REPORT.md")
    print(" Plots Directory : evaluation/plots/")
    print("=" * 75)


if __name__ == "__main__":
    run_phase6_demo()
