import email.utils
from email.message import EmailMessage
from unittest.mock import patch, MagicMock
from app.config import Settings
from app.core.email_builder import (
    build_compliant_email_message,
    deliver_email_message_smtp,
)

def test_rfc5322_email_headers_construction(monkeypatch):
    """Verify that build_compliant_email_message creates RFC-5322 compliant headers."""
    monkeypatch.setattr("app.config.settings.SMTP_FROM", "SecureVote <noreply@securevote.org>")
    monkeypatch.setattr("app.config.settings.SMTP_FROM_NAME", "SecureVote Authority")
    monkeypatch.setattr("app.config.settings.SMTP_USER", "noreply@securevote.org")
    monkeypatch.setattr("app.config.settings.SMTP_HOST", "localhost")
    
    msg = build_compliant_email_message(
        to_email="alice@institution.edu",
        subject="Official Trustee Invitation",
        plain_text="Hello Alice,\nYour code is here.",
        html_content="<p>Hello Alice,<br>Your code is here.</p>",
    )

    assert isinstance(msg, EmailMessage)
    assert msg["To"] == "alice@institution.edu"
    assert "Official Trustee Invitation" in msg["Subject"]
    
    # Must have Date and Message-ID
    assert msg["Date"] is not None
    assert msg["Message-ID"] is not None
    assert "@" in msg["Message-ID"]

    # From address format
    from_header = msg["From"]
    assert "alice@institution.edu" not in from_header
    assert "@securevote.org" in from_header
    # Should not have nested angle brackets
    assert "<<" not in from_header
    assert ">>" not in from_header

def test_gmail_sender_alignment(monkeypatch):
    """Verify that when host is smtp.gmail.com, From header strictly aligns with SMTP_USER."""
    monkeypatch.setattr("app.config.settings.SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr("app.config.settings.SMTP_USER", "realuser@gmail.com")
    monkeypatch.setattr("app.config.settings.SMTP_FROM", "someother@customdomain.com")
    monkeypatch.setattr("app.config.settings.SMTP_FROM_NAME", "SecureVote Security")
    
    from app.config import settings
    display_name, effective_addr = settings.get_effective_sender()
    assert display_name == "SecureVote Security"
    assert effective_addr == "realuser@gmail.com"

    msg = build_compliant_email_message(
        to_email="bob@gmail.com",
        subject="Sequential Unlock Notification",
        plain_text="Ceremony is active.",
        html_content="<p>Ceremony is active.</p>",
    )

    # Effective sender must use realuser@gmail.com to prevent DKIM/SPF rejection (550 5.7.30)
    assert msg["From"] == "SecureVote Security <realuser@gmail.com>"

def test_deliver_email_message_smtp_success(monkeypatch):
    """Verify SMTP transmission with clean envelope sender."""
    monkeypatch.setattr("app.config.settings.SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr("app.config.settings.SMTP_PORT", 587)
    monkeypatch.setattr("app.config.settings.SMTP_USER", "user@example.com")
    monkeypatch.setattr("app.config.settings.SMTP_PASSWORD", "secret")
    monkeypatch.setattr("app.config.settings.SMTP_USE_TLS", False)
    monkeypatch.setattr("app.config.settings.SMTP_USE_SSL", False)
    monkeypatch.setattr("app.config.settings.SMTP_FROM", "user@example.com")
    monkeypatch.setattr("app.config.settings.SMTP_FROM_NAME", "SecureVote")

    msg = build_compliant_email_message(
        to_email="trustee1@organization.com",
        subject="Test SMTP Message",
        plain_text="Plain text message",
        html_content="<p>Plain text message</p>",
    )

    with patch("smtplib.SMTP") as mock_smtp:
        instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = instance

        success, err, attempts = deliver_email_message_smtp(
            msg=msg,
            recipient_email="trustee1@organization.com",
            max_retries=1,
        )

        assert success is True
        assert err is None
        assert attempts == 1
        instance.send_message.assert_called_once()
        _, kwargs = instance.send_message.call_args
        assert kwargs["from_addr"] == "user@example.com"
        assert kwargs["to_addrs"] == ["trustee1@organization.com"]
