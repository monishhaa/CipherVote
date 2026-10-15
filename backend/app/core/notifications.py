"""
CipherVote Notification & Email Dispatching Core Module.
Handles formatted date-time representation, in-site notification creation,
HTML/Plain-text email templating in the institutional palette, background SMTP delivery,
and local outbox archiving with zero secret leakage.
"""

import asyncio
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
import smtplib
import ssl
import time
from typing import Dict, List, Optional, Tuple
import zoneinfo
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.database import AsyncSessionLocal
from app.models.entities import Election, EmailOutbox, Notification, Voter

logger = logging.getLogger("ciphervote.notifications")
logger.setLevel(logging.INFO)

OUTBOX_DIR = os.path.join(settings.DATA_DIR, "outbox")
os.makedirs(OUTBOX_DIR, exist_ok=True)


def format_election_datetime(dt: Optional[datetime], tz_name: str = "UTC") -> str:
    """
    Format a UTC datetime into the designated election timezone.
    Format example: "Wed, 21 Oct 2026, 9:00 AM IST"
    """
    if dt is None:
        return "Dates to be announced"

    try:
        # Ensure dt is timezone-aware UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        target_tz = zoneinfo.ZoneInfo(tz_name)
        local_dt = dt.astimezone(target_tz)
        
        # Abbreviated timezone code or name
        tz_abbr = local_dt.strftime("%Z") or tz_name
        
        # Format string: "Wed, 21 Oct 2026, 9:00 AM IST"
        # Using cross-platform format
        formatted = local_dt.strftime("%a, %d %b %Y, %I:%M %p")
        # Remove leading zero in hour if present for clean look
        formatted = formatted.replace(" 0", " ")
        return f"{formatted} {tz_abbr}"
    except Exception as e:
        logger.warning(f"Error formatting datetime {dt} with tz {tz_name}: {e}")
        return dt.strftime("%Y-%m-%d %H:%M UTC")


def format_voting_window(
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    tz_name: str = "UTC",
) -> str:
    """Format full voting window string with timezone."""
    if not start_dt or not end_dt:
        return "Voting schedule to be announced by the election authority."
    
    start_str = format_election_datetime(start_dt, tz_name)
    end_str = format_election_datetime(end_dt, tz_name)
    return f"{start_str} to {end_str}"


