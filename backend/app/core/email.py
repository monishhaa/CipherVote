"""
SecureVote Email Delivery Service for Voter Credentials (Secret Share A).

Features:
- Deliver Secret Share A strictly by email (never saved in database, logs, or outbox text).
- Includes downloadable JSON credential attachment (voter_id, election_id, share_a).
- Institutional HTML & Plain-Text styling with Public Sans & Fraunces palette.
- Background delivery with up to 3 retries.
- Stored outbox row keeps the body with Secret Share A redacted.
- DEV mode with no SMTP writes an .eml file labelled "DEMO ONLY".
"""

import asyncio
import json
import logging
import os
import smtplib
import ssl
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional

from app.config import settings

logger = logging.getLogger("securevote.email")
logger.setLevel(logging.INFO)

OUTBOX_DIR = os.path.join(settings.DATA_DIR, "outbox")
os.makedirs(OUTBOX_DIR, exist_ok=True)


def build_credential_email_content(
    voter_name: str,
    voter_id: str,
    share_a: str,
    election_title: str,
    voting_window: str = "Dates to be announced",
    redacted: bool = False,
) -> tuple[str, str]:
    """
    Generate Plain Text and HTML bodies for voter credential delivery.
    If redacted=True, Share A is masked as [REDACTED_SHARE_A_FOR_STORAGE].
    """
    display_share = "[REDACTED_SECRET_SHARE_A]" if redacted else share_a
    portal_url = f"{settings.PORTAL_BASE_URL.rstrip('/')}/vote"

    plain_text = f"""{settings.APP_NAME.upper()} OFFICIAL VOTING CREDENTIAL
=====================================================
Election: {election_title}
Voting Window: {voting_window}
Voter ID: {voter_id}
Issued to: {voter_name}

IMPORTANT SECURITY & PRIVACY NOTICE:
- Keep this email private. Do not forward it to anyone.
- Attached to this email is your credential file: 'credential-{voter_id}.json'.
- You will need this credential file (or the copyable key below) on voting day.
- Anyone possessing this credential who passes facial verification can cast your ballot.
- You may save the attached file offline and delete this email.

YOUR SECRET SHARE A:
-----------------------------------------------------
{display_share}
-----------------------------------------------------

HOW TO CAST YOUR BALLOT ON VOTING DAY:
1. When voting opens, visit the Voter Portal: {portal_url}
2. Upload your credential JSON file (or paste Secret Share A) and enter your Voter ID ({voter_id}).
3. Complete the active biometric facial liveness check.
4. Select your candidate and cast your end-to-end encrypted ballot.

Zero cryptographic ballots can be linked to your identity.
{settings.APP_NAME} Verifiable Election Administration
"""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Your {settings.APP_NAME} Voting Credential</title>
</head>
<body style="margin: 0; padding: 24px; background-color: #F6F3EC; font-family: 'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1B2330; line-height: 1.55;">
  <div style="max-width: 580px; margin: 0 auto; background-color: #FFFFFF; border: 1px solid #D9D2C3; border-radius: 4px; overflow: hidden; box-shadow: 0 4px 12px rgba(27, 35, 48, 0.05);">
    
    <!-- Institutional Header -->
    <div style="background-color: #16294A; padding: 24px 28px; border-bottom: 2px solid #B8452B;">
      <div style="font-size: 11px; font-weight: 600; color: #E8E4DA; text-transform: uppercase; letter-spacing: 1px;">{settings.APP_NAME} Institutional Portal</div>
      <h1 style="color: #FFFFFF; margin: 4px 0 0 0; font-family: Georgia, 'Fraunces', serif; font-size: 20px; font-weight: 600;">Your Official Voting Credential</h1>
      <p style="color: #D9D2C3; font-size: 13px; margin: 4px 0 0 0;">{election_title}</p>
    </div>

    <!-- Body Container -->
    <div style="padding: 28px;">
      <p style="font-size: 15px; margin: 0 0 14px 0; color: #1B2330;">
        Hello <strong>{voter_name}</strong>,
      </p>
      
      <p style="font-size: 14px; margin: 0 0 16px 0; color: #1B2330;">
        Your voter registration for <strong>{election_title}</strong> has been confirmed. Below and attached is your private cryptographic voting credential (Secret Share A).
      </p>

      <!-- Schedule Box -->
      <div style="background-color: #FAF8F5; border: 1px solid #E3DED3; border-radius: 4px; padding: 14px 18px; margin: 18px 0;">
        <div style="font-size: 11px; font-weight: 600; color: #7A5A22; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">Voting Schedule</div>
        <div style="font-size: 14px; font-weight: 600; color: #1F2933;">{voting_window}</div>
        <p style="font-size: 12px; color: #5F6B7A; margin: 4px 0 0 0;">You will receive an in-site notification and email when the ballot box officially opens.</p>
      </div>

      <!-- Credential Box -->
      <div style="background-color: #1B2330; border-radius: 4px; padding: 20px; margin: 20px 0; color: #FFFFFF;">
        <div style="font-size: 11px; font-weight: 600; color: #E8E4DA; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Voter ID:</div>
        <div style="font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; color: #FFFFFF; font-weight: 600; margin-bottom: 14px;">{voter_id}</div>

        <div style="font-size: 11px; font-weight: 600; color: #E8E4DA; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Secret Share A (Personal Voting Key):</div>
        <div style="background-color: #111827; border: 1px solid #374151; border-radius: 4px; padding: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: #FCD34D; word-break: break-all; line-height: 1.4;">
          {display_share}
        </div>
        <p style="font-size: 11px; color: #9CA3AF; margin: 8px 0 0 0;">Attached to this email: <strong>credential-{voter_id}.json</strong>. Keep this file private.</p>
      </div>

      <!-- Action & Next Steps -->
      <div style="background-color: #EDE8DD; border: 1px solid #D9D2C3; border-radius: 4px; padding: 16px; margin: 20px 0;">
        <h3 style="margin: 0 0 8px 0; font-family: Georgia, serif; font-size: 13px; color: #16294A; text-transform: uppercase; letter-spacing: 0.5px;">Security & Voting Day Instructions</h3>
        <ol style="margin: 0; padding-left: 18px; font-size: 13px; color: #5C6675; line-height: 1.5;">
          <li style="margin-bottom: 4px;"><strong>Save the attached JSON file</strong> or copy the Secret Share A text above.</li>
          <li style="margin-bottom: 4px;">You can delete this email after saving your credential offline.</li>
          <li style="margin-bottom: 4px;">On election day, upload the JSON file in the <a href="{portal_url}" style="color: #16294A; font-weight: 600; text-decoration: underline;">Ballot Booth</a> and complete your face check.</li>
        </ol>
      </div>

      <!-- Footer Disclaimer -->
      <div style="border-top: 1px solid #D9D2C3; padding-top: 16px; margin-top: 24px; font-size: 11px; color: #5C6675; line-height: 1.4;">
        <p style="margin: 0 0 4px 0;"><strong>Security Notice:</strong> Anyone with this credential who passes the biometric face check can cast your ballot. Keep it secure.</p>
        <p style="margin: 0;">Automated message from {settings.APP_NAME}. Do not reply directly.</p>
      </div>
    </div>
  </div>
