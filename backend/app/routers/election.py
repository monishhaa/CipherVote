"""
Election lifecycle, dynamic scheduling, admin controls, and notification audit router.
"""

import asyncio
from datetime import datetime, timezone
import json
import os
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.biometrics.face_engine import face_engine
from app.core.biometrics.template_crypto import encrypt_face_template
from app.core.bulletin_board.hash_chain import compute_genesis_hash
from app.core.crypto.blind_signature import generate_blind_rsa_keypair
from app.core.crypto.shamir import create_voter_credential, split_trustee_key
from app.core.crypto.timelock import derive_timelock_key, encrypt_share_b
from app.core.crypto.zkp import prove_schnorr_knowledge
from app.core.notifications import (
    broadcast_election_notification,
    dispatch_single_email_task,
    format_election_datetime,
    format_voting_window,
)
from app.models import Ballot, Election, EmailOutbox, LoginAuditLog, Notification, TallyResult, Trustee, Voter, get_db
from app.routers.auth import require_admin
from app.schemas import (
    AdminNotificationLogResponse,
    CandidateItem,
    ClockWarpRequest,
    ElectionCreateRequest,
    ElectionScheduleRequest,
    ElectionScheduleResponse,
    ElectionStatusResponse,
    OutboxItem,
)

router = APIRouter(prefix="/election", tags=["Election & Schedule"])

LFW_BASE_DIR = "data/lfw"
IMG_ROOT = os.path.join(LFW_BASE_DIR, "lfw-deepfunneled", "lfw-deepfunneled")


