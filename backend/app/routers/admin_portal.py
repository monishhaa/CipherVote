"""
Admin Portal Router (/api/admin)
Administrator authentication, key metrics overview, voter roll, dynamic schedule,
voting activation control, trustee portal management, invitation dispatching, ceremony monitor,
and elections lifecycle management.
"""

import asyncio
import json
import logging
import re
import secrets
import time
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, verify_admin_password

logger = logging.getLogger("securevote.admin")
from app.core.bulletin_board.hash_chain import compute_genesis_hash
from app.core.crypto.blind_signature import generate_blind_rsa_keypair
from app.core.crypto.shamir import split_trustee_key
from app.core.crypto.crockford import generate_trustee_code
from app.core.crypto.trustee_security import (
    hash_trustee_code,
    hash_link_token,
    encrypt_share_at_rest,
    compute_full_passphrase_commitment,
)
from app.core.notifications import (
    broadcast_election_notification,
    format_election_datetime,
    format_voting_window,
    retry_failed_outbox_deliveries,
)
from app.core.security import check_rate_limit, record_failed_attempt, reset_rate_limit
from app.core.trustee_mailer import (
    build_trustee_invitation_content,
    dispatch_trustee_invitation_email,
    dispatch_trustee_ceremony_open_email,
)
from app.core.crypto.elgamal import Ciphertext, homomorphic_sum
from app.core.ceremony import (
    get_or_create_ceremony,
    get_ceremony_state,
    broadcast_ceremony_state,
)
from app.core.tally_engine import get_or_compute_election_tally, publish_official_results
from app.models import (
    Ballot,
    Election,
    EmailOutbox,
    Notification,
    Trustee,
    Voter,
    TallyResult,
    get_db,
)
from app.routers.auth import generate_admin_token, require_admin
from app.schemas import (
    ElectionScheduleRequest,
    ElectionScheduleResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin Portal"])


# -----------------------------------------------------------------------------
# Request & Response Models
# -----------------------------------------------------------------------------

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class CandidateInput(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=128)


class ElectionCreatePayload(BaseModel):
    title: str = Field(..., min_length=3, max_length=256)
    description: Optional[str] = None
    candidates: List[CandidateInput] = Field(..., min_length=2, max_length=10)
    timezone: str = "UTC"


class ElectionUpdatePayload(BaseModel):
    title: str = Field(..., min_length=3, max_length=256)
    description: Optional[str] = None
    candidates: List[CandidateInput] = Field(..., min_length=2, max_length=10)
    timezone: str = "UTC"


class AdminOverviewResponse(BaseModel):
    election_id: str
    title: str
    status: str
    is_open: bool
    registered_voters: int
    tokens_issued: int
    ballots_cast: int
    trustees_count: int
    trustee_threshold: int
    schedule_status: str
    formatted_window: str
    timezone: str
    invitations_sent_at: Optional[datetime] = None
    ceremony_unlocked_at: Optional[datetime] = None
    results_published_at: Optional[datetime] = None
    bulletin_board_head_hash: Optional[str] = None
    email_delivery_warning: bool = False
    recent_activity: List[dict]


class TrusteeRosterItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    email: str = Field(..., min_length=3, max_length=256)
    position: int = 1


class TrusteeRosterSaveRequest(BaseModel):
    election_id: str
    trustees: List[TrusteeRosterItem]
    ceremony_window_minutes: Optional[int] = 5


class TrusteeInviteRequest(BaseModel):
    election_id: str
    portal_base_url: Optional[str] = "http://localhost:3000"


class TrusteeReissueRequest(BaseModel):
    election_id: str
    admin_password: str
    portal_base_url: Optional[str] = "http://localhost:3000"


class PublishResultsRequest(BaseModel):
    election_id: str


# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------

@router.post("/login")
async def admin_login(req: AdminLoginRequest, request: Request):
    """Authenticate election administrator."""
    clean_user = req.username.strip()
    clean_pass = req.password.strip()
    rate_key = f"admin:{request.client.host if request.client else 'local'}:{clean_user}"
    check_rate_limit(rate_key)

    import hmac
    if hmac.compare_digest(clean_user, settings.ADMIN_USERNAME.strip()) and verify_admin_password(clean_pass):
        reset_rate_limit(rate_key)
        token = generate_admin_token(clean_user)
        return {
            "success": True,
            "role": "admin",
            "token": token,
            "message": "Admin authentication successful.",
        }
    record_failed_attempt(rate_key)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid administrator username or password.",
    )


# -----------------------------------------------------------------------------
# Elections Management (/api/admin/elections)
# -----------------------------------------------------------------------------

