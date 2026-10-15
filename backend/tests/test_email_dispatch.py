import os
import pytest
from app.core.email import (
    build_credential_email_content,
    build_credential_attachment_json,
    send_credential_email_with_retries,
    OUTBOX_DIR,
)

def test_build_credential_email_content():
    plain, html = build_credential_email_content(
        voter_name="Alice Candidate",
        voter_id="voter-alice-01",
        share_a="0x123456789abcdef",
        election_title="Acme Board Election 2026",
    )
    assert "Acme Board Election 2026" in plain
    assert "voter-alice-01" in plain
    assert "0x123456789abcdef" in plain
    assert "0x123456789abcdef" in html
    assert "Alice Candidate" in html

def test_build_credential_attachment_json():
    att = build_credential_attachment_json(
        election_id="acme-2026",
        voter_id="voter-alice-01",
        share_a="0x123456789abcdef",
    )
    assert "voter-alice-01" in att
    assert "0x123456789abcdef" in att

@pytest.mark.asyncio
async def test_send_credential_email_archiving():
    res = await send_credential_email_with_retries(
        recipient_email="test.voter@organization.com",
        voter_id="voter-test-999",
        voter_name="Test Voter",
        share_a="0xabcdef0123456789",
        election_id="org-election-2026",
        election_title="Test Organization Election",
    )
    assert res["success"] is True
    assert res["recipient"] == "test.voter@organization.com"
    
    # Check that outbox file exists in data/outbox
    files = [f for f in os.listdir(OUTBOX_DIR) if "voter-test-999" in f]
    assert len(files) >= 1

