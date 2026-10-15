"""
Seed Registered Voters from LFW Dataset (Identities with 2+ Images).
Image 1 = Registration Photo -> Encrypted Biometric Template (AES-256-GCM Vault)
Image 2 = Live Probe Photo -> Used for Election Day Authentication Demo
"""

import asyncio
import csv
import json
import os
import sys
from sqlalchemy import select

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config import settings
from app.core.biometrics.face_engine import face_engine
from app.core.biometrics.template_crypto import encrypt_face_template
from app.core.crypto.shamir import create_voter_credential
from app.core.crypto.timelock import derive_timelock_key, encrypt_share_b
from app.models import Election, Voter
from app.models.database import AsyncSessionLocal, init_db


LFW_BASE_DIR = "data/lfw"
IMG_ROOT = os.path.join(LFW_BASE_DIR, "lfw-deepfunneled", "lfw-deepfunneled")


async def seed_voters(count: int = 50, election_id: str = "council-2026"):
    await init_db()
    print("=" * 70)
    print(f" SEEDING {count} VOTERS FROM LFW DATASET (Identities with 2+ Images)")
    print("=" * 70)

    async with AsyncSessionLocal() as db:
        # Ensure election exists
        el_res = await db.execute(select(Election).where(Election.election_id == election_id))
        election = el_res.scalars().first()
        open_time = election.open_time if election else 1775000000

        timelock_key = derive_timelock_key(
            settings.MASTER_TIME_LOCK_SECRET, election_id, open_time
        )

        people_csv = os.path.join(LFW_BASE_DIR, "people.csv")
        multi_img_people = []
        with open(people_csv, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) >= 2 and row[1].strip().isdigit() and int(row[1].strip()) >= 2:
                    name = row[0].strip()
                    img1 = os.path.join(IMG_ROOT, name, f"{name}_0001.jpg")
                    img2 = os.path.join(IMG_ROOT, name, f"{name}_0002.jpg")
                    if os.path.exists(img1) and os.path.exists(img2):
                        multi_img_people.append((name, img1, img2, int(row[1].strip())))

        print(f"Found {len(multi_img_people)} verified multi-image identities in LFW.")
        selected = multi_img_people[:count]

        seeded_records = []
        for idx, (name, img1, img2, total_imgs) in enumerate(selected, start=1):
            voter_id = f"voter-lfw-{name.lower().replace('_', '-')}"
            email = f"{name.lower()}@university.edu"
            formatted_name = name.replace("_", " ")

            # Check if already seeded
            v_check = await db.execute(select(Voter).where(Voter.voter_id == voter_id))
            if v_check.scalars().first():
                continue

            # 1. Extract 128-d embedding from Image 1
            embedding = face_engine.extract_embedding_from_image(img1)

            # 2. Encrypt biometric template (AES-256-GCM)
            encrypted_template = encrypt_face_template(embedding)

            # 3. Generate 2-of-2 Shamir credential
            cred = create_voter_credential()

            # 4. Encrypt Share B with time-lock key
            enc_share_b = encrypt_share_b(cred.share_b, timelock_key)

            voter = Voter(
                voter_id=voter_id,
                full_name=formatted_name,
                email=email,
                is_approved=True,
                encrypted_face_template=encrypted_template,
                credential_commitment=cred.commitment,
                encrypted_share_b=enc_share_b,
                share_a_preview=cred.share_a[:10] + "...",
                token_issued=False,
            )
            db.add(voter)
            seeded_records.append({
                "voter_id": voter_id,
                "name": formatted_name,
                "share_a": cred.share_a,
                "commitment": cred.commitment,
                "reg_image": img1,
                "probe_image": img2,
            })

            if idx % 10 == 0 or idx == len(selected):
                print(f" -> Seeded {idx}/{len(selected)}: {formatted_name}")

        await db.commit()
        face_engine.save_cache()

        # Save seeded roster info for demo
        out_file = "data/lfw/seeded_voters.json"
        with open(out_file, "w") as f:
            json.dump(seeded_records, f, indent=2)
        print(f"\n[+] Successfully seeded {len(seeded_records)} LFW voters.")
        print(f"[+] Saved voter roster to: {out_file}")


if __name__ == "__main__":
    count_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    asyncio.run(seed_voters(count_arg))
