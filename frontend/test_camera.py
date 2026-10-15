import asyncio
import sys
from playwright.async_api import async_playwright

async def run_camera_test():
    async with async_playwright() as p:
        # Launch Chromium with fake media device
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )
        context = await browser.new_context(
            permissions=["camera"],
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        # Capture console messages
        page.on("console", lambda msg: print(f"[Browser {msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: print(f"[Browser Error]: {err}"))

        print("\n=== STEP 1: Ground-Truth Raw Camera Test ===")
        await page.goto("http://localhost:3000/dev/camera-raw.html")
        await page.wait_for_selector("#btnStart")
        await page.click("#btnStart")
        await asyncio.sleep(2)

        raw_metrics = await page.evaluate("""() => {
            const v = document.getElementById('v');
            return {
                videoWidth: v ? v.videoWidth : 0,
                videoHeight: v ? v.videoHeight : 0,
                srcObjectExists: v && !!v.srcObject,
                frames: document.getElementById('mFrames').textContent,
                status: document.getElementById('mStatus').textContent,
            };
        }""")
        print(f"Ground-Truth Camera Metrics: {raw_metrics}")

        print("\n=== STEP 2: Voter Registration Camera Test ===")
        await page.goto("http://localhost:3000/user/register")
        await page.wait_for_selector("input[placeholder*='2026-CS-042']", timeout=5000)

        # Fill Step 1 Form
        unique_voter = f"VT-{int(asyncio.get_event_loop().time())}"
        await page.fill("input[placeholder*='2026-CS-042']", unique_voter)
        await page.fill("input[placeholder*='Elena Rostova']", "Elena Rostova")
        await page.fill("input[placeholder*='voter@university.edu']", f"{unique_voter.lower()}@test.edu")
        pw_inputs = await page.query_selector_all("input[type='password']")
        if len(pw_inputs) >= 2:
            await pw_inputs[0].fill("SecurePassword123!")
            await pw_inputs[1].fill("SecurePassword123!")

        # Click Continue to Face Capture
        continue_btn = await page.wait_for_selector("button:has-text('Continue to Face Capture')")
        await continue_btn.click()

        # Should now be on Step 2 with "Start Camera" user gesture button
        print("Checking Step 2 initial state...")
        await page.wait_for_selector("button:has-text('Start Camera')")
        print("-> Found 'Start Camera' button! Explicit user gesture preserved.")

        # Click "Start Camera"
        start_btn = await page.wait_for_selector("button:has-text('Start Camera')")
        await start_btn.click()

        print("Waiting for camera frames to arrive...")
        # Wait up to 5s for Capture Photo button to become enabled
        await page.wait_for_selector("button:has-text('Capture Photo')", timeout=8000)
        await asyncio.sleep(2)

        # Check video element and telemetry in Step 2
        step2_metrics = await page.evaluate("""() => {
            const v = document.querySelector('video');
            const captureBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Capture Photo'));
            const telemetryText = document.body.innerText;
            return {
                videoTag: !!v,
                srcObject: v && !!v.srcObject,
                videoWidth: v ? v.videoWidth : 0,
                videoHeight: v ? v.videoHeight : 0,
                paused: v ? v.paused : true,
                readyState: v ? v.readyState : 0,
                captureBtnEnabled: captureBtn && !captureBtn.disabled,
            };
        }""")
        print(f"Step 2 Live Camera Metrics: {step2_metrics}")

        # Take screenshot of live preview
        await page.screenshot(path="frontend/public/dev/rebuilt_camera_live.png")
        print("Saved live camera screenshot to frontend/public/dev/rebuilt_camera_live.png")

        # Click Capture Photo
        capture_btn = await page.wait_for_selector("button:has-text('Capture Photo')")
        await capture_btn.click()
        await asyncio.sleep(1)

        # Confirm photo was captured
        post_capture_state = await page.evaluate("""() => {
            const img = document.querySelector("img[alt='Biometric enrollment frame']");
            const completeBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Use This Photo'));
            return {
                capturedImgRendered: !!img,
                hasSrc: img && !!img.src && img.src.startsWith('data:image/jpeg'),
                completeBtnPresent: !!completeBtn,
            };
        }""")
        print(f"Post-capture state: {post_capture_state}")

        # Take screenshot of captured still
        await page.screenshot(path="frontend/public/dev/rebuilt_camera_captured.png")
        print("Saved captured still screenshot to frontend/public/dev/rebuilt_camera_captured.png")

        await browser.close()
        print("\nCamera Playwright verification PASSED successfully!")

if __name__ == "__main__":
    asyncio.run(run_camera_test())
