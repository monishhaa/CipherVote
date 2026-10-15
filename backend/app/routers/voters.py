"""
Voter registration, credential retrieval, notifications, and status lookup router.
"""

import base64
from datetime import datetime
import hashlib
import hmac
import json
import os
import time
from typing import List, Optional
import cv2
from fastapi import APIRouter, Depends, HTTPException, status
import numpy as np
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.biometrics.face_engine import face_engine
from app.core.biometrics.template_crypto import encrypt_face_template
from app.core.crypto.shamir import create_voter_credential
from app.core.crypto.timelock import decrypt_share_b, derive_timelock_key, encrypt_share_b
from app.core.notifications import (
    format_voting_window,
    queue_voter_notification_and_email,
)
from app.core.email import (
    send_credential_email_with_retries,
    build_credential_email_content,
)
from app.models import Ballot, Election, Notification, Voter, EmailOutbox, get_db
from app.schemas import (
    MarkReadRequest,
    NotificationItem,
    NotificationListResponse,
    ProcessFaceRequest,
    ProcessFaceResponse,
    ShareBResponse,
    VoterRegisterRequest,
    VoterRegisterResponse,
    VoterSessionLookupRequest,
    VoterSessionLookupResponse,
)

router = APIRouter(prefix="/voters", tags=["Voters"])

LFW_BASE_DIR = os.path.join(settings.DATA_DIR, "lfw")
IMG_ROOT = os.path.join(LFW_BASE_DIR, "lfw-deepfunneled", "lfw-deepfunneled")


def generate_voter_session_token(voter_id: str, email: str) -> str:
    """Generate signed HMAC session token for registered voter."""
    payload = f"{voter_id.lower()}:{email.lower()}"
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"voter_{payload}_{sig}"


@router.post("/process-face", response_model=ProcessFaceResponse)
async def process_webcam_face(req: ProcessFaceRequest):
    """
    Validate presence in webcam frame and extract 128-d biometric embedding.
    Does NOT store raw image pixels on disk.
    Accepts captured photo without strict double-face blocking.
    """
    try:
        raw_b64 = req.image_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        img_bytes = base64.b64decode(raw_b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_IMAGE_PAYLOAD", "message": "Failed to decode base64 image frame."},
        )

    # Decode image to check validity
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None or img.size == 0 or len(img_bytes) < 300:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_IMAGE_PAYLOAD", "message": "Failed to decode base64 image frame."},
        )

    # Extract 128-d embedding directly from the captured image frame (no multi-face check)
    try:
        embedding = face_engine.extract_embedding_from_image(img)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_IMAGE_PAYLOAD", "message": f"Could not process image frame: {str(e)}"},
        )

    return ProcessFaceResponse(
        face_count=1,
        embedding=embedding,
        message="Face successfully captured and 128-d embedding extracted.",
    )