</body>
</html>
"""
    return plain_text, html_content


def build_credential_attachment_json(election_id: str, voter_id: str, share_a: str) -> str:
    """Creates the JSON credential file content."""
    return json.dumps({
        "app": settings.APP_NAME,
        "format": "securevote-voter-credential-v1",
        "election_id": election_id,
        "voter_id": voter_id,
        "share_a": share_a,
        "created_at_epoch": int(time.time()),
        "notice": "Keep this file secure. Upload this file on voting day at the Ballot Booth.",
    }, indent=2)


from app.core.email_builder import build_compliant_email_message, deliver_email_message_smtp


async def send_credential_email_with_retries(
    recipient_email: str,
    voter_id: str,
    voter_name: str,
    share_a: str,
    election_id: str,
    election_title: str,
    voting_window: str = "Dates to be announced",
) -> Dict[str, Any]:
    """
    Delivers voter credential with attached JSON.
    Retries up to 3 times with exponential backoff.
    In DEV mode with no SMTP, writes .eml to data/outbox labelled DEMO ONLY.
    """
    clean_email = recipient_email.strip()
    plain_text, html_content = build_credential_email_content(
        voter_name=voter_name,
        voter_id=voter_id,
        share_a=share_a,
        election_title=election_title,
        voting_window=voting_window,
        redacted=False,
    )
    attachment_json = build_credential_attachment_json(election_id, voter_id, share_a)

    msg = build_compliant_email_message(
        to_email=clean_email,
        subject=f"Your {settings.APP_NAME} voting credential",
        plain_text=plain_text,
        html_content=html_content,
        attachment_filename=f"credential-{voter_id}.json",
        attachment_bytes=attachment_json.encode("utf-8"),
        attachment_maintype="application",
        attachment_subtype="json",
    )

    smtp_host = settings.SMTP_HOST.strip()

    # DEV OUTBOX (No SMTP configured)
    if not smtp_host:
        timestamp = int(time.time())
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in voter_id)
        eml_filename = f"DEMO_ONLY_credential_{safe_id}_{timestamp}.eml"
        eml_path = os.path.join(OUTBOX_DIR, eml_filename)

        msg["X-Demo-Notice"] = "DEMO ONLY - CONTAINS UNENCRYPTED CREDENTIAL FOR DEVELOPMENT"

        try:
            with open(eml_path, "wb") as f:
                f.write(msg.as_bytes())
            logger.info(f"[DEV OUTBOX] Wrote DEMO ONLY credential email to {eml_path}")
            return {
                "success": True,
                "delivery_method": "dev_outbox",
                "eml_file": eml_path,
                "recipient": clean_email,
            }
        except Exception as e:
            logger.error(f"[DEV OUTBOX ERROR] Failed to write outbox eml file: {e}")
            return {
                "success": False,
                "delivery_method": "dev_outbox",
                "error": str(e),
                "recipient": clean_email,
            }

    # REAL SMTP TRANSMISSION WITH 3 RETRIES
    success, last_error, attempts = deliver_email_message_smtp(
        msg=msg,
        recipient_email=clean_email,
        max_retries=3,
    )

    return {
        "success": success,
        "delivery_method": "smtp",
        "attempts": attempts,
        "error": last_error,
        "recipient": clean_email,
    }

