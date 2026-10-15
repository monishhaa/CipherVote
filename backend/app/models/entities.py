"""
SQLAlchemy ORM Entities for CipherVote.
"""

from datetime import datetime
import json
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .database import Base


class Election(Base):
    __tablename__ = "elections"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), default="REGISTRATION")  # REGISTRATION, OPEN, TALLYING, CLOSED, ARCHIVED
    open_time = Column(Integer, nullable=False)  # Legacy Unix timestamp for cryptographic key derivation
    close_time = Column(Integer, nullable=False)  # Legacy Unix timestamp
    simulated_clock_offset = Column(Integer, default=0)

    # Dynamic Admin-Controlled Schedule (Stored in UTC)
    scheduled_start = Column(DateTime, nullable=True)  # UTC Datetime
    scheduled_end = Column(DateTime, nullable=True)  # UTC Datetime
    timezone = Column(String(64), default="UTC")  # IANA Timezone string (e.g. Asia/Kolkata, America/New_York)
    schedule_published_at = Column(DateTime, nullable=True)  # UTC Datetime when schedule was published/announced
    actual_open_at = Column(DateTime, nullable=True)  # UTC Datetime when admin clicked "Open voting"
    actual_close_at = Column(DateTime, nullable=True)  # UTC Datetime when admin clicked "Close voting"

    # Cryptographic keys
    public_key_h = Column(Text, nullable=False)  # ElGamal public key hex
    blind_rsa_n = Column(Text, nullable=False)  # RSA Modulus hex
    blind_rsa_e = Column(Integer, default=65537)
    blind_rsa_d = Column(Text, nullable=False)  # RSA Private key hex
    private_key_x = Column(Text, nullable=True)  # ElGamal master private key hex

    # Candidates JSON list [{"id": 0, "name": "Alice"}, {"id": 1, "name": "Bob"}]
    candidates_json = Column(Text, nullable=False)

    # Threshold for trustee threshold decryption
    trustee_threshold = Column(Integer, default=3)
    ceremony_window_minutes = Column(Integer, default=5)
    invitations_sent_at = Column(DateTime, nullable=True)
    ceremony_unlocked_at = Column(DateTime, nullable=True)
    results_published_at = Column(DateTime, nullable=True)
    full_passphrase_commitment = Column(String(128), nullable=True)
    full_passphrase_salt = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    trustees = relationship("Trustee", back_populates="election", cascade="all, delete-orphan", order_by="Trustee.position")
    ballots = relationship("Ballot", back_populates="election", cascade="all, delete-orphan")
    tally = relationship("TallyResult", back_populates="election", uselist=False)
    notifications = relationship("Notification", back_populates="election", cascade="all, delete-orphan")
    email_outbox = relationship("EmailOutbox", back_populates="election", cascade="all, delete-orphan")

    @property
    def candidates(self):
        return json.loads(self.candidates_json) if self.candidates_json else []


class Trustee(Base):
    __tablename__ = "trustees"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(String(64), ForeignKey("elections.election_id"), nullable=False)
    trustee_id = Column(Integer, nullable=False)  # 1 to 9
    name = Column(String(128), nullable=False)
    email = Column(String(256), nullable=True)
    position = Column(Integer, default=1)
    verification_key_h = Column(Text, nullable=True)  # g^(s_i) mod p
    schnorr_proof_json = Column(Text, nullable=True)
    encrypted_share_value = Column(Text, nullable=True)  # Encrypted secret share for trustee

    # Task B: Unlock Ceremony & Link Tokens
    link_token_hash = Column(String(128), index=True, nullable=True)
    raw_link_token = Column(String(128), nullable=True)  # Stored to allow resending ceremony link (never code)
    code_hash = Column(String(256), nullable=True)
    code_salt = Column(String(64), nullable=True)
    email_status = Column(String(32), default="PENDING")  # PENDING, SENT, FAILED
    email_sent_at = Column(DateTime, nullable=True)
    link_opened_at = Column(DateTime, nullable=True)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    has_approved = Column(Boolean, default=False)
    approved_at = Column(DateTime, nullable=True)
    partial_decryption_json = Column(Text, nullable=True)

    election = relationship("Election", back_populates="trustees")

    __table_args__ = (UniqueConstraint("election_id", "trustee_id", name="uq_election_trustee"),)