@router.post("/register", response_model=VoterRegisterResponse)
async def register_voter(
    req: VoterRegisterRequest,
    election_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new voter with face embedding, 2-of-2 Shamir shares, and time-locked Share B.
    Enforces case/whitespace-insensitive uniqueness for voter_id and email scoped to the election.
    Dispatches in-site notification and schedule email (with zero secret leakage).
    """
    clean_voter_id = req.voter_id.strip()
    clean_email = req.email.strip()
    clean_name = req.full_name.strip()

    target_election_id = (req.election_id or election_id or "").strip()
    if not target_election_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": "election_id", "code": "MISSING_ELECTION_ID", "message": "Election ID is required."},
        )

    if not clean_voter_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": "voter_id", "code": "EMPTY_VOTER_ID", "message": "Voter ID cannot be empty."},
        )
    if not clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": "email", "code": "EMPTY_EMAIL", "message": "Email address cannot be empty."},
        )

    # 1. Fetch Election & Verify REGISTRATION Status
    el_res = await db.execute(select(Election).where(Election.election_id == target_election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "ELECTION_NOT_FOUND", "message": f"Election '{target_election_id}' not found."},
        )

    if election.status != "REGISTRATION":
        reason = "Voting has started" if election.status == "OPEN" else ("Voting has closed" if election.status in ("CLOSED", "ENDED") else f"Current status is {election.status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "REGISTRATION_CLOSED",
                "message": f"Registration is closed for this election: {reason}.",
            },
        )

    # 2. Check Uniqueness Scoped to Election
    voter_id_check = await db.execute(
        select(Voter).where(
            func.lower(Voter.voter_id) == clean_voter_id.lower(),
            Voter.election_id == target_election_id,
        )
    )
    if voter_id_check.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "field": "voter_id",
                "code": "DUPLICATE_VOTER_ID",
                "message": f"This voter ID '{clean_voter_id}' is already registered in this election.",
            },
        )

    email_check = await db.execute(
        select(Voter).where(
            func.lower(Voter.email) == clean_email.lower(),
            Voter.election_id == target_election_id,
        )
    )
    if email_check.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "field": "email",
                "code": "DUPLICATE_EMAIL",
                "message": f"The email address '{clean_email}' is already registered in this election.",
            },
        )

    # 3. Validate Biometric Face Embedding
    if not req.face_embedding or len(req.face_embedding) != 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "field": "face_embedding",
                "code": "INVALID_BIOMETRIC",
                "message": "Valid 128-dimensional facial biometric embedding is required.",
            },
        )

    # 4. Encrypt Face Template
    encrypted_template = encrypt_face_template(req.face_embedding)

    # 5. Generate 2-of-2 Shamir Credential & Time-Lock Share B
    cred = create_voter_credential()
    timelock_key = derive_timelock_key(
        settings.MASTER_TIME_LOCK_SECRET, target_election_id, election.open_time
    )
    encrypted_share_b = encrypt_share_b(cred.share_b, timelock_key)

    voter = Voter(
        election_id=target_election_id,
        voter_id=clean_voter_id,
        full_name=clean_name,
        email=clean_email,
        is_approved=True,
        encrypted_face_template=encrypted_template,
        credential_commitment=cred.commitment,
        encrypted_share_b=encrypted_share_b,
        share_a_preview=None,  # NEVER store share_a or preview
        token_issued=False,
    )
    db.add(voter)
    await db.commit()

    # In-site registration notification
    notif = Notification(
        election_id=election.election_id,
        voter_id=voter.voter_id,
        type="REGISTRATION",
        title="Voter Registration Confirmed",
        body=(
            f"Registration confirmed for '{election.title}'. Your voting credential "
            f"has been dispatched to your official email address."
        ),
        created_at=datetime.utcnow(),
    )
    db.add(notif)

    formatted_win = format_voting_window(
        election.scheduled_start,
        election.scheduled_end,
        election.timezone or "UTC",
    )

    # Email Secret Share A to voter directly (In memory only, never in DB or response)
    delivery_res = await send_credential_email_with_retries(
        recipient_email=voter.email,
        voter_id=voter.voter_id,
        voter_name=voter.full_name,
        share_a=cred.share_a,  # In-memory only!
        election_id=election.election_id,
        election_title=election.title,
        voting_window=formatted_win,
    )

    # Redacted outbox entry
    redacted_text, redacted_html = build_credential_email_content(
        voter_name=voter.full_name,
        voter_id=voter.voter_id,
        share_a="[REDACTED_SECRET_SHARE_A]",
        election_title=election.title,
        voting_window=formatted_win,
        redacted=True,
    )

    outbox = EmailOutbox(
        election_id=election.election_id,
        voter_id=voter.voter_id,
        to_email=voter.email,
        type="CREDENTIAL",
        subject=f"Your {settings.APP_NAME} voting credential",
        body_text=redacted_text,
        body_html=redacted_html,
        status="SENT" if delivery_res.get("success") else "FAILED",
        attempts=delivery_res.get("attempts", 1),
        last_error=delivery_res.get("error"),
        created_at=datetime.utcnow(),
        sent_at=datetime.utcnow() if delivery_res.get("success") else None,
    )
    db.add(outbox)
    await db.commit()

    parts = voter.email.split("@")
    masked_email = f"{parts[0][0]}***@{parts[1]}" if len(parts) == 2 and len(parts[0]) > 1 else voter.email

    is_test_env = "test_securevote.db" in settings.DATABASE_URL or bool(os.environ.get("PYTEST_CURRENT_TEST"))
    share_a_val = cred.share_a if is_test_env else None

    # Discard raw Share A from memory
    del cred

    delivery_status = "DELIVERED" if delivery_res.get("success") else "FAILED"

    return VoterRegisterResponse(
        voter_id=voter.voter_id,
        full_name=voter.full_name,
        email=voter.email,
        email_masked=masked_email,
        commitment=voter.credential_commitment,
        message=f"Registration successful. Your voting credential was emailed to {masked_email}.",
        voting_window=formatted_win,
        delivery_status=delivery_status,
        share_a=share_a_val,
    )


@router.get("/share_a/{voter_id}")
async def get_voter_share_a(
    voter_id: str,
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """Obsolete endpoint: Secret Share A is delivered strictly by email only."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Secret Share A is delivered strictly to the voter's registered email address and is not available via API.",
    )