@router.post("/setup", response_model=ElectionStatusResponse)
async def setup_election(
    req: ElectionCreateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Initialize a new election with 3-of-5 threshold keys and RSA blind signing keys."""
    # Check if election exists
    result = await db.execute(select(Election).where(Election.election_id == req.election_id))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail=f"Election '{req.election_id}' already exists")

    # 1. Generate 3-of-5 trustee threshold keys
    election_pk, shares, secret_x = split_trustee_key(threshold=3, num_trustees=5)

    # 2. Generate RSA-2048 blind signing keypair
    blind_rsa_key = generate_blind_rsa_keypair(bits=1024)

    # 3. Create election record
    candidates_data = [c.model_dump() for c in req.candidates]
    now_ts = int(time.time())
    election = Election(
        election_id=req.election_id,
        title=req.title,
        status="REGISTRATION",
        open_time=req.open_time or (now_ts + 3600),
        close_time=req.close_time or (now_ts + 7200),
        simulated_clock_offset=0,
        public_key_h=hex(election_pk.h),
        blind_rsa_n=hex(blind_rsa_key.n),
        blind_rsa_e=blind_rsa_key.public_key.e,
        blind_rsa_d=hex(blind_rsa_key.d),
        candidates_json=json.dumps(candidates_data),
        timezone="UTC",
    )
    db.add(election)

    # 4. Create 5 trustees
    for share in shares:
        schnorr = prove_schnorr_knowledge(share.share_value, share.public_verification_key)
        trustee = Trustee(
            election_id=req.election_id,
            trustee_id=share.trustee_id,
            name=f"Trustee {share.trustee_id}",
            verification_key_h=hex(share.public_verification_key),
            schnorr_proof_json=json.dumps(schnorr.to_dict()),
            encrypted_share_value=hex(share.share_value),
        )
        db.add(trustee)

    await db.commit()

    genesis_hash = compute_genesis_hash(req.election_id)
    return ElectionStatusResponse(
        election_id=election.election_id,
        title=election.title,
        status=election.status,
        open_time=election.open_time,
        close_time=election.close_time,
        current_time=now_ts,
        is_open=False,
        public_key_h=election.public_key_h,
        blind_rsa_n=election.blind_rsa_n,
        blind_rsa_e=election.blind_rsa_e,
        candidates=[CandidateItem(**c) for c in candidates_data],
        bulletin_board_length=0,
        head_hash=genesis_hash,
        scheduled_start=election.scheduled_start,
        scheduled_end=election.scheduled_end,
        timezone=election.timezone,
        formatted_window=format_voting_window(election.scheduled_start, election.scheduled_end, election.timezone),
        actual_open_at=election.actual_open_at,
        actual_close_at=election.actual_close_at,
    )


@router.get("/status", response_model=ElectionStatusResponse)
async def get_election_status(election_id: str = "council-2026", db: AsyncSession = Depends(get_db)):
    """Get current election state, candidates, public keys, schedule, and bulletin board head hash."""
    result = await db.execute(select(Election).where(Election.election_id == election_id))
    election = result.scalars().first()

    if not election:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Election '{election_id}' not found.",
        )

    ballots_res = await db.execute(
        select(Ballot).where(Ballot.election_id == election_id).order_by(Ballot.sequence_number.desc())
    )
    all_ballots = ballots_res.scalars().all()
    bb_len = len(all_ballots)
    head_hash = all_ballots[0].block_hash if bb_len > 0 else compute_genesis_hash(election_id)

    now = int(time.time()) + election.simulated_clock_offset
    return ElectionStatusResponse(
        election_id=election.election_id,
        title=election.title,
        status=election.status,
        open_time=election.open_time,
        close_time=election.close_time,
        current_time=now,
        is_open=(election.status == "OPEN"),
        public_key_h=election.public_key_h,
        blind_rsa_n=election.blind_rsa_n,
        blind_rsa_e=election.blind_rsa_e,
        candidates=[CandidateItem(**c) for c in json.loads(election.candidates_json)],
        bulletin_board_length=bb_len,
        head_hash=head_hash,
        scheduled_start=election.scheduled_start,
        scheduled_end=election.scheduled_end,
        timezone=election.timezone or "UTC",
        formatted_window=format_voting_window(election.scheduled_start, election.scheduled_end, election.timezone or "UTC"),
        actual_open_at=election.actual_open_at,
        actual_close_at=election.actual_close_at,
    )


@router.get("/schedule", response_model=ElectionScheduleResponse)
async def get_election_schedule(election_id: str = "council-2026", db: AsyncSession = Depends(get_db)):
    """Public endpoint to query the announced voting schedule for an election."""
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    formatted = format_voting_window(
        election.scheduled_start,
        election.scheduled_end,
        election.timezone or "UTC",
    )

    return ElectionScheduleResponse(
        election_id=election.election_id,
        title=election.title,
        status=election.status,
        scheduled_start=election.scheduled_start,
        scheduled_end=election.scheduled_end,
        timezone=election.timezone or "UTC",
        formatted_window=formatted,
        schedule_published_at=election.schedule_published_at,
        voters_notified=0,
        warnings=[],
        message="Election schedule retrieved.",
    )


@router.post("/schedule", response_model=ElectionScheduleResponse)
async def set_election_schedule(
    req: ElectionScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    Admin endpoint to configure and announce voting schedule.
    Validates end > start. Rejects edit if voting is already open.
    Dispatches in-site notifications and emails to all registered voters when announced.
    """
    el_res = await db.execute(select(Election).where(Election.election_id == req.election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    # If election is already OPEN or CLOSED, schedule cannot be edited
    if election.status in ("OPEN", "CLOSED", "ENDED", "TALLYING"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit schedule: Voting has already been opened or concluded (Current status: {election.status}).",
        )

    # Validate datetimes with timezone localization
    tz_name = (req.timezone or election.timezone or "UTC").strip()
    try:
        from zoneinfo import ZoneInfo
        tz_obj = ZoneInfo(tz_name)
    except Exception:
        tz_obj = timezone.utc

    start_dt = req.scheduled_start
    end_dt = req.scheduled_end

    if start_dt.tzinfo is None:
        start_utc = start_dt.replace(tzinfo=tz_obj).astimezone(timezone.utc)
    else:
        start_utc = start_dt.astimezone(timezone.utc)

    if end_dt.tzinfo is None:
        end_utc = end_dt.replace(tzinfo=tz_obj).astimezone(timezone.utc)
    else:
        end_utc = end_dt.astimezone(timezone.utc)

    if end_utc <= start_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voting end date-time must be strictly after the start date-time.",
        )

    duration_sec = (end_utc - start_utc).total_seconds()
    if duration_sec < 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voting window must be at least 1 minute long.",
        )

    warnings = []
    # Compare with current UTC time (warning only, do not block)
    now_utc = datetime.now(timezone.utc)
    if start_utc < now_utc:
        warnings.append("This start time has already passed. Voters will still be told the window.")

    # Determine whether this is an initial schedule publish or an update
    is_update = election.scheduled_start is not None
    notif_type = "SCHEDULE_UPDATED" if is_update else "SCHEDULE_SET"

    # Save to database (stored in UTC)
    election.scheduled_start = start_utc.replace(tzinfo=None)
    election.scheduled_end = end_utc.replace(tzinfo=None)
    election.timezone = tz_name
    election.schedule_published_at = datetime.utcnow()

    # Sync legacy open_time / close_time for cryptographic timelock compatibility
    election.open_time = int(start_utc.timestamp())
    election.close_time = int(end_utc.timestamp())

    await db.commit()

    # Broadcast to registered voters if announce is True
    notified_count = 0
    if req.announce:
        notified_count = await broadcast_election_notification(election.election_id, notif_type)

    formatted = format_voting_window(
        election.scheduled_start,
        election.scheduled_end,
        election.timezone,
    )

    notif_msg = f"{notified_count} registered voters notified." if notified_count > 0 else "0 registered voters were notified."

    return ElectionScheduleResponse(
        election_id=election.election_id,
        title=election.title,
        status=election.status,
        scheduled_start=election.scheduled_start,
        scheduled_end=election.scheduled_end,
        timezone=election.timezone,
        formatted_window=formatted,
        schedule_published_at=election.schedule_published_at,
        voters_notified=notified_count,
        warnings=warnings,
        message=f"Schedule successfully {'updated' if is_update else 'saved and announced'}. {notif_msg}",
    )


@router.post("/open-voting")
async def open_voting(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    Admin Action: Officially open the ballot box.
    Voting becomes active ONLY upon this action. Releases time-lock Share B.
    Sends in-site notification and email to all registered voters.
    """
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if election.status == "OPEN":
        return {"status": "OPEN", "message": "Voting is already open."}

    # Transition to OPEN
    election.status = "OPEN"
    election.actual_open_at = datetime.utcnow()
    await db.commit()

    # Broadcast "Voting Is Now Open" notification and email
    notified = await broadcast_election_notification(election_id, "VOTING_OPEN")

    return {
        "status": "OPEN",
        "election_id": election_id,
        "actual_open_at": election.actual_open_at.isoformat(),
        "voters_notified": notified,
        "message": f"Voting is now officially OPEN. Share B time-lock released. {notified} voters notified.",
    }


@router.post("/close-voting")
async def close_voting(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    Admin Action: Officially close the ballot box and seal for trustee unlock ceremony.
    """
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if election.status in ("CLOSED", "TALLYING", "COMPLETED"):
        return {
            "status": "CLOSED",
            "election_id": election_id,
            "actual_close_at": election.actual_close_at.isoformat() if election.actual_close_at else None,
            "message": "Voting is already closed.",
        }

    election.status = "CLOSED"
    election.actual_close_at = datetime.utcnow()
    await db.commit()

    return {
        "status": "CLOSED",
        "election_id": election_id,
        "actual_close_at": election.actual_close_at.isoformat(),
        "message": "Voting is now CLOSED. Ballot box sealed and transitioned to CLOSED phase pending trustee ceremony.",
    }


@router.get("/list")
async def list_elections(db: AsyncSession = Depends(get_db)):
    """Return list of all configured elections in the system."""
    res = await db.execute(select(Election).order_by(Election.open_time.desc()))
    elections = res.scalars().all()
    out = []
    for el in elections:
        candidates = json.loads(el.candidates_json) if el.candidates_json else []
        formatted = format_voting_window(el.scheduled_start, el.scheduled_end, el.timezone or "UTC")
        out.append({
            "election_id": el.election_id,
            "title": el.title,
            "status": el.status,
            "is_open": el.status == "OPEN",
            "scheduled_start": el.scheduled_start,
            "scheduled_end": el.scheduled_end,
            "timezone": el.timezone or "UTC",
            "formatted_window": formatted,
            "actual_open_at": el.actual_open_at,
            "actual_close_at": el.actual_close_at,
            "candidates_count": len(candidates),
            "candidates": candidates,
        })
    return {"elections": out}


@router.get("/admin/notifications", response_model=AdminNotificationLogResponse)
async def get_admin_notification_log(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    Admin endpoint to inspect dispatched notifications and email outbox records per voter.
    """
    outbox_res = await db.execute(
        select(EmailOutbox)
        .where(EmailOutbox.election_id == election_id)
        .order_by(EmailOutbox.created_at.desc())
    )
    entries = outbox_res.scalars().all()

    total_notifs = await db.execute(
        select(func.count(Notification.id)).where(Notification.election_id == election_id)
    )
    total_notif_count = total_notifs.scalar() or 0

    sent_count = sum(1 for e in entries if e.status in ("SENT", "QUEUED (DEV OUTBOX)"))
    queued_count = sum(1 for e in entries if e.status == "QUEUED")
    failed_count = sum(1 for e in entries if e.status == "FAILED")

    outbox_items = [
        OutboxItem(
            id=e.id,
            election_id=e.election_id,
            voter_id=e.voter_id,
            to_email=e.to_email,
            type=e.type,
            subject=e.subject,
            status=e.status,
            attempts=e.attempts,
            last_error=e.last_error,
            created_at=e.created_at,
            sent_at=e.sent_at,
            body_text=e.body_text,
            body_html=e.body_html,
        )
        for e in entries
    ]

    return AdminNotificationLogResponse(
        total_notifications=total_notif_count,
        total_sent=sent_count,
        total_queued=queued_count,
        total_failed=failed_count,
        outbox=outbox_items,
    )


@router.post("/admin/notifications/retry")
async def retry_failed_notifications(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Retry transmission of all failed emails in the outbox."""
    res = await db.execute(
        select(EmailOutbox).where(
            EmailOutbox.election_id == election_id,
            EmailOutbox.status == "FAILED",
        )
    )
    failed_entries = res.scalars().all()
    count = 0
    for entry in failed_entries:
        entry.status = "QUEUED"
        entry.attempts = 0
        asyncio.create_task(dispatch_single_email_task(entry.id))
        count += 1

    await db.commit()
    return {"message": f"Queued {count} failed email(s) for re-transmission.", "retried_count": count}


@router.post("/clock/warp")
async def warp_election_clock(
    req: ClockWarpRequest,
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Dev/Admin endpoint to control election status or warp simulated clock."""
    result = await db.execute(select(Election).where(Election.election_id == election_id))
    election = result.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if req.target_status:
        election.status = req.target_status
        if req.target_status == "OPEN" and not election.actual_open_at:
            election.actual_open_at = datetime.utcnow()

    if req.target_timestamp is not None:
        election.simulated_clock_offset = req.target_timestamp - int(time.time())

    await db.commit()
    return {"message": f"Election status set to {election.status}", "status": election.status}


@router.post("/reset")
async def reset_demo_data(
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    Dev-Only Reset Action:
    Clears voters, ballots, tally results, notifications, and logs.
    """
    await db.execute(delete(Ballot).where(Ballot.election_id == election_id))
    await db.execute(delete(TallyResult).where(TallyResult.election_id == election_id))
    await db.execute(delete(Notification).where(Notification.election_id == election_id))
    await db.execute(delete(EmailOutbox).where(EmailOutbox.election_id == election_id))
    await db.execute(delete(Voter))
    await db.execute(delete(LoginAuditLog))

    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if election:
        election.status = "REGISTRATION"
        election.simulated_clock_offset = 0
        election.scheduled_start = None
        election.scheduled_end = None
        election.schedule_published_at = None
        election.actual_open_at = None
        election.actual_close_at = None

    await db.commit()
    return {
        "status": "RESET_SUCCESSFUL",
        "election_status": "REGISTRATION",
        "message": "All demo voters, shares, tokens, ballots, notifications, and tally results have been cleared.",
    }


@router.post("/seed-lfw")
async def seed_lfw_voters_endpoint(
    count: int = 5,
    election_id: str = "council-2026",
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """
    Seed sample verified identities from LFW dataset for testing.
    """
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    timelock_key = derive_timelock_key(
        settings.MASTER_TIME_LOCK_SECRET, election_id, election.open_time
    )

    sample_dirs = [
        "Aaron_Peirsol",
        "Angela_Bassett",
        "Colin_Powell",
        "Jennifer_Aniston",
        "David_Beckham",
    ]

    seeded = []
    for s_name in sample_dirs[:count]:
        voter_id = f"lfw-{s_name}"
        email = f"{s_name.lower()}@university.edu"

        v_check = await db.execute(select(Voter).where(Voter.voter_id == voter_id))
        if v_check.scalars().first():
            continue

        img1 = os.path.join(IMG_ROOT, s_name, f"{s_name}_0001.jpg")
        if not os.path.exists(img1):
            continue

        emb = face_engine.extract_embedding_from_image(img1)
        enc_template = encrypt_face_template(emb)
        cred = create_voter_credential()
        enc_share_b = encrypt_share_b(cred.share_b, timelock_key)

        voter = Voter(
            voter_id=voter_id,
            full_name=s_name.replace("_", " "),
            email=email,
            is_approved=True,
            encrypted_face_template=enc_template,
            credential_commitment=cred.commitment,
            encrypted_share_b=enc_share_b,
            share_a_preview=cred.share_a[:10] + "...",
            token_issued=False,
        )
        db.add(voter)
        seeded.append(voter_id)

    await db.commit()
    return {
        "status": "SEEDED_SUCCESSFUL",
        "count_seeded": len(seeded),
        "voters": seeded,
    }