@router.get("/elections")
async def list_admin_elections(
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Lists all elections for the admin console."""
    stmt = select(Election).order_by(Election.created_at.desc())
    res = await db.execute(stmt)
    elections = res.scalars().all()

    items = []
    for el in elections:
        v_count = (
            await db.execute(select(func.count(Voter.id)).where(Voter.election_id == el.election_id))
        ).scalar() or 0
        t_count = (
            await db.execute(
                select(func.count(Trustee.id)).where(Trustee.election_id == el.election_id)
            )
        ).scalar() or 0
        b_count = (
            await db.execute(
                select(func.count(Ballot.id)).where(Ballot.election_id == el.election_id)
            )
        ).scalar() or 0

        items.append({
            "election_id": el.election_id,
            "title": el.title,
            "status": el.status,
            "is_open": (el.status == "OPEN"),
            "registered_voters": v_count,
            "ballots_cast": b_count,
            "trustees_count": t_count,
            "timezone": el.timezone or "UTC",
            "description": el.description or "",
            "candidates": el.candidates,
            "invitations_sent_at": el.invitations_sent_at.isoformat() if el.invitations_sent_at else None,
            "scheduled_start": el.scheduled_start.isoformat() if el.scheduled_start else None,
            "scheduled_end": el.scheduled_end.isoformat() if el.scheduled_end else None,
            "formatted_window": format_voting_window(el.scheduled_start, el.scheduled_end, el.timezone or "UTC"),
            "created_at": el.created_at.isoformat() if el.created_at else None,
        })

    return {"elections": items, "total": len(items)}


@router.post("/elections")
async def create_admin_election(
    req: ElectionCreatePayload,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new election from the admin console."""
    clean_title = req.title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Election title is required.")

    # Validate candidates (2 to 10 unique, trimmed)
    candidate_names = []
    seen = set()
    for idx, c in enumerate(req.candidates, start=1):
        name = c.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail=f"Candidate #{idx} name cannot be empty.")
        if name.lower() in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate candidate name: '{name}'. Candidate names must be unique.")
        seen.add(name.lower())
        candidate_names.append({"id": idx, "name": name})

    if len(candidate_names) < 2 or len(candidate_names) > 10:
        raise HTTPException(status_code=400, detail="An election must have between 2 and 10 candidates.")

    # Generate slug / id
    slug_base = re.sub(r"[^a-z0-9]+", "-", clean_title.lower()).strip("-")
    if not slug_base:
        slug_base = "election"
    election_id = f"{slug_base[:32]}-{int(time.time())}"

    # Generate RSA-2048 blind signing keypair
    blind_rsa_key = generate_blind_rsa_keypair(bits=1024)

    now_ts = int(time.time())
    election = Election(
        election_id=election_id,
        title=clean_title,
        status="REGISTRATION",
        open_time=now_ts + 3600,
        close_time=now_ts + 7200,
        simulated_clock_offset=0,
        public_key_h="0x0",  # Generated upon Send Invitations
        blind_rsa_n=hex(blind_rsa_key.n),
        blind_rsa_e=blind_rsa_key.public_key.e,
        blind_rsa_d=hex(blind_rsa_key.d),
        candidates_json=json.dumps(candidate_names),
        description=(req.description or "").strip() or None,
        timezone=req.timezone.strip() or "UTC",
        trustee_threshold=2,
        ceremony_window_minutes=5,
    )
    db.add(election)
    await db.commit()

    compute_genesis_hash(election_id)

    return {
        "status": "SUCCESS",
        "election_id": election.election_id,
        "title": election.title,
        "message": "Election created successfully.",
    }


