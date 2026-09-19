"""Take mobile-viewport screenshots of every Petzy screen.

Uses Playwright with the system Google Chrome so we don't have to wait
for the Chromium download. Runs against the dev stack at
http://localhost:5173 with seeded data (admin / test1234).

Saves screenshots into screenshots/ for inspection.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


FRONTEND = "http://localhost:5173"
OUTPUT_DIR = Path(__file__).parent.parent / "screenshots"
USERNAME = "admin"
PASSWORD = "test1234"

# Screens to capture after login. Order matters — Dashboard first.
SCREENS = [
    ("dashboard", "/"),
    ("pets", "/pets"),
    ("history", "/history"),
    ("medications", "/medications"),
    ("settings", "/settings"),
]


def main() -> int:
    OUTPUT_DIR.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        # iPhone 13 viewport: 390x844 logical pixels.
        browser = pw.chromium.launch(
            channel="chrome",
            headless=True,
        )
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        )
        page = context.new_page()

        # Login first.
        page.goto(f"{FRONTEND}/login", wait_until="networkidle")
        page.screenshot(path=str(OUTPUT_DIR / "00_login.png"), full_page=False)

        page.fill('input[placeholder="Введите имя пользователя"]', USERNAME)
        page.fill('input[placeholder="Введите пароль"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url(lambda url: not url.endswith("/login"), timeout=10_000)

        # Capture each screen.
        for name, path in SCREENS:
            page.goto(f"{FRONTEND}{path}", wait_until="networkidle")
            # Wait for layout to settle.
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUTPUT_DIR / f"{name}.png"), full_page=False)
            print(f"  captured {name} ({path})")

        # Bonus: capture the QuickAdd bottom sheet by tapping the FAB.
        page.goto(f"{FRONTEND}/", wait_until="networkidle")
        page.wait_for_timeout(1500)
        # Use a programmatic click() instead of locator.click() — Playwright's
        # actionability checks don't always trigger React's synthetic onClick
        # on the FAB's inner button (it's a styled div, not a native button).
        page.evaluate(
            "document.querySelector('.adm-floating-bubble-button')?.click()"
        )
        # QuickAddSheet is rendered as antd-mobile Popup. Wait for the grid
        # items to appear rather than the popup container — the spring-animated
        # popup body is sometimes flagged "hidden" by Playwright's checks
        # even when it's actually rendered and visible to the user.
        page.wait_for_selector(".adm-grid-item", timeout=5_000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUTPUT_DIR / "quick_add_sheet.png"), full_page=False)
        print("  captured quick_add_sheet (FAB sheet)")

        browser.close()

    print(f"\nScreenshots saved to {OUTPUT_DIR}")
    for f in sorted(OUTPUT_DIR.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name:20s}  {size // 1024:5d} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())