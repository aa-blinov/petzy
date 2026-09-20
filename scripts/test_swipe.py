"""Comprehensive swipe test — various swipe lengths."""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

FRONTEND = "http://localhost:5173"


async def swipe_cdp(client, x1, y1, x2, y2, steps=10, delay=15):
    await client.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": x1, "y": y1, "id": 1}],
    })
    for i in range(1, steps):
        t = i / steps
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        await client.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x, "y": y, "id": 1}],
        })
        await asyncio.sleep(delay / 1000)
    await client.send("Input.dispatchTouchEvent", {
        "type": "touchEnd",
        "touchPoints": [],
    })


async def get_state(page):
    return await page.evaluate(
        """() => {
            const el = document.querySelector('.swipeable-row__surface');
            const tr = el ? getComputedStyle(el).transform : 'none';
            // Parse the tx value from matrix(a, b, c, d, tx, ty)
            let offset = 0;
            const m = tr.match(/matrix\\([^)]+\\)/);
            if (m) {
                const parts = m[0].replace(/matrix\\(/, '').replace(/\\)/, '').split(',').map(s => parseFloat(s.trim()));
                offset = parts[4] || 0;
            }
            const dialogs = document.querySelectorAll('.adm-dialog').length;
            return { transform: tr, offset: Math.round(offset), dialogs };
        }"""
    )


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 412, "height": 915},
            has_touch=True,
            is_mobile=True,
        )
        page = await context.new_page()
        client = await page.context.new_cdp_session(page)

        await page.goto(f"{FRONTEND}/login", wait_until="networkidle")
        await page.fill('input[placeholder*="пользователя"]', "admin")
        await page.fill('input[type="password"]', "test1234")
        await page.locator('button:has-text("Войти")').first.click()
        await page.wait_for_url(f"{FRONTEND}/", timeout=10_000)
        await page.wait_for_timeout(2500)

        first_row = page.locator(".swipeable-row__surface").first
        box = await first_row.bounding_box()
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        cases = [
            ("Tap (no movement)", 0, 0),
            ("30px swipe", 30, 0),
            ("40px swipe", 40, 0),
            ("50px swipe (threshold)", 50, 0),
            ("60px swipe", 60, 0),
            ("80px swipe", 80, 0),
            ("120px swipe", 120, 0),
            ("40px fast flick", 40, 5),  # short distance, fast
        ]
        for name, dx, _ in cases:
            # Close any open dialog first
            dialog_count = await page.locator(".adm-dialog").count()
            if dialog_count > 0:
                try:
                    await page.locator('.adm-dialog button:has-text("Отмена")').first.click(timeout=2000)
                except Exception:
                    pass
                await page.wait_for_timeout(400)

            await swipe_cdp(client, cx + dx/2, cy, cx - dx/2, cy, steps=10, delay=12)
            await page.wait_for_timeout(350)
            state = await get_state(page)
            committed = state["dialogs"] > 0
            verdict = "✓ COMMITTED" if committed else "✗ snap-back"
            print(f"  {name:35s}  offset={state['offset']:>4}  dialogs={state['dialogs']}  {verdict}")

        await client.detach()
        await context.close()
        await browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))