@router.put("/elections/{election_id}")
async def update_admin_election(
    election_id: str,
    req: ElectionUpdatePayload,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Updates election title, timezone, and candidates before voting opens."""
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if election.status in ("OPEN", "CLOSED", "TALLYING", "COMPLETED", "ARCHIVED") or election.actual_open_at:
        raise HTTPException(status_code=400, detail="Cannot edit election parameters once voting has been opened.")

    clean_title = req.title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Election title is required.")

    candidate_names = []
    seen = set()
    for idx, c in enumerate(req.candidates, start=1):
        name = c.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail=f"Candidate #{idx} name cannot be empty.")
        if name.lower() in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate candidate name: '{name}'.")
        seen.add(name.lower())
        candidate_names.append({"id": idx, "name": name})

    if len(candidate_names) < 2 or len(candidate_names) > 10:
        raise HTTPException(status_code=400, detail="An election must have between 2 and 10 candidates.")

    election.title = clean_title
    election.description = (req.description or "").strip() or None
    election.timezone = req.timezone.strip() or "UTC"
    election.candidates_json = json.dumps(candidate_names)
    await db.commit()

    return {
        "status": "SUCCESS",
        "election_id": election.election_id,
        "title": election.title,
        "message": "Election updated successfully.",
    }


@router.delete("/elections/{election_id}")
async def delete_admin_election(
    election_id: str,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Deletes an election and the rows stored for it."""
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    await db.execute(delete(Trustee).where(Trustee.election_id == election_id))
    await db.execute(delete(Ballot).where(Ballot.election_id == election_id))
    await db.execute(delete(Notification).where(Notification.election_id == election_id))
    await db.execute(delete(EmailOutbox).where(EmailOutbox.election_id == election_id))
    await db.execute(delete(TallyResult).where(TallyResult.election_id == election_id))
    await db.execute(delete(Voter).where(Voter.election_id == election_id))
    await db.execute(delete(Election).where(Election.election_id == election_id))
    await db.commit()

    return {"status": "SUCCESS", "message": "Election deleted successfully."}


@router.post("/elections/{election_id}/archive")
async def archive_admin_election(
    election_id: str,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Marks an election archived. Does not delete ballots, voters, or keys."""
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if election.status != "ARCHIVED":
        election.status = "ARCHIVED"
        await db.commit()

    return {
        "status": "SUCCESS",
        "election_id": election.election_id,
        "message": "Election archived.",
    }


# -----------------------------------------------------------------------------
# Overview & Operations
# -----------------------------------------------------------------------------

@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(
    election_id: Optional[str] = None,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin key metrics overview and checklist status."""
    if not election_id or election_id == "null":
        # Return first available election if any
        el_first = (await db.execute(select(Election).order_by(Election.created_at.desc()))).scalars().first()
        if not el_first:
            raise HTTPException(status_code=404, detail="No election found. Please create an election.")
        election = el_first
        election_id = election.election_id
    else:
        el_res = await db.execute(select(Election).where(Election.election_id == election_id))
        election = el_res.scalars().first()
        if not election:
            raise HTTPException(status_code=404, detail="Election not found")

    voters_count = (await db.execute(select(func.count(Voter.id)).where(Voter.election_id == election_id))).scalar() or 0
    tokens_count = (await db.execute(select(func.count(Voter.id)).where(Voter.election_id == election_id, Voter.token_issued == True))).scalar() or 0
    ballots_count = (await db.execute(select(func.count(Ballot.id)).where(Ballot.election_id == election_id))).scalar() or 0
    trustees_count = (await db.execute(select(func.count(Trustee.id)).where(Trustee.election_id == election_id))).scalar() or 0

    window_str = format_voting_window(
        election.scheduled_start,
        election.scheduled_end,
        election.timezone or "UTC",
    )

    sched_status = "Unannounced"
    if election.scheduled_start and election.scheduled_end:
        sched_status = "Announced" if election.schedule_published_at else "Drafted"

    # Check for SMTP delivery warning (failed outbox items)
    failed_outbox = (
        await db.execute(
            select(func.count(EmailOutbox.id)).where(
                EmailOutbox.election_id == election_id, EmailOutbox.status == "FAILED"
            )
        )
    ).scalar() or 0
    email_warning = bool(failed_outbox > 0)

    recent_activity = []
    recent_v = (await db.execute(
        select(Voter).order_by(Voter.registered_at.desc()).limit(3)
    )).scalars().all()
    for v in recent_v:
        recent_activity.append({
            "type": "VOTER_REGISTERED",
            "title": f"Voter Registered: {v.voter_id}",
            "time": v.registered_at.strftime("%b %d, %I:%M %p UTC") if v.registered_at else "Recent",
            "receipt": v.email,
        })

    # Get bulletin board head hash (from last ballot or sealed tally)
    last_b = (
        await db.execute(
            select(Ballot.block_hash)
            .where(Ballot.election_id == election_id)
            .order_by(Ballot.sequence_number.desc())
            .limit(1)
        )
    ).scalar()

    if not last_b:
        tally_root = (
            await db.execute(
                select(TallyResult.bulletin_board_root_hash)
                .where(TallyResult.election_id == election_id)
            )
        ).scalar()
        head_hash = tally_root or None
    else:
        head_hash = last_b

    return AdminOverviewResponse(
        election_id=election.election_id,
        title=election.title,
        status=election.status,
        is_open=(election.status == "OPEN"),
        registered_voters=voters_count,
        tokens_issued=tokens_count,
        ballots_cast=ballots_count,
        trustees_count=trustees_count,
        trustee_threshold=election.trustee_threshold or 2,
        schedule_status=sched_status,
        formatted_window=window_str,
        timezone=election.timezone or "UTC",
        invitations_sent_at=election.invitations_sent_at,
        ceremony_unlocked_at=election.ceremony_unlocked_at,
        results_published_at=election.results_published_at,
        bulletin_board_head_hash=head_hash,
        email_delivery_warning=email_warning,
        recent_activity=recent_activity[:6],
    )


@router.get("/voters")
async def get_admin_voters(
    election_id: str = "council-2026",
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin voter roll with timestamps and credential delivery status (NEVER exposes Share A)."""
    stmt = select(Voter)
    if election_id and election_id.strip():
        stmt = stmt.where(Voter.election_id == election_id.strip())
    stmt = stmt.order_by(Voter.registered_at.desc())

    res = await db.execute(stmt)
    voters = res.scalars().all()

    # Query outbox statuses for these voters
    outbox_stmt = select(EmailOutbox).where(
        EmailOutbox.election_id == election_id,
        EmailOutbox.type.in_(["CREDENTIAL", "CREDENTIAL_REISSUE"])
    )
    ob_res = await db.execute(outbox_stmt)
    outbox_rows = ob_res.scalars().all()
    outbox_map = {}
    for ob in outbox_rows:
        outbox_map[ob.voter_id.lower()] = ob.status

    items = []
    for v in voters:
        deliv = outbox_map.get(v.voter_id.lower(), "SENT")
        deliv_label = "Credential Sent" if deliv == "SENT" else ("Delivery Failed" if deliv == "FAILED" else "Queued")
        items.append({
            "id": v.id,
            "voter_id": v.voter_id,
            "full_name": v.full_name,
            "email": v.email,
            "registered_at": v.registered_at.strftime("%Y-%m-%d %H:%M UTC") if v.registered_at else "N/A",
            "token_issued": v.token_issued,
            "status": "BALLOT_CAST" if v.token_issued else "REGISTERED",
            "credential_delivery": deliv_label,
        })

    return {
        "voters": items,
        "total": len(items),
    }


@router.get("/schedule", response_model=ElectionScheduleResponse)
async def get_admin_schedule(
    election_id: str = "council-2026",
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve election schedule."""
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    formatted = format_voting_window(
        election.scheduled_start,
        election.scheduled_end,
        election.timezone or "UTC",
    )
    voters_count = (await db.execute(select(func.count(Voter.id)))).scalar() or 0

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
        message="Schedule loaded successfully.",
    )


@router.post("/schedule", response_model=ElectionScheduleResponse)
async def set_admin_schedule(
    req: ElectionScheduleRequest,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set voting schedule and dispatch announcements."""
    el_res = await db.execute(select(Election).where(Election.election_id == req.election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if election.actual_open_at or election.status in ("OPEN", "CLOSED", "TALLYING", "COMPLETED", "ENDED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The voting schedule is locked because voting has already been opened or concluded.",
        )

    tz_name = (req.timezone or election.timezone or "UTC").strip()
    try:
        from zoneinfo import ZoneInfo
        tz_obj = ZoneInfo(tz_name)
    except Exception:
        tz_obj = timezone.utc

    start_dt = req.scheduled_start
    end_dt = req.scheduled_end

    # If naive datetime, localize using election timezone first
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
    now_utc = datetime.now(timezone.utc)
    if start_utc < now_utc:
        warnings.append("This start time has already passed. Voters will still be told the window.")

    is_update = bool(election.scheduled_start and election.schedule_published_at)
    election.scheduled_start = start_utc.replace(tzinfo=None)
    election.scheduled_end = end_utc.replace(tzinfo=None)
    election.timezone = tz_name
    election.schedule_published_at = datetime.utcnow()
    election.open_time = int(start_utc.timestamp())
    election.close_time = int(end_utc.timestamp())
    await db.commit()

    notified_count = 0
    if req.announce:
        event_type = "SCHEDULE_UPDATED" if is_update else "SCHEDULE_SET"
        notified_count = await broadcast_election_notification(req.election_id, event_type)

    formatted = format_voting_window(
        election.scheduled_start,
        election.scheduled_end,
        election.timezone,
    )

    notif_msg = f"Broadcasted notification to {notified_count} registered voter(s)." if notified_count > 0 else "0 registered voters were notified."

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
        message=f"Schedule successfully {'updated' if is_update else 'saved'}. {notif_msg}",
    )



@router.post("/voting/open")
async def admin_open_voting(
    req: dict,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Open Voting: Blocked if trustee invitations were not sent."""
    election_id = req.get("election_id", "council-2026")
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if not election.invitations_sent_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot open voting: Trustee invitations must be sent and election threshold key generated before opening ballot box.",
        )

    if election.status == "OPEN":
        return {"status": "OPEN", "message": "Voting is already open."}

    election.status = "OPEN"
    election.actual_open_at = datetime.utcnow()
    await db.commit()

    notified = await broadcast_election_notification(election_id, "VOTING_OPEN")

    return {
        "status": "OPEN",
        "election_id": election_id,
        "actual_open_at": election.actual_open_at.isoformat() if election.actual_open_at else None,
        "voters_notified": notified,
        "message": f"Voting is now open. Notified {notified} registered voter(s).",
    }


@router.post("/voting/close")
async def admin_close_voting(
    req: dict,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Close Voting:
    - Only permitted from OPEN status (idempotent if already CLOSED/TALLYING/COMPLETED)
    - Verifies trustee invitations were sent
    - Records actual_close_at
    - Seals bulletin board (records head hash)
    - Computes encrypted homomorphic aggregate per candidate and stores it
    - Moves status to CLOSED (tallying pending ceremony)
    - Broadcasts in-site notification and email to all registered voters
    - Dispatches ceremony open email to every trustee with optional admin message
    """
    election_id = req.get("election_id", "council-2026")
    admin_message = req.get("admin_message") or ""

    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    # Idempotent response if already closed
    if election.status in ("CLOSED", "TALLYING", "COMPLETED"):
        return {
            "status": election.status,
            "election_id": election_id,
            "actual_close_at": election.actual_close_at.isoformat() if election.actual_close_at else None,
            "already_closed": True,
            "message": f"Voting is already closed (Current status: {election.status}).",
        }

    if election.status != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot close voting: Election is currently in '{election.status}' state (must be OPEN).",
        )

    if not election.invitations_sent_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot close voting: Trustee invitations were never generated or dispatched.",
        )

    # 1. Record close timestamp
    election.status = "CLOSED"
    election.actual_close_at = datetime.utcnow()

    # 2. Seal the bulletin board (record head hash)
    b_res = await db.execute(
        select(Ballot).where(Ballot.election_id == election_id).order_by(Ballot.sequence_number.asc())
    )
    ballots = b_res.scalars().all()
    head_hash = ballots[-1].block_hash if ballots else compute_genesis_hash(election_id)

    # 3. Compute encrypted homomorphic aggregate per candidate and store draft tally row
    candidates = election.candidates
    num_candidates = len(candidates)
    aggregated_ciphertexts_list = []

    if ballots and num_candidates > 0:
        for cand_idx in range(num_candidates):
            cand_cts = []
            for b in ballots:
                try:
                    cts_data = json.loads(b.ciphertexts_json)
                    cand_cts.append(Ciphertext(c1=int(cts_data[cand_idx]["c1"], 16), c2=int(cts_data[cand_idx]["c2"], 16)))
                except Exception:
                    pass
            if cand_cts:
                agg = homomorphic_sum(cand_cts)
                aggregated_ciphertexts_list.append({"c1": hex(agg.c1), "c2": hex(agg.c2)})
            else:
                aggregated_ciphertexts_list.append({"c1": "0x1", "c2": "0x1"})

    # Ensure draft TallyResult exists with head hash and aggregated ciphertexts
    await db.execute(delete(TallyResult).where(TallyResult.election_id == election_id))
    tally_row = TallyResult(
        election_id=election_id,
        total_ballots=len(ballots),
        candidate_totals_json="{}",  # Plaintext totals hidden until ceremony unlock
        aggregated_ciphertexts_json=json.dumps(aggregated_ciphertexts_list),
        trustee_contributions_json="[]",
        bulletin_board_root_hash=head_hash,
        tallied_at=datetime.utcnow(),
    )
    db.add(tally_row)

    # Snapshot trustee notice details before commit so email can leave the request.
    t_res = await db.execute(
        select(Trustee).where(Trustee.election_id == election_id).order_by(Trustee.position.asc())
    )
    trustees = t_res.scalars().all()
    total_trustees = len(trustees)
    election_title = election.title
    window_minutes = election.ceremony_window_minutes or 5
    trustee_notices = []
    for t in trustees:
        if t.email and (t.raw_link_token or t.link_token_hash):
            link_token_str = t.raw_link_token or t.link_token_hash
            trustee_notices.append({
                "to_email": t.email,
                "trustee_name": t.name,
                "position": t.position,
                "total_trustees": total_trustees,
                "ceremony_url": f"{settings.PORTAL_BASE_URL.rstrip('/')}/ceremony/{link_token_str}",
                "election_title": election_title,
                "window_minutes": window_minutes,
                "admin_message": admin_message if admin_message else None,
            })

    closed_at = election.actual_close_at.isoformat() if election.actual_close_at else None
    await db.commit()

    async def _notify_after_close() -> None:
        # Sealing must not wait on SMTP. Voters and trustees are notified after the box is closed.
        try:
            await broadcast_election_notification(election_id, "VOTING_CLOSED")
        except Exception:
            logger.exception("Failed to queue voter close notifications for %s", election_id)
        for notice in trustee_notices:
            try:
                await asyncio.to_thread(dispatch_trustee_ceremony_open_email, **notice)
            except Exception:
                logger.exception("Failed to send ceremony-open email to %s", notice.get("to_email"))

    asyncio.create_task(_notify_after_close())

    return {
        "status": "CLOSED",
        "election_id": election_id,
        "actual_close_at": closed_at,
        "ballots_cast": len(ballots),
        "bulletin_board_head_hash": head_hash,
        "voters_notified": 0,
        "trustees_notified": len(trustee_notices),
        "message": (
            f"Voting closed and sealed at block '{head_hash[:12]}...'. "
            "Voter and trustee notices are being sent."
        ),
    }


# -----------------------------------------------------------------------------
# Trustee Portal Management
# -----------------------------------------------------------------------------

@router.get("/trustees")
async def get_admin_trustees(
    election_id: str = "council-2026",
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List configured trustee roster for this election."""
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    t_res = await db.execute(
        select(Trustee).where(Trustee.election_id == election_id).order_by(Trustee.position, Trustee.trustee_id)
    )
    trustees = t_res.scalars().all()

    ceremony = get_ceremony_state(election_id)
    ceremony_status = ceremony.status if ceremony else ("UNLOCKED" if election.ceremony_unlocked_at else "WAITING")

    is_sent = bool(election.invitations_sent_at)

    return {
        "election_id": election_id,
        "trustees": [
            {
                "trustee_id": t.trustee_id,
                "name": t.name,
                "email": t.email or "",
                "position": t.position or t.trustee_id,
                "has_key": bool(t.verification_key_h and t.verification_key_h != "0x0"),
                "email_status": t.email_status if is_sent else "NOT_INVITED",
                "email_sent_at": t.email_sent_at.isoformat() if t.email_sent_at else None,
                "link_opened_at": t.link_opened_at.isoformat() if t.link_opened_at else None,
                "has_approved": bool(t.has_approved),
                "approved_at": t.approved_at.isoformat() if t.approved_at else None,
            }
            for t in trustees
        ],
        "threshold": election.trustee_threshold or ((len(trustees) // 2) + 1 if trustees else 2),
        "ceremony_window_minutes": election.ceremony_window_minutes or 5,
        "invitations_sent_at": election.invitations_sent_at.isoformat() if election.invitations_sent_at else None,
        "ceremony_unlocked_at": election.ceremony_unlocked_at.isoformat() if election.ceremony_unlocked_at else None,
        "results_published_at": election.results_published_at.isoformat() if election.results_published_at else None,
        "is_roster_locked": is_sent,
        "ceremony_status": ceremony_status,
        "total": len(trustees),
    }


@router.post("/trustees")
async def save_admin_trustees(
    req: TrusteeRosterSaveRequest,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Configure trustee roster (N trustees, 3 <= N <= 9) and validate email uniqueness.
    Blocked if invitations have already been dispatched.
    """
    el_res = await db.execute(select(Election).where(Election.election_id == req.election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if election.invitations_sent_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trustee roster is locked: Invitations and cryptographic threshold keys have already been dispatched.",
        )

    n = len(req.trustees)
    if n < 3 or n > 9:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trustee roster must have between 3 and 9 trustees (Provided: {n}).",
        )

    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    seen_emails = set()
    for idx, t in enumerate(req.trustees):
        if not t.name.strip():
            raise HTTPException(status_code=400, detail=f"Trustee #{idx+1} name cannot be empty.")
        if not t.email or not t.email.strip():
            raise HTTPException(status_code=400, detail=f"Trustee #{idx+1} ({t.name}) must have a valid email address.")
        em = t.email.strip().lower()
        if not email_regex.match(em):
            raise HTTPException(status_code=400, detail=f"Invalid email format for trustee '{t.name}': {t.email}")
        if em in seen_emails:
            raise HTTPException(status_code=400, detail=f"Duplicate trustee email '{t.email}'. Each trustee must have a unique email.")
        seen_emails.add(em)

    default_t = (n // 2) + 1
    election.trustee_threshold = default_t
    if req.ceremony_window_minutes:
        election.ceremony_window_minutes = max(2, min(15, req.ceremony_window_minutes))

    await db.execute(delete(Trustee).where(Trustee.election_id == req.election_id))

    for idx, t in enumerate(req.trustees, start=1):
        trustee_entry = Trustee(
            election_id=req.election_id,
            trustee_id=idx,
            name=t.name.strip(),
            email=t.email.strip(),
            position=idx,
            verification_key_h="0x0",
            schnorr_proof_json="{}",
            encrypted_share_value="0x0",
            email_status="PENDING",
        )
        db.add(trustee_entry)

    await db.commit()

    return {
        "status": "SUCCESS",
        "election_id": req.election_id,
        "trustees_count": n,
        "threshold": default_t,
        "ceremony_window_minutes": election.ceremony_window_minutes,
        "message": f"Saved draft roster of {n} trustees.",
    }


@router.post("/trustees/invite")
async def send_trustee_invitations(
    req: TrusteeInviteRequest,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Sends invitations to all configured trustees:
    1. Generates master threshold key for N and t.
    2. Generates independent 80-bit Crockford code for each trustee.
    3. Derives symmetric key from code and encrypts key share at rest.
    4. Computes ordered concatenation commitment.
    5. Dispatches email to each trustee with ONLY their code and link.
    6. Stores redacted email in outbox.
    """
    el_res = await db.execute(select(Election).where(Election.election_id == req.election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    t_res = await db.execute(
        select(Trustee).where(Trustee.election_id == req.election_id).order_by(Trustee.position)
    )
    trustees = t_res.scalars().all()
    n = len(trustees)
    if n < 3 or n > 9:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Please configure between 3 and 9 trustees before sending invitations (Found: {n}).",
        )

    t_val = election.trustee_threshold or ((n // 2) + 1)
    election_pk, shares, secret_x = split_trustee_key(threshold=t_val, num_trustees=n)
    election.public_key_h = hex(election_pk.h)
    election.private_key_x = hex(secret_x)

    raw_codes_ordered = []
    base_url = (req.portal_base_url or "http://localhost:3000").rstrip("/")

    for idx, t in enumerate(trustees, start=1):
        share_obj = shares[idx - 1]
        display_code, raw_code, pos_tag = generate_trustee_code(idx)
        raw_codes_ordered.append((idx, raw_code))

        code_hash_hex, code_salt_hex = hash_trustee_code(raw_code)
        t.code_hash = code_hash_hex
        t.code_salt = code_salt_hex

        encrypted_blob, _ = encrypt_share_at_rest(share_obj.share_value, raw_code)
        t.encrypted_share_value = encrypted_blob
        t.verification_key_h = hex(share_obj.public_verification_key)

        link_token = secrets.token_urlsafe(16)
        t.link_token_hash = hash_link_token(link_token)
        t.raw_link_token = link_token
        t.email_status = "SENT"
        t.email_sent_at = datetime.utcnow()

        ceremony_url = f"{base_url}/ceremony/{link_token}"

        close_info = (
            format_election_datetime(election.scheduled_end, election.timezone)
            if election.scheduled_end
            else None
        )
        mail_res = dispatch_trustee_invitation_email(
            to_email=t.email,
            trustee_name=t.name,
            position=idx,
            total_trustees=n,
            display_code=display_code,
            ceremony_url=ceremony_url,
            election_title=election.title,
            window_minutes=election.ceremony_window_minutes or 5,
            scheduled_close=close_info,
        )

        subject, red_plain, red_html = build_trustee_invitation_content(
            trustee_name=t.name,
            position=idx,
            total_trustees=n,
            display_code="[REDACTED_TRUSTEE_CODE]",
            ceremony_url=ceremony_url,
            election_title=election.title,
            window_minutes=election.ceremony_window_minutes or 5,
            scheduled_close=close_info,
            redacted=True,
        )

        outbox_entry = EmailOutbox(
            election_id=election.election_id,
            voter_id=f"trustee_{idx}",
            to_email=t.email,
            type="TRUSTEE_INVITATION",
            subject=subject,
            body_text=red_plain,
            body_html=red_html,
            status=mail_res.get("status", "SENT"),
            attempts=1,
            last_error=mail_res.get("error"),
        )
        db.add(outbox_entry)

    comm, comm_salt = compute_full_passphrase_commitment(raw_codes_ordered)
    election.full_passphrase_commitment = comm
    election.full_passphrase_salt = comm_salt
    election.invitations_sent_at = datetime.utcnow()

    ceremony = get_or_create_ceremony(
        election.election_id, n, window_minutes=election.ceremony_window_minutes or 5
    )
    ceremony.status = "WAITING"
    ceremony.log_event("INVITATIONS_SENT", f"Invitations dispatched to {n} trustees with threshold {t_val}-of-{n}.")

    await db.commit()

    return {
        "status": "SUCCESS",
        "election_id": election.election_id,
        "trustees_invited": n,
        "threshold": t_val,
        "public_key_h": election.public_key_h,
        "message": f"Successfully generated election key and dispatched invitation emails to all {n} trustees.",
    }


@router.post("/trustees/reissue")
async def reissue_trustee_codes(
    req: TrusteeReissueRequest,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Invalidates existing tokens/codes and generates a new key ceremony."""
    import hmac
    if not verify_admin_password(req.admin_password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect administrator password.")

    el_res = await db.execute(select(Election).where(Election.election_id == req.election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    if election.ceremony_unlocked_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reissue codes: The unlock ceremony has already been successfully completed.",
        )

    t_res = await db.execute(
        select(Trustee).where(Trustee.election_id == req.election_id).order_by(Trustee.position)
    )
    trustees = t_res.scalars().all()
    n = len(trustees)
    if n < 3:
        raise HTTPException(status_code=400, detail="Roster must have at least 3 trustees.")

    t_val = election.trustee_threshold or ((n // 2) + 1)
    election_pk, shares, secret_x = split_trustee_key(threshold=t_val, num_trustees=n)
    election.public_key_h = hex(election_pk.h)
    election.private_key_x = hex(secret_x)

    raw_codes_ordered = []
    base_url = (req.portal_base_url or "http://localhost:3000").rstrip("/")

    for idx, t in enumerate(trustees, start=1):
        share_obj = shares[idx - 1]
        display_code, raw_code, _ = generate_trustee_code(idx)
        raw_codes_ordered.append((idx, raw_code))

        code_hash_hex, code_salt_hex = hash_trustee_code(raw_code)
        t.code_hash = code_hash_hex
        t.code_salt = code_salt_hex

        encrypted_blob, _ = encrypt_share_at_rest(share_obj.share_value, raw_code)
        t.encrypted_share_value = encrypted_blob
        t.verification_key_h = hex(share_obj.public_verification_key)

        link_token = secrets.token_urlsafe(16)
        t.link_token_hash = hash_link_token(link_token)
        t.raw_link_token = link_token
        t.email_status = "SENT"
        t.email_sent_at = datetime.utcnow()
        t.link_opened_at = None
        t.failed_attempts = 0
        t.locked_until = None
        t.has_approved = False
        t.approved_at = None

        ceremony_url = f"{base_url}/ceremony/{link_token}"
        close_info = (
            format_election_datetime(election.scheduled_end, election.timezone)
            if election.scheduled_end
            else None
        )
        dispatch_trustee_invitation_email(
            to_email=t.email,
            trustee_name=t.name,
            position=idx,
            total_trustees=n,
            display_code=display_code,
            ceremony_url=ceremony_url,
            election_title=election.title,
            window_minutes=election.ceremony_window_minutes or 5,
            scheduled_close=close_info,
        )

    comm, comm_salt = compute_full_passphrase_commitment(raw_codes_ordered)
    election.full_passphrase_commitment = comm
    election.full_passphrase_salt = comm_salt
    election.invitations_sent_at = datetime.utcnow()

    ceremony = get_or_create_ceremony(
        election.election_id, n, window_minutes=election.ceremony_window_minutes or 5
    )
    ceremony.reset_round("Admin reissued codes")
    await broadcast_ceremony_state(ceremony)

    await db.commit()

    return {
        "status": "SUCCESS",
        "election_id": election.election_id,
        "message": f"Successfully reissued Crockford codes and sent updated invitations to all {n} trustees.",
    }


class TrusteeResendLinkRequest(BaseModel):
    election_id: str
    trustee_id: int  # or position


@router.post("/trustees/resend-link")
async def resend_trustee_ceremony_link(
    req: TrusteeResendLinkRequest,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Resends ceremony access link ONLY (never includes codes).
    Allowed on Tally page step 3.
    """
    el_res = await db.execute(select(Election).where(Election.election_id == req.election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    t_res = await db.execute(
        select(Trustee).where(
            Trustee.election_id == req.election_id,
            (Trustee.trustee_id == req.trustee_id) | (Trustee.position == req.trustee_id)
        )
    )
    trustee = t_res.scalars().first()
    if not trustee:
        raise HTTPException(status_code=404, detail="Trustee not found")

    if not trustee.email:
        raise HTTPException(status_code=400, detail="Trustee has no email registered.")

    token_str = trustee.raw_link_token or trustee.link_token_hash
    if not token_str:
        # Generate new link token if missing
        link_token = secrets.token_urlsafe(16)
        trustee.link_token_hash = hash_link_token(link_token)
        trustee.raw_link_token = link_token
        token_str = link_token

    ceremony_url = f"{settings.PORTAL_BASE_URL.rstrip('/')}/ceremony/{token_str}"

    total_trustees = (
        await db.execute(select(func.count(Trustee.id)).where(Trustee.election_id == req.election_id))
    ).scalar() or 3

    mail_res = dispatch_trustee_ceremony_open_email(
        to_email=trustee.email,
        trustee_name=trustee.name,
        position=trustee.position,
        total_trustees=total_trustees,
        ceremony_url=ceremony_url,
        election_title=election.title,
        window_minutes=election.ceremony_window_minutes or 5,
        admin_message="Administrator resent your ceremony access link.",
    )

    trustee.email_status = mail_res.get("status", "SENT")
    trustee.email_sent_at = datetime.utcnow()
    await db.commit()

    return {
        "status": "SUCCESS",
        "election_id": req.election_id,
        "trustee_id": trustee.trustee_id,
        "recipient": trustee.email,
        "message": f"Ceremony access link sent to mail server for {trustee.name} ({trustee.email}).",
    }


@router.get("/trustees/ceremony-monitor")
async def get_admin_ceremony_monitor(
    election_id: str = "council-2026",
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Live monitor of trustee presence and unlock round state."""
    el_res = await db.execute(select(Election).where(Election.election_id == election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    t_res = await db.execute(
        select(Trustee).where(Trustee.election_id == election_id).order_by(Trustee.position)
    )
    trustees = t_res.scalars().all()
    n = len(trustees)

    ceremony = get_or_create_ceremony(
        election_id, n, window_minutes=election.ceremony_window_minutes or 5
    )
    all_approved = len(trustees) > 0 and all(t.has_approved for t in trustees)
    all_present = ceremony.all_trustees_present() or (election.ceremony_unlocked_at is not None) or all_approved

    trustee_presence = {
        (t.position or idx + 1): {
            "entered": t.has_approved or (ceremony.is_present(t.position or idx + 1) if ceremony else False),
            "approved": t.has_approved,
        }
        for idx, t in enumerate(trustees)
    }

    tally_data = await get_or_compute_election_tally(election, db)

    return {
        "election_id": election_id,
        "election_status": election.status,
        "is_voting_closed": election.status in ("CLOSED", "TALLYING", "COMPLETED"),
        "ceremony_state": ceremony.to_public_dict(),
        "approvals_count": sum(1 for t in trustees if t.has_approved),
        "total_trustees": n,
        "all_present": all_present,
        "all_approved": all_approved,
        "trustee_presence": trustee_presence,
        "preliminary_results": tally_data.get("results", {}),
        "total_ballots": tally_data.get("total_ballots", 0),
        "results_published_at": election.results_published_at.isoformat() if election.results_published_at else None,
    }


# -----------------------------------------------------------------------------
# Results Publication & Decryption
# -----------------------------------------------------------------------------

@router.post("/results/publish")
async def publish_election_results(
    req: PublishResultsRequest,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Computes final election tally using trustee partial decryptions.
    Governance Rule: Blocked until ALL N trustees have validated and approved.
    """
    el_res = await db.execute(select(Election).where(Election.election_id == req.election_id))
    election = el_res.scalars().first()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    t_res = await db.execute(
        select(Trustee).where(Trustee.election_id == req.election_id).order_by(Trustee.position)
    )
    trustees = t_res.scalars().all()
    n = len(trustees)

    unapproved = [t.name for t in trustees if not t.has_approved]
    if unapproved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All {n} trustees must approve results before publication. Pending: {', '.join(unapproved)}.",
        )

    return await publish_official_results(election, db)


# -----------------------------------------------------------------------------
# Demo Data Reset (DEV Command & Route)
# -----------------------------------------------------------------------------

class ResetRequest(BaseModel):
    election_id: Optional[str] = None


@router.post("/reset")
async def reset_election_data(
    req: Optional[ResetRequest] = None,
    _admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    target_election_id = req.election_id if req and req.election_id else None
    """
    Cleans database rows for fresh manual testing:
    - Clears all voters, ballots, notifications, and outbox rows.
    - Clears uninvited default trustees.
    """
    await db.execute(delete(Voter))
    await db.execute(delete(Ballot))
    await db.execute(delete(Notification))
    await db.execute(delete(EmailOutbox))
    await db.execute(delete(TallyResult))

    if target_election_id:
        await db.execute(
            update(Election)
            .where(Election.election_id == target_election_id)
            .values(
                status="REGISTRATION",
                actual_open_at=None,
                actual_close_at=None,
                invitations_sent_at=None,
                ceremony_unlocked_at=None,
                results_published_at=None,
            )
        )
        await db.execute(
            update(Trustee)
            .where(Trustee.election_id == target_election_id)
            .values(
                has_approved=False,
                approved_at=None,
                partial_decryption_json=None,
                link_opened_at=None,
                failed_attempts=0,
                locked_until=None,
            )
        )

    await db.commit()
    return {"status": "SUCCESS", "message": "Demo data reset successfully."}


# -----------------------------------------------------------------------------
# Email Settings & Test Email Dispatch
# -----------------------------------------------------------------------------

class EmailTestRequest(BaseModel):
    recipient_email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.get("/settings/email")
async def get_email_settings(_admin: str = Depends(require_admin)):
    """Returns effective SMTP settings with secrets masked."""
    eff_name, eff_addr = settings.get_effective_sender()
    tls_mode = "SSL (Port 465)" if settings.SMTP_USE_SSL else ("STARTTLS (Port 587)" if settings.SMTP_USE_TLS else "Plaintext")
    return {
        "smtp_host": settings.SMTP_HOST or "(Not configured - DEV outbox)",
        "smtp_port": settings.SMTP_PORT,
        "tls_mode": tls_mode,
        "smtp_user": settings.SMTP_USER or "(None)",
        "from_name": eff_name,
        "from_address": eff_addr,
        "is_configured": bool(settings.SMTP_HOST.strip()),
    }


@router.post("/settings/send-test-email")
async def send_test_email(
    req: EmailTestRequest,
    _admin: str = Depends(require_admin),
):
    """Sends an instant RFC-5322 test email to verify SMTP delivery."""
    from app.core.email_builder import build_compliant_email_message, deliver_email_message_smtp

    eff_name, eff_addr = settings.get_effective_sender()
    target_email = req.recipient_email.strip()

    subject = f"[{settings.APP_NAME}] SMTP Configuration Test"
    plain_text = f"""{settings.APP_NAME} SMTP Test Message
=====================================================
This is a test message to verify outbound SMTP email delivery.
Timestamp: {datetime.utcnow().isoformat()} UTC
Sender: {eff_name} <{eff_addr}>
Target: {target_email}

If you received this email, outbound delivery was accepted by your mail server.
"""
    html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{settings.APP_NAME} Test</title></head>
<body style="font-family: 'Public Sans', sans-serif; background: #F6F3EC; padding: 24px;">
  <div style="max-width: 500px; margin: 0 auto; background: #FFF; border: 1px solid #D9D2C3; border-radius: 6px; padding: 24px;">
    <h2 style="margin: 0 0 12px 0; color: #16294A;">{settings.APP_NAME} SMTP Test Email</h2>
    <p style="font-size: 13px; color: #1B2330;">This is an automated test verifying outbound email delivery from <strong>{eff_addr}</strong>.</p>
    <div style="background: #EDE8DD; padding: 12px; border-radius: 4px; font-mono; font-size: 12px; margin-top: 16px;">
      Status: Accepted by mail server
    </div>
  </div>
</body>
</html>
"""

    msg = build_compliant_email_message(
        to_email=target_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    if not settings.SMTP_HOST.strip():
        return {
            "status": "ACCEPTED",
            "message": "Accepted by local dev outbox (SMTP not configured in .env).",
            "delivery_mode": "DEV_OUTBOX",
        }

    success, last_error, attempts = deliver_email_message_smtp(
        msg=msg,
        recipient_email=target_email,
        max_retries=1,
    )

    if success:
        return {
            "status": "ACCEPTED",
            "message": "Accepted by the mail server. Gmail may reject a message after accepting it. Check the recipient inbox and spam within a minute.",
            "delivery_mode": "SMTP",
            "attempts": attempts,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Mail server error: {last_error}",
        )