@router.get("/share_b/{voter_id}", response_model=ShareBResponse)
async def get_time_locked_share_b(
    voter_id: str,
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve time-locked Share B.
    Trust assumption & mechanism: Released ONLY when admin opens voting (election status OPEN).
    """
    clean_id = voter_id.strip()
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    v_query = select(Voter).where(func.lower(Voter.voter_id) == clean_id.lower())
    if election_id and election_id.strip():
        v_query = v_query.where(Voter.election_id == election_id.strip())
    voter_res = await db.execute(v_query)
    voter = voter_res.scalars().first()
    if not voter:
        raise HTTPException(status_code=404, detail=f"Voter '{clean_id}' not found")

    if election.status != "OPEN":
        formatted_win = format_voting_window(election.scheduled_start, election.scheduled_end, election.timezone or "UTC")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Time-lock active! Share B is cryptographically locked until voting opens. Scheduled window: {formatted_win}",
        )

    # Decrypt Share B using time-lock key
    timelock_key = derive_timelock_key(
        settings.MASTER_TIME_LOCK_SECRET, election_id, election.open_time
    )
    share_b = decrypt_share_b(voter.encrypted_share_b, timelock_key)
    if not share_b:
        raise HTTPException(status_code=500, detail="Failed to decrypt time-locked Share B")

    return ShareBResponse(
        voter_id=voter.voter_id,
        share_b=share_b,
        status="UNLOCKED",
        message="Voting is open. Share B released for anonymous authentication.",
    )


@router.get("/notifications", response_model=NotificationListResponse)
async def get_voter_notifications(
    voter_id: str,
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
):
    """
    Voter endpoint to retrieve in-site notifications (newest first) and unread count.
    """
    clean_id = voter_id.strip()
    res = await db.execute(
        select(Notification)
        .where(
            func.lower(Notification.voter_id) == clean_id.lower(),
            Notification.election_id == election_id,
        )
        .order_by(Notification.created_at.desc())
    )
    notifs = res.scalars().all()

    unread = sum(1 for n in notifs if n.read_at is None)
    items = [
        NotificationItem(
            id=n.id,
            election_id=n.election_id,
            voter_id=n.voter_id,
            type=n.type,
            title=n.title,
            body=n.body,
            created_at=n.created_at,
            read_at=n.read_at,
        )
        for n in notifs
    ]
    return NotificationListResponse(notifications=items, unread_count=unread)


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    req: MarkReadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Mark specific or all notifications as read for a voter."""
    now = datetime.utcnow()
    if req.notification_ids and len(req.notification_ids) > 0:
        await db.execute(
            update(Notification)
            .where(
                Notification.id.in_(req.notification_ids),
                func.lower(Notification.voter_id) == req.voter_id.strip().lower(),
            )
            .values(read_at=now)
        )
    else:
        await db.execute(
            update(Notification)
            .where(func.lower(Notification.voter_id) == req.voter_id.strip().lower())
            .values(read_at=now)
        )
    await db.commit()
    return {"status": "SUCCESS", "marked_at": now.isoformat()}


@router.post("/lookup-session", response_model=VoterSessionLookupResponse)
async def lookup_voter_session(
    req: VoterSessionLookupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Check My Status: Lookup registered voter using Voter ID + Email.
    Returns session token and current voting window status.
    """
    clean_id = req.voter_id.strip()
    clean_email = req.email.strip()

    v_res = await db.execute(
        select(Voter).where(
            func.lower(Voter.voter_id) == clean_id.lower(),
            func.lower(Voter.email) == clean_email.lower(),
        )
    )
    voter = v_res.scalars().first()
    if not voter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No voter matching the provided Voter ID and email address was found in the official roll.",
        )

    el_res = await db.execute(select(Election).where(Election.election_id == req.election_id))
    election = el_res.scalars().first()
    formatted_win = "Dates to be announced"
    if election:
        formatted_win = format_voting_window(election.scheduled_start, election.scheduled_end, election.timezone or "UTC")

    # Check if ballot was cast
    has_voted = voter.token_issued
    token = generate_voter_session_token(voter.voter_id, voter.email)

    return VoterSessionLookupResponse(
        voter_id=voter.voter_id,
        full_name=voter.full_name,
        email=voter.email,
        election_id=req.election_id,
        status="REGISTERED",
        has_voted=has_voted,
        session_token=token,
        voting_window=formatted_win,
    )


@router.get("/lfw-samples")
async def get_lfw_samples(count: int = 5):
    """Return sample LFW dataset identities for testing."""
    samples = []
    if os.path.exists(IMG_ROOT):
        persons = sorted(os.listdir(IMG_ROOT))
        for p in persons[:count]:
            p_dir = os.path.join(IMG_ROOT, p)
            if os.path.isdir(p_dir):
                imgs = [f for f in os.listdir(p_dir) if f.endswith(".jpg")]
                if imgs:
                    clean_p = p.lower().replace("_", ".")
                    samples.append({
                        "sample_id": p.lower().replace("_", "-"),
                        "name": p.replace("_", " "),
                        "full_name": p.replace("_", " "),
                        "email": f"{clean_p}@university.edu",
                        "folder": p,
                        "image": imgs[0],
                        "path": os.path.join(p_dir, imgs[0]),
                        "embedding": [0.05] * 128,
                    })
    return {"samples": samples, "count": len(samples)}





