# SecureVote: Project Handbook & Comprehensive Technical Reference

> **Document Purpose**: This handbook serves as the definitive reference manual for the SecureVote architecture, cryptographic protocols, biometric subsystems, machine learning anomaly detection engine, and empirical evaluation results. It is structured to provide all theoretical explanations, mathematical formulations, concrete parameters, system diagrams, and real experimental data necessary for writing a complete academic research paper.

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Background and Related Work](#2-background-and-related-work)
3. [System Architecture & Technology Stack](#3-system-architecture--technology-stack)
4. [Detailed Protocol Description](#4-detailed-protocol-description)
5. [Threat Model & Security Analysis](#5-threat-model--security-analysis)
6. [Biometric Face Verification & Machine Learning Subsystems](#6-biometric-face-verification--machine-learning-subsystems)
7. [Dataset Description & Usage](#7-dataset-description--usage)
8. [Experimental Methodology & Evaluation Results](#8-experimental-methodology--evaluation-results)
9. [Limitations & Honest Scope](#9-limitations--honest-scope)
10. [Future Work](#10-future-work)
11. [Academic Paper-Writing Guide](#11-academic-paper-writing-guide)
12. [Reproducibility & Execution Instructions](#12-reproducibility--execution-instructions)
13. [Glossary of Terms and Acronyms](#13-glossary-of-terms-and-acronyms)

---

## 1. Project Overview

### 1.1 Title & Executive Summary
**Project Title**: SecureVote: A Verifiable Online Voting System with Threshold Credentials, Face Liveness Verification and ML-based Anomaly Detection.

**Executive Summary**: SecureVote is an end-to-end verifiable electronic voting system designed to solve the trilemma of remote voting: authentic eligibility without central surveillance, total ballot secrecy with individual/universal verifiability, and robust resilience against automated attacks. SecureVote introduces a layered security architecture:
1. **Pre-Election Credential Protection**: Combines a $2$-of-$2$ Shamir Secret Sharing scheme with server-side time-lock release, ensuring voter credentials cannot be prematurely used or harvested prior to poll opening.
2. **Identity-Ballot Decoupling via Blind Signatures**: Uses Chaum RSA blind signatures to issue anonymous, one-time voting tokens upon successful biometric liveness verification, mathematically preventing the election authority from linking a voter's identity to their submitted ballot.
3. **Verifiable In-Browser Encryption**: Encrypts ballots using Additive Exponential ElGamal over a 2048-bit safe-prime group alongside Non-Interactive Zero-Knowledge Proofs (NIZKPs) generated via the Fiat-Shamir heuristic (Disjunctive Chaum-Pedersen $1$-of-$2$ validity proofs and Sum-to-One equality proofs).
4. **Append-Only Merkle Hash-Chain Bulletin Board**: Logs all cast ballots sequentially into a cryptographically auditable ledger, giving voters individual receipt codes to verify ballot inclusion without revealing candidate choices.
5. **Trustee Threshold Decryption**: Requires a $3$-of-$5$ polynomial threshold of independent trustees to compute partial decryptions with Discrete Logarithm Equality (DLEQ) proofs, eliminating any single point of trust.
6. **Telemetry-Driven ML Anomaly Detection**: Employs a dual-model machine learning pipeline (Supervised Random Forest and Unsupervised Isolation Forest) over 12 engineered temporal, behavioral, and biometric features to flag automated credential stuffing, botnets, and replay attacks in real time.

### 1.2 Problem Statement
Traditional remote internet voting architectures face severe security challenges:
- **Centralized Credential Compromise**: If an election server stores voter passwords or credentials, a compromised administrator or adversary can forge ballots prior to election day.
- **Voter Privacy vs. Eligibility Conflict**: Ensuring that only eligible voters vote typically requires authentication, but authentication records often allow the server to correlate voter identity with the timestamp and content of the cast ballot.
- **Ballot Stuffing & Malformed Ballots**: Without zero-knowledge proofs, malicious clients can inject encrypted values representing invalid vote weights (e.g., voting for multiple candidates or casting negative votes to subtract from a rival).
- **Single-Trustee Decryption Vulnerability**: If one entity holds the election private key, key compromise exposes all individual ballots and destroys ballot secrecy.
- **Automated Bot & Spoof Attacks**: Remote web interfaces are vulnerable to credential stuffing, presentation attacks (static photos/recordings), and automated replay flooding.

### 1.3 Key Contributions
SecureVote synthesizes modern threshold cryptography, computer vision, and machine learning into a unified open architecture:
- **Time-Locked Split Credentialing**: Voters never possess the full voting secret before election opening; the secret is split into Share A (held by the voter) and Share B (held in an encrypted server vault, locked until the election start timestamp).
- **Unlinkable Token Issuance with Biometric Gatekeeping**: Real-time facial liveness (Eye Aspect Ratio variance and head yaw trajectory) gates the issuance of an unlinked Chaum blind signature.
- **Client-Side Auditable Cryptography**: Full NIZKP generation in the browser ensures the server never receives unverified ciphertexts.
- **Lightweight High-Throughput Ledger**: Demonstrates that an append-only SHA-256 Merkle hash chain delivers over $700,000$ transactions/second without the latency, financial cost, or infrastructure overhead of public blockchains.
- **Dual-Model Attack Classification**: Combines supervised and unsupervised learning to achieve high detection rates on known attacks while maintaining sensitivity to zero-day anomalous sessions.

### 1.4 Walkthrough: College Student Council Election (500 Voters)
To understand how SecureVote functions in practice, consider a college election for Student Council President with 500 registered student voters:
1. **Registration (Phase 1)**: A student (e.g., Priya) enters her Student ID and institutional email, and captures a live facial photo via the browser. The server extracts a 128-dimensional embedding, encrypts it using AES-256-GCM into a biometric template vault, generates a 256-bit secret $S$, stores $H(S) = \text{SHA-256}(S)$, and splits $S$ into Share A and Share B. Priya downloads Share A as her private credential card. Share B is encrypted under a time-lock key that remains inaccessible until election opening.
2. **Election Day Authentication (Phase 2)**: At 09:00 AM (poll opening), the time-lock releases Share B. Priya logs in by providing Share A. The server retrieves Share B, computes $S' = \text{Share A} + \text{Share B}$, and verifies $H(S') == H(S)$. Priya is prompted to perform an active liveness challenge (e.g., blink twice and turn her head left). Upon passing, Priya's browser generates a random 256-bit token nonce $N_{\text{token}}$, blinds it with a random blinding factor $r$, and submits $m'$. The server signs $m'$ using RSA-2048 without seeing $N_{\text{token}}$, registers Priya as having collected her ballot, and returns the blind signature $s'$.
3. **Voting & In-Browser Encryption (Phase 3)**: Priya's browser unblinds $s'$ to obtain $(N_{\text{token}}, s)$. In the private voting booth, Priya selects Candidate 2 (out of 3 candidates: $[0, 1, 0]$). The browser encrypts each choice into an Exponential ElGamal ciphertext $(\alpha_i, \beta_i)$, generates three $1$-of-$2$ Disjunctive Chaum-Pedersen ZKPs proving each value is $0$ or $1$, and generates a Sum-to-One ZKP proving the sum of votes equals $1$. The browser submits the encrypted ballot payload along with $(N_{\text{token}}, s)$.
4. **Bulletin Board Logging**: The server verifies the RSA blind signature on $N_{\text{token}}$, verifies all four ZKPs, ensures $N_{\text{token}}$ is not spent, and appends the ballot to the public hash chain. Priya receives a tracking receipt code (e.g., `A93F-7C21-BB40-91E2`).
5. **Tallying & 3-of-5 Trustee Decryption (Phase 4)**: At 05:00 PM, the election closes. The server homomorphically multiplies the ciphertexts for each candidate across all 500 ballots, producing a single combined ciphertext $(A_k, B_k)$ for each candidate. Three of the five college trustees log into the portal and submit partial decryptions with DLEQ zero-knowledge proofs. The server interpolates the shares via Lagrange polynomials, decrypts the total tallies in under $0.3$ seconds, and publishes the final certified results.
6. **Independent Public Auditing**: Any student, auditor, or candidate downloads the public bulletin board ledger, verifies the hash chain integrity from genesis, verifies every ballot's ZKP, recomputes the homomorphic product, and checks the trustees' DLEQ proofs.

---

## 2. Background and Related Work

### 2.1 E-Voting Security Requirements
An academic electronic voting protocol must formally satisfy the following security properties:
- **Ballot Secrecy (Privacy)**: No entity (including administrators, election servers, and trustees) can determine which candidate a specific voter selected.
- **Eligibility**: Only authorized, registered voters are permitted to cast a vote.
- **One-Person-One-Vote (Double-Voting Prevention)**: Each eligible voter can cast at most one valid ballot that counts toward the final tally.
- **Individual Verifiability**: A voter can independently verify that their ballot was cast as intended and recorded on the official bulletin board without modification ("cast-as-intended" and "recorded-as-cast").
- **Universal Verifiability**: Any third-party auditor can independently verify that the published final tally is the exact mathematical sum of all validly recorded ballots ("tallied-as-recorded").
- **Coercion Resistance & Receipt-Freeness**: A voter cannot prove to a third party (coercer or vote buyer) how they voted, preventing vote-selling.

### 2.2 Core Cryptographic Foundations
- **Shamir's Secret Sharing ($k$-of-$n$)**: A threshold scheme where a secret $S \in \mathbb{Z}_q$ is encoded as the constant term of a degree $k-1$ random polynomial $f(x) = S + a_1 x + \dots + a_{k-1} x^{k-1} \pmod q$. Any $k$ distinct shares $(x_i, f(x_i))$ can reconstruct $S$ via Lagrange interpolation:
  $$S = \sum_{i=1}^k f(x_i) \prod_{j \neq i} \frac{-x_j}{x_i - x_j} \pmod q$$
  Any subset of $k-1$ or fewer shares reveals zero information about $S$.
- **Time-Lock Encryption**: A cryptographic mechanism that prevents decryption of a ciphertext before a predetermined time. In SecureVote, this is implemented as an epoch-gated key derivation function (KDF) coupled with verifiable delay primitives (Sloth VDF).
- **Chaum RSA Blind Signatures**: Allows a user to obtain a valid digital signature on a message $m$ from an authority without revealing $m$. The user blinds $m$ using a secret random factor $r \in \mathbb{Z}_N^*$: $m' = m \cdot r^e \pmod N$. The signer computes $s' = (m')^d \pmod N$. The user unblinds: $s = s' \cdot r^{-1} = m^d \pmod N$.
- **Additive Exponential ElGamal Encryption**: Given public key $h = g^x \pmod p$, a plaintext integer message $v \in \{0, 1\}$ is encrypted with randomness $r \in_R \mathbb{Z}_q$:
  $$E(v, r) = (\alpha, \beta) = (g^r \bmod p, \; h^r \cdot g^v \bmod p)$$
  *Homomorphic Addition Property*: Multiplying two ciphertexts yields the encryption of the sum of the plaintexts:
  $$E(v_1, r_1) \cdot E(v_2, r_2) = (g^{r_1+r_2} \bmod p, \; h^{r_1+r_2} \cdot g^{v_1+v_2} \bmod p) = E(v_1 + v_2, r_1 + r_2)$$
- **Zero-Knowledge Proofs (ZKPs)**:
  - *Schnorr Proof of Knowledge*: Proves knowledge of discrete log $x$ such that $y = g^x \pmod p$ without revealing $x$.
  - *Chaum-Pedersen Protocol*: Proves equality of discrete logarithms across different bases: $\log_{g_1}(y_1) = \log_{g_2}(y_2)$.
  - *Disjunctive Chaum-Pedersen Proof ($1$-of-$2$)*: Proves a ciphertext encrypts either $0$ or $1$ without revealing which.
  - *Fiat-Shamir Heuristic*: Transforms interactive sigma protocols into non-interactive proofs (NIZKPs) by replacing the verifier's random challenge with a cryptographic hash of the commitments and public parameters ($c = H(\dots) \bmod q$).

### 2.3 Comparative Analysis with Existing Systems
The following table compares SecureVote against leading verifiable voting architectures:

| Feature Dimension | SecureVote (This Work) | Helios Voting [VERIFY CITATION BEFORE USE] | Belenios [VERIFY CITATION BEFORE USE] |
| :--- | :--- | :--- | :--- |
| **Voter Credential Model** | $2$-of-$2$ Shamir Secret Sharing | Single Password / OAuth ID | Single Credential Code |
| **Pre-Election Key Protection** | Cryptographic Time-Lock ($K_{\text{timelock}}$) | None (Server holds credentials) | None |
| **Biometric Anti-Spoofing** | Active Liveness (EAR + Yaw Telemetry) | None | None |
| **Identity-Ballot Linkage** | Chaum RSA Blind Signatures (Unlinked) | Voter Alias / Public ID Mapping | Voter Pseudonym Tracking |
| **Encryption Primitive** | Exponential ElGamal (RFC 3526 Group 14) | Exponential ElGamal | Exponential ElGamal |
| **Zero-Knowledge Proofs** | Disjunctive $1$-of-$2$ + Sum-to-One NIZKP | Disjunctive $1$-of-$2$ NIZKP | Disjunctive $1$-of-$2$ NIZKP |
| **Trustee Decryption** | $3$-of-$5$ Polynomial Shamir + DLEQ | $k$-of-$n$ Threshold ElGamal | $k$-of-$n$ Threshold ElGamal |
| **Public Bulletin Board** | Append-Only SHA-256 Merkle Hash Chain | HTML Table / Web Ledger | Append-Only Web Table |
| **Anomaly & Attack Detection**| Dual ML (Random Forest + Isolation Forest) | Basic Web Server Logs | None |

---

## 3. System Architecture & Technology Stack

### 3.1 Technology Stack & Versions
The system is implemented as a modular client-server architecture:

```
+-------------------------------------------------------------------------------+
| SecureVote Tech Stack                                                         |
+-----------------------------------+-------------------------------------------+
| Layer                             | Technologies & Exact Installed Versions   |
+-----------------------------------+-------------------------------------------+
| Operating System & Runtime        | macOS / Linux POSIX, Python 3.14.2        |
| Backend Web Framework             | FastAPI 0.142.2, Starlette 1.7.0          |
| ASGI & HTTP Server                | Uvicorn 0.54.0, AnyIO 4.15.1              |
| Database & ORM                    | SQLite 3, SQLAlchemy 2.1.2, aiosqlite     |
| Numerical & Cryptographic Core    | NumPy 2.5.3, SciPy 1.18.1, RFC 3526 MODP  |
| Machine Learning Subsystem        | scikit-learn 1.9.1, pandas 3.0.6          |
| Computer Vision & Biometrics      | OpenCV Headless 5.0.0.93, Pillow 12.3.0   |
| Evaluation & Visualization        | Matplotlib 3.11.2, Seaborn 0.13.2         |
| Frontend UI Framework             | React 18.3.1, TypeScript 5.4.5, Vite 5.3.1|
| Styling & Icons                   | Tailwind CSS 3.4.4, Lucide-React 0.395.0  |
+-----------------------------------+-------------------------------------------+
```

### 3.2 Repository Directory Structure
```
CipherVote/
├── backend/
│   ├── app/
│   │   ├── config.py                 # System configuration and global settings
│   │   ├── main.py                   # FastAPI application initialization
│   │   ├── core/
│   │   │   ├── crypto/               # ElGamal, Shamir, Blind Signatures, ZKP, Time-Lock
│   │   │   ├── biometrics/           # Face embedding extraction, AES vault, Liveness
│   │   │   ├── bulletin_board/       # Hash-chain and Merkle tree ledger
│   │   │   └── ml/                   # Feature extraction, log simulator, RF/IF models
│   │   ├── models/                   # SQLAlchemy database entities (Voter, Ballot, etc.)
│   │   ├── routers/                  # API endpoints (auth, voters, ballots, tally, bb)
│   │   └── schemas/                  # Pydantic request/response data models
│   └── tests/                        # 28 Pytest test suites (100% passing)
├── frontend/
│   ├── src/
│   │   ├── App.tsx                   # Main SPA container and navigation
│   │   ├── components/               # Navbar, WebcamLiveness
│   │   ├── pages/                    # VoterRegistration, VoterElection, Admin, Trustee, Auditor
│   │   └── crypto/                   # Client-side constants, ElGamal, and ZKP generators
├── data/
│   └── lfw/                          # LFW deep-funneled dataset and evaluation splits
├── evaluation/                       # Evaluation benchmarks, attack suites, report scripts
│   └── plots/                        # Generated high-resolution evaluation charts (.png)
└── docs/                             # Academic Handbook, diagrams (.mmd), raw results (.csv)
    ├── figures/                      # Mermaid source files (.mmd)
    └── results/                      # Evaluation output CSVs and PNGs
```

### 3.3 Database Schema
The database (`securevote.db`) uses SQLite with SQLAlchemy asynchronous ORM across five primary tables:

1. **`voters` Table**:
   - `voter_id` (VARCHAR, Primary Key): Unique voter identifier (e.g., `CS21B045`).
   - `full_name` (VARCHAR): Legal full name.
   - `email` (VARCHAR, Unique): Institutional email.
   - `commitment` (VARCHAR): SHA-256 hash commitment $H(S)$ of the voter's combined secret $S$.
   - `encrypted_share_b` (TEXT): Server-side Share B encrypted under $K_{\text{timelock}}$.
   - `encrypted_face_template` (TEXT): AES-256-GCM encrypted 128-dimensional face embedding.
   - `status` (VARCHAR): Current lifecycle state (`REGISTERED`, `TOKEN_ISSUED`, `VOTED`).
   - `registered_at` (TIMESTAMP): UTC registration timestamp.

2. **`ballots` Table (Public Bulletin Board Ledger)**:
   - `sequence_number` (INTEGER, Primary Key): Monotonically increasing index ($1, 2, \dots, N$).
   - `election_id` (VARCHAR): Target election identifier.
   - `ciphertexts_json` (TEXT): Array of candidate ElGamal ciphertexts $[(\alpha_0, \beta_0), \dots, (\alpha_{m-1}, \beta_{m-1})]$.
   - `zkp_proofs_json` (TEXT): Serialized Disjunctive $1$-of-$2$ proofs and Sum-to-One proof.
   - `token_signature` (VARCHAR, Unique): RSA blind signature proving ballot authorization.
   - `previous_hash` (VARCHAR): SHA-256 hash of the preceding ledger entry $H_{i-1}$.
   - `current_hash` (VARCHAR): SHA-256 hash of this entry $H_i$.
   - `receipt_code` (VARCHAR): First 16 characters of $H_i$ formatted as `XXXX-XXXX-XXXX-XXXX`.
   - `timestamp` (INTEGER): Unix epoch seconds at ingestion.

3. **`spent_tokens` Table**:
   - `token_nonce` (VARCHAR, Primary Key): 256-bit unblinded nonce $N_{\text{token}}$ presented at ballot casting.
   - `spent_at` (TIMESTAMP): Ingestion timestamp preventing double-submission.

4. **`elections` Table**:
   - `election_id` (VARCHAR, Primary Key): Election identifier.
   - `title` (VARCHAR): Election display name.
   - `status` (VARCHAR): Lifecycle state (`SETUP`, `REGISTRATION`, `OPEN`, `TALLYING`, `RESULTS`).
   - `public_key_h` (TEXT): Joint ElGamal public key $h = g^x \pmod p$.
   - `blind_rsa_n` (TEXT): Public modulus $N_{\text{rsa}}$ for Chaum blind signatures.
   - `blind_rsa_e` (INTEGER): Public exponent $e = 65537$.
   - `open_time` (INTEGER): Unix timestamp for voting commencement.
   - `close_time` (INTEGER): Unix timestamp for poll closure.

5. **`trustee_shares` Table**:
   - `trustee_id` (INTEGER): Trustee index ($1 \le i \le 5$).
   - `public_verification_key` (TEXT): Trustee verification key $h_i = g^{s_i} \pmod p$.
   - `partial_decryption` (TEXT): Submitted partial decryption $D_i = A^{s_i} \pmod p$.
   - `dleq_proof` (TEXT): Serialized Chaum-Pedersen DLEQ proof of correct partial decryption.

### 3.4 API Endpoints Specification

```
+-------------------------------------------------------------------------------------------------+
| SecureVote API Endpoints                                                                        |
+--------------------------+--------+-------------------------------------------------------------+
| Path                     | Method | Functional Description                                      |
+--------------------------+--------+-------------------------------------------------------------+
| /api/voters/process-face | POST   | Validates single face photo and extracts 128-d embedding    |
| /api/voters/register     | POST   | Registers voter, creates Shamir split, encrypts vault       |
| /api/voters/share_b/{id} | GET    | Releases Share B if election phase == OPEN                  |
| /api/auth/challenge      | POST   | Generates random challenge (Blink / Head Turn sequence)     |
| /api/auth/blind-token    | POST   | Validates Share A+B + liveness, issues RSA blind signature  |
| /api/ballots/cast        | POST   | Verifies blind signature + ZKPs, appends to hash chain      |
| /api/bulletin-board      | GET    | Returns all ledger entries and cryptographic receipts       |
| /api/bulletin-board/verify| GET   | Performs full audit check of hash chain integrity           |
| /api/election/setup      | POST   | Initializes election parameters and trustee key generation  |
| /api/election/status     | GET    | Retrieves current election state and public keys            |
| /api/tally/compute       | POST   | Homomorphically aggregates ciphertexts across all ballots   |
| /api/tally/trustee-share | POST   | Submits 3-of-5 trustee partial decryption with DLEQ proof   |
| /api/tally/finalize      | POST   | Reconstructs discrete log tallies and publishes results     |
| /api/ml/predict-session  | POST   | Evaluates session telemetry against RF/IF anomaly detectors |
+--------------------------+--------+-------------------------------------------------------------+
```

### 3.5 Election State Transitions
The election proceeds through five sequential states managed by administrative time-locks:
```
[ SETUP ] ──► [ REGISTRATION ] ──► [ OPEN ] ──► [ TALLYING ] ──► [ RESULTS ]
```
- **`SETUP`**: System generates election keypair $(h, x)$, initializes 5 trustee shares, and generates RSA-2048 blind signing keys.
- **`REGISTRATION`**: Voters submit IDs and photos, receive Share A, and Share B is locked.
- **`OPEN`**: Polls open. Wall-clock reaches $T_{\text{open}}$. Time-lock releases Share B. Blind tokens and encrypted ballots are accepted.
- **`TALLYING`**: Polls close at $T_{\text{close}}$. Ballot ingestion terminates. Homomorphic sum is computed; trustees submit partial decryptions.
- **`RESULTS`**: Final tallies, DLEQ proofs, and audit logs are published publicly for universal verification.

---

## 4. Detailed Protocol Description

```
+-------------------------------------------------------------------------------+
| Summary of Cryptographic Parameters                                           |
+-------------------------------+-----------------------------------------------+
| Parameter                     | Concrete Value / Specification                |
+-------------------------------+-----------------------------------------------+
| Asymmetric Group Standard     | RFC 3526 2048-bit MODP Group 14               |
| Safe Prime $p$                | $2^{2048} - 2^{1984} - 1 + 2^{64} \cdot \dots$ |
| Prime Subgroup Order $q$      | $(p - 1) / 2$ (1024-bit safe prime order)     |
| Group Generator $g$           | $g = 2$                                       |
| Secret Sharing Finite Field   | $\mathbb{Z}_q$ (Integers modulo $q$)          |
| Symmetric Encryption Standard | AES-256-GCM (256-bit key, 96-bit random IV)   |
| Blind Signature Standard      | Chaum RSA-2048 ($e = 65537$, $d = \dots$)     |
| Cryptographic Hash Function   | SHA-256 (Big-endian domain separation)        |
| Non-Interactive ZKP Transform | Fiat-Shamir Heuristic over SHA-256            |
+-------------------------------+-----------------------------------------------+
```

### 4.1 Registration & Encrypted Biometric Template
- **Purpose**: Enroll the eligible voter, extract a compact biometric embedding, securely vault the embedding under AES-256-GCM, and generate the voter's split credentials.
- **Actors**: Voter (Client Browser), SecureVote Registration Authority.
- **Mathematical Flow**:
  1. Client captures a facial snapshot and posts `image_base64` to `/api/voters/process-face`.
  2. Server uses OpenCV Haar Cascades to verify exactly one face is present, normalizes the crop to $160 \times 160$, and extracts a $128$-dimensional unit vector:
     $$\mathbf{e} = [e_1, e_2, \dots, e_{128}], \quad \|\mathbf{e}\|_2 = 1.0$$
  3. Server generates a random 256-bit voter credential secret $S \in_R \mathbb{Z}_q^*$.
  4. Server computes the public commitment:
     $$C = \text{SHA-256}(S)$$
  5. Server encrypts embedding $\mathbf{e}$ under master key $K_{\text{bio}}$ using AES-256-GCM:
     $$C_{\text{bio}} = \text{AES-256-GCM-Encrypt}(K_{\text{bio}}, \; \mathbf{e})$$
  6. Server discards the raw image immediately (zero raw biometrics stored).

### 4.2 Credential Generation, 2-of-2 Shamir Split, Email Delivery & Time-Lock
- **Purpose**: Prevent premature voting, voter impersonation, or credential harvesting prior to election opening, while ensuring cryptographic secrets are never displayed on the website or stored in database logs.
- **Mathematical Flow & Security Architecture**:
  1. Server constructs a random linear polynomial $f(x) \in \mathbb{Z}_q[x]$ such that $f(0) = S$:
     $$f(x) = S + a_1 x \pmod q, \quad a_1 \in_R \mathbb{Z}_q^*$$
  2. Evaluates two distinct evaluation points:
     $$\text{Share A} = (1, f(1)) = (1, (S + a_1) \bmod q)$$
     $$\text{Share B} = (2, f(2)) = (2, (S + 2a_1) \bmod q)$$
  3. **Strict Email-Only Delivery of Share A**:
     - Secret Share A is delivered strictly to the voter's verified email address via SMTP with TLS encryption as a secure `.json` credential attachment (`credential-{voter_id}.json`) and plain text fallback.
     - **Zero Secret Exposure**: Share A is **never** printed on the website, never returned in HTTP registration responses, never stored in voter database rows (`share_a_preview` removed), and never recorded in plaintext email outbox logs (redacted as `[REDACTED_SECRET_SHARE_A]`). Once sent, Share A is deleted from server volatile memory.
  4. **Rate-Limited Credential Reissue Flow**:
     - If a voter does not receive their credential email (due to network or spam filtering), the system provides an authenticated reissue endpoint (`POST /api/voter/reissue-credential`).
     - Reissuance requires voter password authentication and verifies that no ballot token has been issued.
     - Reissuing generates a completely **new** polynomial and Shamir shares, overwriting Share B and commitment $C$, thereby permanently invalidating any previously issued Share A.
  5. Share B is encrypted under an epoch-derived time-lock key $K_{\text{timelock}}$:
     $$C_{\text{ShareB}} = \text{AES-256-GCM-Encrypt}(K_{\text{timelock}}, \; \text{Share B})$$
  6. **Security Assumption**: An adversary compromising the server database prior to $T_{\text{open}}$ obtains only Share B (in encrypted form) and commitment $C$. Because Share A is strictly delivered to the voter's private email inbox, the secret $S$ maintains information-theoretic secrecy under the $2$-of-$2$ Shamir scheme.

### 4.3 Election-Day Authentication & Secret Reconstruction
- **Purpose**: Authenticate the eligible voter on election day without retaining an identification trail.
- **Mathematical Flow**:
  1. At $T \ge T_{\text{open}}$, the server unlocks $K_{\text{timelock}}$ and allows retrieval of Share B.
  2. Voter submits $\text{Share A} = (1, y_1)$ and $\text{Share B} = (2, y_2)$.
  3. Server reconstructs the candidate secret $S'$ via Lagrange basis polynomials:
     $$\lambda_1 = \frac{0 - 2}{1 - 2} = 2 \pmod q, \quad \lambda_2 = \frac{0 - 1}{2 - 1} = -1 \pmod q$$
     $$S' = (2 y_1 - y_2) \pmod q$$
  4. Server evaluates the commitment check:
     $$\text{SHA-256}(S') \stackrel{?}{=} C$$
  5. If valid, the voter has proven ownership of an authentic registration credential.

### 4.4 Biometric Facial Liveness & Challenge-Response
- **Purpose**: Ensure physical presence and prevent replay of static photos, deepfakes, or stolen credentials.
- **Mathematical Flow**:
  1. Server issues a randomized challenge sequence: $\mathcal{C} = [\text{BLINK}, \text{TURN\_LEFT}]$.
  2. Client tracks real-time Eye Aspect Ratio (EAR) across consecutive video frames:
     $$\text{EAR} = \frac{\|p_2 - p_6\| + \|p_3 - p_5\|}{2 \|p_1 - p_4\|}$$
     *Blink condition*: $\text{EAR}_{\text{min}} < 0.22$ with dynamic recovery.
  3. Client tracks facial landmark symmetry to determine head yaw angle $\theta_{\text{yaw}}$:
     *Turn-left condition*: $\theta_{\text{yaw}} \le -8.0^\circ$.
  4. Telemetry is verified server-side. If the probe embedding $\mathbf{e}_{\text{probe}}$ matches the vaulted embedding within Euclidean distance threshold $\theta^* = 0.7274$, liveness is certified.

### 4.5 Chaum Blind-Signed Voting Token Issuance
- **Purpose**: Provide the voter with an unforgeable, unlinked voting token that prevents double-voting without binding the voter's identity to the ballot.
- **Mathematical Flow**:
  1. Voter's browser generates a random 256-bit token nonce $N_{\text{token}} \in_R \{0, 1\}^{256}$.
  2. Browser generates a blinding factor $r \in_R \mathbb{Z}_N^*$ and computes blinded message:
     $$m = \text{int}(\text{SHA-256}(N_{\text{token}})), \quad m' = (m \cdot r^e) \bmod N_{\text{rsa}}$$
  3. Server validates voter credentials and liveness, verifies the voter has not previously received a token, marks the voter as `TOKEN_ISSUED`, and computes:
     $$s' = (m')^d \bmod N_{\text{rsa}}$$
  4. Browser unblinds the signature:
     $$s = (s' \cdot r^{-1}) \bmod N_{\text{rsa}} = (m^d) \bmod N_{\text{rsa}}$$
  5. The resulting pair $(N_{\text{token}}, s)$ satisfies $s^e \equiv \text{SHA-256}(N_{\text{token}}) \pmod N_{\text{rsa}}$. The server has never seen $N_{\text{token}}$ or $s$.

### 4.6 In-Browser Exponential ElGamal & Zero-Knowledge Validity Proofs
- **Purpose**: Encrypt candidate selections and mathematically prove ballot validity without decrypting.
- **Mathematical Flow**:
  For an election with $m$ candidates, the vote is a one-hot vector $\mathbf{v} = [v_0, v_1, \dots, v_{m-1}]$ where $v_k = 1$ and $v_{j \neq k} = 0$, satisfying $\sum_{i=0}^{m-1} v_i = 1$.
  1. **Encryption**: For each candidate $i \in \{0, \dots, m-1\}$, the browser picks random $r_i \in_R \mathbb{Z}_q$ and computes:
     $$\alpha_i = g^{r_i} \bmod p, \quad \beta_i = (h^{r_i} \cdot g^{v_i}) \bmod p$$
  2. **Disjunctive Chaum-Pedersen $1$-of-$2$ Proof**: For each ciphertext $(\alpha_i, \beta_i)$, the browser generates a NIZKP proving $v_i \in \{0, 1\}$.
     - If $v_i = 0$: The real proof is constructed for $0$, and a simulated proof is forged for $1$.
     - If $v_i = 1$: A simulated proof is forged for $0$, and the real proof is constructed for $1$.
     - Challenge commitments: $a_0 = g^{w_0} \bmod p$, $b_0 = h^{w_0} \bmod p$, $a_1 = g^{w_1} \bmod p$, $b_1 = h^{w_1} \cdot (g)^{-c_1} \bmod p$.
     - Fiat-Shamir challenge: $c = \text{SHA-256}(h, \alpha_i, \beta_i, a_0, b_0, a_1, b_1) \bmod q$.
     - Constraint: $c_0 + c_1 \equiv c \pmod q$.
  3. **Sum-to-One Equality Proof**: To prove $\sum v_i = 1$, compute the aggregated ciphertext:
     $$A_{\text{sum}} = \prod_{i=0}^{m-1} \alpha_i = g^{\sum r_i} \bmod p, \quad B_{\text{sum}} = \prod_{i=0}^{m-1} \beta_i = h^{\sum r_i} \cdot g^{\sum v_i} \bmod p$$
     Because $\sum v_i = 1$, $B_{\text{sum}} \cdot g^{-1} = h^{\sum r_i} \bmod p$.
     The client generates a standard Chaum-Pedersen DLEQ proof that $\log_g(A_{\text{sum}}) = \log_h(B_{\text{sum}} \cdot g^{-1}) = \sum r_i \pmod q$.

### 4.7 Receipt Code & Public Append-Only Bulletin Board
- **Purpose**: Record cast ballots sequentially into an immutable, universally auditable hash chain.
- **Mathematical Flow**:
  1. Each ingested ballot $i$ has payload $P_i = (\text{ciphertexts}, \text{zkps}, \text{token\_signature}, T_i)$.
  2. The entry hash $H_i$ is computed recursively:
     $$H_0 = \text{0x0000000000000000000000000000000000000000000000000000000000000000}$$
     $$H_i = \text{SHA-256}(i \;\|\; T_i \;\|\; \text{JSON}(P_i) \;\|\; H_{i-1})$$
  3. The voter receives the tracking receipt:
     $$\text{Receipt Code} = \text{FormatHex}(H_i[0:16]) \implies \text{e.g., A93F-7C21-BB40-91E2}$$
  4. The voter can query the bulletin board to confirm $H_i$ is present at sequence index $i$.

### 4.8 Homomorphic Tally & 3-of-5 Trustee Threshold Decryption
- **Purpose**: Tally all votes without decrypting any individual ballot.
- **Mathematical Flow**:
  1. **Homomorphic Aggregation**: For each candidate $k \in \{0, \dots, m-1\}$, the server multiplies ciphertexts across all $N$ ballots:
     $$A_k = \prod_{j=1}^N \alpha_{j, k} = g^{\sum_{j=1}^N r_{j, k}} \bmod p$$
     $$B_k = \prod_{j=1}^N \beta_{j, k} = h^{\sum_{j=1}^N r_{j, k}} \cdot g^{\sum_{j=1}^N v_{j, k}} \bmod p = h^{R_k} \cdot g^{T_k} \bmod p$$
     where $T_k = \sum_{j=1}^N v_{j, k}$ is the final total vote count for candidate $k$.
  2. **Trustee Partial Decryptions**: Each active trustee $i \in \{1, 2, 3\}$ holds private share $s_i = f_{\text{trustee}}(i)$ corresponding to public key $h_i = g^{s_i} \pmod p$.
     Trustee $i$ computes partial decryption:
     $$D_{i, k} = (A_k)^{s_i} \bmod p$$
     Trustee $i$ supplies a Chaum-Pedersen DLEQ proof certifying $\log_g(h_i) = \log_{A_k}(D_{i, k})$.
  3. **Threshold Reconstruction**: Using Lagrange coefficients $\lambda_i = \prod_{j \neq i} \frac{-j}{i - j} \pmod q$, the decryptor computes:
     $$D_k = \prod_{i=1}^3 (D_{i, k})^{\lambda_i} = (A_k)^{\sum \lambda_i s_i} = (A_k)^x = h^{R_k} \bmod p$$
  4. **Discrete Logarithm Recovery**: The decryptor isolates the plaintext group element:
     $$M_k = B_k \cdot (D_k)^{-1} \bmod p = (h^{R_k} \cdot g^{T_k}) \cdot (h^{R_k})^{-1} = g^{T_k} \bmod p$$
  5. Because $T_k \le N \le 10,000$, $T_k$ is solved via baby-step giant-step or precomputed table lookup in under $1\text{ ms}$.

### 4.9 Blockchain-Style Ledger Comparison Variant
For experimental comparison against the SHA-256 hash chain, a Proof-of-Authority (PoA) block ledger variant was implemented (`evaluation/eval_comparison.py`). It packages transactions into blocks of 50, computes Merkle roots, generates simulated 4096-bit validator signatures, and chains block headers.

---

## 5. Threat Model and Security Analysis

### 5.1 Adversary Models & Trust Assumptions
- **Adversary Model $\mathcal{A}_{\text{net}}$ (Network Adversary)**: Can eavesdrop, delay, or inject network packets between clients and the server.
- **Adversary Model $\mathcal{A}_{\text{srv}}$ (Malicious Server / Insider)**: Controls the election server and database, attempts to forge ballots, deanonymize voters, or manipulate tallies.
- **Adversary Model $\mathcal{A}_{\text{trustee}}$ (Corrupted Trustees)**: Controls up to $k-1 = 2$ trustees in the $3$-of-$5$ scheme.
- **Adversary Model $\mathcal{A}_{\text{voter}}$ (Malicious Voter)**: Attempts double-voting, ballot stuffing (voting multiple times on one ballot), or replaying stolen credentials.

### 5.2 Security Properties & Formal Arguments
1. **Ballot Secrecy (Zero-Knowledge Privacy)**:
   - *Claim*: $\mathcal{A}_{\text{srv}}$ cannot determine candidate choice $v$ from ciphertext $(\alpha, \beta)$.
   - *Proof Sketch*: Exponential ElGamal is IND-CPA secure under the Decisional Diffie-Hellman (DDH) assumption in RFC 3526 Group 14. Decrypting requires solving the discrete log of $h^r$, which requires $x$. Because the election key $x$ is shared via a $3$-of-$5$ polynomial Shamir scheme, any coalition of $\le 2$ trustees obtains zero information about $x$.
2. **Voter Anonymity & Unlinkability**:
   - *Claim*: $\mathcal{A}_{\text{srv}}$ cannot link voter identity $V_{\text{id}}$ to ballot payload $(\mathbf{\alpha}, \mathbf{\beta}, N_{\text{token}}, s)$.
   - *Proof Sketch*: Blind signatures provide unconditional blinding. The blinding factor $r \in_R \mathbb{Z}_N^*$ is chosen uniformly at random by the client. The distribution of blinded messages $m' = m \cdot r^e \pmod N$ is statistically independent of $m$. Thus, no computational adversary can link $m'$ to $(N_{\text{token}}, s)$.
3. **Double-Voting Prevention**:
   - *Claim*: No voter can cast more than one valid ballot.
   - *Proof Sketch*: A ballot is accepted if and only if $s^e \equiv \text{SHA-256}(N_{\text{token}}) \pmod N$ and $N_{\text{token}}$ is not in `spent_tokens`. To double-vote, an adversary must either obtain two distinct blind signatures (blocked because the server marks $V_{\text{id}}$ as `TOKEN_ISSUED` upon first issuance) or forge an RSA signature (equivalent to factoring $N_{\text{rsa}}$).
4. **Ballot Validity & Integrity (No Ballot Stuffing)**:
   - *Claim*: Malicious voters cannot submit ciphertexts where $v_i \notin \{0, 1\}$ or $\sum v_i \neq 1$.
   - *Proof Sketch*: Under the random oracle model for Fiat-Shamir hash $H$, the Disjunctive Chaum-Pedersen and Sum-to-One proofs are sound. An invalid vote vector yields a falsified challenge relation with probability $\le 1/q \approx 2^{-1024}$.

### 5.3 Explicit Limitations & Attack Surface
- **Coercion Resistance & Vote-Selling**: Because voters generate their own randomness $r_i$ in the browser, a voter could voluntarily reveal $r_i$ to a third party to prove how they voted. SecureVote is *receipt-free with respect to the public bulletin board* (receipt code reveals nothing), but does not prevent client-side screen capture or shoulder surfing.
- **Client-Side Platform Integrity**: If a voter's device is compromised by malware or a malicious browser extension, the malware can intercept credentials or alter the ballot before encryption.
- **Biometric Threshold Trade-offs**: Inherent in any statistical face embedding matcher is a non-zero FAR/FRR trade-off under poor illumination or camera noise.

---

## 6. Biometric Face Verification & Machine Learning Subsystems

### 6.1 Biometric Face Embedding Engine
- **Architecture**: Compact deep feature extractor producing a normalized 128-dimensional continuous vector $\mathbf{e} \in \mathbb{R}^{128}$ with $\|\mathbf{e}\|_2 = 1.0$.
- **Distance Metric**: Standard Euclidean distance:
  $$d(\mathbf{e}_1, \mathbf{e}_2) = \sqrt{\sum_{i=1}^{128} (e_{1, i} - e_{2, i})^2}$$
  Because vectors are $L_2$-normalized, Euclidean distance relates directly to cosine similarity: $d^2 = 2 - 2 \cos(\mathbf{e}_1, \mathbf{e}_2)$.
- **Verification Decision Rule**:
  $$\text{Decision}(d) = \begin{cases} \text{GENUINE (Accept)}, & \text{if } d \le \theta^* \\ \text{IMPOSTOR (Reject)}, & \text{if } d > \theta^* \end{cases}$$

### 6.2 Active Liveness Verification Design
The liveness subsystem counters presentation attacks (printed photos, screen replays) via dynamic visual challenge-response:
- **Challenge Types**:
  - `BLINK`: Requires Eye Aspect Ratio drop below $0.22$ followed by return to baseline ($>0.30$).
  - `TURN_LEFT`: Requires facial landmark horizontal displacement yielding yaw angle $\theta_{\text{yaw}} \le -8.0^\circ$.
  - `TURN_RIGHT`: Requires yaw angle $\theta_{\text{yaw}} \ge +8.0^\circ$.
- **Temporal Anti-Spoof Metric**: Static photos exhibit near-zero temporal variance in landmark coordinates ($\sigma^2_{\text{EAR}} < 10^{-4}$), causing immediate rejection.

### 6.3 Machine Learning Anomaly Detection Engine
To counter automated botnets, credential stuffing, and high-frequency replays, SecureVote deploys a dual-model ML engine analyzing session metadata across 12 engineered features:

```
+-------------------------------------------------------------------------------+
| Engineered ML Features (12 Dimensions)                                        |
+----+----------------------------+---------------------------------------------+
| #  | Feature Name               | Description & Measurement Unit              |
+----+----------------------------+---------------------------------------------+
| 1  | request_rate_per_min       | Client HTTP request frequency (req / min)   |
| 2  | inter_request_std_dev      | Jitter / variance of request intervals (ms) |
| 3  | session_duration_sec       | Total session active duration (seconds)     |
| 4  | user_agent_entropy         | Shannon entropy of HTTP User-Agent string   |
| 5  | session_retry_count        | Number of failed attempts within session    |
| 6  | auth_failure_flag          | Binary indicator of preceding auth error    |
| 7  | ear_variance               | Variance of Eye Aspect Ratio sequence       |
| 8  | ear_min_value              | Minimum EAR reached during blink challenge  |
| 9  | yaw_range_degrees          | Total angular deflection of head turn (deg) |
| 10 | yaw_velocity               | Angular speed of head movement (deg / sec)  |
| 11 | challenge_duration_ms      | Total time taken to respond to challenge    |
| 12 | frame_count                | Total video frames processed during test    |
+----+----------------------------+---------------------------------------------+
```

- **Dual-Model Architecture**:
  1. **Supervised Random Forest**: 100 decision trees, maximum depth 12, Gini impurity criterion. Trained to detect known attack signatures.
  2. **Unsupervised Isolation Forest**: 100 isolation trees, contamination rate $0.15$, subsample size 256. Flags zero-day anomalies based on path length deviations without requiring prior attack labels.

---

## 7. Dataset Description & Usage

### 7.1 LFW Deep-Funneled Dataset Structure
Biometric evaluation is conducted on the standard **Labeled Faces in the Wild (LFW)** dataset (Deep-Funneled pre-aligned alignment):
- **Source**: Kaggle / University of Massachusetts Amherst LFW Deep-Funneled benchmark.
- **Total Images**: 13,233 images of 5,749 individuals.
- **Resolution**: $250 \times 250$ RGB JPEG images.
- **Directory Structure**: `data/lfw/lfw-deepfunneled/lfw-deepfunneled/{Person_Name}/{Person_Name}_{NNNN}.jpg`.

### 7.2 Strict Train / Test Experimental Separation
To prevent data snooping and optimistic threshold bias, the evaluation follows the official LFW development split protocol:
- **DevTrain Partition (Threshold Tuning / Calibration Only)**:
  - Genuine Pairs: 1,100 pairs from `matchpairsDevTrain.csv`.
  - Impostor Pairs: 1,100 pairs from `mismatchpairsDevTrain.csv`.
  - Total Calibration Pairs: 2,200 pairs.
  - *Rule*: The optimal threshold $\theta^*$ is calibrated strictly on this split by finding the Equal Error Rate operating point.
- **DevTest Partition (Independent Evaluation Only)**:
  - Genuine Pairs: 500 pairs from `matchpairsDevTest.csv`.
  - Impostor Pairs: 500 pairs from `mismatchpairsDevTest.csv`.
  - Total Independent Test Pairs: 1,000 pairs.
  - *Rule*: Evaluated strictly using $\theta^*$ obtained from DevTrain. Zero threshold adjustment is performed on DevTest.

### 7.3 Synthetic Data Usage
- **Scale Benchmarks ($1\text{k}, 5\text{k}, 10\text{k}$ Voters)**: Use cryptographically valid synthetic Exponential ElGamal ciphertexts and NIZKPs generated via the official group parameters to benchmark server ingestion, modular multiplication, and discrete log solving.
- **ML Anomaly Simulation (10,000 Session Logs)**: Generated using `app/core/ml/log_simulator.py` (80% genuine voter behavioral distributions, 20% multi-vector attack distributions including credential stuffing, robotic replay, and static photo spoofing).

---

## 8. Experimental Methodology & Evaluation Results

> [!IMPORTANT]
> All quantitative metrics in this section are reproduced from real execution of the evaluation suite on Apple Silicon (macOS, Python 3.14.2, NumPy 2.5.3, scikit-learn 1.9.1). Raw CSVs are available in `docs/results/`.

### 8.1 Cryptographic Scale Benchmarks (1,000 to 10,000 Voters)
- **Goal**: Measure client-side encryption latency, bulletin board ingestion throughput, homomorphic aggregation time, and $3$-of-$5$ threshold decryption speed.
- **Execution Command**: `./venv/bin/python evaluation/eval_scale_benchmark.py`
- **Output Artifacts**: `docs/results/scale_benchmarks.csv`, `docs/results/scale_benchmark.png`
- **Measured Results Table**:

| Registered Voters ($N$) | Client Encrypt + ZKP Latency | Bulletin Board Ingestion Throughput | Homomorphic Aggregation Time | 3-of-5 Threshold Decryption | Total Election Tally Duration |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1,000 Voters** | $424.72\text{ ms}$ | $1,000,000.0\text{ tx/s}$ | $0.0512\text{ s}$ | $0.2152\text{ s}$ | **$0.2664\text{ s}$** |
| **5,000 Voters** | $425.04\text{ ms}$ | $4,255,167.2\text{ tx/s}$ | $0.2679\text{ s}$ | $0.2107\text{ s}$ | **$0.4786\text{ s}$** |
| **10,000 Voters** | $426.29\text{ ms}$ | $4,257,886.5\text{ tx/s}$ | $0.5143\text{ s}$ | $0.2109\text{ s}$ | **$0.7252\text{ s}$** |

- **Interpretation**: Client-side encryption and 4 NIZKP generations require $\approx 425\text{ ms}$, ensuring responsive browser interactions. Server-side homomorphic aggregation scales linearly with voter count ($O(N)$ modular multiplications) but completes in just $0.51\text{ s}$ for 10,000 voters. Threshold decryption and discrete logarithm recovery are constant-time ($O(1)$ polynomial combinations plus table lookup), taking $\approx 0.21\text{ s}$.

### 8.2 Biometric Verification Results (LFW Benchmark)
- **Goal**: Measure False Accept Rate (FAR), False Reject Rate (FRR), Equal Error Rate (EER), and overall accuracy under strict DevTrain / DevTest separation.
- **Execution Command**: `./venv/bin/python evaluation/eval_far_frr.py`
- **Output Artifacts**: `docs/results/lfw_far_frr.csv`, `docs/results/lfw_roc_curve.png`
- **Measured Results Table**:

| Dataset Partition | Pair Count | Calibrated Threshold ($\theta^*$) | Accuracy | False Accept Rate (FAR) | False Reject Rate (FRR) | Equal Error Rate (EER) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **DevTrain (Calibration)** | 2,200 | $0.7274$ | $57.55\%$ | $42.45\%$ | $42.45\%$ | $42.45\%$ |
| **DevTest (Independent Test)** | 1,000 | $0.7274$ | **$58.40\%$** | **$44.00\%$** | **$39.20\%$** | **$41.40\%$** |

- **Interpretation**: The compact prototype feature extractor operating without GPU acceleration yields an EER of $41.40\%$ on LFW. This confirms that the biometric layer functions as a lightweight gatekeeper in the prototype, while high-security deployments should integrate deeper neural models (e.g., ArcFace/FaceNet).

### 8.3 Multi-Vector Attack Simulation & Defense Rates
- **Goal**: Empirically verify system defense mechanisms against 4 primary attack vectors across 50 trials per vector.
- **Execution Command**: `./venv/bin/python evaluation/eval_attacks.py`
- **Output Artifacts**: `docs/results/attack_simulations.csv`
- **Measured Results Table**:

| Attack Vector Description | Trials | Blocked Attacks | Defense Rate | Primary Security Defense Mechanism |
| :--- | :---: | :---: | :---: | :--- |
| **1. Stolen Share A / Fake Share B Attack** | 50 | 50 | **$100.00\%$** | Secret reconstruction $S' \neq S \implies \text{SHA-256}(S') \neq C$ commitment check. |
| **2. Biometric Static Photo / Video Replay** | 50 | 50 | **$100.00\%$** | Zero EAR temporal variance ($\sigma^2 < 10^{-4}$) and yaw mismatch rejected by liveness engine. |
| **3. Blind Token Replay (Double-Voting)** | 50 | 50 | **$100.00\%$** | $N_{\text{token}}$ recorded in `spent_tokens` table; duplicate token rejected on ledger append. |
| **4. Ballot Stuffing / Forged ZKPs** | 50 | 50 | **$100.00\%$** | Fiat-Shamir verification fails on forged Disjunctive 1-of-2 and Sum-to-One proofs. |

### 8.4 Machine Learning Anomaly Detection Performance
- **Goal**: Evaluate Supervised Random Forest vs. Unsupervised Isolation Forest on 10,000 session logs (2,000 independent test samples).
- **Execution Command**: `./venv/bin/python evaluation/eval_ml_detector.py`
- **Output Artifacts**: `docs/results/ml_anomaly_detection.csv`, `docs/results/ml_anomaly_detection.png`
- **Measured Results Table**:

| Model Architecture | Model Paradigm | Test Samples | Accuracy | Precision | Recall | F1-Score | ROC-AUC |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Forest** | Supervised Ensemble | 2,000 | **$100.00\%$** | **$100.00\%$** | **$100.00\%$** | **$100.00\%$** | **$100.00\%$** |
| **Isolation Forest** | Unsupervised Anomaly | 2,000 | **$84.50\%$** | **$56.43\%$** | **$98.75\%$** | **$71.82\%$** | **$97.92\%$** |

- **Top Engineered Feature Importances (Random Forest Gini Impurity)**:
  1. `request_rate_per_min`: $24.16\%$
  2. `session_retry_count`: $22.65\%$
  3. `yaw_range_degrees`: $17.43\%$
  4. `challenge_duration_ms`: $13.33\%$
  5. `ear_variance`: $7.60\%$
  6. `user_agent_entropy`: $5.80\%$

### 8.5 Ledger Architecture: Hash Chain vs. Blockchain
- **Goal**: Quantify throughput, latency, and storage overhead of an append-only SHA-256 Merkle hash chain versus a Proof-of-Authority (PoA) blockchain.
- **Execution Command**: `./venv/bin/python evaluation/eval_comparison.py`
- **Output Artifacts**: `docs/results/ledger_comparison.csv`, `docs/results/blockchain_vs_hashchain.png`
- **Measured Results Table**:

| Metric Dimension | Append-Only SHA-256 Hash Chain | PoA Blockchain Ledger (Block Size = 50) | Advantage of SecureVote Approach |
| :--- | :---: | :---: | :--- |
| **Throughput** | $700,167.8\text{ tx/s}$ | $5,322,106.6\text{ tx/s}$ (Batched) | High individual verification throughput |
| **Confirmation Latency** | **$0.001\text{ ms}$** | $0.009\text{ ms}$ | $9\times$ lower per-ballot confirmation latency |
| **Storage Overhead** | $139.4\text{ bytes/ballot}$ | $20.4\text{ bytes/ballot}$ (Compressed) | Includes full standalone cryptographic proofs |
| **Infrastructure & Cost** | **Zero Gas / Zero Mining** | Requires Validator Cluster & Consensus | Significantly simpler deployment model |

---

## 9. Limitations & Honest Scope

In academic research, honest reporting of design constraints and prototype boundaries is essential:
1. **Prototype Face Recognition Architecture**: The facial feature extractor implemented in `face_engine.py` is a lightweight, CPU-efficient prototype intended to demonstrate end-to-end integration. In production, this should be replaced with deep metric learning models (e.g., InsightFace/ArcFace).
2. **Simulated Clock Warp for Demonstrations**: While SecureVote enforces strict wall-clock Unix timestamp checks ($T \ge T_{\text{open}}$), administrative fast-forward endpoints (`/api/election/clock/warp`) are enabled for interactive testing and demonstration.
3. **Discrete Logarithm Bound in Exponential ElGamal**: Decrypting an Exponential ElGamal sum $g^M$ requires solving discrete log $M = \log_g(g^M)$. For institutional and student elections ($N \le 100,000$), table lookup or baby-step giant-step is instantaneous ($<1\text{ ms}$). However, for national elections with millions of voters, homomorphic tallying must be partitioned by precinct or paired with verifiable mix-nets.
4. **Single-Server Deployment Boundary**: The prototype runs on a single FastAPI backend with an asynchronous SQLite database. A production election system requires distributed replicas of the bulletin board across independent administrative domains.

---

## 10. Future Work

1. **Post-Quantum Cryptographic Migration**: Transition from 2048-bit discrete log groups to lattice-based primitives (e.g., Kyber for key encapsulation, Dilithium for blind signatures, and lattice-based zero-knowledge arguments) to achieve quantum resistance.
2. **Universal Composability & Coercion Resistance (JCJ / Civitas Model)**: Integrate fake credential generation and re-voting capabilities where voters can cast decoy ballots to neutralize physical coercion.
3. **Decentralized Multi-Party Computation (MPC) Key Generation**: Replace the current centralized trustee split with a distributed key generation (DKG) protocol (e.g., Pedersen DKG) where trustees interact over secure channels without any single coordinator ever learning the master secret $x$.
4. **Client-Side Hardware Enclave Attestation**: Leverage WebAuthn and hardware security modules (Apple Secure Enclave, Android StrongBox) to bind voter shares to hardware-backed biometric authenticators.

---

## 11. Academic Paper-Writing Guide

### 11.1 Proposed Paper Outline (IMRaD Structure)
The following structure maps directly to the sections of this handbook:
- **Title**: SecureVote: An End-to-End Verifiable E-Voting System Integrating Threshold Credentials, Face Liveness, and Telemetry-Driven Anomaly Detection
- **Abstract** (See Section 11.4)
- **1. Introduction**: Motivation, voting security requirements, problem statement, and key contributions $\rightarrow$ *Source: Handbook Section 1*
- **2. Background & Related Work**: Shamir secret sharing, ElGamal, NIZKPs, blind signatures, Helios/Belenios comparison $\rightarrow$ *Source: Handbook Section 2*
- **3. System Architecture**: Threat model, trust assumptions, system layers, database entities, state machine $\rightarrow$ *Source: Handbook Sections 3 & 5*
- **4. Cryptographic & Verification Protocol**: Mathematical step-by-step protocol (Registration, Authentication, Token Issuance, Ballot Encryption, Bulletin Board, Trustee Decryption) $\rightarrow$ *Source: Handbook Section 4*
- **5. Biometric Liveness & ML Anomaly Detection**: Facial embedding, EAR/Yaw liveness, 12-feature pipeline, Random Forest & Isolation Forest $\rightarrow$ *Source: Handbook Section 6*
- **6. Experimental Evaluation**: Scale benchmarks (1k, 5k, 10k), LFW benchmark, attack simulations, ML results, ledger comparison $\rightarrow$ *Source: Handbook Section 8*
- **7. Discussion & Limitations**: Trust boundaries, coercion limits, prototype scope $\rightarrow$ *Source: Handbook Section 9*
- **8. Future Work & Conclusion**: Quantum resistance, DKG, concluding remarks $\rightarrow$ *Source: Handbook Section 10*

### 11.2 Suggested Figures and Tables for the Paper
```
+---------------------------------------------------------------------------------------------------+
| Paper Figures & Tables Mapping                                                                    |
+-------------------+---------------------------------------------+---------------------------------+
| Paper Element     | Description / Caption                       | Source File Location            |
+-------------------+---------------------------------------------+---------------------------------+
| Figure 1          | Overall SecureVote System Architecture      | docs/figures/system_architecture.mmd |
| Figure 2          | Voter Registration & Shamir Split Sequence  | docs/figures/voter_registration_flow.mmd |
| Figure 3          | Election-Day Auth & Blind Token Flow        | docs/figures/election_day_auth_flow.mmd |
| Figure 4          | In-Browser Ballot Encryption & ZKP Protocol | docs/figures/ballot_encryption_zkp_flow.mmd |
| Figure 5          | Append-Only Merkle Hash Chain Structure     | docs/figures/bulletin_board_hashchain.mmd |
| Figure 6          | 3-of-5 Trustee Threshold Decryption Flow    | docs/figures/trustee_threshold_tally_flow.mmd |
| Figure 7          | Dual-Model ML Feature Pipeline Architecture | docs/figures/ml_anomaly_detection_pipeline.mmd |
| Figure 8          | LFW ROC & Distance Distribution Curves      | docs/results/lfw_roc_curve.png  |
| Figure 9          | Cryptographic Scale Benchmarks (1k-10k)     | docs/results/scale_benchmark.png|
| Figure 10         | ML Anomaly Detector Confusion & Importance  | docs/results/ml_anomaly_detection.png |
| Figure 11         | Hash Chain vs. Blockchain Comparison        | docs/results/blockchain_vs_hashchain.png |
| Table 1           | Helios vs. Belenios vs. SecureVote Matrix   | Handbook Section 2.3            |
| Table 2           | Cryptographic Parameter Specifications      | Handbook Section 4              |
| Table 3           | Large-Scale Performance Benchmarks          | docs/results/scale_benchmarks.csv |
| Table 4           | LFW Biometric Evaluation Results            | docs/results/lfw_far_frr.csv    |
| Table 5           | Attack Simulation Defense Rates             | docs/results/attack_simulations.csv |
| Table 6           | ML Anomaly Detector Performance Metrics     | docs/results/ml_anomaly_detection.csv |
+-------------------+---------------------------------------------+---------------------------------+
```

### 11.3 Permissible vs. Prohibited Claims
- **Claims the Paper CAN Safely Make**:
  - SecureVote achieves mathematical ballot secrecy under the DDH assumption in RFC 3526 Group 14.
  - The $2$-of-$2$ Shamir credential scheme with time-locked server shares provides information-theoretic security prior to poll opening.
  - The combination of Chaum blind signatures and client-side NIZKPs prevents the election authority from linking voters to ballots while guaranteeing ballot validity.
  - In-browser encryption and NIZKP generation take $\approx 425\text{ ms}$, and homomorphic tallying of 10,000 ballots completes in $0.725\text{ s}$.
  - The dual-model ML detector achieves $100\%$ precision on simulated attack vectors and $98.75\%$ recall on unsupervised anomaly detection.
- **Claims the Paper MUST NOT Make**:
  - Do NOT claim SecureVote is immune to client-side malware or screen-recording coercion.
  - Do NOT claim the biometric subsystem achieves state-of-the-art commercial face recognition accuracy (the prototype EER on LFW is $41.40\%$).
  - Do NOT claim the system is post-quantum secure (it relies on classical discrete log and RSA).

### 11.4 Suggested Paper Abstract (212 Words)
> Electronic voting systems must simultaneously guarantee voter eligibility, ballot secrecy, end-to-end verifiability, and resilience against automated attacks without imposing prohibitive computational or usability burdens. This paper presents **SecureVote**, a comprehensive verifiable online voting architecture that synthesizes threshold cryptography, biometric liveness verification, and machine learning anomaly detection. To prevent premature credential harvesting, SecureVote splits voter credentials using a $2$-of-$2$ Shamir secret sharing scheme combined with server-side time-lock release. On election day, active facial liveness verification gates the issuance of an unlinkable Chaum RSA-2048 blind-signed voting token. Ballots are encrypted in the voter's browser using Additive Exponential ElGamal over RFC 3526 2048-bit MODP Group 14 and accompanied by Non-Interactive Zero-Knowledge Proofs of validity (Disjunctive $1$-of-$2$ and Sum-to-One proofs). Ballots are logged onto an append-only SHA-256 Merkle hash-chain bulletin board, providing voters with cryptographic receipts. A $3$-of-$5$ trustee threshold network computes the final homomorphic tally with Discrete Logarithm Equality proofs. In parallel, a dual-model machine learning engine analyzes session telemetry across 12 engineered features to flag malicious behavior. Empirical evaluation demonstrates that in-browser encryption completes in $425\text{ ms}$, homomorphic tallying of 10,000 ballots requires $0.725\text{ s}$, and the system successfully defends against $100\%$ of simulated multi-vector attacks.

---

## 12. Reproducibility & Execution Instructions

### 12.1 Environment Setup
```bash
# 1. Clone repository and navigate to root
cd /Users/monishav/Desktop/CipherVote

# 2. Activate Python virtual environment
source venv/bin/activate

# 3. Verify Python dependencies
pip install -r requirements.txt  # FastAPI, Pytest, scikit-learn, OpenCV, NumPy, etc.
```

### 12.2 Running Backend Tests
```bash
# Execute full backend test suite (28 tests)
PYTHONPATH=backend ./venv/bin/pytest backend/tests/ -v
```

### 12.3 Regenerating All Evaluation Results & Charts
```bash
# 1. Run large-scale cryptographic benchmarks (1k, 5k, 10k voters)
./venv/bin/python evaluation/eval_scale_benchmark.py

# 2. Run LFW biometric evaluation on strict DevTrain / DevTest splits
./venv/bin/python evaluation/eval_far_frr.py

# 3. Run multi-vector attack simulation suite
./venv/bin/python evaluation/eval_attacks.py

# 4. Run ML anomaly detector evaluation (Random Forest vs Isolation Forest)
./venv/bin/python evaluation/eval_ml_detector.py

# 5. Run hash chain vs blockchain comparison
./venv/bin/python evaluation/eval_comparison.py

# 6. Copy updated figures and tables to docs directory
cp evaluation/plots/*.png docs/results/
```

### 12.4 Running the Full Interactive Web Application
```bash
# Terminal 1: Start FastAPI Backend Server
source venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Start React Frontend Development Server
cd frontend
npm run dev  # Starts at http://localhost:3000
```

---

## 13. Glossary of Terms and Acronyms

- **AES-GCM**: Advanced Encryption Standard in Galois/Counter Mode. An authenticated symmetric encryption standard providing confidentiality and integrity.
- **Blind Signature**: A cryptographic digital signature protocol (invented by David Chaum) where the message is blinded prior to signing, preventing the signer from viewing the message or linking it to the resulting unblinded signature.
- **Bulletin Board (BB)**: An append-only, publicly readable, immutable ledger where election authorities publish cast ballots, receipts, and cryptographic proofs for public auditing.
- **Chaum-Pedersen Protocol**: A zero-knowledge sigma protocol used to prove the equality of discrete logarithms across two different generator bases without revealing the exponent.
- **DDH**: Decisional Diffie-Hellman assumption. The computational hardness assumption that given $(g, g^a, g^b, g^c)$, it is computationally infeasible to determine whether $c = ab \pmod q$ or $c$ is random.
- **DLEQ**: Discrete Logarithm Equality. A proof certifying that two group elements share the identical discrete logarithm.
- **EAR**: Eye Aspect Ratio. A scalar metric computed from 2D facial landmark coordinates measuring the degree of eye openness.
- **EER**: Equal Error Rate. The biometric operating point where the False Accept Rate (FAR) equals the False Reject Rate (FRR).
- **ElGamal Encryption**: A public-key cryptosystem based on Diffie-Hellman key exchange. In its exponential/additive form, plaintexts are placed in the exponent ($g^m$), enabling homomorphic addition of ciphertexts.
- **FAR**: False Accept Rate. The proportion of impostor biometric probes incorrectly classified as genuine matches.
- **Fiat-Shamir Heuristic**: A cryptographic technique that converts an interactive zero-knowledge proof into a non-interactive proof (NIZKP) by replacing the verifier's challenge with a hash of the commitments.
- **FRR**: False Reject Rate. The proportion of genuine biometric probes incorrectly rejected as impostors.
- **Lagrange Interpolation**: A polynomial interpolation technique used in Shamir's Secret Sharing to reconstruct a secret polynomial from $k$ distinct evaluation points.
- **LFW**: Labeled Faces in the Wild. A standard academic computer vision benchmark dataset for unconstrained facial verification.
- **MODP**: Modular Exponentiation Groups. Standardized finite cyclic groups defined in IETF RFC 3526 for Diffie-Hellman cryptography.
- **NIZKP**: Non-Interactive Zero-Knowledge Proof. A proof that establishes the truth of a statement without revealing secret witness information and without interactive rounds between prover and verifier.
- **PoA**: Proof-of-Authority. A blockchain consensus mechanism where designated trusted validators produce and sign blocks.
- **ROC**: Receiver Operating Characteristic. A graphical plot of True Accept Rate versus False Accept Rate across varying classification thresholds.
- **Shamir's Secret Sharing**: A threshold cryptographic algorithm where a secret is split into $n$ shares such that any $k$ shares can reconstruct the secret, but $k-1$ shares reveal no information.
- **TAR**: True Accept Rate ($1 - \text{FRR}$). The proportion of genuine biometric probes correctly verified.
- **Time-Lock Encryption**: A cryptographic technique ensuring that a ciphertext cannot be decrypted until a specified future time has elapsed.
- **ZKP**: Zero-Knowledge Proof. A cryptographic method by which one party (the prover) can prove to another party (the verifier) that a given statement is true without conveying any information beyond the validity of the statement itself.

---

## 14. Election Lifecycle, Trustee Portal, and Notifications Subsystem

### 14.1 Multi-Election Management & Setup Checklist
SecureVote supports multi-election administration with isolated cryptographic parameters:
1. **Election Creation**: Administrators can provision multiple independent elections with customizable title, description, candidate rosters ($2$ to $10$ unique candidates), and IANA timezone configurations.
2. **Setup Checklist**: Each election guides the administrator through a sequential 5-step operational workflow:
   - Step 1: Election Created & Parameters Defined.
   - Step 2: Add Trustee Roster & Dispatch Cryptographic Invitations.
   - Step 3: Configure Voting Schedule & Announce to Eligible Voters.
   - Step 4: Open Voting & Enable Biometric Time-Lock Token Issuance.
   - Step 5: Close Polls & Conduct All-Trustees Unlock Ceremony.
3. **Immutability & Safety Constraints**: Election configuration is strictly locked once voting opens (`OPEN` state). Election deletion is permitted only when zero voters are registered to protect audit trail integrity.

### 14.2 Trustee Portal Architecture & Key Generation
SecureVote enforces a decentralized threshold trust model where election authorities never hold sole decryption authority:
1. **Empty-Start Roster**: Every newly created election initializes with an empty trustee roster ($0$ trustees). Trustees are explicitly entered by institutional name and verified email address ($3$ to $9$ trustees).
2. **Draft Persistence**: Administrators can save roster drafts with status `NOT_INVITED` without premature cryptographic key generation.
3. **Automatic Majority Threshold**: The decryption threshold $t$ is automatically computed as the strict majority:
   $$t = \lfloor N/2 \rfloor + 1$$
   Eliminating administrative configuration errors while ensuring resilience against minority trustee unavailability.
4. **Invitation Ceremony & Share Distribution**:
   - Clicking `Send Invitations` constructs the joint ElGamal public key $h = g^x \pmod p$ and computes polynomial Shamir shares $s_i = f(i) \pmod q$ for each trustee.
   - Unique 128-bit random invitation tokens and Crockford Base32-encoded unlock passphrase parts are generated and dispatched via transactional email.
   - Voting cannot be opened until all trustee invitations have been successfully generated and dispatched.
5. **Ceremony Round Window**: Administrators configure an unlock ceremony synchrony window ($2$ to $15$ minutes, default $5$ minutes) to ensure trustees submit their shares concurrently during the tallying phase.

### 14.3 Admin-Controlled Dynamic Scheduling & Time-Locks
1. **Scheduled Start & End Dates**: Submitted in ISO 8601 format and stored internally in Coordinated Universal Time (UTC).
2. **Display Formatting**: Datetimes are rendered to voters and auditors in their local time with the standard timezone abbreviation (e.g., `"Wed, 21 Oct 2026, 9:00 AM IST"`).
3. **Validation & Schedule Immutability**: The system validates that `scheduled_end > scheduled_start`. A schedule remains editable during the registration phase, but becomes strictly locked once the administrator opens voting (`OPEN` status).
4. **Time-Lock Share B Release**: During registration, Share B is encrypted with a master time-lock key. The backend releases Share B to authenticated voters only when the election status is transitioned to `OPEN` by the administrator.

### 14.4 In-Site Notifications & Infrastructure Logging
To keep voters informed without exposing sensitive cryptographic secrets:
1. **Registration Triggers**: Upon completing biometric registration, the voter receives an in-site notification and a transactional email confirming their registration status and stating the scheduled voting window (or `"Dates to be announced"` if not yet scheduled).
2. **Zero Secrets Guarantee**:
   - **Share A** is displayed on the voter's secure screen once and must be retained by the voter.
   - **No Secret Shares (Share A or Share B)** or facial embeddings are EVER embedded within email notifications.
3. **Background Delivery & Operational Diagnostics**:
   - Administrative email log pages exposing internal codes have been removed from the UI.
   - Outbound transactional emails are managed by backend queuing with an automatic alert banner surfaced on the Admin Overview if SMTP delivery encounters network failures.
   - In development environments, `.eml` and `.html` payloads are captured under `data/outbox/`.

### 14.6 RFC 5322 Email Compliance, Gmail DKIM Alignment, & Delivery Governance
SecureVote enforces strict RFC 5322 email formatting and transport security for all voter credentials and trustee invitations:
1. **Compliant Header Formatting**:
   - Every outbound email message is constructed using Python's modern `EmailMessage` API.
   - Headers utilize RFC 5322 `formataddr((display_name, email_address))`, guaranteeing valid angles (`Display Name <user@domain.com>`) and avoiding malformed double-nesting.
   - Standard `Date` (via `formatdate(localtime=True)`) and `Message-ID` (via `make_msgid(domain=...)`) headers are attached to every message.
   - Content is structured as `multipart/alternative` with both plaintext and accessible HTML bodies.
2. **Gmail SMTP & DKIM Policy Alignment**:
   - When configured with `smtp.gmail.com`, Google strictly enforces that the envelope sender and `From:` header match the authenticated Google Account (`SMTP_USER`).
   - SecureVote dynamically aligns the effective sender address with `SMTP_USER` while maintaining the configured display name (`SMTP_FROM_NAME`), guaranteeing that SPF and DKIM pass without bounce error `550 5.7.30`.
   - Administrators configure `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER=account@gmail.com`, `SMTP_PASSWORD=16-char-app-password`, and `SMTP_FROM_NAME=SecureVote`.
3. **Honest Delivery Tracking**:
   - The system tracks email statuses honestly as `"sent to mail server"` once accepted by the upstream MTA, rather than falsely declaring `"delivered"` before final recipient inbox delivery.
4. **Live Email Diagnostic Console**:
   - In Admin > Settings, administrators can inspect the active SMTP host, port, TLS security mode, and effective From address, and send a live test message to verify deliverability.

### 14.7 Standalone Ceremony Entry Point & Sealed Chain Head Verification
1. **Direct & Standalone Trustee Access**:
   - Trustees can access the ceremony at `/ceremony/:token` directly from their email invitation links, or visit `/ceremony` to paste their private access token or ceremony URL.
   - The landing page footer includes a quiet `"Trustee access"` link directing to `/ceremony`.
   - In Step 3 of Tally & Results, administrators can copy the trustee page address (`/ceremony`) or trigger `"Resend ceremony link"` to re-dispatch invitation links to trustees without exposing or resetting their secret passphrase parts.
2. **Real Sealed Bulletin Board Head**:
   - In Step 1 of Tally & Results, the system renders the authentic 64-hex SHA-256 Merkle chain head hash of the sealed ballot box, complete with a one-click copy button, or indicates `"No ballots"` if zero ballots were cast.

### 14.8 Developer CLI & Reset Utilities
For automated testing and sandbox demonstrations, SecureVote provides administrative CLI tools:
```bash
# Reset all elections, voters, ballots, and trustee rosters to pristine state
python -m app.cli reset-all

# Seed clean demo election and mock trustee configuration
python -m app.cli reset-demo
```


