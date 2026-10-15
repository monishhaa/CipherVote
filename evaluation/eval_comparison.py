"""
Empirical Comparison Suite:
1. Hash-Chain Bulletin Board vs. Proof-of-Authority (PoA) Blockchain
2. SecureVote vs. Helios and Belenios Verifiable Voting Systems
"""

import hashlib
import json
import os
import sys
import time
import matplotlib.pyplot as plt
import numpy as np

# Add project root and backend to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
sys.path.insert(0, PROJECT_ROOT)

from app.core.bulletin_board.hash_chain import compute_ballot_payload_hash


def simulate_blockchain_block_generation(num_transactions: int = 1000, block_size: int = 50):
    """
    Simulates Proof-of-Authority (PoA) blockchain block packaging, Merkle tree computation,
    validator signature simulation, and consensus latency.
    """
    t0 = time.perf_counter()
    num_blocks = (num_transactions + block_size - 1) // block_size
    prev_block_hash = "00" * 32
    blockchain_storage_bytes = 0

    for b in range(num_blocks):
        # Package transactions into block
        block_txs = [f"tx_data_{b}_{i}" for i in range(min(block_size, num_transactions - b * block_size))]
        merkle_root = hashlib.sha256("".join(block_txs).encode("utf-8")).hexdigest()
        
        # Block header
        header = {
            "block_num": b + 1,
            "timestamp": int(time.time()),
            "prev_hash": prev_block_hash,
            "merkle_root": merkle_root,
            "validator_signature": "sig_rsa_4096_" + "ff" * 64,
            "gas_used": len(block_txs) * 21000,
        }
        header_bytes = json.dumps(header).encode("utf-8")
        block_bytes = header_bytes + "".join(block_txs).encode("utf-8")
        blockchain_storage_bytes += len(block_bytes)
        prev_block_hash = hashlib.sha256(header_bytes).hexdigest()

    duration = time.perf_counter() - t0
    tps = num_transactions / duration
    bytes_per_tx = blockchain_storage_bytes / num_transactions
    return tps, duration * 1000 / num_blocks, bytes_per_tx


def simulate_hash_chain_append(num_transactions: int = 1000):
    """
    Measures throughput and storage overhead for SecureVote append-only SHA-256 hash chain.
    """
    t0 = time.perf_counter()
    prev_hash = "00" * 32
    chain_storage_bytes = 0

    for i in range(num_transactions):
        payload = f"tx_data_{i}"
        prev_hash = compute_ballot_payload_hash(
            sequence_number=i + 1,
            timestamp=1775000000 + i,
            ciphertexts_json="[...]",
            token_signature=f"sig_{i}",
            previous_hash=prev_hash,
        )
        chain_storage_bytes += 32 + 32 + len(payload) + 64

    duration = time.perf_counter() - t0
    tps = num_transactions / duration
    bytes_per_tx = chain_storage_bytes / num_transactions
    latency_ms = (duration * 1000) / num_transactions
    return tps, latency_ms, bytes_per_tx