def build_notification_content(
    notif_type: str,
    voter_name: str,
    election_title: str,
    scheduled_start: Optional[datetime],
    scheduled_end: Optional[datetime],
    tz_name: str = "UTC",
    portal_url: str = "http://localhost:3000/vote",
) -> Tuple[str, str, str, str]:
    """
    Generate Title, Body, Plain Text Email, and HTML Email for a notification type.
    GUARANTEE: NEVER includes Share A, Share B, face embeddings, or secrets.
    """
    window_str = format_voting_window(scheduled_start, scheduled_end, tz_name)
    has_schedule = scheduled_start is not None and scheduled_end is not None

    if notif_type == "REGISTRATION":
        title = "Voter Registration Confirmed"
        if has_schedule:
            body = (
                f"You have successfully registered for {election_title}. "
                f"Voting is scheduled from {window_str}. Please retain your Secret Share A securely."
            )
            email_intro = (
                f"Your registration for <strong>{election_title}</strong> has been successfully verified and recorded."
            )
            schedule_section = f"""
            <div style="background-color: #FAF8F5; border: 1px solid #E3DED3; border-radius: 6px; padding: 16px; margin: 20px 0;">
              <div style="font-size: 11px; font-weight: 600; color: #7A5A22; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Announced Voting Schedule</div>
              <div style="font-size: 14px; font-weight: 600; color: #1F2933;">{window_str}</div>
              <p style="font-size: 12px; color: #5F6B7A; margin: 6px 0 0 0;">Voting will open online upon official authorization by election officers.</p>
            </div>
            """
        else:
            body = (
                f"You have successfully registered for {election_title}. "
                f"The official voting schedule will be announced soon and you will be notified."
            )
            email_intro = (
                f"Your registration for <strong>{election_title}</strong> has been successfully verified and recorded."
            )
            schedule_section = """
            <div style="background-color: #FAF8F5; border: 1px solid #E3DED3; border-radius: 6px; padding: 16px; margin: 20px 0;">
              <div style="font-size: 11px; font-weight: 600; color: #7A5A22; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Voting Schedule</div>
              <div style="font-size: 13px; color: #1F2933;">Official dates and polling hours will be announced soon. You will receive an immediate notification when published.</div>
            </div>
            """

    elif notif_type == "SCHEDULE_SET":
        title = "Voting Schedule Announced"
        body = (
            f"The voting schedule for {election_title} has been established: {window_str}. "
            f"Voting will open once authorized by election officers."
        )
        email_intro = (
            f"The election authorities have announced the official voting schedule for <strong>{election_title}</strong>."
        )
        schedule_section = f"""
        <div style="background-color: #FAF8F5; border: 1px solid #E3DED3; border-radius: 6px; padding: 16px; margin: 20px 0;">
          <div style="font-size: 11px; font-weight: 600; color: #7A5A22; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Official Voting Window</div>
          <div style="font-size: 14px; font-weight: 600; color: #1F2933;">{window_str}</div>
        </div>
        """

    elif notif_type == "SCHEDULE_UPDATED":
        title = "Voting Schedule Updated"
        body = (
            f"The voting schedule for {election_title} has been updated to: {window_str}. "
            f"Please take note of the updated polling hours."
        )
        email_intro = (
            f"The election authorities have updated the official voting schedule for <strong>{election_title}</strong>."
        )
        schedule_section = f"""
        <div style="background-color: #FAF8F5; border: 1px solid #E3DED3; border-radius: 6px; padding: 16px; margin: 20px 0;">
          <div style="font-size: 11px; font-weight: 600; color: #B45309; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Updated Voting Window</div>
          <div style="font-size: 14px; font-weight: 600; color: #1F2933;">{window_str}</div>
        </div>
        """

    elif notif_type == "VOTING_OPEN":
        title = "Voting Is Now Open"
        body = (
            f"The ballot box for {election_title} is now officially open! "
            f"You may now log in to the voter portal and cast your confidential encrypted ballot."
        )
        email_intro = (
            f"The election authorities have officially opened the ballot box for <strong>{election_title}</strong>."
        )
        schedule_section = f"""
        <div style="background-color: #E2EFE7; border: 1px solid #B7D8C4; border-radius: 6px; padding: 16px; margin: 20px 0;">
          <div style="font-size: 11px; font-weight: 600; color: #1E4D36; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Ballot Box Active</div>
          <div style="font-size: 14px; font-weight: 600; color: #1E4D36;">Voting is now live and accepting encrypted ballots.</div>
          <div style="font-size: 12px; color: #2F6B4F; margin-top: 4px;">Window: {window_str}</div>
        </div>
        """
    elif notif_type == "VOTING_CLOSED":
        title = "Voting Has Closed"
        body = (
            f"Voting for {election_title} has officially closed. The public bulletin board is permanently sealed. "
            f"Official results will be published after the trustees complete the threshold validation ceremony."
        )
        email_intro = (
            f"The election authorities have officially closed the ballot box for <strong>{election_title}</strong>."
        )
        schedule_section = f"""
        <div style="background-color: #EDE8DD; border: 1px solid #D9D2C3; border-radius: 6px; padding: 16px; margin: 20px 0;">
          <div style="font-size: 11px; font-weight: 600; color: #16294A; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Ballot Box Sealed</div>
          <div style="font-size: 14px; font-weight: 600; color: #1B2330;">Voting is now closed. No further ballots will be accepted.</div>
          <div style="font-size: 12px; color: #5C6675; margin-top: 4px;">Official results will be published once trustees validate the homomorphic tally.</div>
        </div>
        """
    else:
        title = "Election Notification"
        body = f"Update regarding {election_title}: {window_str}"
        email_intro = f"Update regarding <strong>{election_title}</strong>."
        schedule_section = f"<p>{window_str}</p>"

    # Plain Text Version
    plain_text = f"""{settings.APP_NAME} Official Election Notification
=====================================================
Election: {election_title}
Subject: {title}

Hello {voter_name},

{email_intro.replace('<strong>', '').replace('</strong>', '')}

VOTING SCHEDULE:
{window_str}

WHAT TO DO NEXT:
1. Ensure you have saved your personal Secret Share A provided upon registration.
2. When voting opens, visit the Voter Portal: {portal_url}
3. Enter your Voter ID, paste your Secret Share A, and complete the quick anti-spoof liveness check.
4. Select your preferred candidate and cast your end-to-end encrypted ballot.

SECURITY NOTICE:
Never share your personal credentials. Individual ballots are encrypted client-side using threshold ElGamal cryptography and zero-knowledge proofs.

{settings.APP_NAME} Election Administration
"""

    # Clean Institutional HTML Version (Paper & Ink Palette)
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title} - {settings.APP_NAME}</title>
</head>
<body style="margin: 0; padding: 24px; background-color: #F6F3EC; font-family: 'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1B2330; line-height: 1.55;">
  <div style="max-width: 580px; margin: 0 auto; background-color: #FFFFFF; border: 1px solid #D9D2C3; border-radius: 4px; overflow: hidden;">
    
    <!-- Institutional Header -->
    <div style="background-color: #16294A; padding: 24px 28px; border-bottom: 2px solid #B8452B;">
      <div style="font-size: 11px; font-weight: 600; color: #E8E4DA; text-transform: uppercase; letter-spacing: 1px;">{settings.APP_NAME} Institutional Portal</div>
      <h1 style="color: #FFFFFF; margin: 4px 0 0 0; font-family: Georgia, 'Fraunces', serif; font-size: 20px; font-weight: 600;">{election_title}</h1>
    </div>

    <!-- Body Container -->
    <div style="padding: 28px;">
      <p style="font-size: 15px; margin: 0 0 14px 0; color: #1B2330;">
        Hello <strong>{voter_name}</strong>,
      </p>
      
      <p style="font-size: 14px; margin: 0 0 16px 0; color: #1B2330;">
        {email_intro}
      </p>

      {schedule_section}

      <!-- Next Steps Box -->
      <div style="background-color: #EDE8DD; border: 1px solid #D9D2C3; border-radius: 4px; padding: 18px; margin: 20px 0;">
        <h3 style="margin: 0 0 10px 0; font-family: Georgia, serif; font-size: 13px; color: #16294A; text-transform: uppercase; letter-spacing: 0.5px;">What to do next</h3>
        <ol style="margin: 0; padding-left: 20px; font-size: 13px; color: #5C6675; line-height: 1.6;">
          <li style="margin-bottom: 4px;">Keep your Secret Share A (provided during registration) safe.</li>
          <li style="margin-bottom: 4px;">When voting opens, access the official <a href="{portal_url}" style="color: #16294A; font-weight: 600; text-decoration: underline;">Voter Portal</a>.</li>
          <li style="margin-bottom: 4px;">Enter your credentials, complete the facial liveness check, and submit your encrypted ballot.</li>
        </ol>
      </div>

      <!-- Action Button -->
      <div style="text-align: center; margin: 24px 0;">
        <a href="{portal_url}" style="display: inline-block; background-color: #16294A; color: #FFFFFF; font-size: 13px; font-weight: 600; text-decoration: none; padding: 10px 24px; border-radius: 4px;">
          Access Voter Portal &rarr;
        </a>
      </div>

      <!-- Footer Disclaimer -->
      <div style="border-top: 1px solid #D9D2C3; padding-top: 16px; margin-top: 24px; font-size: 11px; color: #5C6675; line-height: 1.4;">
        <p style="margin: 0 0 4px 0;"><strong>Cryptographic Assurance:</strong> Your ballot is encrypted client-side using threshold ElGamal and zero-knowledge proofs. No party can observe your individual candidate choice.</p>
        <p style="margin: 0;">This is an automated administrative notification from {settings.APP_NAME}. Do not reply directly to this email.</p>
      </div>
    </div>
  </div>
