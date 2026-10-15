"""
Trustee Invitation Email Builder and Dispatch Service.

Features:
- Plain-text and HTML email generation in the institutional palette (#F6F3EC, #11161F, #16294A, #B8452B).
- Strict code isolation: Each email includes ONLY that trustee's code.
- Redacted storage: Outbox rows stored in the database redact the raw secret code as "[REDACTED_TRUSTEE_CODE]".
- DEV mode support: Writes .eml files to data/outbox/trustee/ clearly labelled DEMO ONLY.
- Up to 3 in-memory retries for SMTP delivery.
"""

import os
import smtplib
import ssl
import time
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, Tuple
from app.config import settings

logger = logging.getLogger("securevote.trustee_mailer")
logger.setLevel(logging.INFO)

TRUSTEE_OUTBOX_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")), "data", "outbox", "trustee"
)
os.makedirs(TRUSTEE_OUTBOX_DIR, exist_ok=True)


def build_trustee_invitation_content(
    trustee_name: str,
    position: int,
    total_trustees: int,
    display_code: str,
    ceremony_url: str,
    election_title: str,
    window_minutes: int,
    scheduled_close: Optional[str] = None,
    redacted: bool = False,
) -> Tuple[str, str, str]:
    """
    Builds subject, plain-text and HTML email content for a trustee.
    If redacted is True, the secret code is replaced with '[REDACTED_TRUSTEE_CODE]' for outbox DB storage.
    """
    code_str = "[REDACTED_TRUSTEE_CODE]" if redacted else display_code
    close_info = scheduled_close if scheduled_close else "Once voting closes"
    subject = f"[{settings.APP_NAME}] Trustee Cryptographic Invitation — {election_title}"

    plain_text = f"""{settings.APP_NAME} OFFICIAL TRUSTEE INVITATION
=====================================================
Election: {election_title}
Trustee: {trustee_name} (Trustee {position} of {total_trustees})

You have been designated as a Cryptographic Key Trustee for this election.

YOUR SECRET TRUSTEE CODE (PART {position} OF {total_trustees}):
-----------------------------------------------------
{code_str}
-----------------------------------------------------

STANDALONE CEREMONY LINK:
{ceremony_url}

VALIDATION TIMELINE & PROTOCOL RULES:
1. When validation becomes available: {close_info}.
2. All {total_trustees} trustees must access their ceremony link at the same time.
3. Each trustee must enter their own code in sequential order (Positions 1 through {total_trustees}).
4. You will have a {window_minutes}-minute active round window once the ceremony begins.
5. If all {total_trustees} parts are submitted correctly in order, the validation console will unlock to allow threshold result verification and partial decryption.

SECURITY NOTICE:
- Do NOT forward this email or share your secret code.
- No election official or administrator can view your code or unlock the ceremony without you.
- Your code is required to decrypt your private threshold key share at rest.

{settings.APP_NAME} Institutional Cryptographic Voting System
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Trustee Invitation — {settings.APP_NAME}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F6F3EC; color: #11161F; padding: 32px 16px; margin: 0;">
  <div style="max-width: 600px; margin: 0 auto; background-color: #FFFFFF; border: 1px solid #D9D2C3; border-radius: 8px; padding: 36px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
    
    <div style="border-bottom: 1px solid #D9D2C3; padding-bottom: 20px; margin-bottom: 24px;">
      <div style="font-size: 11px; font-family: monospace; letter-spacing: 1px; color: #B8452B; text-transform: uppercase; font-weight: bold; margin-bottom: 6px;">
        Institutional Trustee Invitation
      </div>
      <h1 style="color: #11161F; margin: 0; font-size: 24px; font-weight: 700; line-height: 1.3;">
        {election_title}
      </h1>
      <p style="color: #555555; font-size: 13px; margin: 6px 0 0 0;">
        Designated Role: <strong>Trustee {position} of {total_trustees}</strong>
      </p>
    </div>

    <p style="font-size: 14px; color: #333333; line-height: 1.6; margin-bottom: 20px;">
      Hello <strong>{trustee_name}</strong>, you have been appointed as an official cryptographic trustee. You hold one piece of the master threshold key required to unlock the final election validation ceremony.
    </p>

    <!-- SECRET CODE BOX -->
    <div style="background-color: #EDE8DD; border: 1px solid #D9D2C3; border-radius: 6px; padding: 20px; margin-bottom: 24px; text-align: center;">
      <div style="font-size: 11px; font-weight: bold; color: #16294A; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">
        Your Secret Trustee Code (Part {position} of {total_trustees})
      </div>
      <div style="background-color: #11161F; border: 1px solid #252E3D; border-radius: 4px; padding: 14px; font-family: 'JetBrains Mono', Consolas, Monaco, monospace; font-size: 18px; color: #E8E4DA; font-weight: bold; letter-spacing: 2px; word-break: break-all;">
        {code_str}
      </div>
      <p style="font-size: 11px; color: #777777; margin: 10px 0 0 0;">
        Keep this code strictly confidential. Never share or forward it.
      </p>
    </div>

    <!-- CEREMONY ACCESS LINK -->
    <div style="margin-bottom: 28px; text-align: center;">
      <a href="{ceremony_url}" style="display: inline-block; background-color: #16294A; color: #FFFFFF; font-weight: 600; font-size: 14px; text-decoration: none; padding: 12px 24px; border-radius: 6px;">
        Open Standalone Ceremony Portal &rarr;
      </a>
      <div style="margin-top: 8px; font-size: 11px; color: #666666; font-family: monospace; word-break: break-all;">
        {ceremony_url}
      </div>
    </div>

    <!-- PROTOCOL RULES -->
    <div style="background-color: #FAFAFA; border: 1px solid #E5E5E5; border-radius: 6px; padding: 18px; margin-bottom: 24px;">
      <h3 style="margin: 0 0 10px 0; color: #16294A; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">
        Ceremony Unlock Protocol:
      </h3>
      <ul style="margin: 0; padding-left: 20px; color: #444444; font-size: 12px; line-height: 1.6;">
        <li><strong>Availability:</strong> {close_info}.</li>
        <li><strong>Presence:</strong> All {total_trustees} trustees must be present on the ceremony page concurrently.</li>
        <li><strong>Sequential Entry:</strong> Codes must be entered strictly in order (Trustee 1, then Trustee 2, etc.).</li>
        <li><strong>Round Timer:</strong> All codes must be entered within a {window_minutes}-minute window.</li>
        <li><strong>Security:</strong> If a wrong code is entered or a trustee disconnects, the round automatically resets.</li>
      </ul>
    </div>

    <div style="border-top: 1px solid #E5E5E5; padding-top: 16px; font-size: 11px; color: #888888; text-align: center;">
      {settings.APP_NAME} &bull; Verifiable Institutional Cryptographic Voting
    </div>
  </div>
</body>
</html>
"""
    return subject, plain_text, html_content


