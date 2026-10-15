"""
SecureVote Email Builder and Protocol Transmission Utility.

Implements strict RFC-5322 compliance:
- Built with standard email.message.EmailMessage
- From header via email.utils.formataddr((display_name, email_address))
- Date header via email.utils.formatdate(localtime=True)
- Message-ID header via email.utils.make_msgid(domain=...)
- multipart/alternative with plain-text and HTML utf-8 parts
- Clean envelope sender matching authenticated SMTP user
- Zero custom/unverified DKIM-Signature, Sender, or Return-Path headers
"""

import email.utils
from email.message import EmailMessage
import logging
import os
import smtplib
import ssl
import time
from typing import Dict, Any, Optional, List, Tuple
from app.config import settings

logger = logging.getLogger("securevote.email_builder")
logger.setLevel(logging.INFO)


def build_compliant_email_message(
    to_email: str,
    subject: str,
    plain_text: str,
    html_content: str,
    reply_to: Optional[str] = None,
    attachment_filename: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
    attachment_maintype: str = "application",
    attachment_subtype: str = "json",
) -> EmailMessage:
    """
    Constructs an RFC-5322 EmailMessage object.
    Never adds manual DKIM-Signature, Sender, or Return-Path headers.
    """
    display_name, sender_address = settings.get_effective_sender()
    clean_to = to_email.strip()

    # Determine domain for make_msgid
    domain = sender_address.split("@")[-1] if "@" in sender_address else "securevote.org"

    msg = EmailMessage()
    msg["Subject"] = subject.strip()
    msg["From"] = email.utils.formataddr((display_name, sender_address))
    msg["To"] = clean_to
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=domain)

    if reply_to and "@" in reply_to:
        msg["Reply-To"] = reply_to.strip()

    # Set content as multipart/alternative
    msg.set_content(plain_text, subtype="plain", charset="utf-8")
    msg.add_alternative(html_content, subtype="html", charset="utf-8")

    # Optional Attachment (e.g. voter credential JSON)
    if attachment_filename and attachment_bytes:
        msg.add_attachment(
            attachment_bytes,
            maintype=attachment_maintype,
            subtype=attachment_subtype,
            filename=attachment_filename,
        )

    return msg


def deliver_email_message_smtp(
    msg: EmailMessage,
    recipient_email: str,
    max_retries: int = 3,
) -> Tuple[bool, Optional[str], int]:
    """
    Transmits an EmailMessage through the configured SMTP server.
    Uses clean envelope sender (matching effective sender address).
    Returns (success, last_error_message, attempts).
    """
    display_name, sender_address = settings.get_effective_sender()
    clean_to = recipient_email.strip()

    smtp_host = settings.SMTP_HOST.strip()
    smtp_port = settings.SMTP_PORT
    smtp_user = settings.SMTP_USER.strip()
    smtp_pass = settings.SMTP_PASSWORD.strip()

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            if settings.SMTP_USE_SSL:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=10) as server:
                    if smtp_user and smtp_pass:
                        server.login(smtp_user, smtp_pass)
                    server.send_message(msg, from_addr=sender_address, to_addrs=[clean_to])
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.ehlo()
                    if settings.SMTP_USE_TLS:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                        server.ehlo()
                    if smtp_user and smtp_pass:
                        server.login(smtp_user, smtp_pass)
                    server.send_message(msg, from_addr=sender_address, to_addrs=[clean_to])

            logger.info(f"[SMTP DELIVERED] Email successfully sent to mail server for {clean_to} (attempt {attempt}).")
            return True, None, attempt

        except Exception as e:
            last_error = str(e)
            logger.warning(f"[SMTP ATTEMPT {attempt}/{max_retries} FAILED] {clean_to}: {e}")
            if attempt < max_retries:
                time.sleep(1.0 * attempt)

    logger.error(f"[SMTP EXHAUSTED] Delivery failed after {max_retries} attempts for {clean_to}: {last_error}")
    return False, last_error, max_retries