</body>
</html>

"""

    return title, body, plain_text, html_content


from app.core.email_builder import build_compliant_email_message, deliver_email_message_smtp


async def dispatch_single_email_task(outbox_id: int):
    """
    Background worker that attempts SMTP transmission for a specific outbox entry.
    Retries up to 3 times before setting status to FAILED.
    """
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(EmailOutbox).where(EmailOutbox.id == outbox_id))
        entry = res.scalars().first()
        if not entry or entry.status == "SENT":
            return

        clean_to = entry.to_email.strip()
        smtp_host = settings.SMTP_HOST.strip()

        # DEV OUTBOX MODE (if SMTP not configured)
        if not smtp_host:
            safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in entry.voter_id)
            timestamp = int(time.time())
            eml_path = os.path.join(OUTBOX_DIR, f"{safe_id}_{entry.type.lower()}_{timestamp}.eml")

            msg = build_compliant_email_message(
                to_email=clean_to,
                subject=entry.subject,
                plain_text=entry.body_text,
                html_content=entry.body_html,
            )
            msg["X-Demo-Notice"] = "DEMO ONLY - ARCHIVED LOCALLY WITHOUT SMTP"

            try:
                with open(eml_path, "wb") as f:
                    f.write(msg.as_bytes())
            except Exception as e:
                logger.warning(f"Failed to write outbox archive: {e}")

            entry.status = "QUEUED (DEV OUTBOX)"
            entry.sent_at = datetime.utcnow()
            await db.commit()
            logger.info(f"[DEV OUTBOX] Archived email for {clean_to} ({entry.type}) to {eml_path}")
            return

        # REAL SMTP DELIVERY
        msg = build_compliant_email_message(
            to_email=clean_to,
            subject=entry.subject,
            plain_text=entry.body_text,
            html_content=entry.body_html,
        )

        success, last_err, attempts = deliver_email_message_smtp(
            msg=msg,
            recipient_email=clean_to,
            max_retries=3,
        )

        entry.attempts = attempts
        if success:
            entry.status = "SENT"
            entry.sent_at = datetime.utcnow()
            entry.last_error = None
            logger.info(f"[SMTP SUCCESS] Email sent to mail server for {clean_to}")
        else:
            entry.status = "FAILED"
            entry.last_error = last_err
            logger.error(f"[SMTP FAILED] Failed to deliver email to {clean_to}: {last_err}")

        await db.commit()



async def queue_voter_notification_and_email(
    db: AsyncSession,
    election: Election,
    voter: Voter,
    notif_type: str,
) -> Tuple[Notification, EmailOutbox]:
    """
    Create an in-site Notification and an EmailOutbox entry, then spawn background delivery task.
    """
    portal_url = f"{settings.PORTAL_BASE_URL.rstrip('/')}/vote"
    title, body, plain_text, html_content = build_notification_content(
        notif_type=notif_type,
        voter_name=voter.full_name or voter.voter_id,
        election_title=election.title,
        scheduled_start=election.scheduled_start,
        scheduled_end=election.scheduled_end,
        tz_name=election.timezone or "UTC",
        portal_url=portal_url,
    )

    # 1. Create In-site Notification
    notif = Notification(
        election_id=election.election_id,
        voter_id=voter.voter_id,
        type=notif_type,
        title=title,
        body=body,
        created_at=datetime.utcnow(),
    )
    db.add(notif)

    # 2. Create Email Outbox Record
    outbox = EmailOutbox(
        election_id=election.election_id,
        voter_id=voter.voter_id,
        to_email=voter.email,
        type=notif_type,
        subject=f"{title}: {election.title}",
        body_text=plain_text,
        body_html=html_content,
        status="QUEUED",
        attempts=0,
        created_at=datetime.utcnow(),
    )
    db.add(outbox)
    await db.flush()  # assign IDs

    # 3. Spawn background transmission task
    asyncio.create_task(dispatch_single_email_task(outbox.id))

    return notif, outbox


async def broadcast_election_notification(
    election_id: str,
    notif_type: str,
) -> int:
    """
    Broadcast a schedule announcement, update, or voting-open notification
    to ALL registered voters in the election.
    """
    async with AsyncSessionLocal() as db:
        el_res = await db.execute(select(Election).where(Election.election_id == election_id))
        election = el_res.scalars().first()
        if not election:
            return 0

        voters_res = await db.execute(select(Voter).where(Voter.election_id == election_id))
        voters = voters_res.scalars().all()

        count = 0
        for voter in voters:
            await queue_voter_notification_and_email(db, election, voter, notif_type)
            count += 1
            # Slight throttle between queuing
        await db.commit()
        return count


async def retry_failed_outbox_deliveries() -> int:
    """
    Re-queue all failed email outbox items for transmission.
    """
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(EmailOutbox).where(EmailOutbox.status == "FAILED"))
        failed_entries = res.scalars().all()
        count = 0
        for entry in failed_entries:
            entry.status = "QUEUED"
            entry.attempts = 0
            entry.error_message = None
            asyncio.create_task(dispatch_single_email_task(entry.id))
            count += 1
        await db.commit()
        return count