from app.core.email_builder import build_compliant_email_message, deliver_email_message_smtp


def dispatch_trustee_invitation_email(
    to_email: str,
    trustee_name: str,
    position: int,
    total_trustees: int,
    display_code: str,
    ceremony_url: str,
    election_title: str,
    window_minutes: int,
    scheduled_close: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends the invitation email using RFC-5322 compliant builder.
    - If SMTP is configured: Attempts live delivery with up to 3 retries.
    - If in DEV mode or SMTP unconfigured: Writes an .eml file to data/outbox/trustee/.
    Returns result metadata dictionary.
    """
    subject, plain_text, html_content = build_trustee_invitation_content(
        trustee_name=trustee_name,
        position=position,
        total_trustees=total_trustees,
        display_code=display_code,
        ceremony_url=ceremony_url,
        election_title=election_title,
        window_minutes=window_minutes,
        scheduled_close=scheduled_close,
        redacted=False,
    )

    clean_email = to_email.strip()
    msg = build_compliant_email_message(
        to_email=clean_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    use_smtp = (
        bool(settings.SMTP_HOST)
        and settings.SMTP_HOST != "smtp.example.com"
        and bool(settings.SMTP_USER)
    )

    if use_smtp:
        success, last_error, attempts = deliver_email_message_smtp(
            msg=msg,
            recipient_email=clean_email,
            max_retries=3,
        )
        if success:
            logger.info(f"Trustee email sent to mail server for {clean_email} via SMTP.")
            return {
                "status": "SENT",
                "delivery_mode": "SMTP",
                "recipient": clean_email,
                "subject": subject,
                "attempts": attempts,
            }
        else:
            return {
                "status": "FAILED",
                "delivery_mode": "SMTP",
                "recipient": clean_email,
                "error": last_error,
                "attempts": attempts,
            }

    # DEV OUTBOX MODE (.eml files)
    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_email = clean_email.replace("@", "_at_").replace(".", "_")
    eml_filename = f"DEMO_ONLY_Trustee_{position}_{safe_email}_{timestamp_str}.eml"
    eml_path = os.path.join(TRUSTEE_OUTBOX_DIR, eml_filename)

    with open(eml_path, "wb") as f:
        f.write(msg.as_bytes())

    logger.info(f"[DEV OUTBOX] Written trustee invitation EML to {eml_path}")
    return {
        "status": "SENT",
        "delivery_mode": "DEV_OUTBOX",
        "recipient": clean_email,
        "eml_path": eml_path,
        "subject": subject,
    }


def build_trustee_ceremony_open_content(
    trustee_name: str,
    position: int,
    total_trustees: int,
    ceremony_url: str,
    election_title: str,
    window_minutes: int,
    admin_message: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    Builds subject, plain-text and HTML notification when voting closes and ceremony opens.
    NEVER includes the secret trustee code.
    """
    subject = f"[{settings.APP_NAME}] Voting Closed: Validation Ceremony Now Open — {election_title}"

    msg_section = f"\nAdministrator Message:\n{admin_message}\n" if admin_message else ""
    msg_html_section = f"""
    <div style="background-color: #FAF8F5; border-left: 3px solid #16294A; padding: 12px 16px; margin: 16px 0;">
      <div style="font-size: 11px; font-weight: bold; color: #16294A; text-transform: uppercase;">Message from Election Administrator:</div>
      <p style="font-size: 13px; color: #1B2330; margin: 4px 0 0 0;">{admin_message}</p>
    </div>
    """ if admin_message else ""

    plain_text = f"""{settings.APP_NAME} ELECTION CEREMONY NOTIFICATION
=====================================================
Election: {election_title}
Trustee: {trustee_name} (Trustee {position} of {total_trustees})

Voting for '{election_title}' has closed.
The All-Trustees Validation Ceremony is now officially OPEN.{msg_section}
INSTRUCTIONS:
1. Open your ceremony link: {ceremony_url}
2. Join at the same time as all other trustees.
3. When prompted in sequence (Round window: {window_minutes} minutes), enter the secret Crockford code part you received in your initial invitation email.
4. Review and approve the homomorphic partial decryption proofs.

DO NOT forward this link.
{settings.APP_NAME} Verifiable Election Administration
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Validation Ceremony Open — {settings.APP_NAME}</title>
</head>
<body style="font-family: 'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F6F3EC; color: #11161F; padding: 32px 16px; margin: 0;">
  <div style="max-width: 600px; margin: 0 auto; background-color: #FFFFFF; border: 1px solid #D9D2C3; border-radius: 8px; padding: 36px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
    <div style="border-bottom: 1px solid #D9D2C3; padding-bottom: 20px; margin-bottom: 24px;">
      <div style="font-size: 11px; font-family: monospace; letter-spacing: 1px; color: #B8452B; text-transform: uppercase; font-weight: bold; margin-bottom: 6px;">
        Ceremony Authorization Notice
      </div>
      <h1 style="color: #11161F; margin: 0; font-size: 22px; font-weight: 700;">
        Voting Closed — Unlock Ceremony Open
      </h1>
      <p style="color: #555555; font-size: 13px; margin: 6px 0 0 0;">
        {election_title} &bull; Trustee {position} of {total_trustees}
      </p>
    </div>

    <p style="font-size: 14px; color: #333333; line-height: 1.6; margin-bottom: 16px;">
      Hello <strong>{trustee_name}</strong>, voting has officially closed and the public bulletin board is sealed. The All-Trustees Unlock Ceremony is now open for validation.
    </p>

    {msg_html_section}

    <!-- CEREMONY LINK -->
    <div style="margin: 24px 0; text-align: center;">
      <a href="{ceremony_url}" style="display: inline-block; background-color: #16294A; color: #FFFFFF; font-weight: 600; font-size: 14px; text-decoration: none; padding: 12px 28px; border-radius: 6px;">
        Enter Validation Ceremony &rarr;
      </a>
      <div style="margin-top: 8px; font-size: 11px; color: #666666; font-family: monospace; word-break: break-all;">
        {ceremony_url}
      </div>
    </div>

    <div style="background-color: #FAFAFA; border: 1px solid #E5E5E5; border-radius: 6px; padding: 16px; margin-bottom: 24px; font-size: 12px; color: #444444; line-height: 1.5;">
      <strong>Reminder:</strong> Have the secret code part from your original invitation email ready. All {total_trustees} trustees must be present simultaneously. The round window is {window_minutes} minutes.
    </div>

    <div style="border-top: 1px solid #E5E5E5; padding-top: 16px; font-size: 11px; color: #888888; text-align: center;">
      {settings.APP_NAME} &bull; Threshold Cryptography & Verifiable Governance
    </div>
  </div>
</body>
</html>
"""
    return subject, plain_text, html_content


def dispatch_trustee_ceremony_open_email(
    to_email: str,
    trustee_name: str,
    position: int,
    total_trustees: int,
    ceremony_url: str,
    election_title: str,
    window_minutes: int,
    admin_message: Optional[str] = None,
) -> Dict[str, Any]:
    """Sends notification to trustee that ceremony is now open (never contains secret code)."""
    subject, plain_text, html_content = build_trustee_ceremony_open_content(
        trustee_name=trustee_name,
        position=position,
        total_trustees=total_trustees,
        ceremony_url=ceremony_url,
        election_title=election_title,
        window_minutes=window_minutes,
        admin_message=admin_message,
    )

    clean_email = to_email.strip()
    msg = build_compliant_email_message(
        to_email=clean_email,
        subject=subject,
        plain_text=plain_text,
        html_content=html_content,
    )

    use_smtp = (
        bool(settings.SMTP_HOST)
        and settings.SMTP_HOST != "smtp.example.com"
        and bool(settings.SMTP_USER)
    )

    if use_smtp:
        success, last_error, attempts = deliver_email_message_smtp(
            msg=msg,
            recipient_email=clean_email,
            max_retries=3,
        )
        if success:
            logger.info(f"Ceremony open email delivered to mail server for {clean_email} via SMTP.")
            return {"status": "SENT", "delivery_mode": "SMTP", "recipient": clean_email, "attempts": attempts}
        else:
            return {"status": "FAILED", "delivery_mode": "SMTP", "recipient": clean_email, "error": last_error, "attempts": attempts}

    # DEV OUTBOX
    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_email = clean_email.replace("@", "_at_").replace(".", "_")
    eml_filename = f"DEMO_ONLY_CeremonyOpen_{position}_{safe_email}_{timestamp_str}.eml"
    eml_path = os.path.join(TRUSTEE_OUTBOX_DIR, eml_filename)
    try:
        with open(eml_path, "wb") as f:
            f.write(msg.as_bytes())
    except Exception as e:
        logger.warning(f"Could not write ceremony open eml: {e}")
    return {"status": "SENT", "delivery_mode": "DEV_OUTBOX", "recipient": clean_email, "eml_path": eml_path}