class Voter(Base):
    __tablename__ = "voters"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(String(64), ForeignKey("elections.election_id"), nullable=True, index=True)
    voter_id = Column(String(64), index=True, nullable=False)
    full_name = Column(String(256), nullable=False)
    email = Column(String(256), index=True, nullable=False)
    password_hash = Column(String(256), nullable=True)  # Salted hash for voter portal login
    is_approved = Column(Boolean, default=True)

    # Biometric template (AES-256-GCM encrypted 128-d vector)
    encrypted_face_template = Column(Text, nullable=False)

    # Credential commitments & time-locked shares
    credential_commitment = Column(String(64), nullable=False)  # SHA256(S)
    encrypted_share_b = Column(Text, nullable=False)  # Time-locked until admin opens voting
    share_a_preview = Column(String(32), nullable=True)  # Prefix helper for UI demo

    # Token issuance state
    token_issued = Column(Boolean, default=False)
    registered_at = Column(DateTime, default=datetime.utcnow)

    election = relationship("Election")

    __table_args__ = (
        UniqueConstraint("election_id", "voter_id", name="uq_election_voter"),
        UniqueConstraint("election_id", "email", name="uq_election_email"),
    )



class Ballot(Base):
    """Public Bulletin Board append-only ledger entry."""
    __tablename__ = "ballots"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(String(64), ForeignKey("elections.election_id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)  # Strict 1, 2, 3...
    timestamp = Column(Integer, nullable=False)

    # Encrypted candidate votes: [{"c1": "0x...", "c2": "0x..."}, ...]
    ciphertexts_json = Column(Text, nullable=False)
    # ZKPs: {"disjunctive": [...], "sum_to_one": {...}}
    zkp_proofs_json = Column(Text, nullable=False)

    # Unblinded Chaum RSA token signature
    token_signature = Column(Text, unique=True, nullable=False)
    # Receipt code: SHA256(ciphertexts_json)
    receipt_code = Column(String(64), unique=True, index=True, nullable=False)

    # Hash chain link
    previous_hash = Column(String(64), nullable=False)
    block_hash = Column(String(64), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    election = relationship("Election", back_populates="ballots")

    __table_args__ = (
        UniqueConstraint("election_id", "sequence_number", name="uq_election_sequence"),
    )


class TallyResult(Base):
    __tablename__ = "tally_results"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(String(64), ForeignKey("elections.election_id"), unique=True, nullable=False)
    total_ballots = Column(Integer, nullable=False)
    # Final decrypted candidate counts: {"Alice": 450, "Bob": 320}
    candidate_totals_json = Column(Text, nullable=False)
    # Homomorphic aggregated ciphertexts: [{"c1": "0x...", "c2": "0x..."}, ...]
    aggregated_ciphertexts_json = Column(Text, nullable=False)
    # Trustee partial decryptions: [{"trustee_id": 1, "d_i": "0x...", "proof": {...}}]
    trustee_contributions_json = Column(Text, nullable=False)
    bulletin_board_root_hash = Column(String(64), nullable=False)
    tallied_at = Column(DateTime, default=datetime.utcnow)

    election = relationship("Election", back_populates="tally")


class Notification(Base):
    """In-site notification for voters regarding election lifecycle, schedules, and status."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(String(64), ForeignKey("elections.election_id"), nullable=False, index=True)
    voter_id = Column(String(64), index=True, nullable=False)
    type = Column(String(32), nullable=False)  # REGISTRATION, SCHEDULE_SET, SCHEDULE_UPDATED, VOTING_OPEN
    title = Column(String(256), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)

    election = relationship("Election", back_populates="notifications")


class EmailOutbox(Base):
    """Audit log of queued, delivered, and failed email dispatches."""
    __tablename__ = "email_outbox"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(String(64), ForeignKey("elections.election_id"), nullable=False, index=True)
    voter_id = Column(String(64), index=True, nullable=False)
    to_email = Column(String(256), nullable=False)
    type = Column(String(32), nullable=False)  # REGISTRATION, SCHEDULE_SET, SCHEDULE_UPDATED, VOTING_OPEN
    subject = Column(String(256), nullable=False)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text, nullable=False)
    status = Column(String(32), default="QUEUED")  # QUEUED, SENT, FAILED
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)

    election = relationship("Election", back_populates="email_outbox")


class LoginAuditLog(Base):
    __tablename__ = "login_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    voter_id = Column(String(64), index=True, nullable=True)
    timestamp = Column(Integer, nullable=False)
    ip_address = Column(String(64), nullable=False)
    user_agent = Column(String(256), nullable=False)
    event_type = Column(String(64), nullable=False)  # REGISTER, SHARE_RETRIEVE, TOKEN_REQUEST, BALLOT_CAST
    status = Column(String(32), nullable=False)  # SUCCESS, FAILED, ANOMALY_BLOCKED
    features_json = Column(Text, nullable=True)  # 12-dimensional feature vector JSON
    anomaly_score = Column(Float, default=0.0)
    is_attack_simulated = Column(Boolean, default=False)
