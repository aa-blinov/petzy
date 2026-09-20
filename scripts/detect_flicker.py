"""Capture multi-frame screenshots of the dashboard to detect flickering.

Login as admin/test1234, navigate to /, then take screenshots at intervals.
Save to screenshots/flicker/. Also captures a network log so we can see
which queries fire repeatedly.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

FRONTEND = "http://localhost:5173"
OUT = Path("screenshots/flicker")
OUT.mkdir(parents=True, exist_ok=True)


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 412, "height": 915},
            device_scale_factor=2,
        )
        page = await context.new_page()

        api_calls: list[tuple[float, str, int | None]] = []
        page.on(
            "response",
            lambda r: api_calls.append((time.time(), r.url, r.status))
            if "/api/" in r.url
            else None,
        )

        console_errors: list[str] = []
        page.on(
            "console",
            lambda msg: console_errors.append(f"{msg.type}: {msg.text}")
            if msg.type in ("error", "warning")
            else None,
        )

        # 1. Login
        await page.goto(f"{FRONTEND}/login", wait_until="networkidle")
        await page.wait_for_timeout(500)
        await page.fill('input[placeholder*="пользователя"]', "admin")
        await page.fill('input[type="password"]', "test1234")
        await page.locator('button:has-text("Войти")').first.click()
        await page.wait_for_url(f"{FRONTEND}/", timeout=10_000)
        await page.wait_for_timeout(2000)

        # 2. Reset markers
        t0 = time.time()
        api_calls.clear()
        console_errors.clear()

        # Take 20 frames at 250ms intervals to check post-settle stability.
        frames = []
        for i in range(20):
            t_now = time.time() - t0
            shot = OUT / f"frame_{i:02d}_{int(t_now*1000):05d}ms.png"
            try:
                await page.screenshot(path=str(shot), full_page=False)
            except Exception as e:
                print(f"  frame {i} screenshot error: {e}")
            frames.append((i, t_now, shot))
            print(f"  frame {i:2d} @ {t_now:.2f}s -> {shot.name}")
            await page.wait_for_timeout(250)

        print(f"\n=== Captured {len(api_calls)} /api calls in {time.time()-t0:.1f}s ===")
        api_summary: dict[str, int] = {}
        for _ts, url, status in api_calls:
            path = url.split("?")[0].replace(FRONTEND, "")
            api_summary[path] = api_summary.get(path, 0) + 1
        for path, count in sorted(api_summary.items(), key=lambda x: -x[1]):
            print(f"  {count:3d}x  {path}")

        print(f"\n=== {len(console_errors)} console errors/warnings ===")
        for e in console_errors[:20]:
            print(f"  {e}")

        print("\n=== Per-frame perceptual diff (pixel diff vs prev) ===")
        try:
            from PIL import Image, ImageChops
            prev_img = None
            for i, t_now, shot in frames:
                img = Image.open(shot).convert("RGB")
                if prev_img is not None:
                    diff = ImageChops.difference(prev_img, img)
                    bbox = diff.getbbox()
                    if bbox:
                        stat = diff.getextrema()
                        max_delta = max(c[1] for c in stat) if stat else 0
                        print(f"  frame {i:2d}  bbox={bbox}  max-channel-delta={max_delta}")
                    else:
                        print(f"  frame {i:2d}  identical")
                prev_img = img
        except ImportError:
            print("  PIL not available; skipped diff")

        await context.close()
        await browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))