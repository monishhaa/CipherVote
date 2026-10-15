"""
Pydantic Schemas for CipherVote API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import AliasChoices, BaseModel, Field


# ==========================================
# Election Schemas
# ==========================================

class CandidateItem(BaseModel):
    id: int
    name: str
    party: Optional[str] = None


class ElectionCreateRequest(BaseModel):
    election_id: str = Field(..., json_schema_extra={"example": "council-2026"})
    title: str = Field(..., json_schema_extra={"example": "University Student Council Election 2026"})
    candidates: List[CandidateItem]
    open_time: int = Field(..., description="Unix timestamp when election opens")
    close_time: int = Field(..., description="Unix timestamp when election closes")


class ElectionStatusResponse(BaseModel):
    election_id: str
    title: str
    status: str
    open_time: int
    close_time: int
    current_time: int
    is_open: bool
    public_key_h: str
    blind_rsa_n: str
    blind_rsa_e: int
    candidates: List[CandidateItem]
    bulletin_board_length: int
    head_hash: str
    # Schedule info
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    timezone: Optional[str] = "UTC"
    formatted_window: Optional[str] = None
    actual_open_at: Optional[datetime] = None
    actual_close_at: Optional[datetime] = None


class ElectionScheduleRequest(BaseModel):
    election_id: str
    scheduled_start: datetime = Field(..., validation_alias=AliasChoices("scheduled_start", "start_datetime"))
    scheduled_end: datetime = Field(..., validation_alias=AliasChoices("scheduled_end", "end_datetime"))
    timezone: str = "UTC"  # IANA timezone (e.g. Asia/Kolkata, America/New_York)
    announce: bool = True  # If true, sends notifications & emails to registered voters

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


class ElectionScheduleResponse(BaseModel):
    election_id: str
    title: str
    status: str
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    timezone: str
    formatted_window: str
    schedule_published_at: Optional[datetime]
    voters_notified: int = 0
    warnings: List[str] = []
    message: str


class ClockWarpRequest(BaseModel):
    target_status: Optional[str] = None  # REGISTRATION, OPEN, TALLYING, CLOSED
    target_timestamp: Optional[int] = None


class PublicElectionListItem(BaseModel):
    election_id: str
    title: str
    status: str
    is_open: bool
    registration_open: bool
    closed_reason: Optional[str] = None
    scheduled_window: Optional[str] = None
    timezone: Optional[str] = "UTC"
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    candidates_count: int = 0
    created_at: Optional[str] = None


class PublicElectionListResponse(BaseModel):
    elections: List[PublicElectionListItem]


# ==========================================
# Voter & Credential Schemas
# ==========================================

class VoterRegisterRequest(BaseModel):
    election_id: Optional[str] = None
    voter_id: str
    full_name: str
    email: str
    face_embedding: List[float] = Field(..., description="128-dimensional embedding vector")


class VoterRegisterResponse(BaseModel):
    voter_id: str
    full_name: str
    email: Optional[str] = None
    email_masked: str
    commitment: str
    message: str
    voting_window: Optional[str] = None
    delivery_status: str = "DELIVERED"
    share_a: Optional[str] = None  # None by default, never exposed


class ProcessFaceRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded JPEG/PNG frame")


class ProcessFaceResponse(BaseModel):
    face_count: int
    embedding: List[float]
    message: str


class ShareBResponse(BaseModel):
    voter_id: str
    share_b: Optional[str] = None
    status: str
    message: str


class VoterSessionLookupRequest(BaseModel):
    voter_id: str
    email: str
    election_id: str = "council-2026"


class VoterSessionLookupResponse(BaseModel):
    voter_id: str
    full_name: str
    email: str
    election_id: str
    status: str
    has_voted: bool
    session_token: str
    voting_window: str


# ==========================================
# Notification & Outbox Schemas
# ==========================================

class NotificationItem(BaseModel):
    id: int
    election_id: str
    voter_id: str
    type: str
    title: str
    body: str
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    notifications: List[NotificationItem]
    unread_count: int


class MarkReadRequest(BaseModel):
    notification_ids: Optional[List[int]] = None  # If None, marks all as read
    voter_id: str


class OutboxItem(BaseModel):
    id: int
    election_id: str
    voter_id: str
    to_email: str
    type: str
    subject: str
    status: str
    attempts: int
    last_error: Optional[str]
    created_at: datetime
    sent_at: Optional[datetime]
    body_text: str
    body_html: str


class AdminNotificationLogResponse(BaseModel):
    total_notifications: int
    total_sent: int
    total_queued: int
    total_failed: int
    outbox: List[OutboxItem]


# ==========================================
# Token Issuance Schemas
# ==========================================

class LivenessTelemetry(BaseModel):
    challenge_id: str = "challenge_web"
    ear_scores: List[float] = Field(default_factory=list, validation_alias=AliasChoices("ear_scores", "earScores"))
    yaw_angles: List[float] = Field(default_factory=list, validation_alias=AliasChoices("yaw_angles", "yawAngles"))
    probe_embedding: Optional[List[float]] = Field(default=None, validation_alias=AliasChoices("probe_embedding", "probeEmbedding"))

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


class BlindTokenRequest(BaseModel):
    voter_id: str
    share_a: str
    share_b: str
    blinded_token: str  # Hex string m'
    liveness_telemetry: Optional[LivenessTelemetry] = None


class BlindTokenResponse(BaseModel):
    blind_signature: str  # Hex string s'
    message: str


# ==========================================
# Ballot Casting Schemas
# ==========================================

class CiphertextItem(BaseModel):
    c1: str
    c2: str


class DisjunctiveZKPItem(BaseModel):
    a0: str
    b0: str
    a1: str
    b1: str
    c0: str
    c1: str
    z0: str
    z1: str


class EqualityZKPItem(BaseModel):
    a: str
    b: str
    c: str
    z: str


class ZKPPayload(BaseModel):
    disjunctive_proofs: List[DisjunctiveZKPItem]
    sum_proof: EqualityZKPItem


class BallotCastRequest(BaseModel):
    election_id: str
    ciphertexts: List[CiphertextItem]
    zkp_proofs: ZKPPayload
    token_nonce: str  # Plaintext unblinded message
    token_signature: str  # Unblinded RSA signature s


class BallotCastResponse(BaseModel):
    receipt_code: str
    sequence_number: int
    block_hash: str
    timestamp: int
    message: str


# ==========================================
# Bulletin Board & Tally Schemas
# ==========================================

class BulletinBoardItem(BaseModel):
    sequence_number: int
    timestamp: int
    ciphertexts: List[CiphertextItem]
    receipt_code: str
    previous_hash: str
    block_hash: str


class BulletinBoardResponse(BaseModel):
    election_id: str
    total_ballots: int
    genesis_hash: str
    head_hash: str
    ballots: List[BulletinBoardItem]


class BulletinBoardVerifyResponse(BaseModel):
    is_valid: bool
    total_ballots: int
    genesis_hash: str
    head_hash: str
    merkle_root: str
    error: Optional[str] = None


class TallyResultResponse(BaseModel):
    election_id: str
    total_ballots: int
    candidate_results: Dict[str, int]
    bulletin_board_root_hash: str
    trustee_shares_used: List[int]
    status: str