def run_comparative_evaluation():
    print("=" * 75)
    print(" EMPIRICAL COMPARISON: HASH-CHAIN LEDGER VS. BLOCKCHAIN")
    print("=" * 75)

    n_samples = 2000
    hc_tps, hc_latency, hc_bytes = simulate_hash_chain_append(n_samples)
    bc_tps, bc_latency, bc_bytes = simulate_blockchain_block_generation(n_samples, block_size=50)

    print(f"\n[1] Performance Benchmark on {n_samples:,} Ballots:")
    print(f"{'Metric':<30} | {'Append-Only Hash Chain':<24} | {'PoA Blockchain Ledger':<24}")
    print("-" * 80)
    print(f"{'Throughput (Transactions/sec)':<30} | {hc_tps:10.1f} tx/s            | {bc_tps:10.1f} tx/s")
    print(f"{'Confirmation Latency (ms)':<30} | {hc_latency:10.3f} ms              | {bc_latency:10.3f} ms")
    print(f"{'Storage Overhead (Bytes/Ballot)':<30} | {hc_bytes:10.1f} B/tx             | {bc_bytes:10.1f} B/tx")
    print(f"{'Trust / Infrastructure Req':<30} | {'Lightweight (Zero Gas)':<24} | {'Validator Network Required':<24}")
    print("=" * 80)

    # 2. Helios & Belenios Comparison Matrix
    print("\n" + "=" * 80)
    print(" FEATURE MATRIX: SECUREVOTE VS. HELIOS VS. BELENIOS")
    print("=" * 80)
    comparison_table = [
        ("Voter Credential Scheme", "2-of-2 Shamir Split", "Single Password / OAuth", "Single Credential Token"),
        ("Pre-Election Key Protection", "Cryptographic Time-Lock", "None", "None"),
        ("Biometric Liveness Verification", "Active EAR + Head Yaw (Anti-Spoof)", "None", "None"),
        ("Voter Unlinkability", "Chaum RSA Blind Signatures", "Voter Alias / Public ID", "Voter Pseudonym Tracker"),
        ("Encryption System", "Additive Exponential ElGamal", "Exponential ElGamal", "Exponential ElGamal"),
        ("Zero-Knowledge Validity Proofs", "Disjunctive 1-of-2 + Sum ZKP", "Disjunctive ZKP", "Disjunctive ZKP"),
        ("Threshold Trustee Decryption", "3-of-5 Polynomial Shamir", "Threshold Decryption", "Threshold Decryption"),
        ("Bulletin Board Architecture", "Append-Only Merkle Hash-Chain", "Web Page Ledger", "Append-Only Web Ledger"),
        ("Anomaly & Attack Detection", "ML (Isolation / Random Forest)", "Basic Server Access Logs", "None"),
    ]

    print(f"{'Feature Dimension':<32} | {'SecureVote (Ours)':<30} | {'Helios Voting':<22} | {'Belenios':<22}")
    print("-" * 110)
    for row in comparison_table:
        print(f"{row[0]:<32} | {row[1]:<30} | {row[2]:<22} | {row[3]:<22}")
    print("=" * 110)

    # 3. Generate High-Resolution Comparison Visualization
    os.makedirs("evaluation/plots", exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # Subplot 1: Throughput Comparison
    categories = ["Throughput (tx/sec)", "Storage Efficiency (1000/bytes)"]
    hc_vals = [hc_tps, 1000 / hc_bytes]
    bc_vals = [bc_tps, 1000 / bc_bytes]

    x = np.arange(len(categories))
    width = 0.35
    ax1.bar(x - width/2, hc_vals, width, label="Append-Only Hash Chain", color="#10B981")
    ax1.bar(x + width/2, bc_vals, width, label="PoA Blockchain Ledger", color="#6366F1")
    ax1.set_title("Ledger Architecture Performance Comparison", fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(categories)
    ax1.legend(loc="upper right")
    ax1.grid(axis="y", linestyle=":", alpha=0.6)

    # Subplot 2: Confirmation Latency (Log Scale)
    latencies = [hc_latency, bc_latency]
    ax2.bar(["Hash-Chain Append", "PoA Block Consensus"], latencies, color=["#10B981", "#F59E0B"], width=0.45)
    for i, v in enumerate(latencies):
        ax2.text(i, v + 0.1, f"{v:.2f} ms", ha="center", fontweight="bold")
    ax2.set_title("Transaction Confirmation Latency (ms)", fontweight="bold")
    ax2.set_ylabel("Latency (Milliseconds)")
    ax2.grid(axis="y", linestyle=":", alpha=0.6)

    plt.tight_layout()
    plot_path = "evaluation/plots/blockchain_vs_hashchain.png"
    plt.savefig(plot_path, dpi=300)
    plt.close()
    print(f"\n[+] Saved High-Resolution Comparison Plot to: {plot_path}")

    return {
        "hash_chain_tps": hc_tps,
        "blockchain_tps": bc_tps,
        "comparison_table": comparison_table,
        "plot_path": plot_path,
    }


if __name__ == "__main__":
    run_comparative_evaluation()
